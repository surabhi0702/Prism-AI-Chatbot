"""
PRISM — RAG Pipeline (v2 — RAGAS-Optimized)
═══════════════════════════════════════════════════════════════════════════════
LAYERS IMPLEMENTED:
  Layer 1 — BGE-base-en-v1.5 embedder (768-dim, MTEB #1 retrieval)
  Layer 2 — Hybrid Retrieval: Vector + BM25 + Reciprocal Rank Fusion
  Layer 5 — Enhanced Chunking: smaller chunks (512), semantic headers, metadata

Pipeline: Chunking → Embedding → ChromaDB → Hybrid Retrieve → RRF Merge → Rerank
═══════════════════════════════════════════════════════════════════════════════
"""
import re
import hashlib
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import chromadb
from chromadb.config import Settings as ChromaSettings
from sentence_transformers import SentenceTransformer, CrossEncoder
from rank_bm25 import BM25Okapi
from backend.config.settings import get_settings

settings = get_settings()

# ── Singletons ────────────────────────────────────────────────────────────
_embedder: Optional[SentenceTransformer] = None
_reranker: Optional[CrossEncoder]        = None
_chroma:   Optional[chromadb.ClientAPI]  = None
_chroma_mode = None # 'remote' or 'local'


def get_embedder() -> SentenceTransformer:
    """Layer 1: Upgraded embedder — BGE-base-en-v1.5 (768-dim, MTEB top-tier)."""
    global _embedder
    if _embedder is None:
        _embedder = SentenceTransformer("BAAI/bge-base-en-v1.5")
    return _embedder


def get_reranker() -> CrossEncoder:
    global _reranker
    if _reranker is None:
        _reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
    return _reranker


def get_chroma() -> chromadb.ClientAPI:
    global _chroma, _chroma_mode
    if _chroma is not None:
        return _chroma

    # 1. Attempt Remote Connection (if configured)
    if settings.chroma_host and settings.chroma_port:
        try:
            print(f"[CHROMA] Attempting connection at {settings.chroma_host}:{settings.chroma_port}...")
            client = chromadb.HttpClient(
                host=settings.chroma_host,
                port=settings.chroma_port,
                settings=ChromaSettings(anonymized_telemetry=False, is_persistent=True)
            )
            client.heartbeat() 
            _chroma = client
            _chroma_mode = "remote"
            print("[CHROMA] Successfully connected to remote ChromaDB.")
            return _chroma
        except Exception as e:
            print(f"[CHROMA_WARNING] Remote connection failed: {e}")
            print(f"[CHROMA] Falling back to local storage...")

    # 2. Fallback to Local Persistent Storage
    print(f"[CHROMA] Initializing local persistent storage at {settings.chroma_persist_dir}")
    _chroma = chromadb.PersistentClient(
        path=settings.chroma_persist_dir,
        settings=ChromaSettings(anonymized_telemetry=False),
    )
    _chroma_mode = "local"
    return _chroma


# ── Layer 5: Enhanced Chunker ─────────────────────────────────────────────
@dataclass
class Chunk:
    chunk_id:   str
    text:       str
    token_est:  int
    position:   int
    metadata:   Dict


class PRISMChunker:
    """
    Layer 5 — Enhanced Hierarchical Chunker:
    1. Smaller target chunks (512 tokens) for higher precision
    2. Larger overlap (200 chars) for better cross-chunk continuity
    3. Semantic header prepended to each chunk for embedding quality
    4. Split by paragraph → merge short → split long at sentences → overlap
    """
    def __init__(self, target=512, overlap=200, min_chunk=60):
        self.target  = target
        self.overlap = overlap
        self.min_c   = min_chunk

    def _build_semantic_header(self, meta: Dict) -> str:
        """Prepend a semantic header to help the embedding model understand chunk context."""
        parts = []
        if meta.get("topic"):
            parts.append(f"Topic: {meta['topic']}")
        if meta.get("disease_code"):
            parts.append(f"Disease: {meta['disease_code']}")
        if meta.get("source"):
            parts.append(f"Source: {meta['source']}")
        if meta.get("year"):
            parts.append(f"Year: {meta['year']}")
        if meta.get("evidence_grade"):
            parts.append(f"Evidence: Grade {meta['evidence_grade']}")
        return " | ".join(parts) + "\n" if parts else ""

    def _extract_topic(self, text: str) -> str:
        """Extract a topic summary from the first sentence of a chunk."""
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())
        if sentences:
            first = sentences[0][:120].strip()
            # Remove trailing fragments
            if first and not first[-1] in '.!?':
                first += '...'
            return first
        return ""

    def chunk(self, text: str, base_meta: Dict) -> List[Chunk]:
        # Step 1: paragraph split
        paras = [p.strip() for p in re.split(r'\n{2,}', text) if len(p.strip()) > 20]
        # Step 2: merge short paras
        merged, buf = [], ""
        for p in paras:
            if len(buf) + len(p) < self.target:
                buf = (buf + " " + p).strip()
            else:
                if buf: merged.append(buf)
                buf = p
        if buf: merged.append(buf)
        # Step 3: split long chunks at sentence boundaries
        final = []
        for seg in merged:
            if len(seg) <= self.target + 150:
                final.append(seg)
            else:
                sentences = re.split(r'(?<=[.!?])\s+', seg)
                buf2 = ""
                for s in sentences:
                    if len(buf2) + len(s) < self.target:
                        buf2 = (buf2 + " " + s).strip()
                    else:
                        if buf2: final.append(buf2)
                        buf2 = s
                if buf2: final.append(buf2)
        # Step 4: overlap windows + semantic headers
        chunks = []
        for i, seg in enumerate(final):
            prev = final[i-1][-self.overlap:] if i > 0 else ""
            text_with_overlap = (prev + " " + seg).strip() if prev else seg

            # Layer 5: Extract topic and build semantic header
            topic = self._extract_topic(seg)
            enriched_meta = {**base_meta, "chunk_pos": i, "chunk_total": len(final)}
            if topic:
                enriched_meta["topic"] = topic

            header = self._build_semantic_header(enriched_meta)
            full_text = header + text_with_overlap

            cid = hashlib.md5(full_text[:300].encode()).hexdigest()[:12]
            chunks.append(Chunk(
                chunk_id=cid,
                text=full_text,
                token_est=int(len(full_text.split()) * 1.3),
                position=i,
                metadata=enriched_meta,
            ))
        return [c for c in chunks if c.token_est >= self.min_c]


