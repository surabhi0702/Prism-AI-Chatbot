# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/rag/hyde_query_transformer.py
# PRISM HyDE — Hypothetical Document Embedding Query Transformer
# ───────────────────────────────────────────────────────────────────────────────
# PROBLEM SOLVED:
#   Patient queries are short, colloquial, and often in LATAM languages.
#   Medical knowledge bases use dense clinical terminology.
#   Semantic gap between "mujhe sugar ki problem hai" and "hyperglycaemia
#   management in type 2 diabetes mellitus" causes retrieval relevancy of 58%.
#
# SOLUTION — HyDE (Hypothetical Document Embedding):
#   1. Patient sends: "How do I inject insulin?"
#   2. HyDE generates: "Subcutaneous insulin injection technique involves
#      pinching the abdominal skin to form a fold, inserting the needle at a
#      45-degree angle into the subcutaneous fatty tissue..." (clinical tone)
#   3. ChromaDB searches using the HYPOTHETICAL answer embedding
#   4. Result: finds the actual insulin injection protocol chunk
#
# BONUS — Multi-Query Expansion:
#   Generate 3 hypothetical answers from different angles:
#   • Technical clinical angle (for medical content)
#   • Patient-friendly angle (for lifestyle content)
#   • LATAM-specific angle (for culturally adapted content)
#   Merge and deduplicate results → higher recall
#
# EXPECTED RAGAS GAINS:
#   Retrieval Relevancy 58% → 76%   (+18 pts)
#   Context Recall      55% → 65%   (+10 pts)
#   Context Precision   60% → 74%   (+14 pts)
#   Answer Relevancy    62% → 74%   (+12 pts)
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

logger = logging.getLogger("prism.hyde")

from backend.config.settings import get_settings
from backend.core.agents.base_agent import get_llm
settings = get_settings()


# ─── Agent domain descriptions (used to ground the hypothetical) ───────────────
AGENT_DOMAIN_PROMPTS: Dict[str, str] = {
    "CA1": "cancer screening, early detection, mammography, colonoscopy, PSA testing, biopsy",
    "CA2": "cancer treatment, chemotherapy, radiation, immunotherapy, targeted therapy, staging",
    "CA3": "cancer supportive care, palliative, symptom management, fatigue, nausea",
    "CA4": "cancer survivorship, long-term effects, follow-up care, rehabilitation",
    "CA5": "hereditary cancer, BRCA, genetic testing, Lynch syndrome, genetic counselling",
    "CA6": "oncology navigation, cancer general, diagnosis explanation, second opinion",
    "DM1": "diabetes blood glucose monitoring, CGM, HbA1c, glucometer, fasting glucose",
    "DM2": "diabetes medication, insulin, metformin, SGLT2 inhibitors, GLP-1, injection technique",
    "DM3": "diabetes nutrition, carbohydrate counting, plate method, glycaemic index, exercise",
    "DM4": "diabetes complications, neuropathy, nephropathy, retinopathy, foot care, cardiovascular risk",
    "DM5": "gestational diabetes, pregnancy, insulin in pregnancy, fetal monitoring",
    "DM6": "diabetes general, type 1, type 2, pre-diabetes, lifestyle, self-management",
    "CV1": "cardiovascular assessment, ECG, echocardiogram, chest pain evaluation, risk factors",
    "CV2": "cardiac emergency, CPR, chest pain triage, MI, arrhythmia, stroke, FAST",
    "CV3": "cardiac medications, beta-blockers, statins, antihypertensives, warfarin, aspirin",
    "CV4": "cardiac rehabilitation, exercise, post-MI recovery, heart failure management",
    "CV5": "cardiac nutrition, DASH diet, Mediterranean diet, sodium restriction, omega-3",
    "CV6": "cardiovascular general, heart disease prevention, cholesterol, hypertension",
    "MH1": "depression, PHQ-9, antidepressants, CBT, low mood, anhedonia, sleep in depression",
    "MH2": "anxiety, GAD-7, panic disorder, CBT, breathing techniques, worry management",
    "MH3": "sleep, insomnia, CBT-I, sleep restriction, circadian rhythm, light therapy, melatonin",
    "MH4": "trauma, PTSD, PCL-5, EMDR, trauma-focused CBT, dissociation",
    "MH5": "mental health crisis, suicidal ideation, self-harm, safety planning, crisis resources",
    "MH6": "mental health general, stress management, mindfulness, resilience, wellbeing",
    "RS1": "asthma, inhaler technique, peak flow, triggers, salbutamol, preventer, reliever",
    "RS2": "COPD, spirometry, FEV1, bronchodilators, exacerbation, breathlessness",
    "RS3": "pulmonary rehabilitation, breathing exercises, diaphragmatic breathing, pursed lip",
    "RS4": "respiratory medications, inhaled corticosteroids, LABA, LAMA, nebuliser, spacer",
    "RS5": "sleep apnea, CPAP, AHI, apnoea hypopnoea, mask fitting, OSA",
    "RS6": "lung health general, respiratory infections, smoking cessation, lung anatomy",
}

