# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/agents/smart_router.py
# PRISM Smart Routing Engine — 3-Tier Agent Escalation
# ───────────────────────────────────────────────────────────────────────────────
# ARCHITECTURE:
#   Primary Agent  → confidence ≥ 0.70  → respond directly
#                  → confidence < 0.70  → escalate to Specialist Agent
#                  → frustration > 75   → escalate to Human Coordinator Agent
#
# LANGGRAPH PIPELINE (9 nodes):
#   INPUT → DETECT_LANGUAGE → RETRIEVE → RERANK → PRIMARY_AGENT
#         → CONFIDENCE_CHECK → [SPECIALIST | FRUSTRATION_CHECK]
#         → [HUMAN_ESCALATION | RESPOND] → OUTPUT
#
# FRUSTRATION SIGNALS (any one triggers +25 frustration points):
#   - Explicit frustration keywords ("rubbish", "ridiculous", "useless"…)
#   - Repeated concern (same question asked again)
#   - Explicit request for human ("speak to a real doctor", "I need a person")
#   - Agent uncertainty detected 3+ times in same conversation
#   - Emergency symptom detected
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import re
import time
import uuid
import asyncio
from typing import TypedDict, List, Dict, Optional, Literal, Any
from datetime import datetime

# ADDED: PRISM RAG Enhancement Pipeline
from backend.core.rag.hyde_query_transformer import PRISMFullRAGPipeline

# LangGraph
from langgraph.graph import StateGraph, END

from backend.config.settings import get_settings

settings = get_settings()

# ─── RAG Pipeline Singleton ───────────────────────────────────────────────────
_rag_pipeline: PRISMFullRAGPipeline | None = None

def get_rag_pipeline() -> PRISMFullRAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = PRISMFullRAGPipeline()
    return _rag_pipeline

# ─────────────────────────────────────────────────────────────────────────────
# CONFIG CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
CONFIDENCE_THRESHOLD  = 0.70    # Below this → Specialist Agent activated
FRUSTRATION_THRESHOLD = 75      # Above this → Human Escalation Agent activated
TOP_K_RETRIEVE        = 10      # Retrieve top-10 chunks initially
TOP_K_RERANK          = 5       # Re-rank down to top-5 for the prompt

from backend.core.conversation.frustration_detector import (
    FrustrationDetector, FRUSTRATION_KEYWORDS, HUMAN_REQUEST_PHRASES, 
    EMPATHY_THRESHOLD, HUMAN_THRESHOLD
)

