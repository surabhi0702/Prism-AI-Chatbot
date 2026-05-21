# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/history/chat_history.py
# PRISM Chat History Service — 15-Day Rolling Window per User
# ───────────────────────────────────────────────────────────────────────────────
# FEATURES:
#   • 15-day rolling retention window (auto-purge older conversations)
#   • History grouped by Disease then by Agent
#   • Cross-disease & cross-agent unified timeline view
#   • Conversation title auto-generation from first user message
#   • Smart summary snippet for each conversation card
#   • Background cleanup scheduler (runs daily at 02:00 UTC)
#   • Per-user history statistics
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import re
import asyncio
import difflib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

# ─── Configuration ─────────────────────────────────────────────────────────────
HISTORY_DAYS      = 15       # Retention window in days
SNIPPET_LENGTH    = 120      # Characters for conversation preview snippet
MAX_HISTORY_ITEMS = 200      # Max conversations returned in one history call
TITLE_MAX_WORDS   = 8        # Max words in auto-generated conversation title

# ─── Disease metadata (mirrors frontend) ──────────────────────────────────────
DISEASE_META: Dict[str, Dict] = {
    "CA": {"name": "Cancer Care",         "icon": "🎗", "color": "#7C3AED"},
    "DM": {"name": "Diabetes",            "icon": "🩺", "color": "#2563EB"},
    "CV": {"name": "Cardiovascular",      "icon": "❤️", "color": "#DB2777"},
    "MH": {"name": "Mental Health",       "icon": "🧠", "color": "#059669"},
    "RS": {"name": "Chronic Respiratory", "icon": "🫁", "color": "#D97706"},
}