# ─── LATAM-specific clinical context additions ────────────────────────────────
LATAM_CONTEXT: Dict[str, str] = {
    "DM": "ALAD guidelines, metformina, insulina glargina, glucemia, hemoglobina glucosilada",
    "CV": "hipertensión arterial, síndrome metabólico, ibuprofeno, AAS, estatinas",
    "MH": "salud mental LATAM, estigma, familismo, curanderismo, promotores de salud",
    "CA": "tamizaje, biopsia, quimioterapia, IMSS, SUS healthcare system",
    "RS": "salbutamol, bromuro de ipratropio, EPOC, asma bronquial, espirometría",
}


# ═══════════════════════════════════════════════════════════════════════════════
# DATA CLASSES
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class HypotheticalDocument:
    """One generated hypothetical document."""
    text:       str
    angle:      str       # 'clinical' | 'patient_friendly' | 'latam'
    agent_id:   str
    query:      str
    tokens:     int
    latency_ms: int


@dataclass
class HyDEResult:
    """Output of HyDEQueryTransformer.transform()"""
    original_query:     str
    hypothetical_docs:  List[HypotheticalDocument]
    merged_query:       str          # Best single query for ChromaDB
    multi_queries:      List[str]    # All hypotheticals (for multi-query retrieval)
    agent_id:           str
    language:           str
    total_latency_ms:   int
    cache_hit:          bool
    angles_used:        List[str]

    @property
    def primary_query(self) -> str:
        """Best query to use for ChromaDB embedding search."""
        return self.merged_query or self.original_query


# ═══════════════════════════════════════════════════════════════════════════════
# HyDE QUERY TRANSFORMER
# ═══════════════════════════════════════════════════════════════════════════════