# ─────────────────────────────────────────────────────────────────────────────
# SPECIALIST AGENT DEFINITIONS  (one per primary agent)
# ─────────────────────────────────────────────────────────────────────────────
SPECIALIST_AGENTS: Dict[str, Dict] = {
    "CA1": {"name": "Oncology Screening Specialist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR clinical oncologist with expertise in population-level cancer screening. Provide deeper evidence-based answers with clinical nuance. Cite specific trial names, sensitivity/specificity values, and ACS Grade levels."},
    "CA2": {"name": "Medical Oncology Treatment Specialist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR medical oncologist expert in NCCN-guided treatment protocols. Provide detailed biomarker-driven treatment options, regimen specifics (without doses), and clinical trial eligibility considerations."},
    "CA3": {"name": "Palliative Medicine Specialist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR palliative medicine and supportive care specialist. Provide detailed symptom management frameworks using MASCC, WHO and NCCN Supportive Care guidelines."},
    "CA4": {"name": "Cancer Survivorship Specialist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR cancer survivorship and rehabilitation specialist. Provide detailed long-term surveillance schedules, late-effect management and ASCO Survivorship Care Plan elements."},
    "CA5": {"name": "Oncogenetics Specialist", "tier": "specialist",
            "prompt_suffix": "You are a CERTIFIED oncogenetics specialist with expertise in BRCA1/2, Lynch, PALB2. Provide detailed variant classification interpretation, chemoprevention evidence, and prophylactic surgical option frameworks."},

    "DM1": {"name": "Endocrinology CGM Specialist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR endocrinologist with CGM/closed-loop expertise. Provide deeper clinical interpretation of glucose patterns, DKA management protocols, and ADA 2024 precision medicine guidance."},
    "DM2": {"name": "Diabetes Pharmacotherapy Specialist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR clinical pharmacologist specialising in diabetes therapeutics. Provide in-depth drug mechanism comparisons, real-world effectiveness data (EMPA-REG, LEADER, SURPASS) and comorbidity-guided selection."},
    "DM3": {"name": "Diabetes Dietitian Specialist", "tier": "specialist",
            "prompt_suffix": "You are a REGISTERED clinical dietitian specialising in diabetes MNT. Provide detailed carbohydrate exchange plans, cultural food substitution tables, and evidence-based exercise prescription (METs, duration, intensity)."},
    "DM4": {"name": "Diabetology Complications Specialist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR diabetologist specialising in microvascular complications. Provide detailed nephropathy staging (KDIGO CGA), retinopathy grading (ETDRS), neuropathy scoring (MNSI), and foot risk classification (IWGDF)."},
    "DM5": {"name": "Maternal-Fetal Medicine Specialist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR maternal-fetal medicine specialist (perinatologist). Provide detailed GDM insulin titration frameworks, fetal surveillance protocols (HAPO thresholds), and paediatric T1D transition-of-care guidance (ISPAD)."},

    "CV1": {"name": "Interventional Cardiology Specialist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR interventional cardiologist. Provide detailed AHA/ACC heart failure staging, CHA2DS2-VASc scoring, echocardiographic parameter interpretation, and guideline-directed medical therapy protocols."},
    "CV2": {"name": "Cardiac Emergency Specialist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR emergency cardiologist/intensivist. CRITICAL: For any cardiac emergency, 911 FIRST always. Then provide ACLS-guided clinical frameworks, STEMI reperfusion strategies, and cardiogenic shock management protocols."},
    "CV3": {"name": "Clinical Cardiac Pharmacologist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR cardiac clinical pharmacologist. Provide detailed drug interaction profiles, PK/PD considerations for cardiac medications, PARADIGM-HF/COPERNICUS trial data, and INR therapeutic window management."},
    "CV4": {"name": "Cardiac Rehabilitation Physiologist", "tier": "specialist",
            "prompt_suffix": "You are a CERTIFIED cardiac rehabilitation physiologist. Provide detailed Karvonen HRR prescription, Borg RPE targets, Phase II/III progression protocols (HF-ACTION), and home-based equivalent frameworks (Cochrane evidence)."},
    "CV5": {"name": "Preventive Cardiology Nutritionist", "tier": "specialist",
            "prompt_suffix": "You are a REGISTERED dietitian specialising in preventive cardiology. Provide detailed DASH diet sodium targets, PREDIMED Mediterranean adherence scoring, REDUCE-IT EPA dosing protocols, and hypertriglyceridaemia dietary algorithms."},

    "MH1": {"name": "Mood Disorders Psychiatrist", "tier": "specialist",
            "prompt_suffix": "You are a CONSULTANT psychiatrist specialising in mood disorders. Provide detailed PHQ-9 severity-matched treatment algorithms, SSRI/SNRI switching protocols, augmentation strategies, and CBT adaptation frameworks (NICE CG90). ALWAYS screen for suicidal ideation first."},
    "MH2": {"name": "Anxiety Disorders Psychologist", "tier": "specialist",
            "prompt_suffix": "You are a CONSULTANT clinical psychologist specialising in anxiety disorders. Provide detailed GAD-7 severity-matched CBT/exposure hierarchies, GABAergic risk stratification for benzodiazepines, and NICE CG113/CG159 stepped-care protocols."},
    "MH3": {"name": "Sleep Medicine Specialist", "tier": "specialist",
            "prompt_suffix": "You are a CERTIFIED sleep medicine physician (AASM). Provide detailed CBT-I session-by-session protocols, sleep restriction titration schedules, circadian rhythm disorder classification, and ISI-guided treatment response tracking."},
    "MH4": {"name": "Trauma Psychiatry Specialist", "tier": "specialist",
            "prompt_suffix": "You are a CONSULTANT trauma psychiatrist (APA/ISTSS certified). Provide detailed PCL-5 diagnostic interpretation, EMDR phase-by-phase framework, Prolonged Exposure session structure, and complex PTSD (ICD-11) stabilisation protocols. DV: Safety plan FIRST always."},
    "MH5": {"name": "Crisis Psychiatry Specialist", "tier": "specialist",
            "prompt_suffix": "You are a CRISIS PSYCHIATRY specialist. CRITICAL: Crisis lines FIRST always. Then provide C-SSRS risk stratification, safety plan construction (Stanley-Brown), means restriction counselling, and acute psychiatric emergency triage frameworks."},

    "RS1": {"name": "Respiratory & Asthma Specialist", "tier": "specialist",
            "prompt_suffix": "You are a CONSULTANT respiratory physician specialising in difficult-to-treat asthma. Provide GINA 2024 step 4-5 biologics eligibility (severe asthma phenotyping), FeNO interpretation, AERD management, and MDI/DPI/BAI device optimisation evidence."},
    "RS2": {"name": "COPD & Pulmonology Specialist", "tier": "specialist",
            "prompt_suffix": "You are a CONSULTANT pulmonologist specialising in GOLD 2024 COPD. Provide detailed spirometry interpretation (FEV1/FVC, Z-scores), GOLD E group management, roflumilast eligibility (FEV1 <50%, chronic bronchitis), and LTOT criteria (NOTT trial)."},
    "RS3": {"name": "Pulmonary Rehabilitation Specialist", "tier": "specialist",
            "prompt_suffix": "You are a CERTIFIED pulmonary rehabilitation physiotherapist (ATS/ERS). Provide detailed 6MWT clinically significant difference thresholds (25m), HRQL outcome measures (SGRQ, CAT), tele-PR evidence, and post-exacerbation PR timing (4-week safe window)."},
    "RS4": {"name": "Respiratory Pharmacology Specialist", "tier": "specialist",
            "prompt_suffix": "You are a SENIOR respiratory clinical pharmacologist. Provide detailed ICS dose equivalency tables, DPI/MDI/SMI lung deposition evidence, Respimat vs DPI comparative effectiveness, montelukast neuropsychiatric mechanism, and theophylline TDM protocols."},
    "RS5": {"name": "Sleep-Disordered Breathing Specialist", "tier": "specialist",
            "prompt_suffix": "You are a CONSULTANT respiratory sleep physician (AASM). Provide detailed PSG report interpretation, AHI phenotype analysis (obstructive vs central vs mixed), CPAP pressure titration protocols, Inspire upper-airway stimulation candidacy criteria, and OHS BiPAP initiation thresholds."},
}

