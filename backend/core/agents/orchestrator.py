"""
PRISM — LangGraph Multi-Agent Orchestrator
Flow: detect_language → translate → pre_check → retrieve → primary_agent
      → score_confidence → [specialist] → check_frustration → [human_escalation]
      → format_response → translate_response → END
"""
import re
import time
import json
from typing import TypedDict, Annotated, List, Dict, Optional, Any, Tuple
from datetime import datetime

from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from backend.config.settings import get_settings
from backend.config.disease_config import AGENTS, DISEASE_DOMAINS
from backend.core.rag.pipeline import get_rag_pipeline
from backend.core.multilingual.translator import translate_text, translate_response as ml_translate_response
from backend.core.quality.response_quality import ResponseQualityScorer

settings = get_settings()
quality_scorer = ResponseQualityScorer()


# ── State ─────────────────────────────────────────────────────────────────
class PRISMState(TypedDict):
    # Input
    user_id:         str
    conversation_id: str
    agent_id:        str
    user_message:    str
    language:        str
    multimodal_data: Optional[Dict]

    # Language processing
    detected_lang:   str
    english_message: str

    # Retrieval
    retrieved_chunks: List[Dict]
    context:          str

    # Agent responses
    primary_response:    str
    specialist_response: str
    human_response:      str
    final_response:      str
    translated_response: str

    # Scores
    confidence:       float
    frustration:      int
    ragas_scores:     Dict
    citations:        List[Dict]

    # Routing
    needs_specialist: bool
    needs_human:      bool
    escalated_to:     str
    trigger_log:      List[str]  # New: tracks why escalation happened

    # Meta
    processing_steps: List[str]
    latency_ms:       int
    messages:         Annotated[List, add_messages]


# ── LLM factory ───────────────────────────────────────────────────────────
def _get_llm(temperature: float = 0.2):
    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.llm_model,
            temperature=temperature,
            anthropic_api_key=settings.anthropic_api_key,
            max_tokens=2048,
        )
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model,
            temperature=temperature,
            openai_api_key=settings.openai_api_key,
        )


# ── Node: detect language ─────────────────────────────────────────────────
def detect_language_node(state: PRISMState) -> PRISMState:
    try:
        from langdetect import detect
        lang = detect(state["user_message"])
        supported = settings.languages_list
        detected = lang if lang in supported else "en"
    except Exception:
        detected = state.get("language", "en")

    return {**state,
            "detected_lang":   detected,
            "processing_steps": state.get("processing_steps", []) + ["detect_language"]}


# ── Node: translate to English ────────────────────────────────────────────
def translate_to_english_node(state: PRISMState) -> PRISMState:
    lang = state.get("detected_lang", "en")
    msg  = state["user_message"]
    if lang != "en":
        try:
            msg = translate_text(msg, src=lang, tgt="en")
        except Exception:
            pass
    return {**state,
            "english_message": msg,
            "processing_steps": state.get("processing_steps", []) + ["translate_to_en"]}


# ── Node: retrieve context ────────────────────────────────────────────────
def retrieve_context_node(state: PRISMState) -> PRISMState:
    agent_cfg = AGENTS.get(state["agent_id"])
    if not agent_cfg:
        return {**state, "retrieved_chunks": [], "context": ""}

    pipeline = get_rag_pipeline()
    collection = agent_cfg.collection_name
    query = state.get("english_message", state["user_message"])

    chunks = pipeline.retrieve(
        query, collection,
        top_k_initial=10, # Force top 10 for best-in-class reranking
        top_k_final=10,   # Use all 10 reranked chunks for response coherence
    )

    context_parts = []
    for i, c in enumerate(chunks, 1):
        meta = c.get("metadata", {})
        src  = meta.get("source", "PRISM Knowledge Base")
        yr   = meta.get("year", "")
        grade = meta.get("evidence_grade", "")
        context_parts.append(
            f"[Source {i}: {src} {yr} | Evidence: {grade}]\n{c['text']}"
        )

    return {**state,
            "retrieved_chunks": chunks,
            "context": "\n\n---\n\n".join(context_parts),
            "processing_steps": state.get("processing_steps", []) + ["retrieve_context"]}