# ── Vector Store ──────────────────────────────────────────────────────────
class PRISMVectorStore:
    """
    One ChromaDB collection per agent scope (mutually exclusive).
    15 primary collections + shared specialist/human collections.
    """
    def __init__(self):
        self.client  = get_chroma()
        self._cols: Dict[str, chromadb.Collection] = {}
        # Layer 2: BM25 index cache per collection
        self._bm25_cache: Dict[str, Tuple[BM25Okapi, List[Dict]]] = {}

    def _get_col(self, name: str) -> chromadb.Collection:
        if name not in self._cols:
            self._cols[name] = self.client.get_or_create_collection(
                name=name,
                metadata={"hnsw:space": "cosine"},
            )
        return self._cols[name]

    def add(self, chunks: List[Chunk], collection: str) -> int:
        col = self._get_col(collection)
        emb = get_embedder()
        texts = [c.text for c in chunks]
        vectors = emb.encode(texts, show_progress_bar=False).tolist()
        existing = set(col.get(ids=[c.chunk_id for c in chunks])["ids"])
        new = [(c, v) for c, v in zip(chunks, vectors) if c.chunk_id not in existing]
        if not new: return 0
        col.add(
            ids=[c.chunk_id for c, _ in new],
            documents=[c.text for c, _ in new],
            embeddings=[v for _, v in new],
            metadatas=[c.metadata for c, _ in new],
        )
        # Invalidate BM25 cache for this collection
        self._bm25_cache.pop(collection, None)
        return len(new)

    def query(self, query: str, collection: str, top_k: int = 10) -> List[Dict]:
        col = self._get_col(collection)
        if col.count() == 0:
            return []
        emb = get_embedder()
        q_vec = emb.encode([query], show_progress_bar=False).tolist()
        results = col.query(query_embeddings=q_vec, n_results=min(top_k, col.count()))
        out = []
        for i, doc in enumerate(results["documents"][0]):
            out.append({
                "text":     doc,
                "score":    float(1 - results["distances"][0][i]),
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "id":       results["ids"][0][i],
            })
        return out

    def query_bm25(self, query: str, collection: str, top_k: int = 15) -> List[Dict]:
        """Layer 2: BM25 keyword retrieval for exact-match medical terms."""
        col = self._get_col(collection)
        if col.count() == 0:
            return []

        # Build or fetch BM25 index
        if collection not in self._bm25_cache:
            all_data = col.get(include=["documents", "metadatas"])
            docs = all_data["documents"] or []
            metas = all_data["metadatas"] or [{}] * len(docs)
            ids = all_data["ids"] or []

            # Tokenize for BM25
            tokenized = [re.findall(r'\w+', d.lower()) for d in docs]
            if not tokenized:
                return []
            bm25 = BM25Okapi(tokenized)
            doc_records = [
                {"text": d, "metadata": m, "id": i}
                for d, m, i in zip(docs, metas, ids)
            ]
            self._bm25_cache[collection] = (bm25, doc_records)

        bm25, doc_records = self._bm25_cache[collection]
        query_tokens = re.findall(r'\w+', query.lower())
        if not query_tokens:
            return []

        scores = bm25.get_scores(query_tokens)
        # Get top-k indices
        top_indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:top_k]

        results = []
        for idx in top_indices:
            if scores[idx] > 0:
                results.append({
                    "text":     doc_records[idx]["text"],
                    "score":    float(scores[idx]),
                    "metadata": doc_records[idx]["metadata"],
                    "id":       doc_records[idx]["id"],
                    "retrieval_method": "bm25",
                })
        return results

    def hybrid_query(self, query: str, collection: str,
                     top_k_vector: int = 15, top_k_bm25: int = 15,
                     top_k_final: int = 10, rrf_k: int = 60) -> List[Dict]:
        """
        Layer 2: Hybrid Retrieval — Vector + BM25 + Reciprocal Rank Fusion.
        Combines semantic understanding with exact keyword matching.
        RRF score = Σ 1/(k + rank) for each document across both methods.
        """
        # Run both retrieval methods
        vector_results = self.query(query, collection, top_k=top_k_vector)
        bm25_results = self.query_bm25(query, collection, top_k=top_k_bm25)

        # Build RRF score map keyed by document ID
        rrf_scores: Dict[str, float] = {}
        doc_map: Dict[str, Dict] = {}

        # Score vector results
        for rank, doc in enumerate(vector_results):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank + 1)
            doc_map[doc_id] = {**doc, "retrieval_method": "hybrid"}

        # Score BM25 results
        for rank, doc in enumerate(bm25_results):
            doc_id = doc["id"]
            rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (rrf_k + rank + 1)
            if doc_id not in doc_map:
                doc_map[doc_id] = {**doc, "retrieval_method": "hybrid"}

        # Sort by RRF score and return top-k
        ranked_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
        results = []
        for doc_id in ranked_ids[:top_k_final]:
            doc = doc_map[doc_id]
            doc["rrf_score"] = rrf_scores[doc_id]
            results.append(doc)

        return results

    def count(self, collection: str) -> int:
        try:
            return self._get_col(collection).count()
        except Exception:
            return 0

    def delete_collection(self, collection: str):
        self.client.delete_collection(collection)
        self._cols.pop(collection, None)
        self._bm25_cache.pop(collection, None)