# ─────────────────────────────────────────────────────────────────────────────
# HUMAN ESCALATION AGENT DEFINITIONS  (one per primary agent)
# ─────────────────────────────────────────────────────────────────────────────
HUMAN_AGENTS: Dict[str, Dict] = {
    "CA1": {"name": "Cancer Screening Care Coordinator", "role": "care_coordinator",
            "contact": "800-PRISM-CA · WhatsApp +52 55 1234-5001",
            "empathy_prompt": "cancer screening concern"},
    "CA2": {"name": "Oncology Treatment Navigator", "role": "care_coordinator",
            "contact": "800-PRISM-CA · WhatsApp +52 55 1234-5002",
            "empathy_prompt": "cancer treatment confusion"},
    "CA3": {"name": "Supportive Care Coordinator", "role": "care_coordinator",
            "contact": "800-PRISM-CA · WhatsApp +52 55 1234-5003",
            "empathy_prompt": "cancer symptom distress"},
    "CA4": {"name": "Cancer Survivorship Nurse Navigator", "role": "nurse_navigator",
            "contact": "800-PRISM-CA · WhatsApp +52 55 1234-5004",
            "empathy_prompt": "survivorship anxiety"},
    "CA5": {"name": "Oncogenetics Counselling Coordinator", "role": "genetic_counsellor",
            "contact": "800-PRISM-CA · WhatsApp +52 55 1234-5005",
            "empathy_prompt": "genetic test anxiety"},

    "DM1": {"name": "Diabetes Care Coordinator", "role": "care_coordinator",
            "contact": "800-PRISM-DM · WhatsApp +52 55 1234-5101",
            "empathy_prompt": "glucose management frustration"},
    "DM2": {"name": "Diabetes Medication Specialist Coordinator", "role": "care_coordinator",
            "contact": "800-PRISM-DM · WhatsApp +52 55 1234-5102",
            "empathy_prompt": "medication side-effect distress"},
    "DM3": {"name": "Diabetes Dietitian Coordinator", "role": "dietitian",
            "contact": "800-PRISM-DM · WhatsApp +52 55 1234-5103",
            "empathy_prompt": "dietary confusion and frustration"},
    "DM4": {"name": "Diabetes Complications Nurse Navigator", "role": "nurse_navigator",
            "contact": "800-PRISM-DM · WhatsApp +52 55 1234-5104",
            "empathy_prompt": "complication distress"},
    "DM5": {"name": "Maternal Diabetes Care Coordinator", "role": "care_coordinator",
            "contact": "800-PRISM-DM · WhatsApp +52 55 1234-5105",
            "empathy_prompt": "gestational diabetes anxiety"},

    "CV1": {"name": "Cardiac Care Coordinator", "role": "care_coordinator",
            "contact": "800-PRISM-CV · WhatsApp +52 55 1234-5201",
            "empathy_prompt": "cardiac health anxiety"},
    "CV2": {"name": "Cardiac Emergency Response Team", "role": "emergency_coordinator",
            "contact": "CALL 911 NOW · 800-PRISM-CV for follow-up",
            "empathy_prompt": "cardiac emergency fear"},
    "CV3": {"name": "Cardiac Pharmacist Coordinator", "role": "pharmacist",
            "contact": "800-PRISM-CV · WhatsApp +52 55 1234-5203",
            "empathy_prompt": "medication confusion and concern"},
    "CV4": {"name": "Cardiac Rehab Coordinator", "role": "physiotherapist",
            "contact": "800-PRISM-CV · WhatsApp +52 55 1234-5204",
            "empathy_prompt": "rehabilitation frustration"},
    "CV5": {"name": "Cardiac Nutrition Coordinator", "role": "dietitian",
            "contact": "800-PRISM-CV · WhatsApp +52 55 1234-5205",
            "empathy_prompt": "cardiac diet frustration"},

    "MH1": {"name": "Mental Health Care Coordinator", "role": "mental_health_coordinator",
            "contact": "988 Lifeline · 800-PRISM-MH · WhatsApp +52 55 1234-5301",
            "empathy_prompt": "depression and emotional distress"},
    "MH2": {"name": "Anxiety Support Coordinator", "role": "mental_health_coordinator",
            "contact": "988 Lifeline · 800-PRISM-MH · WhatsApp +52 55 1234-5302",
            "empathy_prompt": "anxiety and panic distress"},
    "MH3": {"name": "Sleep & Wellness Coordinator", "role": "mental_health_coordinator",
            "contact": "800-PRISM-MH · WhatsApp +52 55 1234-5303",
            "empathy_prompt": "sleep deprivation exhaustion"},
    "MH4": {"name": "Trauma Support Coordinator", "role": "trauma_coordinator",
            "contact": "988 Lifeline · DV Hotline 1-800-799-7233 · 800-PRISM-MH",
            "empathy_prompt": "trauma and safety concern"},
    "MH5": {"name": "Crisis Response Coordinator", "role": "crisis_coordinator",
            "contact": "988 NOW · CVV 188 (Brazil) · 800-290-0024 (Mexico)",
            "empathy_prompt": "acute mental health crisis"},

    "RS1": {"name": "Asthma Care Coordinator", "role": "care_coordinator",
            "contact": "800-PRISM-RS · WhatsApp +52 55 1234-5401",
            "empathy_prompt": "breathing difficulty distress"},
    "RS2": {"name": "COPD Care Coordinator", "role": "care_coordinator",
            "contact": "800-PRISM-RS · WhatsApp +52 55 1234-5402",
            "empathy_prompt": "COPD management frustration"},
    "RS3": {"name": "Pulmonary Rehab Coordinator", "role": "physiotherapist",
            "contact": "800-PRISM-RS · WhatsApp +52 55 1234-5403",
            "empathy_prompt": "breathing exercise frustration"},
    "RS4": {"name": "Respiratory Pharmacist Coordinator", "role": "pharmacist",
            "contact": "800-PRISM-RS · WhatsApp +52 55 1234-5404",
            "empathy_prompt": "inhaler technique frustration"},
    "RS5": {"name": "Sleep Apnea Care Coordinator", "role": "care_coordinator",
            "contact": "800-PRISM-RS · WhatsApp +52 55 1234-5405",
            "empathy_prompt": "sleep apnea impact distress"},
}

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — FRUSTRATION DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════