AGENT_META: Dict[str, Dict] = {
    # Cancer Care
    "CA1": {"name": "Screening & Early Detection",    "icon": "🔬"},
    "CA2": {"name": "Treatment Navigation",           "icon": "💊"},
    "CA3": {"name": "Supportive Care",                "icon": "🌿"},
    "CA4": {"name": "Survivorship",                   "icon": "🌟"},
    "CA5": {"name": "Hereditary Genetics",            "icon": "🧬"},
    "CA6": {"name": "Oncology Navigator",             "icon": "🧭"},
    # Diabetes
    "DM1": {"name": "Glucose Monitoring",             "icon": "📊"},
    "DM2": {"name": "Medication & Insulin",           "icon": "💉"},
    "DM3": {"name": "Nutrition & Lifestyle",          "icon": "🥗"},
    "DM4": {"name": "Complications Prevention",       "icon": "⚠️"},
    "DM5": {"name": "Gestational & Special",          "icon": "🤱"},
    "DM6": {"name": "Diabetes Navigator",             "icon": "🧭"},
    # Cardiovascular
    "CV1": {"name": "Clinical Assessment",            "icon": "❤️"},
    "CV2": {"name": "Cardiac Emergency",              "icon": "🚨"},
    "CV3": {"name": "Medications",                    "icon": "💊"},
    "CV4": {"name": "Cardiac Rehabilitation",         "icon": "🏃"},
    "CV5": {"name": "Cardiac Nutrition",              "icon": "🥗"},
    "CV6": {"name": "Heart Health Compass",           "icon": "🧭"},
    # Mental Health
    "MH1": {"name": "Depression Assessment",          "icon": "🧠"},
    "MH2": {"name": "Anxiety Management",             "icon": "💚"},
    "MH3": {"name": "Sleep & Wellness",               "icon": "🌙"},
    "MH4": {"name": "Trauma & PTSD",                  "icon": "🛡️"},
    "MH5": {"name": "Crisis Prevention",              "icon": "🆘"},
    "MH6": {"name": "Mental Wellness Compass",        "icon": "🧭"},
    # Respiratory
    "RS1": {"name": "Asthma Management",              "icon": "🫁"},
    "RS2": {"name": "COPD Management",                "icon": "🌬️"},
    "RS3": {"name": "Pulmonary Rehabilitation",       "icon": "💨"},
    "RS4": {"name": "Respiratory Medications",        "icon": "💊"},
    "RS5": {"name": "Sleep Apnea",                    "icon": "🌙"},
    "RS6": {"name": "Lung Health Compass",            "icon": "🧭"},
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — TITLE & SNIPPET GENERATORS
# ═══════════════════════════════════════════════════════════════════════════════

def generate_conversation_title(first_user_message: str) -> str:
    """
    Generate a short, readable title from the first user message.
    Strips voice/image markers, truncates to TITLE_MAX_WORDS words.
    """
    # Remove markers like [VOICE], [IMAGE: ...], [VOICE] prefix
    text = re.sub(r'\[VOICE\]\s*', '', first_user_message)
    text = re.sub(r'\[IMAGE:.*?\]\s*', '', text)
    text = text.strip()

    if not text:
        return "New Conversation"

    # Remove question mark at start, clean
    text = text.lstrip("?!.,")
    words = text.split()
    if len(words) <= TITLE_MAX_WORDS:
        return text.rstrip("?") if text.endswith("?") else text

    title = " ".join(words[:TITLE_MAX_WORDS])
    # Don't end on a preposition
    last_word = words[TITLE_MAX_WORDS - 1].lower()
    if last_word in {"the", "a", "an", "in", "on", "at", "of", "for", "with", "about"}:
        title = " ".join(words[:TITLE_MAX_WORDS - 1])
    return title + "…"


def generate_snippet(last_ai_message: str) -> str:
    """Generate a preview snippet from the last AI response."""
    if not last_ai_message:
        return ""
    # Strip markdown
    text = re.sub(r'\*+', '', last_ai_message)
    text = re.sub(r'#+\s+', '', text)
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= SNIPPET_LENGTH:
        return text
    # Cut at word boundary
    truncated = text[:SNIPPET_LENGTH]
    last_space = truncated.rfind(' ')
    return truncated[:last_space] + '…' if last_space > 0 else truncated + '…'


def group_by_topic(cards: List[Dict], threshold: float = 0.82) -> Dict[str, List[Dict]]:
    """
    Group conversation cards by semantic similarity of their titles using SentenceTransformer.
    Returns a dict: { "Topic Label": [cards...] }
    """
    if not cards:
        return {}

    from backend.core.rag.pipeline import get_embedder
    import numpy as np

    try:
        embedder = get_embedder()
        titles = [c["title"].lower().strip() for c in cards]
        # Get embeddings for all titles in one batch for efficiency
        embeddings = embedder.encode(titles, show_progress_bar=False)
    except Exception as e:
        print(f"[HISTORY_GROUPING_ERROR] Fallback to fuzzy matching: {e}")
        # Fallback to character-level similarity if embedding fails
        topics: Dict[str, List[Dict]] = {}
        for card in cards:
            title = card["title"]
            assigned = False
            for topic_label in topics.keys():
                similarity = difflib.SequenceMatcher(None, title.lower(), topic_label.lower()).ratio()
                if similarity >= 0.75:
                    topics[topic_label].append(card)
                    assigned = True
                    break
            if not assigned:
                topics[title.rstrip("…").strip()] = [card]
        return topics

    topics: List[Dict[str, Any]] = [] # List of {label: str, embedding: np.array, cards: list}
    
    for i, card in enumerate(cards):
        emb = embeddings[i]
        title = titles[i]
        assigned = False
        
        for topic in topics:
            # Cosine similarity
            sim = np.dot(emb, topic["embedding"]) / (np.linalg.norm(emb) * np.linalg.norm(topic["embedding"]))
            if sim >= threshold:
                topic["cards"].append(card)
                assigned = True
                break
        
        if not assigned:
            # Clean title for label: remove trailing ellipsis, capitalize
            label = card["title"].rstrip("…").strip()
            topics.append({
                "label": label,
                "embedding": emb,
                "cards": [card]
            })
            
    # Convert back to expected dict format
    return {t["label"]: t["cards"] for t in topics}


def format_topics(grouped_cards: Dict[str, List[Dict]]) -> List[Dict]:
    """
    Helper to format grouped cards into the structured list of topics
    with nested disease/agent information as used by the frontend.
    """
    formatted = []
    for label, topic_cards in grouped_cards.items():
        topic_diseases = {}
        for tc in topic_cards:
            dc = tc.get("disease_code", "GA")
            if dc not in topic_diseases:
                topic_diseases[dc] = {
                    "disease_code": dc,
                    "disease_name": tc.get("disease_name", "General"),
                    "disease_icon": tc.get("disease_icon", "🏥"),
                    "disease_color": tc.get("disease_color", "#6B7280"),
                    "agents": {}
                }
            aid = tc.get("agent_id", "Unknown")
            if aid not in topic_diseases[dc]["agents"]:
                topic_diseases[dc]["agents"][aid] = {
                    "agent_id": aid,
                    "agent_name": tc.get("agent_name", aid),
                    "agent_icon": tc.get("agent_icon", "🤖"),
                    "conversations": []
                }
            topic_diseases[dc]["agents"][aid]["conversations"].append(tc)

        formatted.append({
            "label": label,
            "total_convs": len(topic_cards),
            "last_active": max(c["updated_at"] for c in topic_cards),
            "diseases": topic_diseases
        })
    
    # Sort by most recent activity
    formatted.sort(key=lambda x: x["last_active"], reverse=True)
    return formatted


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — HISTORY QUERIES (async SQLAlchemy)
# ═══════════════════════════════════════════════════════════════════════════════

async def get_user_history_grouped(
    user_id:     str,
    db,                           # AsyncSession
    days:        int = HISTORY_DAYS,
    lang:        str = "en",
) -> Dict:
    """
    Fetch all conversations for a user within the last `days` days.
    Returns data grouped by disease domain, then by agent, plus a
    flat timeline (most recent first) for the unified history view.

    Returns:
        by_disease:  { "DM": { meta, agents: { "DM2": { meta, conversations: [...] } } } }
        by_agent:    { "DM2": { meta, conversations: [...] } }
        timeline:    [ conversation_card, ... ] (most recent first)
        stats:       { total_conversations, total_messages, active_agents, etc. }
    """
    from sqlalchemy import select, func, desc
    from backend.database.models import Conversation, Message

    cutoff = datetime.utcnow() - timedelta(days=days)

    # ── 1. Fetch all conversations in retention window ─────────────────────────
    conv_res = await db.execute(
        select(Conversation)
        .where(
            Conversation.user_id   == user_id,
            Conversation.updated_at >= cutoff,
        )
        .order_by(desc(Conversation.updated_at))
        .limit(MAX_HISTORY_ITEMS)
    )
    conversations = conv_res.scalars().all()

    if not conversations:
        return {
            "by_disease":   {},
            "by_agent":     {},
            "timeline":     [],
            "stats":        _empty_stats(),
            "retention_days": days,
            "cutoff_date":  cutoff.isoformat(),
        }

    conv_ids = [c.id for c in conversations]

    # ── 2. Fetch first & last message per conversation in one query ────────────
    # Get first user message (for title)
    first_msg_res = await db.execute(
        select(Message)
        .where(
            Message.conversation_id.in_(conv_ids),
            Message.role == "user",
        )
        .order_by(Message.conversation_id, Message.created_at)
        .distinct(Message.conversation_id)
    )
    first_msgs = {m.conversation_id: m for m in first_msg_res.scalars().all()}

    # Get last AI message (for snippet)
    last_ai_res = await db.execute(
        select(Message)
        .where(
            Message.conversation_id.in_(conv_ids),
            Message.role == "assistant",
        )
        .order_by(Message.conversation_id, desc(Message.created_at))
        .distinct(Message.conversation_id)
    )
    last_ai_msgs = {m.conversation_id: m for m in last_ai_res.scalars().all()}

    # Get message counts per conversation
    count_res = await db.execute(
        select(
            Message.conversation_id,
            func.count(Message.id).label("total"),
            func.sum(
                func.case((Message.role == "user", 1), else_=0)
            ).label("user_count"),
        )
        .where(Message.conversation_id.in_(conv_ids))
        .group_by(Message.conversation_id)
    )
    msg_counts = {row.conversation_id: row for row in count_res.all()}

    # ── 3. Build conversation cards ────────────────────────────────────────────
    cards = []
    for conv in conversations:
        first_msg   = first_msgs.get(conv.id)
        last_ai_msg = last_ai_msgs.get(conv.id)
        counts      = msg_counts.get(conv.id)

        raw_title   = first_msg.content if first_msg else conv.title or "Conversation"
        title       = generate_conversation_title(raw_title)
        snippet     = generate_snippet(last_ai_msg.content if last_ai_msg else "")

        agent_id    = (conv.agent_id or "").upper()
        disease_code = (conv.disease_code or agent_id[:2] or "").upper()

        agent_info  = AGENT_META.get(agent_id, {"name": agent_id, "icon": "🤖"})
        disease_info = DISEASE_META.get(disease_code, {"name": "General", "icon": "🏥", "color": "#6B7280"})

        # Days ago label
        age_days    = (datetime.utcnow() - conv.updated_at).days
        if age_days == 0:   age_label = "Today"
        elif age_days == 1: age_label = "Yesterday"
        else:               age_label = f"{age_days} days ago"

        cards.append({
            "conversation_id":  conv.id,
            "title":            title,
            "snippet":          snippet,
            "agent_id":         agent_id,
            "agent_name":       agent_info["name"],
            "agent_icon":       agent_info["icon"],
            "disease_code":     disease_code,
            "disease_name":     disease_info["name"],
            "disease_icon":     disease_info["icon"],
            "disease_color":    disease_info["color"],
            "language":         conv.language or "en",
            "total_messages":   counts.total if counts else 0,
            "user_turns":       counts.user_count if counts else 0,
            "escalated":        getattr(conv, "escalated", False),
            "updated_at":       conv.updated_at.isoformat(),
            "created_at":       conv.created_at.isoformat(),
            "age_label":        age_label,
            "age_days":         age_days,
            "expires_in_days":  max(0, days - age_days),
        })

    # ── 4. Group by disease ────────────────────────────────────────────────────
    by_disease: Dict = {}
    for card in cards:
        dc = card["disease_code"]
        if dc not in by_disease:
            di = DISEASE_META.get(dc, {"name": "General", "icon": "🏥", "color": "#6B7280"})
            by_disease[dc] = {
                "disease_code":   dc,
                "disease_name":   di["name"],
                "disease_icon":   di["icon"],
                "disease_color":  di["color"],
                "agents":         {},
                "total_convs":    0,
                "last_active":    None,
            }
        # Group by agent within disease
        aid = card["agent_id"]
        if aid not in by_disease[dc]["agents"]:
            ai = AGENT_META.get(aid, {"name": aid, "icon": "🤖"})
            by_disease[dc]["agents"][aid] = {
                "agent_id":    aid,
                "agent_name":  ai["name"],
                "agent_icon":  ai["icon"],
                "conversations": [],
                "total_convs": 0,
                "last_active": None,
            }
        by_disease[dc]["agents"][aid]["conversations"].append(card)
        by_disease[dc]["agents"][aid]["total_convs"] += 1
        by_disease[dc]["agents"][aid]["last_active"] = card["updated_at"]
        by_disease[dc]["total_convs"] += 1
        if not by_disease[dc]["last_active"] or card["updated_at"] > by_disease[dc]["last_active"]:
            by_disease[dc]["last_active"] = card["updated_at"]

    # ── 5. Group by agent (flat, for quick agent-level access) ─────────────────
    by_agent: Dict = {}
    for card in cards:
        aid = card["agent_id"]
        if aid not in by_agent:
            ai = AGENT_META.get(aid, {"name": aid, "icon": "🤖"})
            by_agent[aid] = {
                "agent_id":      aid,
                "agent_name":    ai["name"],
                "agent_icon":    ai["icon"],
                "disease_code":  card["disease_code"],
                "disease_name":  card["disease_name"],
                "disease_color": card["disease_color"],
                "conversations": [],
                "total_convs":   0,
            }
        by_agent[aid]["conversations"].append(card)
        by_agent[aid]["total_convs"] += 1

    # ── 5b. Group by topic (semantic similarity) ───────────────────────────────
    by_topic_raw = group_by_topic(cards)
    by_topic = format_topics(by_topic_raw)

    # ── 6. Statistics ──────────────────────────────────────────────────────────
    total_messages   = sum(c.get("total_messages", 0) for c in cards)
    active_agents    = list(by_agent.keys())
    active_diseases  = list(by_disease.keys())
    most_used_agent  = max(by_agent, key=lambda a: by_agent[a]["total_convs"], default=None)

    stats = {
        "total_conversations":  len(cards),
        "total_messages":       total_messages,
        "active_agents":        active_agents,
        "active_diseases":      active_diseases,
        "most_used_agent":      most_used_agent,
        "most_used_agent_name": AGENT_META.get(most_used_agent, {}).get("name") if most_used_agent else None,
        "first_interaction":    cards[-1]["created_at"] if cards else None,
        "last_interaction":     cards[0]["updated_at"]  if cards else None,
        "avg_messages_per_conv": round(total_messages / max(len(cards), 1), 1),
    }

    return {
        "by_disease":    by_disease,
        "by_agent":      by_agent,
        "by_topic":      by_topic,
        "timeline":      cards,        # Most recent first
        "stats":         stats,
        "retention_days": days,
        "cutoff_date":   cutoff.isoformat(),
    }


async def get_conversation_messages(
    conversation_id: str,
    user_id:         str,
    db,
    include_metadata: bool = True,
) -> Dict:
    """
    Fetch all messages for a specific conversation.
    Validates ownership (user_id) for security.
    """
    from sqlalchemy import select, desc
    from backend.database.models import Conversation, Message

    cutoff = datetime.utcnow() - timedelta(days=HISTORY_DAYS)

    # Validate ownership and retention
    conv_res = await db.execute(
        select(Conversation).where(
            Conversation.id      == conversation_id,
            Conversation.user_id == user_id,
            Conversation.updated_at >= cutoff,
        )
    )
    conv = conv_res.scalar_one_or_none()
    if not conv:
        return {"found": False, "messages": [], "conversation": None}

    # Load all messages
    msg_res = await db.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at)
    )
    messages = msg_res.scalars().all()

    agent_id     = (conv.agent_id or "").upper()
    disease_code = (conv.disease_code or agent_id[:2] or "").upper()
    agent_info   = AGENT_META.get(agent_id, {"name": agent_id, "icon": "🤖"})
    disease_info = DISEASE_META.get(disease_code, {"name": "General", "icon": "🏥", "color": "#6B7280"})

    msg_list = []
    for m in messages:
        entry = {
            "id":         m.id,
            "role":       m.role,
            "content":    m.content,
            "agent_id":   (m.agent_id or "").upper(),
            "created_at": m.created_at.isoformat(),
            "is_voice":   m.content.startswith("[VOICE]") if m.content else False,
            "is_image":   m.content.startswith("[IMAGE:") if m.content else False,
        }
        if include_metadata and m.role == "assistant":
            entry.update({
                "confidence":  getattr(m, "confidence",  None),
                "frustration": getattr(m, "frustration", None),
                "citations":   getattr(m, "citations",   []) or [],
                "follow_up_questions": getattr(m, "follow_up_questions", []) or [],
                "response_format": getattr(m, "response_format", None),
                "intent":          getattr(m, "intent",          None),
            })
        msg_list.append(entry)

    expires_in = max(0, HISTORY_DAYS - (datetime.utcnow() - conv.updated_at).days)

    return {
        "found":     True,
        "conversation": {
            "id":           conv.id,
            "title":        conv.title or generate_conversation_title(
                messages[0].content if messages else "Conversation"
            ),
            "agent_id":     agent_id,
            "agent_name":   agent_info["name"],
            "agent_icon":   agent_info["icon"],
            "disease_code": disease_code,
            "disease_name": disease_info["name"],
            "disease_icon": disease_info["icon"],
            "disease_color": disease_info["color"],
            "language":     conv.language or "en",
            "created_at":   conv.created_at.isoformat(),
            "updated_at":   conv.updated_at.isoformat(),
            "total_messages": len(messages),
            "expires_in_days": expires_in,
            "escalated":    getattr(conv, "escalated", False),
        },
        "messages":  msg_list,
    }


