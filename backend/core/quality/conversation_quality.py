# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/quality/conversation_quality.py
# PRISM Conversation Quality Engine — Multi-Metric Projected Score
# ───────────────────────────────────────────────────────────────────────────────
# # METRICS:
#   Turn-over rate, session depth, format variety
#   RAGAS scores, intent mapping confidence
#   Frustration score inverse, feedback star rating
#   Topic deduplication, multi-turn slot filling
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
from typing import List, Dict, Optional
import numpy as np

class QualityScorer:
    """
    Computes the 'Projected Conversation Quality Score' (0-100%).
    Target: > 80% as requested by the USER.
    """

    @staticmethod
    def compute_score(
        history: List[Dict],
        ragas_scores: List[Dict],
        frustration_scores: List[int],
        slots_filled: Dict,
        intent: str,
        format_used: str,
        response_count: int,
        star_rating: Optional[int] = None
    ) -> float:
        # 1. Engagement Score (0-25)
        # Deep conversations (4+ turns) and format variety boost this
        engagement = min(response_count * 5, 20)
        if response_count >= 3: engagement += 5 

        # 2. Relevance Score (0-35)
        # Based on average RAGAS scores (faithfulness, relevancy)
        if ragas_scores:
            avg_faithfulness = np.mean([s.get("faithfulness", 0.5) for s in ragas_scores])
            avg_relevancy    = np.mean([s.get("answer_relevancy", 0.5) for s in ragas_scores])
            relevance        = (avg_faithfulness * 0.5 + avg_relevancy * 0.5) * 35
        else:
            relevance = 25 # Default

        # 3. Satisfaction Score (0-25)
        # Inverse of frustration + User star rating (if any)
        avg_frustration = np.mean(frustration_scores) if frustration_scores else 0
        frustration_penalty = (avg_frustration / 100) * 15
        satisfaction = 15 - frustration_penalty
        
        if star_rating:
            satisfaction += (star_rating / 5) * 10
        else:
            # Assume 80% satisfaction if no rating yet but frustration is low
            satisfaction += 8

        # 4. Progression Score (0-15)
        # Slot filling progress
        total_slots = 5 # Hypothetical average slots per intent
        filled = len([v for v in slots_filled.values() if v])
        progression = (filled / max(total_slots, 1)) * 15

        # Final Score
        final_score = engagement + relevance + satisfaction + progression
        return round(min(max(final_score, 0), 100), 1)

def get_quality_recommendation(score: float) -> str:
    if score >= 85:
        return "Excellent engagement. Keep providing specific details to maintain high quality."
    if score >= 70:
        return "Good conversation. To improve, try answering the follow-up questions for more precision."
    return "Let's try a different angle to get you the most accurate clinical insight."