# (FrustrationDetector class removed and imported from utility)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — CONFIDENCE SCORER
# ═══════════════════════════════════════════════════════════════════════════════

class ConfidenceScorer:
    """
    Computes a confidence score (0.0–1.0) for an AI response.
    Below CONFIDENCE_THRESHOLD → Specialist Agent is invoked.
    """

    def compute(
        self,
        query: str,
        response: str,
        retrieved_chunks: List[Dict],
        history: List[Dict],
    ) -> float:
        """
        Combines 4 signals:
        1. Average rerank score of retrieved chunks (weight: 0.45)
        2. Query-to-context keyword overlap (weight: 0.25)
        3. Response length/completeness heuristic (weight: 0.15)
        4. Citation density (weight: 0.15)
        """
        if not retrieved_chunks:
            return 0.35  # No context = low confidence

        # Signal 1: Average rerank score
        rerank_scores = [
            c.get("rerank_score", c.get("score", 0.5))
            for c in retrieved_chunks
        ]
        avg_rerank = sum(rerank_scores) / len(rerank_scores) if rerank_scores else 0.4

        # Signal 2: Query ↔ context keyword overlap
        q_words = set(re.findall(r'\w+', query.lower())) - {"the", "a", "an", "is", "to"}
        c_words = set()
        for chunk in retrieved_chunks:
            c_words.update(re.findall(r'\w+', chunk.get("text", "").lower()))
        overlap = len(q_words & c_words) / max(len(q_words), 1) if q_words else 0.4

        # Signal 3: Response completeness (word count heuristic)
        word_count = len(response.split())
        completeness = min(word_count / 120, 1.0)

        # Signal 4: Citation density in response
        citation_signals = ["according to", "evidence grade", "guideline", "study", "trial", "ref"]
        citation_score = min(
            sum(1 for s in citation_signals if s in response.lower()) / 3, 1.0
        )

        # Weighted combination
        confidence = (
            avg_rerank   * 0.45 +
            overlap      * 0.25 +
            completeness * 0.15 +
            citation_score * 0.15
        )
        return round(min(max(confidence, 0.10), 1.0), 3)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — LANGGRAPH ROUTING STATE
# ═══════════════════════════════════════════════════════════════════════════════

class RoutingState(TypedDict):
    # Inputs
    conversation_id:   str
    agent_id:          str
    user_message:      str
    conversation_history: List[Dict]
    language:          str
    context_addendum:  str   # NEW: Injected patient context from intent engine
    system_prompt_override: str   # 🆕 Injected by Response Engine
    chromadb_client:     Any          # ← ADDED

    # Processing state
    detected_language: str
    english_message:   str
    retrieved_chunks:  List[Dict]
    reranked_chunks:   List[Dict]
    primary_response:  str
    specialist_response: str
    final_response:    str
    
    # RAG Enhancement state
    retrieved_context:   str          # ← ADDED
    citations:           List[Dict]   # ← ADDED
    retrieval_confidence: float       # ← ADDED
    chunks_used:         int          # ← ADDED
    hyde_used:           bool         # ← ADDED
    reranker_backend:    str          # ← ADDED

    # Scores
    confidence:        float
    frustration_score: int
    frustration_data:  Dict
    agent_uncertainty_count: int

    # Routing decisions
    route_decision:    Literal["primary", "specialist", "human"]
    escalation_active: bool
    escalation_reason: str

    # Output metadata
    llm_calls:         List[Dict]
    # citations:         List[Dict]  # Moved up
    ragas_scores:      Dict
    processing_ms:     int
    start_time:        float
    # 🆕 Layer 6: Self-verification
    verified_response:     str
    verification_feedback: str


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — LANGGRAPH NODE FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

# These are imported from the existing pipeline modules
# shown here as stubs to illustrate the LangGraph wiring

# ── Layer 2: Query Expansion ──────────────────────────────────────────────
def node_query_expansion(state: RoutingState) -> RoutingState:
    """Generate 2 expanded queries to improve retrieval recall."""
    from backend.core.agents.base_agent import call_llm_sync
    query = state["english_message"]
    
    expansion_prompt = f"""Given the user medical query, generate 2 variations that use different medical terms or keywords to improve document retrieval.
Original: "{query}"
Format: Return exactly 2 lines, one query per line, no numbering.
Example: 
"diabetes diet"
"glycemic control meal plan"
"Type 2 diabetes nutrition guidelines"
"""
    result = call_llm_sync(
        system_prompt="You are a medical search specialist. Expand queries with technical medical terms.",
        user_message=query,
        history=[],
        temperature=0.0,
        max_tokens=100
    )
    
    expanded = [query]
    if result["success"]:
        lines = [l.strip("- ").strip() for l in result["response"].strip().split("\n") if l.strip()]
        expanded.extend(lines[:2])
    
    return {**state, "context_addendum": f"Expanded queries used: {', '.join(expanded)}"}

