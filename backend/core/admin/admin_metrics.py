# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/admin/admin_metrics.py
# PRISM Admin Metrics — 7 sections, all reading from live DB
# ───────────────────────────────────────────────────────────────────────────────
# Each function is called by a FastAPI endpoint in main.py.
# They read from the tables that metrics_tracker.py writes to.
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional

HISTORY_DAYS = 15
AGENT_NAMES = {
    "CA1":"Screening","CA2":"Treatment","CA3":"Supportive","CA4":"Survivorship",
    "CA5":"Genetics","CA6":"CA Navigator","DM1":"Monitoring","DM2":"Medication",
    "DM3":"Nutrition","DM4":"Complications","DM5":"Gestational","DM6":"DM Navigator",
    "CV1":"Clinical","CV2":"Emergency","CV3":"Medications","CV4":"Rehab",
    "CV5":"Nutrition","CV6":"CV Navigator","MH1":"Depression","MH2":"Anxiety",
    "MH3":"Sleep","MH4":"Trauma","MH5":"Crisis","MH6":"MH Navigator",
    "RS1":"Asthma","RS2":"COPD","RS3":"Rehab","RS4":"Medications",
    "RS5":"Sleep Apnea","RS6":"RS Navigator",
}
DISEASE_NAMES = {"CA":"Cancer","DM":"Diabetes","CV":"Cardiovascular","MH":"Mental Health","RS":"Respiratory"}
DISEASE_ICONS = {"CA":"🎗","DM":"🩺","CV":"❤️","MH":"🧠","RS":"🫁"}


def _cutoff(days=HISTORY_DAYS):
    return datetime.utcnow() - timedelta(days=days)


# ══════════════════════════════════════════════════════════════════════════════
# 1. RAGAS METRICS
# ══════════════════════════════════════════════════════════════════════════════