async def search_history(
    user_id:  str,
    query:    str,
    db,
    days:     int = HISTORY_DAYS,
    disease:  Optional[str] = None,
    agent_id: Optional[str] = None,
) -> List[Dict]:
    """
    Full-text search across a user's message history.
    Searches both user messages and AI responses.
    """
    from sqlalchemy import select, func, desc
    from backend.database.models import Conversation, Message

    cutoff = datetime.utcnow() - timedelta(days=days)
    query_lower = query.lower().strip()

    if not query_lower or len(query_lower) < 2:
        return []

    # Build message query with content search
    msg_q = (
        select(Message, Conversation)
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id   == user_id,
            Conversation.updated_at >= cutoff,
            (
                func.lower(Message.content).contains(query_lower) |
                func.lower(Conversation.title).contains(query_lower) |
                func.lower(Conversation.topic_label).contains(query_lower)
            )
        )
        .order_by(desc(Message.created_at))
        .limit(50)
    )
    if disease:
        msg_q = msg_q.where(Conversation.disease_code == disease.upper())
    if agent_id:
        msg_q = msg_q.where(Conversation.agent_id == agent_id.upper())

    result = await db.execute(msg_q)
    rows   = result.all()

    # Group results by conversation (avoid duplicates)
    seen_convs = {}
    search_results = []

    for msg, conv in rows:
        if conv.id not in seen_convs:
            seen_convs[conv.id] = True
            agent_info   = AGENT_META.get((conv.agent_id or "").upper(), {"name": "Agent", "icon": "🤖"})
            disease_info = DISEASE_META.get((conv.disease_code or "").upper(), {"name": "General", "icon": "🏥", "color": "#6B7280"})

            # Highlight matching text in snippet
            snippet = msg.content[:200]
            idx     = snippet.lower().find(query_lower)
            if idx >= 0:
                start     = max(0, idx - 40)
                end       = min(len(snippet), idx + len(query_lower) + 60)
                highlighted = snippet[start:end]
            else:
                highlighted = snippet[:SNIPPET_LENGTH]

            age_days  = (datetime.utcnow() - conv.updated_at).days
            age_label = "Today" if age_days == 0 else ("Yesterday" if age_days == 1 else f"{age_days}d ago")

            search_results.append({
                "conversation_id":  conv.id,
                "title":           generate_conversation_title(conv.title or msg.content),
                "matched_snippet": highlighted,
                "match_role":      msg.role,
                "agent_id":        (conv.agent_id or "").upper(),
                "agent_name":      agent_info["name"],
                "agent_icon":      agent_info["icon"],
                "disease_code":    (conv.disease_code or "").upper(),
                "disease_name":    disease_info["name"],
                "disease_icon":    disease_info["icon"],
                "disease_color":   disease_info["color"],
                "updated_at":      conv.updated_at.isoformat(),
                "age_label":       age_label,
            })

    # Group search results by topic semantically
    grouped_raw = group_by_topic(search_results)
    grouped_topics = format_topics(grouped_raw)

    return grouped_topics


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — PURGE / CLEANUP
# ═══════════════════════════════════════════════════════════════════════════════

