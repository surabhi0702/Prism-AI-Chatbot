# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/agents/smart_router_rag_patch.py
# PRISM smart_router.py — Exact patch to wire all 3 components
# ───────────────────────────────────────────────────────────────────────────────
# This file shows the EXACT lines to change in smart_router.py.
# All 3 components are wired through PRISMFullRAGPipeline — one entry point.
# ═══════════════════════════════════════════════════════════════════════════════

# ─── STEP 1: Add import at top of smart_router.py ─────────────────────────────

# ADD THIS LINE after existing imports:
from backend.core.rag.hyde_query_transformer import PRISMFullRAGPipeline

# ─── STEP 2: Initialise pipeline as module-level singleton ────────────────────

# ADD AFTER IMPORTS (before class definitions):
_rag_pipeline: PRISMFullRAGPipeline | None = None

def get_rag_pipeline() -> PRISMFullRAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = PRISMFullRAGPipeline()
    return _rag_pipeline


# ─── STEP 3: Replace node_retrieve in the LangGraph pipeline ──────────────────
#
# FIND in smart_router.py:
#   async def node_retrieve(state: RoutingState) -> RoutingState:
#       collection = chroma_client.get_collection(f"prism_{state['agent_id'].lower()}")
#       results = collection.query(
#           query_texts=[state["user_message"]], n_results=5
#       )
#       context = "\n\n".join(results["documents"][0])
#       return {**state, "retrieved_context": context}
#
# REPLACE WITH:

async def node_retrieve(state: dict) -> dict:
    """
    Enhanced retrieval node: HyDE → ChromaDB top-10 → Cross-encoder reranker → top-3.
    Replaces the existing 5-chunk flat retrieval.
    """
    import os
    pipeline    = get_rag_pipeline()
    use_hyde    = os.getenv("PRISM_USE_HYDE", "true").lower() == "true"

    retrieval = await pipeline.retrieve(
        query           = state["user_message"],
        agent_id        = state["agent_id"],
        language        = state.get("language", "en"),
        chromadb_client = state.get("chromadb_client"),   # pass from graph initialisation
        use_hyde        = use_hyde,
        use_multi_query = False,   # Enable in Sprint 3 for max recall
    )

    return {
        **state,
        "retrieved_context":  retrieval["context"],        # → inject into LLM prompt
        "citations":          retrieval["citations"],       # → attach to response
        "retrieval_confidence": retrieval["confidence"],    # → routing decision
        "chunks_used":        retrieval["chunks_used"],
        "hyde_used":          retrieval["hyde_used"],
        "reranker_backend":   retrieval["reranker_backend"],
    }


# ─── STEP 4: Use retrieval_confidence in node_confidence_check ────────────────
#
# FIND:
#   async def node_confidence_check(state: dict) -> dict:
#       confidence = compute_confidence(state["response"], state["user_message"])
#       ...
#
# MODIFY to also factor in retrieval confidence:

async def node_confidence_check(state: dict) -> dict:
    """
    Confidence check using BOTH generation confidence and retrieval confidence.
    Retrieval confidence < 0.4 → force specialist routing even if generation looks ok.
    """
    generation_confidence = state.get("generation_confidence", 0.7)
    retrieval_confidence  = state.get("retrieval_confidence", 0.7)

    # Weight: retrieval quality matters as much as generation quality
    final_confidence = 0.50 * generation_confidence + 0.50 * retrieval_confidence

    route = "primary"
    if final_confidence < 0.40:
        route = "specialist"
    if state.get("frustration_score", 0) > 75:
        route = "human"

    return {
        **state,
        "confidence":      final_confidence,
        "route_decision":  route,
        "routing_reason": (
            f"gen={generation_confidence:.2f}, "
            f"retrieval={retrieval_confidence:.2f}, "
            f"combined={final_confidence:.2f}"
        ),
    }


# ─── STEP 5: Inject context into node_primary_agent ──────────────────────────
#
# FIND the system prompt construction in node_primary_agent:
#   system_prompt = agent_config.system_prompt
#
# ADD AFTER:
#   retrieved_context = state.get("retrieved_context", "")
#   if retrieved_context:
#       system_prompt = system_prompt + f"""
#
# ═══════════════════════════════════════════════════════════════════════════════
# RETRIEVED MEDICAL KNOWLEDGE (use ONLY this to answer — do not infer beyond it)
# ═══════════════════════════════════════════════════════════════════════════════
# {retrieved_context}
# ═══════════════════════════════════════════════════════════════════════════════
# """


# ─── STEP 6: Pass chromadb_client through RoutingState ───────────────────────
#
# In smart_router.py, the RoutingState TypedDict should include:
#   class RoutingState(TypedDict):
#       user_message:        str
#       agent_id:            str
#       language:            str
#       conversation_history: list
#       chromadb_client:     Any          # ← ADD THIS
#       retrieved_context:   str          # ← ADD THIS
#       citations:           list         # ← ADD THIS
#       retrieval_confidence: float       # ← ADD THIS
#       chunks_used:         int          # ← ADD THIS
#       hyde_used:           bool         # ← ADD THIS
#       reranker_backend:    str          # ← ADD THIS
#       # ... existing fields ...
#
# When calling run_smart_routing() in main.py, pass chromadb_client:
#   routing_result = run_smart_routing(
#       ...,
#       chromadb_client = app.state.chromadb_client,   # pass the shared client
#   )