# ── Node: primary agent ────────────────────────────────────────────────────
def primary_agent_node(state: PRISMState) -> PRISMState:
    agent_cfg = AGENTS.get(state["agent_id"])
    if not agent_cfg:
        return {**state, "primary_response": "I'm sorry, I couldn't process your request."}

    llm = _get_llm(agent_cfg.temperature)
    context = state.get("context", "")
    query   = state.get("english_message", state["user_message"])

    messages = [
        SystemMessage(content=f"""{agent_cfg.system_prompt}

CONTEXT FROM KNOWLEDGE BASE:
{context if context else "No context retrieved. Use your clinical knowledge with appropriate caveats."}

INSTRUCTIONS:
- Respond in clear, patient-friendly language
- Always provide Evidence Grade (A/B/C) for clinical recommendations
- End with numbered citations if context was used
- If context is insufficient, say so and recommend professional consultation
- For LATAM patients: include relevant regional resources when applicable
"""),
        HumanMessage(content=query),
    ]

    # Add conversation history (last N messages)
    for msg in state.get("messages", [])[-6:]:
        messages.insert(-1, msg)

    start = time.time()
    resp = llm.invoke(messages)
    latency = int((time.time() - start) * 1000)

    response_text = resp.content if hasattr(resp, "content") else str(resp)

    # Extract citations
    citations = _extract_citations(response_text, state.get("retrieved_chunks", []))

    return {**state,
            "primary_response": response_text,
            "citations":         citations,
            "latency_ms":        latency,
            "processing_steps":  state.get("processing_steps", []) + ["primary_agent"]}


# ── Node: score confidence ────────────────────────────────────────────────
def score_confidence_node(state: PRISMState) -> PRISMState:
    response = state.get("primary_response", "")
    query    = state.get("english_message", state["user_message"])
    chunks   = state.get("retrieved_chunks", [])

    # Heuristic confidence scoring
    conf = _compute_confidence(query, response, chunks)
    frust, triggers = _compute_frustration(query, state.get("messages", []))

    needs_spec  = conf < 0.70 # Precise threshold as requested
    needs_human = frust > 75  # Precise threshold as requested

    log = []
    if needs_spec: log.append(f"Low confidence score ({int(conf*100)}%) — Specialist required")
    if needs_human: log.append(f"High frustration score ({frust}%) — Escalating to human care coordinator")
    for t in triggers: log.append(t)

    return {**state,
            "confidence":       conf,
            "frustration":      frust,
            "needs_specialist": needs_spec,
            "needs_human":      needs_human,
            "trigger_log":      log,
            "processing_steps": state.get("processing_steps", []) + ["score_confidence"]}


# ── Node: specialist agent ────────────────────────────────────────────────
def specialist_agent_node(state: PRISMState) -> PRISMState:
    agent_id  = state["agent_id"]
    agent_cfg = AGENTS.get(agent_id)
    spec_id   = agent_cfg.specialist_id if agent_cfg else f"{agent_id}-S"
    spec_cfg  = AGENTS.get(spec_id)

    if not spec_cfg:
        return {**state, "specialist_response": state.get("primary_response", ""),
                "escalated_to": "none"}

    llm = _get_llm(spec_cfg.temperature)
    query   = state.get("english_message", state["user_message"])
    context = state.get("context", "")

    messages = [
        SystemMessage(content=f"""{spec_cfg.system_prompt}

CONTEXT:
{context}

PRIMARY AGENT RESPONSE (insufficient confidence — you are providing deeper analysis):
{state.get("primary_response", "")}

Provide a more detailed, evidence-graded specialist response with full citations."""),
        HumanMessage(content=query),
    ]

    resp = llm.invoke(messages)
    spec_response = resp.content if hasattr(resp, "content") else str(resp)

    return {**state,
            "specialist_response": spec_response,
            "escalated_to":        spec_id,
            "processing_steps":    state.get("processing_steps", []) + ["specialist_agent"]}


# ── Node: human escalation ────────────────────────────────────────────────
def human_escalation_node(state: PRISMState) -> PRISMState:
    agent_id  = state["agent_id"]
    agent_cfg = AGENTS.get(agent_id)
    human_id  = agent_cfg.human_id if agent_cfg else f"{agent_id}-H"
    human_cfg = AGENTS.get(human_id)

    if not human_cfg:
        return {**state, "human_response": state.get("primary_response", ""),
                "escalated_to": "human_coordinator"}

    llm = _get_llm(human_cfg.temperature)
    query = state.get("english_message", state["user_message"])

    messages = [
        SystemMessage(content=f"""{human_cfg.system_prompt}

The patient appears to be experiencing emotional distress (frustration score: {state.get("frustration", 0)}).
Prioritise empathy, validation, and practical support over clinical detail.
Acknowledge their feelings before providing any information."""),
        HumanMessage(content=query),
    ]

    resp = llm.invoke(messages)
    human_response = resp.content if hasattr(resp, "content") else str(resp)

    return {**state,
            "human_response": human_response,
            "escalated_to":   human_id,
            "processing_steps": state.get("processing_steps", []) + ["human_escalation"]}


