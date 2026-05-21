# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/conversation/chip_deduplication.py
# PRISM Chip Deduplication — Semantic Similarity Anti-Repetition
# ───────────────────────────────────────────────────────────────────────────────
# PROBLEM SOLVED:
#   • "What's most worrying you?" shown at turn 7 AND turn 13 (exact repeat)
#   • "Distraction, breathing?" shown at turns 10 AND 12
#   • Patient typing chips back → AI shows same chips again
#   • Chips semantically similar to patient's own messages still appear
#
# APPROACH:
#   1. TF-IDF style token overlap for fast pre-filter (no ML needed)
#   2. LLM-based semantic judgment only for borderline cases (0.55–0.80)
#   3. Track shown chips + patient messages in ConversationMemory
#   4. Dynamic chip count: 4-5 early, 2-3 later
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import re
import math
from typing import Dict, List, Optional, Set, Tuple


# ─── Similarity thresholds ─────────────────────────────────────────────────────
EXACT_REPEAT_THRESHOLD     = 0.92   # Above this → definite duplicate, skip
SEMANTIC_SIMILAR_THRESHOLD = 0.72   # Above this → likely duplicate, skip
SAFE_THRESHOLD             = 0.45   # Below this → definitely different, keep

# ─── Chip count rules ──────────────────────────────────────────────────────────
CHIP_COUNT_RULES = {
    0: 5,   # Turn 0 (first response): show 5 chips
    1: 5,   # Turn 1: show 5
    2: 4,   # Turn 2: show 4
    3: 4,   # Turn 3: show 4
    4: 3,   # Turn 4+: show 3
    6: 3,   # Turn 6+: show 3
    9: 2,   # Turn 9+ with rich context: show 2
}