# ═══════════════════════════════════════════════════════════════════════════════
# FILE: requirements_rag.txt — New dependencies to add to requirements.txt
# ═══════════════════════════════════════════════════════════════════════════════

REQUIREMENTS = """
# ── PRISM RAG Enhancement Dependencies ────────────────────────────────────────
# Add these to requirements.txt

# Cross-encoder reranking
sentence-transformers>=2.6.0   # CrossEncoder class
torch>=2.1.0                    # CPU build (no CUDA needed for inference)

# For GPU acceleration (optional — faster reranking):
# torch>=2.1.0+cu118 --index-url https://download.pytorch.org/whl/cu118

# Already in your stack — no change needed:
# chromadb >= 0.4.0
# anthropic >= 0.27.0
# langchain >= 0.1.0

# ── Install commands ──────────────────────────────────────────────────────────
# pip install sentence-transformers torch --break-system-packages
#
# Download MedCPT Cross-Encoder on first startup (auto via sentence-transformers):
# python -c "from sentence_transformers import CrossEncoder; CrossEncoder('ncats/MedCPT-Cross-Encoder')"
#
# Model size: MedCPT-Cross-Encoder ≈ 440 MB (downloads to ~/.cache/huggingface/)
# ms-marco-MiniLM-L-12-v2 ≈ 130 MB (faster, less medical-specific)
"""


# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/rag/__init__.py
# ═══════════════════════════════════════════════════════════════════════════════

INIT_PY = """
# PRISM RAG Enhancement components
from backend.core.rag.hybrid_chunker        import HybridChunker, PRISMCollectionReindexer
from backend.core.rag.cross_encoder_reranker import CrossEncoderReranker, PRISMRetrievalPipeline
from backend.core.rag.hyde_query_transformer import HyDEQueryTransformer, PRISMFullRAGPipeline

__all__ = [
    "HybridChunker",
    "PRISMCollectionReindexer",
    "CrossEncoderReranker",
    "PRISMRetrievalPipeline",
    "HyDEQueryTransformer",
    "PRISMFullRAGPipeline",
]
"""


# ═══════════════════════════════════════════════════════════════════════════════
# ENVIRONMENT VARIABLES — add to .env
# ═══════════════════════════════════════════════════════════════════════════════

ENV_VARS = """
# ── PRISM RAG Enhancement settings ────────────────────────────────────────────

# Reranker
PRISM_RERANKER_BACKEND=medcpt          # medcpt | msmarco | llm_judge | none
PRISM_RERANKER_TOP_K=3                 # Chunks returned to LLM after reranking
PRISM_RERANKER_MIN_SCORE=0.10          # Discard chunks below this relevance score
PRISM_RERANKER_DEVICE=cpu              # cpu | cuda | mps

# HyDE
PRISM_USE_HYDE=true                    # Enable HyDE query transformation
PRISM_HYDE_TEMPERATURE=0.25            # Lower = more consistent hypotheticals
PRISM_HYDE_MAX_TOKENS=150              # Max tokens per hypothetical document
PRISM_HYDE_LATAM_ANGLE=true            # Generate LATAM-specific hypothetical

# Chunking (for re-indexing)
PRISM_CHUNK_PARENT_SIZE=512            # Parent chunk token size
PRISM_CHUNK_CHILD_SIZE=128             # Child chunk token size
PRISM_CHUNK_PARENT_OVERLAP=64          # Parent overlap tokens
PRISM_CHUNK_CHILD_OVERLAP=20           # Child overlap tokens
"""


# ═══════════════════════════════════════════════════════════════════════════════
# RAGAS EVALUATION SCRIPT — run before and after to measure gains
# ═══════════════════════════════════════════════════════════════════════════════

RAGAS_EVAL_SNIPPET = """
# backend/scripts/evaluate_ragas.py
# Run: python -m backend.scripts.evaluate_ragas --agent DM2 --n 50

from ragas import evaluate
from ragas.metrics import (
    faithfulness, answer_relevancy,
    context_precision, context_recall, answer_correctness,
)
from datasets import Dataset

async def run_eval(agent_id: str, n_samples: int = 50):
    # 1. Load eval set (50 gold Q&A pairs per agent)
    eval_set = load_eval_set(agent_id, n=n_samples)

    # 2. Run PRISM pipeline on each question
    pipeline = PRISMFullRAGPipeline()
    rows = []
    for item in eval_set:
        result = await pipeline.retrieve(
            query=item["question"], agent_id=agent_id
        )
        answer = await generate_answer(result["context"], item["question"], agent_id)
        rows.append({
            "question":  item["question"],
            "answer":    answer,
            "contexts":  [c["source"] for c in result["citations"]],
            "ground_truth": item["reference_answer"],
        })

    # 3. Score with RAGAS
    dataset = Dataset.from_list(rows)
    scores  = evaluate(dataset, metrics=[
        faithfulness, answer_relevancy,
        context_precision, context_recall, answer_correctness,
    ])
    print(scores)
    return scores

# Install ragas: pip install ragas
"""