# ── Node: format response ─────────────────────────────────────────────────
def format_response_node(state: PRISMState) -> PRISMState:
    # Choose the best response based on routing
    if state.get("needs_human") and state.get("human_response"):
        core = state["human_response"]
    elif state.get("needs_specialist") and state.get("specialist_response"):
        core = state["specialist_response"]
    else:
        core = state.get("primary_response", "I'm unable to process your request at this time.")

    # Append citations if not already present
    citations = state.get("citations", [])
    if citations and "References:" not in core and "Citations:" not in core:
        cite_block = "\n\n**References:**\n"
        for i, c in enumerate(citations[:5], 1):
            cite_block += f"{i}. {c.get('source', 'PRISM Knowledge Base')}"
            if c.get("year"): cite_block += f" ({c['year']})"
            if c.get("evidence_grade"): cite_block += f" [Grade {c['evidence_grade']}]"
            cite_block += "\n"
        core = core + cite_block

    # RAGAS heuristic scoring
    ragas = quality_scorer.score_heuristic(
        query=state.get("english_message", state["user_message"]),
        response=core,
        chunks=state.get("retrieved_chunks", []),
    )

    return {**state,
            "final_response": core,
            "ragas_scores":   ragas,
            "processing_steps": state.get("processing_steps", []) + ["format_response"]}


# ── Node: translate response ──────────────────────────────────────────────
def translate_response_node(state: PRISMState) -> PRISMState:
    lang     = state.get("detected_lang", "en")
    response = state.get("final_response", "")
    if lang != "en":
        try:
            response = ml_translate_response(response, lang)
        except Exception:
            pass
    return {**state,
            "translated_response": response,
            "processing_steps":    state.get("processing_steps", []) + ["translate_response"]}


# ── Routing edges ─────────────────────────────────────────────────────────
def route_after_confidence(state: PRISMState) -> str:
    if state.get("needs_human"):
        return "human_escalation"
    if state.get("needs_specialist"):
        return "specialist_agent"
    return "format_response"


def route_after_specialist(state: PRISMState) -> str:
    if state.get("needs_human"):
        return "human_escalation"
    return "format_response"


# ── Build graph ────────────────────────────────────────────────────────────
def build_prism_graph() -> StateGraph:
    g = StateGraph(PRISMState)

    g.add_node("detect_language",   detect_language_node)
    g.add_node("translate_to_en",   translate_to_english_node)
    g.add_node("retrieve_context",  retrieve_context_node)
    g.add_node("primary_agent",     primary_agent_node)
    g.add_node("score_confidence",  score_confidence_node)
    g.add_node("specialist_agent",  specialist_agent_node)
    g.add_node("human_escalation",  human_escalation_node)
    g.add_node("format_response",   format_response_node)
    g.add_node("translate_response",translate_response_node)

    g.set_entry_point("detect_language")
    g.add_edge("detect_language",    "translate_to_en")
    g.add_edge("translate_to_en",    "retrieve_context")
    g.add_edge("retrieve_context",   "primary_agent")
    g.add_edge("primary_agent",      "score_confidence")
    g.add_conditional_edges("score_confidence", route_after_confidence, {
        "specialist_agent": "specialist_agent",
        "human_escalation": "human_escalation",
        "format_response":  "format_response",
    })
    g.add_conditional_edges("specialist_agent", route_after_specialist, {
        "human_escalation": "human_escalation",
        "format_response":  "format_response",
    })
    g.add_edge("human_escalation",   "format_response")
    g.add_edge("format_response",    "translate_response")
    g.add_edge("translate_response", END)

    return g.compile()