def node_detect_language(state: RoutingState) -> RoutingState:
    """Detect patient language and translate to English for processing."""
    from backend.core.multilingual.translator import detect_language, translate_text
    detected = detect_language(state["user_message"])
    english  = state["user_message"]
    if detected != "en":
        english = translate_text(state["user_message"], src=detected, tgt="en")
    return {**state, "detected_language": detected, "english_message": english}


async def node_retrieve(state: RoutingState) -> RoutingState:
    """
    Enhanced retrieval node: HyDE → ChromaDB top-10 → Cross-encoder reranker → top-3.
    Replaces the existing 5-chunk flat retrieval.
    """
    import os
    pipeline    = get_rag_pipeline()
    use_hyde    = os.getenv("PRISM_USE_HYDE", "true").lower() == "true"

    from backend.config.agent_registry import ALL_AGENTS
    agent = ALL_AGENTS.get(state["agent_id"])
    collection_name = agent.collection_name if agent else f"prism_{state['agent_id'].lower()}"

    retrieval = await pipeline.retrieve(
        query           = state["english_message"],
        agent_id        = state["agent_id"],
        language        = state.get("language", "en"),
        chromadb_client = state.get("chromadb_client"),   # pass from graph initialisation
        use_hyde        = use_hyde,
        use_multi_query = False,   # Enable in Sprint 3 for max recall
        collection_name = collection_name,
    )

    # 🆕 Fix: Map chunks to state so evaluator and confidence scorer can see them
    chunks = retrieval.get("chunks", [])

    return {
        **state,
        "retrieved_context":  retrieval["context"],        # → inject into LLM prompt
        "citations":          retrieval["citations"],       # → attach to response
        "retrieval_confidence": retrieval["confidence"],    # → routing decision
        "chunks_used":        retrieval["chunks_used"],
        "hyde_used":          retrieval["hyde_used"],
        "reranker_backend":   retrieval["reranker_backend"],
        "retrieved_chunks":   chunks,                      # Legacy compatibility
        "reranked_chunks":    chunks,                      # For evaluator & scorer
    }


# Redundant: Removed in favour of integrated reranking in node_retrieve
# def node_rerank(state: RoutingState) -> RoutingState:
#     ...


def node_primary_agent(state: RoutingState) -> RoutingState:
    """Run the primary disease agent with the reranked context."""
    from backend.config.agent_registry import ALL_AGENTS
    from backend.core.agents.base_agent import call_llm_sync

    agent_config = ALL_AGENTS.get(state["agent_id"])
    chunks = state["reranked_chunks"]

    context_str = state.get("retrieved_context", "")
    if not context_str:
        # Fallback if retrieve node failed
        context_str = "No context retrieved — use your clinical knowledge with appropriate caveats."

    system_prompt_base = agent_config.system_prompt
    
    # Check for enriched system prompt override from Response Engine
    override = state.get("system_prompt_override", "")
    if override:
        system_prompt = override
    else:
        # 🆕 Inject Medical Analysis context if exists
        analysis_context = ""
        # The history or meta might contain analysis summary. 
        # In main.py we saved it to meta_json. However, RoutingState currently doesn't have meta_json explicitly.
        # But we can pass it via context_addendum in main.py.
        # Let's check main.py line 575 where context_addendum is built.
        
        system_prompt = f"""{system_prompt_base}

GROUNDING INSTRUCTIONS (LAYER 4 — CRITICAL):
Before writing your response, verify every claim against the context below.
- Cite sources using [Source N] for EVERY clinical claim.
- If a claim is from your general knowledge and NOT in context, explicitly state "Based on general medical knowledge..."
- DO NOT FABRICATE citations.
- Priority: Be strictly faithful to the provided context.

GUARDRAILS:
{chr(10).join(f'• {g}' for g in agent_config.guardrails)}

RERANKED KNOWLEDGE BASE CONTEXT (top-{len(chunks) if chunks else 3} chunks):
{context_str}

RESPONSE FORMAT:
1. Direct patient-friendly answer (max 4 paragraphs)
2. Use [Source N] citations in-line for all evidence
3. Evidence Grade (A/B/C) for any clinical recommendation
4. Clear actionable next step
Always end with: consult your [specialist type] for personalised guidance."""

    result = call_llm_sync(
        system_prompt=system_prompt,
        user_message=state["english_message"],
        history=state["conversation_history"][-10:],
        temperature=agent_config.temperature,
        max_tokens=agent_config.max_tokens,
    )

    # Count uncertainty signals in response
    uncertainty_words = [
        "i'm not sure", "i am not sure", "unclear", "i cannot determine",
        "not enough information", "please consult", "i don't have"
    ]
    uncertainty_count = sum(
        1 for w in uncertainty_words
        if w in result["response"].lower()
    )

    return {
        **state,
        "primary_response": result["response"],
        "agent_uncertainty_count": state.get("agent_uncertainty_count", 0) + uncertainty_count,
        "llm_calls": state.get("llm_calls", []) + [{
            "agent_id": state["agent_id"],
            "model": result.get("model", settings.llm_model),
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "latency_ms": result["latency_ms"],
            "success": result["success"]
        }]
    }