async def purge_expired_history(db) -> Dict:
    """
    Delete all conversations (and their messages) older than HISTORY_DAYS.
    Called by the background scheduler and the /api/history/purge endpoint.
    Returns: {conversations_deleted, messages_deleted, ran_at}
    """
    from sqlalchemy import select, delete
    from backend.database.models import Conversation, Message

    cutoff = datetime.utcnow() - timedelta(days=HISTORY_DAYS)

    # Find expired conversations
    expired_res = await db.execute(
        select(Conversation.id).where(Conversation.updated_at < cutoff)
    )
    expired_ids = [r[0] for r in expired_res.all()]

    if not expired_ids:
        return {
            "conversations_deleted": 0,
            "messages_deleted":      0,
            "ran_at":                datetime.utcnow().isoformat(),
        }

    # Delete messages first (FK constraint)
    msg_del = await db.execute(
        delete(Message).where(Message.conversation_id.in_(expired_ids))
    )
    # Delete conversations
    conv_del = await db.execute(
        delete(Conversation).where(Conversation.id.in_(expired_ids))
    )
    await db.commit()

    return {
        "conversations_deleted": len(expired_ids),
        "messages_deleted":      msg_del.rowcount,
        "ran_at":                datetime.utcnow().isoformat(),
    }


async def get_history_stats(user_id: str, db) -> Dict:
    """Quick stats for the history panel header."""
    from sqlalchemy import select, func
    from backend.database.models import Conversation, Message

    cutoff = datetime.utcnow() - timedelta(days=HISTORY_DAYS)

    conv_count = (await db.execute(
        select(func.count(Conversation.id)).where(
            Conversation.user_id   == user_id,
            Conversation.updated_at >= cutoff,
        )
    )).scalar() or 0

    msg_count = (await db.execute(
        select(func.count(Message.id))
        .join(Conversation, Message.conversation_id == Conversation.id)
        .where(
            Conversation.user_id   == user_id,
            Conversation.updated_at >= cutoff,
        )
    )).scalar() or 0

    return {
        "conversations": conv_count,
        "messages":      msg_count,
        "retention_days": HISTORY_DAYS,
        "cutoff":        cutoff.strftime("%d %b %Y"),
    }