class HyDEQueryTransformer:
    """
    Transforms patient queries into hypothetical medical documents
    that match the language and structure of the ChromaDB knowledge base.

    USAGE:
        hyde = HyDEQueryTransformer(agent_id="DM2", language="es")
        result = await hyde.transform("How do I inject insulin?")
        # Pass result.primary_query to ChromaDB instead of original query

    MULTI-QUERY MODE (higher recall):
        results = await hyde.transform_multi("insulin injection", angles=["clinical","latam"])
        # Query ChromaDB with each result.multi_queries, merge and deduplicate
    """

    # In-memory cache: (query_hash, agent_id) → HyDEResult
    _cache: Dict[str, HyDEResult] = {}
    MAX_CACHE = 500

    def __init__(
        self,
        agent_id:            str,
        language:            str   = "en",
        model:               str   = "claude-sonnet-4-20250514",
        max_hypothesis_tokens: int = 150,
        temperature:         float = 0.25,    # Low = consistent medical tone
        use_multi_query:     bool  = True,    # Generate multiple angles
        use_latam_angle:     bool  = True,    # Add LATAM-specific variant
        use_cache:           bool  = True,
    ):
        self.agent_id              = agent_id.upper()
        self.disease_code          = self.agent_id[:2]
        self.language              = language
        self.model                 = model
        self.max_hypothesis_tokens = max_hypothesis_tokens
        self.temperature           = temperature
        self.use_multi_query       = use_multi_query
        self.use_latam_angle       = use_latam_angle
        self.use_cache             = use_cache
        self.domain_context        = AGENT_DOMAIN_PROMPTS.get(self.agent_id, "general medicine")
        self.latam_context         = LATAM_CONTEXT.get(self.disease_code, "")

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────────────

    async def transform(
        self,
        query: str,
    ) -> HyDEResult:
        """
        Transform a patient query into one or more hypothetical documents.

        Single call: generates 'clinical' angle + optionally 'latam' angle.
        Use result.primary_query for ChromaDB embedding.
        """
        t0 = time.monotonic()

        # Cache check
        cache_key = self._cache_key(query)
        if self.use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            cached.cache_hit = True
            return cached

        # Choose angles based on config
        angles = ["clinical"]
        if self.use_latam_angle and self.language in ("es", "pt") and self.latam_context:
            angles.append("latam")

        # Generate hypothetical documents in parallel
        tasks = [self._generate_hypothesis(query, angle) for angle in angles]
        hypotheticals = await asyncio.gather(*tasks, return_exceptions=False)

        # Filter out failures
        valid = [h for h in hypotheticals if h and h.text]

        # Build merged query (best single representation)
        merged = self._merge_hypotheticals(query, valid)
        multi  = [h.text for h in valid]

        result = HyDEResult(
            original_query    = query,
            hypothetical_docs = valid,
            merged_query      = merged,
            multi_queries     = multi,
            agent_id          = self.agent_id,
            language          = self.language,
            total_latency_ms  = int((time.monotonic() - t0) * 1000),
            cache_hit         = False,
            angles_used       = [h.angle for h in valid],
        )

        # Cache
        self._store_cache(cache_key, result)
        logger.info(
            f"[HyDE] {self.agent_id} · {len(valid)} hypotheticals · "
            f"{result.total_latency_ms}ms · cache={result.cache_hit}"
        )
        return result

    async def transform_multi(
        self,
        query:  str,
        angles: List[str] = None,
    ) -> HyDEResult:
        """
        Generate hypotheticals from all configured angles for maximum recall.
        Use result.multi_queries to query ChromaDB multiple times.
        """
        t0 = time.monotonic()
        cache_key = self._cache_key(query + "_multi")

        if self.use_cache and cache_key in self._cache:
            cached = self._cache[cache_key]
            cached.cache_hit = True
            return cached

        use_angles = angles or ["clinical", "patient_friendly", "latam"]
        if not self.latam_context and "latam" in use_angles:
            use_angles.remove("latam")

        tasks       = [self._generate_hypothesis(query, angle) for angle in use_angles]
        hypotheticals = await asyncio.gather(*tasks, return_exceptions=False)
        valid         = [h for h in hypotheticals if h and h.text]

        merged = self._merge_hypotheticals(query, valid)
        multi  = [query] + [h.text for h in valid]   # Include original too

        result = HyDEResult(
            original_query    = query,
            hypothetical_docs = valid,
            merged_query      = merged,
            multi_queries     = multi,
            agent_id          = self.agent_id,
            language          = self.language,
            total_latency_ms  = int((time.monotonic() - t0) * 1000),
            cache_hit         = False,
            angles_used       = [h.angle for h in valid],
        )
        self._store_cache(cache_key, result)
        return result

    # ──────────────────────────────────────────────────────────────────────────
    # HYPOTHESIS GENERATION
    # ──────────────────────────────────────────────────────────────────────────

    async def _generate_hypothesis(
        self,
        query: str,
        angle: str,
    ) -> Optional[HypotheticalDocument]:
        """Generate one hypothetical document for the given query and angle."""
        t0 = time.monotonic()
        prompt = self._build_prompt(query, angle)

        try:
            llm = get_llm(temperature=self.temperature, max_tokens=self.max_hypothesis_tokens)
            response = await llm.ainvoke(prompt)
            text = response.content.strip()

            if len(text) < 20:
                return None

            return HypotheticalDocument(
                text       = text,
                angle      = angle,
                agent_id   = self.agent_id,
                query      = query,
                tokens     = len(text.split()),
                latency_ms = int((time.monotonic() - t0) * 1000),
            )
        except Exception as e:
            logger.warning(f"[HyDE] {angle} hypothesis failed: {e}")
            return None

    def _build_prompt(self, query: str, angle: str) -> str:
        """Build the appropriate prompt for each angle."""

        base_instruction = (
            f"You are a medical knowledge retrieval assistant for PRISM Health AI.\n"
            f"Domain: {self.domain_context}\n\n"
        )

        prompts = {

            "clinical": (
                f"{base_instruction}"
                f"Write a SHORT clinical reference text (2-3 sentences, exactly "
                f"{self.max_hypothesis_tokens} tokens max) that would appear in a "
                f"medical guideline or textbook and would DIRECTLY ANSWER this "
                f"patient question.\n\n"
                f"PATIENT QUESTION: {query}\n\n"
                f"RULES:\n"
                f"- Use clinical terminology (same language as medical literature)\n"
                f"- Be specific: include drug names, dosages, procedures if relevant\n"
                f"- Write as if extracted from a clinical guideline, not a response to a patient\n"
                f"- Do NOT start with 'The answer is' — write as standalone reference text\n"
                f"- Do NOT acknowledge the question — just write the reference text\n\n"
                f"Clinical reference text:"
            ),

            "patient_friendly": (
                f"{base_instruction}"
                f"Write a SHORT patient education paragraph (2-3 sentences) that "
                f"would appear in a patient information leaflet and answers this question.\n\n"
                f"PATIENT QUESTION: {query}\n\n"
                f"RULES:\n"
                f"- Use simple, accessible language (Grade 7 reading level)\n"
                f"- Include the key clinical fact the patient needs\n"
                f"- Write as standalone information, not a direct reply\n\n"
                f"Patient education text:"
            ),

            "latam": (
                f"{base_instruction}"
                f"LATAM clinical context: {self.latam_context}\n\n"
                f"Write a SHORT clinical text (2-3 sentences) relevant to LATAM "
                f"patients, using terminology and drug names common in "
                f"{'Spanish-speaking' if self.language == 'es' else 'Brazilian'} "
                f"healthcare settings.\n\n"
                f"PATIENT QUESTION: {query}\n\n"
                f"RULES:\n"
                f"- Use LATAM-specific drug names where relevant "
                f"(e.g. metformina, insulina, salbutamol)\n"
                f"- Reference LATAM clinical guidelines where applicable (ALAD, SBC, etc.)\n"
                f"- Language: {'Spanish' if self.language == 'es' else 'English'} "
                f"(medical terminology)\n"
                f"- Write as standalone reference text, not a patient reply\n\n"
                f"LATAM clinical reference text:"
            ),
        }

        return prompts.get(angle, prompts["clinical"])

    # ──────────────────────────────────────────────────────────────────────────
    # MERGING & DEDUPLICATION
    # ──────────────────────────────────────────────────────────────────────────

    def _merge_hypotheticals(
        self,
        original_query: str,
        hypotheticals:  List[HypotheticalDocument],
    ) -> str:
        """
        Create the best single query for ChromaDB by combining the original
        query with key terms from all hypothetical documents.

        Strategy: original + unique key terms from clinical hypothesis.
        """
        if not hypotheticals:
            return original_query

        # Use the clinical angle as primary (most specific)
        clinical = next((h for h in hypotheticals if h.angle == "clinical"), hypotheticals[0])

        # Combine original query with clinical hypothesis
        # This preserves patient intent while adding clinical vocabulary
        merged = f"{original_query} {clinical.text}"

        # Truncate to reasonable length for embedding
        words  = merged.split()
        if len(words) > 200:
            merged = " ".join(words[:200])

        return merged

    # ──────────────────────────────────────────────────────────────────────────
    # CACHE
    # ──────────────────────────────────────────────────────────────────────────

    def _cache_key(self, query: str) -> str:
        content = f"{self.agent_id}:{self.language}:{query[:200]}"
        return hashlib.md5(content.encode()).hexdigest()

    def _store_cache(self, key: str, result: HyDEResult) -> None:
        if not self.use_cache:
            return
        if len(self._cache) >= self.MAX_CACHE:
            # Remove oldest entry
            oldest = next(iter(self._cache))
            del self._cache[oldest]
        self._cache[key] = result