def node_confidence_check(state: RoutingState) -> RoutingState:
    """
    Confidence check using BOTH generation confidence and retrieval confidence.
    Retrieval confidence < 0.4 → force specialist routing even if generation looks ok.
    """
    # 1. Generation confidence (heuristic based on response content)
    scorer = ConfidenceScorer()
    generation_confidence = scorer.compute(
        query=state["english_message"],
        response=state["primary_response"],
        retrieved_chunks=state.get("reranked_chunks", []), # Legacy support
        history=state["conversation_history"],
    )
    
    # 2. Retrieval confidence (semantic quality of context)
    retrieval_confidence  = state.get("retrieval_confidence", 0.7)

    # Weight: retrieval quality matters as much as generation quality
    final_confidence = 0.50 * generation_confidence + 0.50 * retrieval_confidence

    detector = FrustrationDetector()
    frustration_data = detector.compute(
        message=state["user_message"],
        conversation_history=state["conversation_history"],
        agent_uncertainty_count=state["agent_uncertainty_count"],
    )
    frustration_score = frustration_data["score"]

    # Routing decision
    route = "primary"
    if frustration_data["needs_human"]:
        route = "human"
    elif final_confidence < 0.40:
        route = "specialist"
    
    if state.get("frustration_score", 0) > 75:
        route = "human"

    return {
        **state,
        "confidence":      final_confidence,
        "frustration_score": frustration_score,
        "frustration_data": frustration_data,
        "route_decision":  route,
        "escalation_active": route in ("specialist", "human"),
        "routing_reason": (
            f"gen={generation_confidence:.2f}, "
            f"retrieval={retrieval_confidence:.2f}, "
            f"combined={final_confidence:.2f}"
        ),
    }


def node_specialist_agent(state: RoutingState) -> RoutingState:
    """
    Specialist Agent: called when confidence < 0.70.
    Uses a deeper clinical prompt with more nuanced evidence.
    """
    from backend.core.agents.base_agent import call_llm_sync

    agent_id = state["agent_id"]
    spec = SPECIALIST_AGENTS.get(agent_id, {})
    chunks = state["reranked_chunks"]

    context_str = "\n\n---\n\n".join(
        f"[Source {i}: {c.get('metadata',{}).get('source','PRISM KB')}]\n{c['text']}"
        for i, c in enumerate(chunks, 1)
    ) if chunks else "No context — use deep clinical knowledge."

    # Check for enriched system prompt override
    override = state.get("system_prompt_override", "")
    
    if override:
        persona = f"You are a {spec.get('name', 'Senior Medical Specialist')} for PRISM.\n"
        specialist_system = persona + override
    else:
        specialist_system = f"""You are a {spec.get('name', 'Senior Medical Specialist')} for PRISM.
CONTEXT: The primary AI agent had a confidence of {state['confidence']:.0%} — escalating for deeper detail.

GROUNDING INSTRUCTIONS (LAYER 4):
- You must be 100% FAITHFUL to the provided context chunks.
- Cite every source explicitly using [Source N].
- Provide deeper clinical detail (cite specific trials, guidelines, thresholds) if found in context.

SPECIALIST GUARDRAILS:
• Never recommend specific drug doses without prescriber involvement
• Never diagnose — provide clinical context and framework only
• Cite specific guidelines and evidence grades

CONTEXT CHUNKS:
{context_str}

RESPONSE FORMAT:
1. Deep clinical answer grounded in context [Source N]
2. Evidence Grade: A/B/C for each recommendation
3. disclaimer: consult a specialist physician for personalised care"""

    result = call_llm_sync(
        system_prompt=specialist_system,
        user_message=state["english_message"],
        history=state["conversation_history"][-10:],
        temperature=0.10,   # Specialist agents are more precise
        max_tokens=2048,
    )
    return {
        **state, 
        "specialist_response": result["response"],
        "llm_calls": state.get("llm_calls", []) + [{
            "agent_id": f"{agent_id}-S",
            "model": result.get("model", settings.llm_model),
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "latency_ms": result["latency_ms"],
            "success": result["success"]
        }]
    }