# ── Orchestrator ──────────────────────────────────────────────────────────
class PRISMOrchestrator:
    def __init__(self):
        self.graph = build_prism_graph()

    async def chat(
        self,
        user_id:        str,
        conversation_id: str,
        agent_id:        str,
        message:         str,
        language:        str = "en",
        history:         List[Dict] = None,
        multimodal_data: Optional[Dict] = None,
    ) -> Dict:
        history = history or []
        lc_msgs = []
        for h in history[-settings.max_chat_history:]:
            if h["role"] == "user":
                lc_msgs.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant":
                lc_msgs.append(AIMessage(content=h["content"]))

        initial: PRISMState = {
            "user_id":         user_id,
            "conversation_id": conversation_id,
            "agent_id":        agent_id,
            "user_message":    message,
            "language":        language,
            "multimodal_data": multimodal_data,
            "detected_lang":   language,
            "english_message": message,
            "retrieved_chunks": [],
            "context":          "",
            "primary_response": "",
            "specialist_response": "",
            "human_response":   "",
            "final_response":   "",
            "translated_response": "",
            "confidence":       0.0,
            "frustration":      0,
            "ragas_scores":     {},
            "citations":        [],
            "needs_specialist": False,
            "needs_human":      False,
            "escalated_to":     "none",
            "processing_steps": [],
            "latency_ms":       0,
            "messages":         lc_msgs,
        }

        result = await self.graph.ainvoke(initial)

        return {
            "response":         result.get("translated_response") or result.get("final_response", ""),
            "confidence":       result.get("confidence", 0.0),
            "frustration":      result.get("frustration", 0),
            "trigger_log":      result.get("trigger_log", []),
            "escalated_to":     result.get("escalated_to", "none"),
            "citations":        result.get("citations", []),
            "ragas_scores":     result.get("ragas_scores", {}),
            "retrieved_chunks": result.get("retrieved_chunks", []),
            "detected_lang":    result.get("detected_lang", "en"),
            "processing_steps": result.get("processing_steps", []),
            "latency_ms":       result.get("latency_ms", 0),
            "agent_id":         agent_id,
        }


# ── Helpers ───────────────────────────────────────────────────────────────
def _extract_citations(response: str, chunks: List[Dict]) -> List[Dict]:
    citations = []
    seen = set()
    for c in chunks:
        meta = c.get("metadata", {})
        src  = meta.get("source", "PRISM Knowledge Base")
        if src not in seen:
            seen.add(src)
            citations.append({
                "source": src,
                "year":   meta.get("year"),
                "evidence_grade": meta.get("evidence_grade"),
                "url":    meta.get("source_url"),
            })
    return citations[:5]


def _compute_confidence(query: str, response: str, chunks: List[Dict]) -> float:
    if not chunks:
        return 0.45
    # Keyword overlap between query and retrieved chunks
    q_words = set(query.lower().split())
    chunk_words = set()
    for c in chunks:
        chunk_words.update(c["text"].lower().split())
    overlap = len(q_words & chunk_words) / max(len(q_words), 1)
    # Response length heuristic
    resp_len = min(len(response.split()) / 100, 1.0)
    # Avg retrieval score
    avg_score = sum(c.get("rerank_score", c.get("score", 0.5)) for c in chunks) / max(len(chunks), 1)
    conf = (overlap * 0.3 + resp_len * 0.2 + avg_score * 0.5)
    return round(min(max(conf, 0.1), 1.0), 3)


def _compute_frustration(message: str, history: List) -> Tuple[int, List[str]]:
    frustration_signals = [
        "frustrated","angry","useless","terrible","worst","hopeless","give up",
        "doesn't work","not helpful","waste","tired of","fed up","sick of",
        "cansado","frustrado","inútil","horrible","rendirse","harto",
        "rubbish", "ridiculous", "are you mad", "stupid", "dumb", "idiot",
        "wrong information", "lying", "basura", "ridículo", "estás loco"
    ]
    score = 0
    triggers = []
    msg_l = message.lower()

    # Keyword check
    keywords_found = []
    for sig in frustration_signals:
        if sig in msg_l:
            score += 25
            keywords_found.append(sig)

    if keywords_found:
        triggers.append(f"Frustration keywords detected: '{', '.join(keywords_found[:3])}'")

    # Repetition check: if same/similar question in history
    if len(history) >= 4:
        last_msgs = [m.content.lower() for m in history if hasattr(m, "content")][-3:]
        if len(set(last_msgs)) < len(last_msgs):
            score += 30
            triggers.append("Repeated concern — same issue stated multiple times")

    # Explicit request for human
    human_req = ["speak to human", "real doctor", "human agent", "talk to someone", "persona real"]
    for hr in human_req:
        if hr in msg_l:
            score += 50
            triggers.append("Explicit request: 'speak to a REAL person'")

    return min(score, 100), triggers


# Shared singleton
_orchestrator: Optional[PRISMOrchestrator] = None

def get_orchestrator() -> PRISMOrchestrator:
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = PRISMOrchestrator()
    return _orchestrator