async def get_ragas_metrics(db, days=HISTORY_DAYS) -> Dict:
    from sqlalchemy import select, func
    from backend.database.models import RAGASMetric

    cutoff = _cutoff(days)
    res = await db.execute(
        select(
            func.avg(RAGASMetric.faithfulness).label("faith"),
            func.avg(RAGASMetric.answer_relevancy).label("relev"),
            func.avg(RAGASMetric.context_recall).label("recall"),
            func.avg(RAGASMetric.context_precision).label("prec"),
            func.avg(RAGASMetric.answer_similarity).label("sim"),
            func.avg(RAGASMetric.overall_score).label("overall"),
            func.avg(RAGASMetric.confidence).label("conf"),
            func.count(RAGASMetric.id).label("total"),
        ).where(RAGASMetric.created_at >= cutoff)
    )
    row = res.first()
    total = int(row.total or 0)

    def p(v): return round(float(v or 0) * 100, 1)

    # Per-agent breakdown
    agent_res = await db.execute(
        select(
            RAGASMetric.agent_id,
            func.avg(RAGASMetric.overall_score).label("avg_score"),
            func.count(RAGASMetric.id).label("count"),
        ).where(RAGASMetric.created_at >= cutoff)
        .group_by(RAGASMetric.agent_id)
        .order_by(func.avg(RAGASMetric.overall_score).desc())
        .limit(10)
    )
    per_agent = [
        {"agent_id": r.agent_id,
         "agent_name": AGENT_NAMES.get(r.agent_id, r.agent_id),
         "avg_score": round(float(r.avg_score or 0) * 100, 1),
         "count": int(r.count)}
        for r in agent_res.all()
    ]

    # Per-disease breakdown
    dis_res = await db.execute(
        select(
            RAGASMetric.disease_code,
            func.avg(RAGASMetric.overall_score).label("avg"),
            func.count(RAGASMetric.id).label("count"),
        ).where(RAGASMetric.created_at >= cutoff)
        .group_by(RAGASMetric.disease_code)
    )
    per_disease = [
        {"code": r.disease_code,
         "name": DISEASE_NAMES.get(r.disease_code, r.disease_code),
         "icon": DISEASE_ICONS.get(r.disease_code, "🏥"),
         "avg_score": round(float(r.avg or 0) * 100, 1),
         "count": int(r.count)}
        for r in dis_res.all()
    ]

    return {
        "total_evaluations": total,
        "period_days":       days,
        "averages": {
            "faithfulness":      p(row.faith),
            "answer_relevancy":  p(row.relev),
            "context_recall":    p(row.recall),
            "context_precision": p(row.prec),
            "answer_similarity": p(row.sim),
            "overall":           p(row.overall),
            "confidence":        p(row.conf),
        },
        "per_agent":   per_agent,
        "per_disease": per_disease,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 2. PATIENT FEEDBACK
# ══════════════════════════════════════════════════════════════════════════════

async def get_patient_feedback(db, days=HISTORY_DAYS) -> Dict:
    from sqlalchemy import select, func, desc
    from backend.database.models import PatientFeedback, User

    cutoff = _cutoff(days)

    # Overall stats
    stats_res = await db.execute(
        select(
            func.count(PatientFeedback.id).label("total"),
            func.avg(PatientFeedback.rating).label("avg_rating"),
        ).where(PatientFeedback.created_at >= cutoff)
    )
    stats = stats_res.first()
    total = int(stats.total or 0)
    avg   = round(float(stats.avg_rating or 0), 2)

    # Distribution
    dist = {}
    for star in range(1, 6):
        res = await db.execute(
            select(func.count(PatientFeedback.id))
            .where(PatientFeedback.rating == star,
                   PatientFeedback.created_at >= cutoff)
        )
        dist[str(star)] = int(res.scalar() or 0)

    # Per disease
    dis_res = await db.execute(
        select(
            PatientFeedback.disease_code,
            func.avg(PatientFeedback.rating).label("avg"),
            func.count(PatientFeedback.id).label("count"),
        ).where(PatientFeedback.created_at >= cutoff)
        .group_by(PatientFeedback.disease_code)
    )
    per_disease = [
        {"code": r.disease_code,
         "name": DISEASE_NAMES.get(r.disease_code or "", r.disease_code or ""),
         "icon": DISEASE_ICONS.get(r.disease_code or "", "🏥"),
         "avg_rating": round(float(r.avg or 0), 2),
         "count": int(r.count)}
        for r in dis_res.all()
    ]

    # Recent 10 with comments
    recent_res = await db.execute(
        select(PatientFeedback)
        .where(PatientFeedback.created_at >= cutoff)
        .order_by(desc(PatientFeedback.created_at))
        .limit(10)
    )
    recent = []
    for f in recent_res.scalars().all():
        try:
            u_res = await db.execute(select(User).where(User.id == f.user_id))
            u = u_res.scalar_one_or_none()
            patient_name = u.name if u else "Patient"
        except Exception:
            patient_name = "Patient"
        recent.append({
            "feedback_id": f.id, "rating": f.rating, "comment": f.comment,
            "agent_id": f.agent_id, "agent_name": AGENT_NAMES.get(f.agent_id or "", f.agent_id or ""),
            "disease_code": f.disease_code, "patient_name": patient_name,
            "created_at": f.created_at.strftime("%d %b %Y %H:%M"),
        })

    return {
        "total_ratings": total, "average_rating": avg,
        "period_days": days,
        "distribution": dist,
        "per_disease":  per_disease,
        "recent":       recent,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 3. AGENT PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════

async def get_agent_performance(db, days=HISTORY_DAYS) -> Dict:
    from sqlalchemy import select, func
    from backend.database.models import RAGASMetric, Message, Conversation, PatientFeedback

    cutoff = _cutoff(days)

    # Conversations per agent
    conv_res = await db.execute(
        select(
            Conversation.agent_id,
            func.count(Conversation.id).label("conversations"),
            func.avg(Conversation.total_messages).label("avg_messages"),
        ).where(Conversation.updated_at >= cutoff)
        .group_by(Conversation.agent_id)
    )
    conv_map = {r.agent_id: {"conversations": int(r.conversations),
                              "avg_messages": round(float(r.avg_messages or 0), 1)}
                for r in conv_res.all()}

    # RAGAS per agent
    ragas_res = await db.execute(
        select(
            RAGASMetric.agent_id,
            func.avg(RAGASMetric.overall_score).label("ragas"),
            func.avg(RAGASMetric.confidence).label("conf"),
            func.avg(RAGASMetric.processing_ms).label("lat"),
            func.count(RAGASMetric.id).label("calls"),
        ).where(RAGASMetric.created_at >= cutoff)
        .group_by(RAGASMetric.agent_id)
    )
    ragas_map = {r.agent_id: {
        "ragas": round(float(r.ragas or 0) * 100, 1),
        "confidence": round(float(r.conf or 0) * 100, 1),
        "avg_latency_ms": int(r.lat or 0),
        "llm_calls": int(r.calls),
    } for r in ragas_res.all()}

    # Feedback per agent
    fb_res = await db.execute(
        select(
            PatientFeedback.agent_id,
            func.avg(PatientFeedback.rating).label("avg"),
            func.count(PatientFeedback.id).label("count"),
        ).where(PatientFeedback.created_at >= cutoff)
        .group_by(PatientFeedback.agent_id)
    )
    fb_map = {r.agent_id: {"avg_rating": round(float(r.avg or 0), 2),
                             "feedback_count": int(r.count)}
              for r in fb_res.all()}

    # Merge all
    all_agents = set(conv_map) | set(ragas_map) | set(fb_map)
    agents_out = []
    for aid in sorted(all_agents):
        agents_out.append({
            "agent_id":       aid,
            "agent_name":     AGENT_NAMES.get(aid, aid),
            "disease_code":   aid[:2] if aid else "",
            "disease_name":   DISEASE_NAMES.get(aid[:2] if aid else "", ""),
            "disease_icon":   DISEASE_ICONS.get(aid[:2] if aid else "", "🏥"),
            **conv_map.get(aid, {"conversations": 0, "avg_messages": 0}),
            **ragas_map.get(aid, {"ragas": 0, "confidence": 0, "avg_latency_ms": 0, "llm_calls": 0}),
            **fb_map.get(aid, {"avg_rating": 0, "feedback_count": 0}),
        })
    agents_out.sort(key=lambda x: x["conversations"], reverse=True)
    return {"agents": agents_out, "total_agents_active": len(agents_out), "period_days": days}


# ══════════════════════════════════════════════════════════════════════════════
# 4. LLM CALL METRICS
# ══════════════════════════════════════════════════════════════════════════════

async def get_llm_calls(db, days=HISTORY_DAYS) -> Dict:
    from sqlalchemy import select, func
    from backend.database.models import SystemAlert

    cutoff = _cutoff(days)

    # All LLM call records
    res = await db.execute(
        select(SystemAlert)
        .where(SystemAlert.component == "llm_call",
               SystemAlert.created_at >= cutoff)
        .order_by(SystemAlert.created_at.desc())
        .limit(1000)
    )
    alerts = res.scalars().all()

    total_calls = len(alerts)
    total_prompt = total_completion = 0
    route_counts: Dict[str, int] = {}
    agent_counts: Dict[str, int] = {}
    disease_counts: Dict[str, int] = {}
    latencies = []

    for a in alerts:
        try:
            d = json.loads(a.message)
        except Exception:
            continue
        total_prompt     += d.get("prompt_tokens", 0)
        total_completion += d.get("completion_tokens", 0)
        latencies.append(d.get("processing_ms", 0))
        route  = d.get("route", "primary")
        agent  = d.get("agent_id", "")
        dis    = d.get("disease_code", "")
        route_counts[route]   = route_counts.get(route, 0) + 1
        agent_counts[agent]   = agent_counts.get(agent, 0) + 1
        disease_counts[dis]   = disease_counts.get(dis, 0) + 1

    avg_lat = int(sum(latencies) / len(latencies)) if latencies else 0
    latencies_sorted = sorted(latencies)
    p50 = latencies_sorted[len(latencies_sorted)//2] if latencies_sorted else 0
    p95 = latencies_sorted[int(len(latencies_sorted)*0.95)] if latencies_sorted else 0

    top_agents = sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        "total_calls":         total_calls,
        "total_prompt_tokens": total_prompt,
        "total_completion_tokens": total_completion,
        "total_tokens":        total_prompt + total_completion,
        "avg_latency_ms":      avg_lat,
        "p50_latency_ms":      p50,
        "p95_latency_ms":      p95,
        "by_route":            route_counts,
        "by_disease":          {k: {"count": v, "name": DISEASE_NAMES.get(k,""), "icon": DISEASE_ICONS.get(k,"")}
                                 for k, v in disease_counts.items()},
        "top_agents":          [{"agent_id": a, "agent_name": AGENT_NAMES.get(a,a), "calls": c}
                                 for a, c in top_agents],
        "period_days":         days,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 5. ESCALATIONS
# ══════════════════════════════════════════════════════════════════════════════

async def get_escalations(db, days=HISTORY_DAYS) -> Dict:
    from sqlalchemy import select
    from backend.database.models import SystemAlert

    cutoff = _cutoff(days)

    res = await db.execute(
        select(SystemAlert)
        .where(SystemAlert.component.like("agent:%"),
               SystemAlert.level.in_(["warning", "critical"]),
               SystemAlert.created_at >= cutoff)
        .order_by(SystemAlert.created_at.desc())
        .limit(500)
    )
    alerts = res.scalars().all()

    specialist_total = 0
    human_total      = 0
    by_agent:   Dict[str, Dict] = {}
    by_disease: Dict[str, Dict] = {}
    recent = []

    for a in alerts:
        try:
            d = json.loads(a.message)
        except Exception:
            d = {}
        etype = d.get("type", "specialist" if a.level == "warning" else "human")
        aid   = d.get("agent_id", "")
        dis   = d.get("disease_code", aid[:2] if aid else "")
        conf  = d.get("confidence", 0)
        frust = d.get("frustration", 0)

        if etype == "specialist": specialist_total += 1
        else:                     human_total      += 1

        if aid not in by_agent:
            by_agent[aid] = {"agent_id": aid, "agent_name": AGENT_NAMES.get(aid,aid),
                              "disease_icon": DISEASE_ICONS.get(dis,"🏥"),
                              "specialist": 0, "human": 0, "total": 0,
                              "last_at": a.created_at.isoformat()}
        by_agent[aid][etype] = by_agent[aid].get(etype, 0) + 1
        by_agent[aid]["total"] += 1

        if dis not in by_disease:
            by_disease[dis] = {"code": dis, "name": DISEASE_NAMES.get(dis,""),
                                "icon": DISEASE_ICONS.get(dis,"🏥"),
                                "specialist": 0, "human": 0, "total": 0}
        by_disease[dis][etype] = by_disease[dis].get(etype, 0) + 1
        by_disease[dis]["total"] += 1

        if len(recent) < 20:
            recent.append({
                "type": etype, "agent_id": aid,
                "agent_name": AGENT_NAMES.get(aid, aid),
                "disease_code": dis, "disease_icon": DISEASE_ICONS.get(dis,"🏥"),
                "confidence": round(conf * 100, 1) if conf else 0,
                "frustration": frust,
                "reason": d.get("reason", ""),
                "created_at": a.created_at.strftime("%d %b %H:%M"),
            })

    agent_list = sorted(by_agent.values(), key=lambda x: x["total"], reverse=True)
    return {
        "total_escalations":      specialist_total + human_total,
        "specialist_escalations": specialist_total,
        "human_escalations":      human_total,
        "period_days":            days,
        "by_agent":               agent_list,
        "by_disease":             list(by_disease.values()),
        "recent":                 recent,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 6. RESPONSIBLE AI / GUARDRAILS
# ══════════════════════════════════════════════════════════════════════════════

async def get_responsible_ai(db, days=HISTORY_DAYS) -> Dict:
    from sqlalchemy import select, func
    from backend.database.models import SystemAlert

    cutoff = _cutoff(days)

    res = await db.execute(
        select(SystemAlert)
        .where(SystemAlert.component.like("guardrail:%"),
               SystemAlert.created_at >= cutoff)
        .order_by(SystemAlert.created_at.desc())
        .limit(500)
    )
    alerts = res.scalars().all()

    by_type: Dict[str, int] = {}
    recent = []

    for a in alerts:
        gtype = a.component.replace("guardrail:", "") if a.component else "unknown"
        by_type[gtype] = by_type.get(gtype, 0) + 1
        try:
            d = json.loads(a.message)
        except Exception:
            d = {}
        if len(recent) < 15:
            recent.append({
                "type":       gtype,
                "agent_id":   d.get("agent_id", ""),
                "details":    d.get("details", "")[:100],
                "created_at": a.created_at.strftime("%d %b %H:%M"),
            })

    total = sum(by_type.values())

    # LLM calls for compliance rate (guardrails fired / total calls)
    llm_total_res = await db.execute(
        select(func.count(SystemAlert.id))
        .where(SystemAlert.component == "llm_call",
               SystemAlert.created_at >= cutoff)
    )
    llm_total = int(llm_total_res.scalar() or 1)
    compliance_rate = round(max(0, 100 - (total / llm_total * 100)), 1)

    return {
        "total_guardrail_events": total,
        "compliance_rate_pct":    compliance_rate,
        "period_days":            days,
        "by_type":                by_type,
        "recent":                 recent,
    }


# ══════════════════════════════════════════════════════════════════════════════
# 7. QUALITY METRICS SUMMARY (re-exports from quality_metrics.py)
# ══════════════════════════════════════════════════════════════════════════════

async def get_quality_summary(db, days=HISTORY_DAYS) -> Dict:
    from backend.core.quality.quality_metrics import compute_quality_for_all_patients
    results = await compute_quality_for_all_patients(db, days=days)
    if not results:
        return {"active_patients": 0, "avg_cqs": 0, "avg_stars": 0, "patients": []}

    avg_cqs   = round(sum(r["cqs"] for r in results) / len(results), 1)
    avg_stars = round(sum(r["predicted_stars"] for r in results) / len(results), 2)

    def avg_dim(k):
        vals = [r["dimensions"].get(k, {}).get("score", 0) for r in results]
        return round(sum(vals) / max(len(vals), 1), 1)

    return {
        "active_patients": len(results),
        "avg_cqs":         avg_cqs,
        "avg_stars":       avg_stars,
        "period_days":     days,
        "dimensions": {
            "engagement":       avg_dim("engagement"),
            "response_quality": avg_dim("response_quality"),
            "clinical_safety":  avg_dim("clinical_safety"),
            "session_flow":     avg_dim("session_flow"),
            "format_variety":   avg_dim("format_variety"),
            "velocity":         avg_dim("velocity"),
        },
        "patients": [
            {"user_id": r["user_id"], "cqs": r["cqs"],
             "predicted_stars": r["predicted_stars"],
             "sessions": r["sessions"]}
            for r in results[:20]
        ],
    }


# ══════════════════════════════════════════════════════════════════════════════
# MASTER DASHBOARD — all 7 sections in one call
# ══════════════════════════════════════════════════════════════════════════════

async def get_admin_dashboard(db, days=HISTORY_DAYS) -> Dict:
    import asyncio
    ragas, feedback, agents, llm, esc, rai, quality = await asyncio.gather(
        get_ragas_metrics(db, days),
        get_patient_feedback(db, days),
        get_agent_performance(db, days),
        get_llm_calls(db, days),
        get_escalations(db, days),
        get_responsible_ai(db, days),
        get_quality_summary(db, days),
    )
    return {
        "refreshed_at": datetime.utcnow().isoformat(),
        "period_days":  days,
        "ragas":        ragas,
        "feedback":     feedback,
        "agents":       agents,
        "llm_calls":    llm,
        "escalations":  esc,
        "responsible_ai": rai,
        "quality":      quality,
    }