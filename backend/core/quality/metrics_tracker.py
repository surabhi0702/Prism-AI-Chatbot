# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/quality/metrics_tracker.py
# PRISM Metrics Tracker — captures ALL events from patient chat into DB
# ───────────────────────────────────────────────────────────────────────────────
# ROOT CAUSE FIX:
#   Admin portal shows zeros because events are computed but never written.
#   This module is the single point of truth — every chat message MUST call
#   MetricsTracker.record_response() before db.commit().
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import uuid, json
from datetime import datetime
from typing import Dict, List, Optional


# ─── All DB models used ────────────────────────────────────────────────────────
# Import lazily inside functions to avoid circular imports at module level


class MetricsTracker:
    """
    Called once per AI response turn.
    Writes rows to: ragas_metrics, system_alerts (escalations/LLM calls),
    image_uploads tracking, and updates conversation state.
    """

    def __init__(self, db):
        self.db = db

    # ══════════════════════════════════════════════════════════════════════════
    # 1. RAGAS + CONFIDENCE + FRUSTRATION → ragas_metrics table
    # ══════════════════════════════════════════════════════════════════════════

    async def record_ragas(
        self,
        message_id:      str,
        conversation_id: str,
        agent_id:        str,
        disease_code:    str,
        ragas_scores:    Dict,
        confidence:      float,
        frustration:     int,
        processing_ms:   int,
    ) -> None:
        from backend.database.models import RAGASMetric

        row = RAGASMetric(
            id=str(uuid.uuid4()),
            message_id=message_id,
            conversation_id=conversation_id,
            agent_id=agent_id.upper(),
            disease_code=(disease_code or "").upper(),
            
            # Retrieval
            context_precision=ragas_scores.get("context_precision", 0.0),
            context_recall=ragas_scores.get("context_recall", 0.0),
            answer_relevancy=ragas_scores.get("answer_relevancy", 0.0),
            utilization=ragas_scores.get("utilization", 0.0),
            
            # Generation
            faithfulness=ragas_scores.get("faithfulness", 0.0),
            answer_similarity=ragas_scores.get("answer_similarity", 0.0),
            answer_correctness=ragas_scores.get("answer_correctness", 0.0),
            retrieval_relevancy=ragas_scores.get("retrieval_relevancy", 0.0),
            
            # Efficiency & Accuracy
            entity_recall=ragas_scores.get("entity_recall", 0.0),
            noise_sensitivity=ragas_scores.get("noise_sensitivity", 0.0),
            conciseness=ragas_scores.get("conciseness", 0.0),
            token_efficiency=ragas_scores.get("token_efficiency", 0.0),
            overall_score=ragas_scores.get("overall", 0.0),
            failure_rate=ragas_scores.get("failure_rate", 0.0),
            critique_depth=ragas_scores.get("critique_depth", 0.0),
            coherence=ragas_scores.get("coherence", 0.0),
            
            # Safety
            harmlessness=ragas_scores.get("harmlessness", 0.0),
            refusal_precision=ragas_scores.get("refusal_precision", 0.0),
            disclaimer_compliance=ragas_scores.get("disclaimer_compliance", 0.0),
            safe_messaging=ragas_scores.get("safe_messaging", 0.0),
            
            # Linguistic
            bert_score=ragas_scores.get("bert_score", 0.0),
            bleu_score=ragas_scores.get("bleu_score", 0.0),
            rouge_score=ragas_scores.get("rouge_score", 0.0),
            meteor_score=ragas_scores.get("meteor_score", 0.0),
            mrr_score=ragas_scores.get("mrr_score", 0.0),
            perplexity=ragas_scores.get("perplexity", 0.0),

            confidence=confidence,
            frustration=frustration,
            processing_ms=processing_ms,
            created_at=datetime.utcnow(),
        )
        self.db.add(row)

    # ══════════════════════════════════════════════════════════════════════════
    # 2. LLM CALL → system_alerts (component="llm_call")
    # ══════════════════════════════════════════════════════════════════════════

    async def record_llm_call(
        self,
        agent_id:        str,
        conversation_id: str,
        model:           str,
        prompt_tokens:   int,
        completion_tokens: int,
        processing_ms:   int,
        route:           str,   # "primary" | "specialist" | "human"
        disease_code:    str,
    ) -> None:
        from backend.database.models import SystemAlert

        self.db.add(SystemAlert(
            id=str(uuid.uuid4()),
            level="info",
            title=f"LLM call: {agent_id} [{route}]",
            message=json.dumps({
                "agent_id":          agent_id,
                "conversation_id":   conversation_id,
                "model":             model,
                "prompt_tokens":     prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens":      prompt_tokens + completion_tokens,
                "processing_ms":     processing_ms,
                "route":             route,
                "disease_code":      disease_code,
            }),
            component="llm_call",
            created_at=datetime.utcnow(),
        ))

    # ══════════════════════════════════════════════════════════════════════════
    # 3. ESCALATION → system_alerts (component="escalation")
    # ══════════════════════════════════════════════════════════════════════════

    async def record_escalation(
        self,
        agent_id:        str,
        conversation_id: str,
        user_id:         str,
        escalation_type: str,   # "specialist" | "human"
        reason:          str,
        confidence:      float,
        frustration:     int,
        disease_code:    str,
    ) -> None:
        from backend.database.models import SystemAlert

        level = "warning" if escalation_type == "specialist" else "critical"

        self.db.add(SystemAlert(
            id=str(uuid.uuid4()),
            level=level,
            title=f"Escalation: {agent_id} → {escalation_type}",
            message=json.dumps({
                "agent_id":        agent_id,
                "conversation_id": conversation_id,
                "user_id":         user_id,
                "type":            escalation_type,
                "reason":          reason,
                "confidence":      confidence,
                "frustration":     frustration,
                "disease_code":    disease_code,
            }),
            component=f"agent:{agent_id}",
            created_at=datetime.utcnow(),
        ))

    # ══════════════════════════════════════════════════════════════════════════
    # 4. RESPONSIBLE AI GUARDRAIL EVENT
    # ══════════════════════════════════════════════════════════════════════════

    async def record_guardrail(
        self,
        agent_id:        str,
        conversation_id: str,
        user_id:         str,
        guardrail_type:  str,   # "medical_validation" | "agent_mismatch" | "non_medical_image" etc.
        triggered:       bool,
        details:         str,
        disease_code:    str,
    ) -> None:
        from backend.database.models import SystemAlert

        if not triggered:
            return   # Only record actual guardrail events

        self.db.add(SystemAlert(
            id=str(uuid.uuid4()),
            level="warning",
            title=f"Guardrail: {guardrail_type}",
            message=json.dumps({
                "agent_id":        agent_id,
                "conversation_id": conversation_id,
                "user_id":         user_id,
                "type":            guardrail_type,
                "details":         details,
                "disease_code":    disease_code,
            }),
            component=f"guardrail:{guardrail_type}",
            created_at=datetime.utcnow(),
        ))

    # ══════════════════════════════════════════════════════════════════════════
    # MAIN: one call per AI response — writes everything in one pass
    # ══════════════════════════════════════════════════════════════════════════

    async def record_response(
        self,
        message_id:        str,
        conversation_id:   str,
        user_id:           str,
        agent_id:          str,
        disease_code:      str,
        ragas_scores:      Dict,
        confidence:        float,
        frustration:       int,
        processing_ms:     int,
        route_decision:    str,
        escalation_active: bool,
        escalation_reason: str,
        llm_calls:         Optional[List[Dict]] = None,
    ) -> None:
        """
        Single entry point. Call this once after every AI response.
        Writes RAGAS row + LLM call row(s) + escalation row (if active).
        All writes are batched — caller does db.commit() once.
        """
        # 1. RAGAS metrics (Faithfulness, Relevancy, Confidence, Frustration etc.)
        await self.record_ragas(
            message_id=message_id,
            conversation_id=conversation_id,
            agent_id=agent_id,
            disease_code=disease_code,
            ragas_scores=ragas_scores,
            confidence=confidence,
            frustration=frustration,
            processing_ms=processing_ms,
        )

        # 2. LLM call tracking (record every call in the chain)
        if llm_calls:
            for call in llm_calls:
                await self.record_llm_call(
                    agent_id=call.get("agent_id", agent_id),
                    conversation_id=conversation_id,
                    model=call.get("model", "unknown"),
                    prompt_tokens=call.get("prompt_tokens", 0),
                    completion_tokens=call.get("completion_tokens", 0),
                    processing_ms=call.get("latency_ms", 0),
                    route=route_decision,
                    disease_code=disease_code,
                )

        # 3. Escalation tracking
        if escalation_active and route_decision in ("specialist", "human"):
            await self.record_escalation(
                agent_id=agent_id,
                conversation_id=conversation_id,
                user_id=user_id,
                escalation_type=route_decision,
                reason=escalation_reason,
                confidence=confidence,
                frustration=frustration,
                disease_code=disease_code,
            )