def _empty_stats() -> Dict:
    return {
        "total_conversations": 0, "total_messages": 0,
        "active_agents": [], "active_diseases": [],
        "most_used_agent": None, "most_used_agent_name": None,
        "first_interaction": None, "last_interaction": None,
        "avg_messages_per_conv": 0,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — BACKGROUND SCHEDULER
# ═══════════════════════════════════════════════════════════════════════════════

async def _daily_cleanup_task(get_db_session):
    """
    Runs daily at 02:00 UTC. Purges all conversations older than 15 days.
    Attach this to FastAPI lifespan events.
    """
    while True:
        now         = datetime.utcnow()
        # Next 02:00 UTC
        next_run    = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        wait_secs   = (next_run - now).total_seconds()

        await asyncio.sleep(wait_secs)

        try:
            async with get_db_session() as db:
                result = await purge_expired_history(db)
                print(
                    f"[PRISM History] Daily cleanup ran at {result['ran_at']}: "
                    f"{result['conversations_deleted']} conversations, "
                    f"{result['messages_deleted']} messages deleted."
                )
        except Exception as e:
            print(f"[PRISM History] Cleanup error: {e}")


def start_cleanup_scheduler(get_db_session):
    """
    Call this in FastAPI startup to launch the background cleanup task.

    Usage in main.py:
        @app.on_event("startup")
        async def startup():
            from backend.core.history.chat_history import start_cleanup_scheduler
            from backend.database.session import get_db_context
            asyncio.create_task(_daily_cleanup_task(get_db_context))
    """
    asyncio.create_task(_daily_cleanup_task(get_db_session))