def node_human_escalation(state: RoutingState) -> RoutingState:
    """
    Human Escalation Agent: called when frustration > 75.
    Generates an empathetic response and activates the human coordinator card.
    """
    from backend.core.agents.base_agent import call_llm_sync

    agent_id  = state["agent_id"]
    human_cfg = HUMAN_AGENTS.get(agent_id, {})
    triggers  = state["frustration_data"].get("triggers", [])

    empathy_system = f"""You are PRISM's Human Escalation Agent for {human_cfg.get('name', 'PRISM Care Coordinator')}.

SITUATION: A patient has reached a frustration score of {state['frustration_score']}/100 (threshold: {FRUSTRATION_THRESHOLD}).
Trigger signals: {'; '.join(triggers) if triggers else 'High frustration detected'}

YOUR ROLE: You are activating a warm, human handoff. Your response must:
1. Open with GENUINE empathy — acknowledge their specific frustration (not generic)
2. Validate that their frustration is completely understandable
3. Reassure them they will NOT need to repeat themselves (conversation summary is shared)
4. Clearly explain what happens next (care coordinator contact)
5. Provide the care coordinator contact information

CRITICAL RULES:
• Do NOT try to answer the medical question — that's done
• Tone: warm, human, apologetic where appropriate, hopeful
• Keep response to 2-3 short paragraphs
• End with the connection card trigger phrase: [CONNECT_CARE_COORDINATOR]

Contact details for handoff: {human_cfg.get('contact', '800-PRISM-HEALTH')}"""

    result = call_llm_sync(
        system_prompt=empathy_system,
        user_message=f"Patient context: {state['user_message'][:200]}",
        history=[],
        temperature=0.50,   # More human-like warmth
        max_tokens=600,
    )

    # Remove the trigger phrase from the response text (UI handles the card)
    response_text = result["response"].replace("[CONNECT_CARE_COORDINATOR]", "").strip()

    return {
        **state,
        "final_response": response_text,
        "escalation_active": True,
        "llm_calls": state.get("llm_calls", []) + [{
            "agent_id": f"{agent_id}-H",
            "model": result.get("model", settings.llm_model),
            "prompt_tokens": result["prompt_tokens"],
            "completion_tokens": result["completion_tokens"],
            "latency_ms": result["latency_ms"],
            "success": result["success"]
        }]
    }


# ── Layer 6: Self-Verification Node ───────────────────────────────────────
def node_self_verify(state: RoutingState) -> RoutingState:
    """Verify the response against context for hallucinations."""
    from backend.core.agents.base_agent import call_llm_sync
    
    # Pick response to verify
    response = state.get("specialist_response") or state["primary_response"]
    if not response or state["route_decision"] == "human":
        return {**state, "verified_response": response}

    context_str = "\n".join([c["text"][:1500] for c in state["reranked_chunks"]])
    
    verify_prompt = f"""You are a medical fact-checker. 
Compare the AI response against the provided context. Identify any medical claims in the response that are NOT supported by the context.
If a claim is unsupported, remove it or correct it to match the context.
Maintain the citations [Source N] where appropriate.

CONTEXT:
{context_str}

AI RESPONSE:
{response}

Return ONLY the verified and corrected response text."""

    result = call_llm_sync(
        system_prompt="You are a strict clinical fact-checker. Correct hallucinations.",
        user_message=verify_prompt,
        history=[],
        temperature=0.0,
        max_tokens=2048
    )
    
    verified = result["response"] if result["success"] else response
    return {**state, "verified_response": verified}

def node_assemble_response(state: RoutingState) -> RoutingState:
    """
    Final assembly node: picks the right response, translates back,
    extracts citations, computes RAGAS scores.
    """
    from backend.core.multilingual.translator import translate_text
    from backend.core.rag.pipeline import extract_citations
    from backend.core.quality.response_quality import score_response_quality

    route = state["route_decision"]

    # Pick the response based on route
    if route == "human":
        english_response = state.get("final_response", state["primary_response"])
    else:
        english_response = state.get("verified_response", state["primary_response"])

    # Translate back to patient's selected language
    final_response = english_response
    target_lang = state.get("language", "en")
    if target_lang != "en":
        final_response = translate_text(english_response, src="en", tgt=target_lang)

    # Extract citations (already computed in node_retrieve)
    citations    = state.get("citations", [])
    ragas_scores = score_response_quality(
        state["english_message"], english_response, state.get("reranked_chunks", [])
    )

    processing_ms = int((time.time() - state["start_time"]) * 1000)

    return {
        **state,
        "final_response": final_response,
        "citations":      citations,
        "ragas_scores":   ragas_scores,
        "processing_ms":  processing_ms,
    }


def route_after_confidence(state: RoutingState) -> str:
    """LangGraph conditional edge function."""
    return state["route_decision"]   # "primary" | "specialist" | "human"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — LANGGRAPH GRAPH BUILDER
# ═══════════════════════════════════════════════════════════════════════════════

def build_smart_routing_graph() -> StateGraph:
    """
    Build and compile the PRISM Smart Routing LangGraph.

    Graph topology:
    ┌─────────────────────────────────────────────────────────┐
    │  INPUT                                                  │
    │    │                                                    │
    │    ▼                                                    │
    │  detect_language                                        │
    │    │                                                    │
    │    ▼                                                    │
    │  retrieve   (top-10 from ChromaDB)                     │
    │    │                                                    │
    │    ▼                                                    │
    │  rerank     (cross-encoder → top-5)                    │
    │    │                                                    │
    │    ▼                                                    │
    │  primary_agent                                          │
    │    │                                                    │
    │    ▼                                                    │
    │  confidence_check  ──── frustration_score               │
    │    │                                                    │
    │    ├─ route = "primary"  ─────────────────┐            │
    │    ├─ route = "specialist" → specialist   │            │
    │    └─ route = "human"     → human_esc     │            │
    │                │                │         │            │
    │                └────────────────┘         │            │
    │                       │                   │            │
    │                       ▼                   │            │
    │              assemble_response ◄───────────┘            │
    │                       │                                │
    │                      END                               │
    └─────────────────────────────────────────────────────────┘
    """
    graph = StateGraph(RoutingState)

    # Add all nodes
    graph.add_node("expansion",        node_query_expansion)
    graph.add_node("detect_language",  node_detect_language)
    graph.add_node("retrieve",         node_retrieve)
    # graph.add_node("rerank",           node_rerank) # REMOVED
    graph.add_node("primary_agent",    node_primary_agent)
    graph.add_node("confidence_check", node_confidence_check)
    graph.add_node("specialist",       node_specialist_agent)
    graph.add_node("human_escalation", node_human_escalation)
    graph.add_node("verify",           node_self_verify)
    graph.add_node("assemble",         node_assemble_response)

    # Linear edges
    graph.set_entry_point("expansion")
    graph.add_edge("expansion",       "detect_language")
    graph.add_edge("detect_language", "retrieve")
    graph.add_edge("retrieve",        "primary_agent")
    # graph.add_edge("rerank",          "primary_agent")
    graph.add_edge("primary_agent",   "confidence_check")

    # Conditional routing after confidence check
    graph.add_conditional_edges(
        "confidence_check",
        route_after_confidence,
        {
            "primary":    "verify",
            "specialist": "specialist",
            "human":      "human_escalation",
        }
    )

    # Specialist goes to verify, human goes to assemble directly
    graph.add_edge("specialist",       "verify")
    graph.add_edge("verify",           "assemble")
    graph.add_edge("human_escalation", "assemble")
    graph.add_edge("assemble",         END)

    return graph.compile()


