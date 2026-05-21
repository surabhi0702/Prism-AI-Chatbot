import re
from typing import Dict, List, Optional
from datetime import datetime

# ─── Frustration Thresholds ───────────────────────────────────────────────────
EMPATHY_THRESHOLD = 40    # Above this → pivot to empathetic suggestions
HUMAN_THRESHOLD   = 75    # Above this → escalate to human coordinator

# ─── Frustration Keywords (multi-language) ────────────────────────────────────
FRUSTRATION_KEYWORDS: Dict[str, int] = {
    "rubbish": 30, "ridiculous": 30, "useless": 30, "hopeless": 30,
    "garbage": 30, "terrible": 30, "awful": 30, "pathetic": 30,
    "are you mad": 35, "are you stupid": 35, "this is nonsense": 35,
    "complete waste": 35, "total failure": 35, "i give up": 30,
    "not helpful": 25, "waste of time": 25, "fed up": 25,
    "doesn't work": 20, "not working": 20, "keeps failing": 20,
    "already told you": 25, "told you before": 25, "said this already": 25,
    "how many times": 25, "again and again": 20,
    "speak to a real doctor": 40, "i need a real person": 40,
    "connect me to a human": 40, "talk to a person": 40,
    "need a real human": 40, "real doctor please": 40,
    "this is not helping": 25, "you are not helping": 25,
    "i am angry": 30, "very frustrated": 30, "so frustrated": 30,
    "unacceptable": 30, "disgusting": 30, "outrageous": 30,
    # Spanish
    "ridículo": 30, "inútil": 30, "basura": 30, "horrible": 30,
    "estás loco": 35, "no sirves": 30, "me tienes harto": 30,
    "esto no funciona": 20, "quiero un médico real": 40,
    "hablar con un humano": 40, "necesito una persona real": 40,
    "que desperdicio": 25, "ya te dije": 25, "cuántas veces": 25,
    # Hindi
    "bakwaas": 30, "bekar": 30, "faltu": 30, "pagal ho": 35,
    "asli doctor chahiye": 40, "insaan se baat": 40,
}

HUMAN_REQUEST_PHRASES = [
    "speak to a real doctor", "talk to a real doctor", "i need a real person",
    "connect me to a human", "talk to a person", "need a real human",
    "real doctor please", "quiero un médico real", "hablar con un humano",
    "asli doctor chahiye", "preciso de um médico de verdade", "falar com humano",
    "transfer me", "escalate", "supervisor", "want a human",
]

class FrustrationDetector:
    """
    Real-time frustration scoring engine shared across routing and response generation.
    """
    def __init__(self):
        self.keyword_pattern = re.compile(
            '|'.join(re.escape(kw) for kw in FRUSTRATION_KEYWORDS.keys()),
            re.IGNORECASE
        )
        self.human_request_pattern = re.compile(
            '|'.join(re.escape(p) for p in HUMAN_REQUEST_PHRASES),
            re.IGNORECASE
        )

    def compute(
        self,
        message: str,
        conversation_history: List[Dict],
        agent_uncertainty_count: int = 0,
        has_emergency_symptom: bool = False,
    ) -> Dict:
        score = 0
        triggers = []
        trigger_codes = []
        msg_lower = message.lower()

        # Signal 1: Keywords
        found_keywords = []
        for kw, pts in FRUSTRATION_KEYWORDS.items():
            if kw in msg_lower:
                found_keywords.append(f"'{kw}'")
                score += pts
        if found_keywords:
            triggers.append(f"Frustration keywords: {', '.join(found_keywords[:3])}")
            trigger_codes.append("KEYWORD")

        # Signal 2: Human Request
        if self.human_request_pattern.search(msg_lower):
            score = max(score, 80)
            triggers.append("Explicit request: 'speak to a REAL doctor'")
            trigger_codes.append("HUMAN_REQUEST")

        # Signal 3: Repetition
        recent_user_msgs = [
            m["content"].lower()
            for m in conversation_history[-6:]
            if isinstance(m, dict) and m.get("role") == "user"
        ]
        if len(recent_user_msgs) >= 2:
            for i in range(len(recent_user_msgs) - 1):
                words_a = set(recent_user_msgs[i].split())
                words_b = set(recent_user_msgs[-1].split())
                if len(words_a) > 3 and len(words_b) > 3:
                    overlap = len(words_a & words_b) / max(len(words_a | words_b), 1)
                    if overlap > 0.55:
                        score += 25
                        triggers.append("Repeated concern detected")
                        trigger_codes.append("REPEATED")
                        break

        # Signal 4: Agent uncertainty
        if agent_uncertainty_count >= 2:
            score += 20
            triggers.append("Agent uncertainty")
            trigger_codes.append("UNCERTAIN")

        score = min(score, 100)

        return {
            "score":         score,
            "triggers":      triggers,
            "trigger_codes": trigger_codes,
            "needs_human":   score >= HUMAN_THRESHOLD,
            "is_frustrated": score >= EMPATHY_THRESHOLD,
            "has_emergency": has_emergency_symptom,
            "timestamp":     datetime.utcnow().isoformat(),
        }