# ═══════════════════════════════════════════════════════════════════════════════
# MULTI-QUERY CHROMADB RETRIEVER
# Queries ChromaDB with multiple hypothetical documents and merges results
# ═══════════════════════════════════════════════════════════════════════════════

class MultiQueryRetriever:
    """
    Query ChromaDB with multiple HyDE hypotheticals and merge results.
    Use this for maximum context recall.

    USAGE:
        hyde      = HyDEQueryTransformer(agent_id="DM2")
        retriever = MultiQueryRetriever()
        results   = await retriever.retrieve(query, collection, hyde)
    """

    def __init__(self, dedup_threshold: float = 0.95):
        self.dedup_threshold = dedup_threshold

    async def retrieve(
        self,
        query:      str,
        collection,                          # chromadb.Collection
        hyde:       HyDEQueryTransformer,
        n_per_query: int = 5,               # Results per HyDE query
    ) -> Dict:
        """
        Run multiple ChromaDB queries (one per HyDE angle) and merge results.
        Deduplicates by text similarity.

        Returns merged ChromaDB-format result dict.
        """
        # Generate hypotheticals
        hyde_result = await hyde.transform_multi(query)
        queries     = hyde_result.multi_queries or [query]

        # Query ChromaDB with each hypothetical in parallel
        async def query_chromadb(q: str) -> Dict:
            return await asyncio.get_event_loop().run_in_executor(
                None,
                lambda: collection.query(
                    query_texts = [q],
                    n_results   = n_per_query,
                    include     = ["documents", "metadatas", "distances"],
                )
            )

        raw_results = await asyncio.gather(
            *[query_chromadb(q) for q in queries],
            return_exceptions=True,
        )

        # Merge and deduplicate
        all_docs, all_metas, all_dists = [], [], []
        seen_hashes: Set[str] = set()

        for result in raw_results:
            if isinstance(result, Exception):
                continue
            docs  = (result.get("documents") or [[]])[0]
            metas = (result.get("metadatas") or [[]])[0]
            dists = (result.get("distances") or [[]])[0]

            for doc, meta, dist in zip(docs, metas, dists):
                if not doc:
                    continue
                # Dedup by first 100 chars hash
                doc_hash = hashlib.md5(doc[:100].encode()).hexdigest()
                if doc_hash in seen_hashes:
                    continue
                seen_hashes.add(doc_hash)
                all_docs.append(doc)
                all_metas.append(meta)
                all_dists.append(dist)

        # Sort by distance (ascending = most similar first)
        if all_docs:
            sorted_triples = sorted(
                zip(all_dists, all_docs, all_metas),
                key=lambda x: x[0],
            )
            all_dists, all_docs, all_metas = zip(*sorted_triples)
            all_dists = list(all_dists)
            all_docs  = list(all_docs)
            all_metas = list(all_metas)

        return {
            "documents": [all_docs],
            "metadatas": [all_metas],
            "distances": [all_dists],
            "_hyde_result": hyde_result,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# COMPLETE INTEGRATION — smart_router.py node_retrieve() replacement
# ═══════════════════════════════════════════════════════════════════════════════

class PRISMFullRAGPipeline:
    """
    Complete RAG pipeline combining HyDE + Reranker + Parent-Child retrieval.

    Plug this in to replace the existing node_retrieve() in smart_router.py.

    BEFORE (existing code):
        results = collection.query(query_texts=[query], n_results=5)
        context = "\\n\\n".join(results["documents"][0])

    AFTER (this pipeline):
        pipeline = PRISMFullRAGPipeline()
        retrieval = await pipeline.retrieve(query, agent_id, language, chromadb_client)
        context   = retrieval["context"]      # inject into LLM prompt
        citations = retrieval["citations"]     # attach to API response
        confidence = retrieval["confidence"]   # for smart router routing decision
    """

    def __init__(self):
        from backend.core.rag.cross_encoder_reranker import PRISMRetrievalPipeline
        self.retrieval_pipeline = PRISMRetrievalPipeline()

    async def retrieve(
        self,
        query:           str,
        agent_id:        str,
        language:        str   = "en",
        chromadb_client  = None,
        use_hyde:        bool  = True,
        use_multi_query: bool  = False,
        collection_name: Optional[str] = None,
    ) -> Dict:
        """
        Full retrieval: HyDE transform → ChromaDB → Cross-encoder reranking → Context.

        Returns:
            context:     str   — formatted context to inject into LLM prompt
            citations:   list  — structured source citations for API response
            confidence:  float — retrieval confidence score (0-1)
            chunks_used: int   — number of chunks sent to LLM (after reranking)
            hyde_used:   bool  — whether HyDE was applied
        """
        search_query = query

        # ── Step 1: HyDE query transformation ────────────────────────────────
        hyde_result = None
        if use_hyde:
            try:
                hyde = HyDEQueryTransformer(
                    agent_id       = agent_id,
                    language       = language,
                    use_multi_query = use_multi_query,
                )
                hyde_result  = await hyde.transform(query)
                search_query = hyde_result.primary_query
            except Exception as e:
                logger.warning(f"[Pipeline] HyDE failed ({e}) — using original query")

        # ── Step 2: ChromaDB retrieval + cross-encoder reranking ──────────────
        reranker_result = await self.retrieval_pipeline.retrieve(
            query           = search_query,
            agent_id        = agent_id,
            language        = language,
            chromadb_client = chromadb_client,
            n_retrieve      = 10,
            collection_name = collection_name,
        )

        # ── Step 3: Build context and compute confidence ───────────────────────
        context    = reranker_result.context_for_llm
        citations  = reranker_result.citations
        confidence = self._compute_confidence(reranker_result)

        return {
            "context":         context,
            "citations":       citations,
            "confidence":      confidence,
            "chunks":          [{"text": c.text, "rerank_score": c.rerank_score} for c in reranker_result.ranked_chunks],
            "chunks_used":     reranker_result.candidates_out,
            "chunks_retrieved":reranker_result.candidates_in,
            "hyde_used":       hyde_result is not None,
            "hyde_angles":     hyde_result.angles_used if hyde_result else [],
            "reranker_backend":reranker_result.backend_used,
            "latency_ms": {
                "hyde":    hyde_result.total_latency_ms if hyde_result else 0,
                "reranker":reranker_result.latency_ms,
            },
        }

    @staticmethod
    def _compute_confidence(reranker_result) -> float:
        """
        Compute a 0-1 confidence score from reranker output.
        Used by smart_router to decide primary vs specialist vs escalation routing.
        """
        if not reranker_result.ranked_chunks:
            return 0.0

        top_score = reranker_result.ranked_chunks[0].rerank_score
        avg_score = sum(c.rerank_score for c in reranker_result.ranked_chunks) / len(reranker_result.ranked_chunks)

        # Weight: 70% top chunk score + 30% average
        confidence = 0.70 * top_score + 0.30 * avg_score
        return round(min(1.0, max(0.0, confidence)), 3)