# ─── Stop words for TF-IDF ────────────────────────────────────────────────────
STOP_WORDS = {
    "the", "a", "an", "in", "on", "at", "of", "for", "to", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "do",
    "does", "did", "will", "would", "could", "should", "may", "might",
    "can", "this", "that", "these", "those", "it", "its", "or", "and",
    "but", "if", "so", "as", "with", "from", "by", "up", "about", "your",
    "you", "me", "my", "i", "we", "us", "our", "they", "them", "their",
    "he", "she", "him", "her", "what", "how", "when", "where", "why",
    "which", "who", "any", "all", "more", "most", "some", "such", "than",
    "then", "there", "also", "just", "like", "even", "still", "again",
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — TEXT TOKENISATION
# ═══════════════════════════════════════════════════════════════════════════════

def tokenise(text: str) -> List[str]:
    """Lowercase, strip punctuation, remove stop words, return meaningful tokens."""
    tokens = re.findall(r'\b[a-z]{3,}\b', text.lower())
    return [t for t in tokens if t not in STOP_WORDS]


def ngrams(tokens: List[str], n: int = 2) -> Set[str]:
    """Generate bigrams for richer overlap."""
    return {f"{tokens[i]}_{tokens[i+1]}" for i in range(len(tokens) - 1)} if n == 2 else set(tokens)


def tf_idf_similarity(text_a: str, text_b: str) -> float:
    """
    Fast token-overlap similarity score between two texts.
    Combines unigram Jaccard + bigram overlap bonus.
    Returns 0.0 to 1.0.
    """
    tok_a = tokenise(text_a)
    tok_b = tokenise(text_b)

    if not tok_a or not tok_b:
        return 0.0

    # Unigram Jaccard
    set_a = set(tok_a)
    set_b = set(tok_b)
    intersection = set_a & set_b
    union        = set_a | set_b
    unigram_sim  = len(intersection) / max(len(union), 1)

    # Bigram overlap bonus
    bi_a = ngrams(tok_a, 2)
    bi_b = ngrams(tok_b, 2)
    if bi_a and bi_b:
        bi_sim    = len(bi_a & bi_b) / max(len(bi_a | bi_b), 1)
        bigram_bonus = bi_sim * 0.3
    else:
        bigram_bonus = 0.0

    return min(unigram_sim + bigram_bonus, 1.0)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — LLM SEMANTIC JUDGE (for borderline cases only)
# ═══════════════════════════════════════════════════════════════════════════════

def llm_semantic_check(question_a: str, question_b: str) -> float:
    """
    Use Claude to judge semantic similarity between two questions.
    Only called when TF-IDF is in the borderline range (0.45–0.72).
    Returns 0.0 (completely different) to 1.0 (same question).
    """
    try:
        from backend.core.agents.base_agent import call_llm_sync

        result = call_llm_sync(
            system_prompt=(
                "You are a semantic similarity judge. Compare two questions and return "
                "ONLY a decimal number from 0.0 to 1.0 representing semantic similarity.\n"
                "0.0 = completely different topics\n"
                "0.5 = related but distinct questions\n"
                "0.9 = same question in different words\n"
                "1.0 = identical meaning\n"
                "Return ONLY the number, nothing else."
            ),
            user_message=f'Question A: "{question_a}"\nQuestion B: "{question_b}"',
            history=[],
            temperature=0.0,
            max_tokens=10,
        )
        return float(result["response"].strip())
    except (ValueError, Exception):
        # If LLM fails or returns non-numeric, fall back to TF-IDF score
        return tf_idf_similarity(question_a, question_b)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — SIMILARITY COMPUTATION (fast + accurate)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_similarity(text_a: str, text_b: str, use_llm_for_borderline: bool = True) -> float:
    """
    Two-stage similarity: TF-IDF first, LLM only for borderline cases.
    This keeps API calls minimal — the LLM is called rarely.
    """
    fast_score = tf_idf_similarity(text_a, text_b)

    # Clear non-duplicate
    if fast_score < SAFE_THRESHOLD:
        return fast_score

    # Clear duplicate
    if fast_score >= EXACT_REPEAT_THRESHOLD:
        return fast_score

    # Borderline — use LLM judge
    if use_llm_for_borderline:
        llm_score = llm_semantic_check(text_a, text_b)
        # Weighted blend (TF-IDF + LLM)
        return fast_score * 0.35 + llm_score * 0.65

    return fast_score


def is_semantically_duplicate(
    candidate:       str,
    reference_texts: List[str],
    threshold:       float = SEMANTIC_SIMILAR_THRESHOLD,
    use_llm:         bool  = True,
) -> Tuple[bool, float, Optional[str]]:
    """
    Check if `candidate` is semantically similar to any text in `reference_texts`.

    Returns:
        (is_duplicate, max_similarity_score, most_similar_text)
    """
    if not reference_texts:
        return False, 0.0, None

    max_score   = 0.0
    most_similar = None

    for ref in reference_texts:
        score = compute_similarity(candidate, ref, use_llm_for_borderline=use_llm)
        if score > max_score:
            max_score    = score
            most_similar = ref

    return max_score >= threshold, max_score, most_similar


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — CHIP POOL DEDUPLICATION
# ═══════════════════════════════════════════════════════════════════════════════

def deduplicate_chips(
    candidate_chips:      List[str],
    shown_chips:          List[str],       # Previously shown to this patient
    patient_messages:     List[str],       # Patient's own messages (chips they typed back)
    slots_filled:         Dict,            # Context slots already answered
    intent:               str,
    conversation_turn:    int,
) -> List[str]:
    """
    Filter `candidate_chips` to produce a deduplicated, sized final list.

    Rules:
    1. Remove candidates too similar to any previously shown chip (threshold 0.72)
    2. Remove candidates too similar to any patient message (threshold 0.85)
       — this catches "chip echoes" where patient typed the chip back
    3. Remove candidates whose slot is already filled
    4. Cap at the turn-appropriate count
    5. Return minimum 2 (if fewer available, include closest non-duplicate)
    """
    # Build reference corpus
    all_references = shown_chips + patient_messages
    reference_lower = [r.lower().strip() for r in all_references]

    # Determine slots already answered (use slot name keywords)
    answered_keywords = set()
    for slot, value in (slots_filled or {}).items():
        if value:
            answered_keywords.update(slot.lower().replace("_", " ").split())

    # Filter each candidate
    survivors = []
    skipped   = []

    for chip in candidate_chips:
        chip_lower = chip.lower().strip()

        # Rule 1+2: semantic similarity to references
        is_dup, score, similar_to = is_semantically_duplicate(
            chip, all_references,
            threshold=SEMANTIC_SIMILAR_THRESHOLD,
            use_llm=True,
        )
        if is_dup:
            skipped.append({"chip": chip, "reason": f"similar({score:.2f}) to '{similar_to[:40]}'"})
            continue

        # Rule 3: slot already answered
        chip_tokens = set(tokenise(chip))
        if answered_keywords and len(chip_tokens & answered_keywords) >= 2:
            skipped.append({"chip": chip, "reason": "slot already answered"})
            continue

        survivors.append(chip)

    # Determine target count
    target_count = _get_chip_count(conversation_turn, slots_filled)

    # Ensure minimum 2 (relax threshold if needed)
    if len(survivors) < 2 and candidate_chips:
        # Re-add least-similar chips from skipped to meet minimum
        skipped_chips = [s["chip"] for s in skipped]
        if skipped_chips:
            # Sort skipped chips by similarity to references (ascending)
            # and pick the ones that are least similar
            skipped_chips.sort(key=lambda c: compute_similarity(c, " ".join(all_references[-10:]), use_llm_for_borderline=False))
            
            for best_candidate in skipped_chips:
                if best_candidate not in survivors:
                    survivors.append(best_candidate)
                if len(survivors) >= 2:
                    break

    return survivors[:target_count]


def _get_chip_count(conversation_turn: int, slots_filled: Dict) -> int:
    """
    Determine how many chips to show based on conversation turn and context richness.
    """
    filled_count = sum(1 for v in (slots_filled or {}).values() if v)

    # Override: very rich context → fewer chips
    if filled_count >= 4 and conversation_turn >= 6:
        return 2

    # Turn-based rules
    for threshold in sorted(CHIP_COUNT_RULES.keys(), reverse=True):
        if conversation_turn >= threshold:
            return CHIP_COUNT_RULES[threshold]

    return 4  # Default


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — PATIENT MESSAGE CHIP DETECTION
# Detects when patient types back one of the suggested chips
# ═══════════════════════════════════════════════════════════════════════════════

def detect_chip_echo(
    patient_message:  str,
    shown_chips:      List[str],
    threshold:        float = 0.85,
) -> Optional[str]:
    """
    Returns the matching chip if the patient's message is a chip echo,
    or None if it's a genuinely new message.

    This is used to:
    1. Mark that chip as definitively "used" (never show again)
    2. Track it as a patient message for future deduplication
    """
    if not shown_chips or len(patient_message.strip()) < 5:
        return None

    is_echo, score, matching_chip = is_semantically_duplicate(
        patient_message, shown_chips,
        threshold=threshold,
        use_llm=False,   # Fast TF-IDF only for real-time detection
    )

    return matching_chip if is_echo else None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — INTEGRATION HELPER (called from main.py chat endpoint)
# ═══════════════════════════════════════════════════════════════════════════════

def process_chips_for_response(
    candidate_chips:    List[str],
    conversation_memory_dict: Dict,    # ConversationMemory.to_dict()
    patient_message:    str,
    conversation_history: List[Dict],
    slots_filled:       Dict,
    intent:             str,
) -> Dict:
    """
    Full chip processing pipeline for one response.

    Returns:
        final_chips:       List[str]  — deduplicated chips to show
        chip_echo_detected: bool      — True if patient typed back a chip
        echoed_chip:       Optional[str]
        updated_shown_chips: List[str] — for saving back to memory
    """
    # Extract tracking data from memory
    shown_chips   = conversation_memory_dict.get("follow_up_asked", [])
    turn_count    = conversation_memory_dict.get("response_count", 0)

    # Gather patient messages from history
    patient_messages = [
        m["content"] for m in conversation_history
        if m.get("role") == "user" and m.get("content")
    ]
    # Add current message
    patient_messages.append(patient_message)

    # Detect if current patient message is a chip echo
    echoed = detect_chip_echo(patient_message, shown_chips)

    # If echo detected, mark that chip as used (it's now in patient_messages)
    # The deduplication will automatically exclude it

    # Deduplicate and size the chip pool
    final_chips = deduplicate_chips(
        candidate_chips=candidate_chips,
        shown_chips=shown_chips,
        patient_messages=patient_messages,
        slots_filled=slots_filled,
        intent=intent,
        conversation_turn=turn_count,
    )

    # Update shown chips list (add new ones being shown)
    updated_shown = list(shown_chips) + final_chips
    updated_shown = updated_shown[-40:]   # Rolling window of last 40

    return {
        "final_chips":          final_chips,
        "chip_echo_detected":   echoed is not None,
        "echoed_chip":          echoed,
        "updated_shown_chips":  updated_shown,
        "chip_count":           len(final_chips),
        "candidates_dropped":   len(candidate_chips) - len(final_chips),
    }