# ── Reranker ──────────────────────────────────────────────────────────────
class PRISMReranker:
    def rerank(self, query: str, chunks: List[Dict], top_k: int = 5) -> List[Dict]:
        if not chunks: return []
        reranker = get_reranker()
        pairs  = [(query, c["text"]) for c in chunks]
        scores = reranker.predict(pairs)
        ranked = sorted(zip(scores, chunks), key=lambda x: x[0], reverse=True)
        for score, chunk in ranked:
            chunk["rerank_score"] = float(score)
        return [c for _, c in ranked[:top_k]]


# ── Full RAG Pipeline ────────────────────────────────────────────────────
class PRISMRAGPipeline:
    def __init__(self):
        self.chunker  = PRISMChunker()
        self.store    = PRISMVectorStore()
        self.reranker = PRISMReranker()

    def ingest(self, text: str, metadata: Dict, collection: str) -> Dict:
        chunks = self.chunker.chunk(text, metadata)
        added  = self.store.add(chunks, collection)
        return {"chunks_created": len(chunks), "chunks_added": added, "collection": collection}

    def retrieve(self, query: str, collection: str,
                 top_k_initial: int = 10, top_k_final: int = 5) -> List[Dict]:
        """Standard vector-only retrieval (backward compatible)."""
        candidates = self.store.query(query, collection, top_k=top_k_initial)
        return self.reranker.rerank(query, candidates, top_k=top_k_final)

    def hybrid_retrieve(self, query: str, collection: str,
                        top_k_initial: int = 15, top_k_final: int = 5) -> List[Dict]:
        """Layer 2: Hybrid retrieval with BM25 + Vector + RRF + Reranking."""
        candidates = self.store.hybrid_query(
            query, collection,
            top_k_vector=top_k_initial,
            top_k_bm25=top_k_initial,
            top_k_final=top_k_initial,
        )
        return self.reranker.rerank(query, candidates, top_k=top_k_final)

    def multi_retrieve(self, query: str, collections: List[str],
                       top_k_final: int = 5) -> List[Dict]:
        """Retrieve across multiple collections and merge-rank."""
        all_chunks = []
        for col in collections:
            all_chunks.extend(self.store.hybrid_query(query, col, top_k_final=6))
        return self.reranker.rerank(query, all_chunks, top_k=top_k_final)


# Shared singleton
_pipeline: Optional[PRISMRAGPipeline] = None

def get_rag_pipeline() -> PRISMRAGPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = PRISMRAGPipeline()
    return _pipeline

# Standalone helper for smart router
def retrieve_context(query: str, collection_name: str, top_k_initial: int = 10, top_k_final: int = 5) -> List[Dict]:
    return get_rag_pipeline().retrieve(query, collection_name, top_k_initial, top_k_final)

# Layer 2: Hybrid retrieval helper for smart router
def hybrid_retrieve_context(query: str, collection_name: str, top_k_initial: int = 15, top_k_final: int = 5) -> List[Dict]:
    return get_rag_pipeline().hybrid_retrieve(query, collection_name, top_k_initial, top_k_final)

def extract_citations(chunks: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for c in chunks:
        meta = c.get("metadata", {})
        src = meta.get("source", "PRISM Knowledge Base")
        if src not in seen:
            seen.add(src)
            out.append({
                "source": src,
                "year": meta.get("year"),
                "evidence_grade": meta.get("evidence_grade"),
                "url": meta.get("source_url")
            })
    return out[:5]