# Global compiled graph (singleton — built once, reused)
_smart_graph = None

def get_smart_graph():
    global _smart_graph
    if _smart_graph is None:
        _smart_graph = build_smart_routing_graph()
    return _smart_graph


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — PUBLIC API FUNCTION
# Called from FastAPI chat endpoint
# ═══════════════════════════════════════════════════════════════════════════════

async def run_smart_routing(
    agent_id:       str,
    user_message:   str,
    conversation_id: str,
    history:        List[Dict],
    language:       str = "en",
    context_addendum: str = "",
    system_prompt_override: str = "",
    chromadb_client: Any = None,
) -> Dict:
    """
    Main entry point called from the FastAPI /api/chat endpoint.
    Returns the complete routing result including escalation metadata.
    """
    import asyncio

    initial_state: RoutingState = {
        "conversation_id":       conversation_id,
        "agent_id":              agent_id.upper(),
        "user_message":          user_message,
        "conversation_history":  history,
        "language":              language,
        "context_addendum":      context_addendum,
        "system_prompt_override": system_prompt_override,
        "chromadb_client":       chromadb_client,
        # Processing state (populated by nodes)
        "detected_language":     "en",
        "english_message":       user_message,
        "retrieved_chunks":      [],
        "reranked_chunks":       [],
        "primary_response":      "",
        "specialist_response":   "",
        "final_response":        "",
        # RAG state
        "retrieved_context":     "",
        "citations":             [],
        "retrieval_confidence":  0.0,
        "chunks_used":           0,
        "hyde_used":             False,
        "reranker_backend":      "none",
        # Scores
        "confidence":            0.0,
        "frustration_score":     0,
        "frustration_data":      {},
        "agent_uncertainty_count": 0,
        # Routing decisions
        # Routing decisions
        "route_decision":        "primary",
        "escalation_active":     False,
        "escalation_reason":     "",
        # Layer 6 output
        "verified_response":     "",
        "verification_feedback": "",
        # Output
        "llm_calls":             [],
        "citations":             [],
        "ragas_scores":          {},
        "processing_ms":         0,
        "start_time":            time.time(),
    }

    graph  = get_smart_graph()
    result = await graph.ainvoke(initial_state)

    # Build the structured response for the API
    agent_id_upper = agent_id.upper()
    specialist_info = SPECIALIST_AGENTS.get(agent_id_upper, {})
    human_info      = HUMAN_AGENTS.get(agent_id_upper, {})

    return {
        "response":           result["final_response"],
        "route_decision":     result["route_decision"],
        "confidence":         result["confidence"],
        "frustration_score":  result["frustration_score"],
        "frustration_data":   result["frustration_data"],
        "escalation_active":  result["escalation_active"],
        "escalation_reason":  result["escalation_reason"],
        "agent_id":           agent_id_upper,
        "specialist_agent":   {
            "agent_id":   f"{agent_id_upper}-S",
            "name":       specialist_info.get("name", ""),
            "activated":  result["route_decision"] == "specialist",
        },
        "human_agent": {
            "agent_id":   f"{agent_id_upper}-H",
            "name":       human_info.get("name", ""),
            "role":       human_info.get("role", ""),
            "contact":    human_info.get("contact", ""),
            "activated":  result["route_decision"] == "human",
        },
        "escalation_monitor": {
            "frustration_score": result["frustration_score"],
            "triggers":          result["frustration_data"].get("triggers", []),
            "trigger_codes":     result["frustration_data"].get("trigger_codes", []),
            "confidence":        result["confidence"],
            "route":             result["route_decision"],
            "active":            result["escalation_active"],
        },
        "rag_metadata": {
            "hyde_used":        result.get("hyde_used", False),
            "chunks_used":      result.get("chunks_used", 0),
            "reranker":         result.get("reranker_backend", "none"),
            "confidence":       result.get("retrieval_confidence", 0.0)
        },
        "llm_calls":          result.get("llm_calls", []),
        "citations":          result["citations"],
        "ragas_scores":       result["ragas_scores"],
        "retrieved_chunks":   result.get("reranked_chunks", []),
        "detected_language":  result["detected_language"],
        "processing_ms":      result["processing_ms"],
    }