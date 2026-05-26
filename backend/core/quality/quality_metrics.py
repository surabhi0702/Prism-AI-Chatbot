import os
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from loguru import logger

# ─── SQL LOADING ─────────────────────────────────────────────────────────────
SQL_FILE_PATH = os.path.join(os.path.dirname(__file__), "quality_queries.sql")

def load_quality_sql() -> str:
    """Load the master quality SQL file."""
    if not os.path.exists(SQL_FILE_PATH):
        logger.error(f"Quality SQL file not found at {SQL_FILE_PATH}")
        return ""
    with open(SQL_FILE_PATH, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

def load_composite_quality_sql() -> str:
    """Returns the cleaned composite quality score SQL query."""
    return load_quality_sql().strip()

# ─── CORE COMPUTATION ────────────────────────────────────────────────────────

async def compute_quality_for_patient(user_id: str, db: AsyncSession, days: int = 15) -> Dict[str, Any]:
    """
    Compute the full 28-parameter quality report for a single patient.
    Returns a nested dictionary matching the Admin Portal's expectations.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    sql_query = load_composite_quality_sql().strip()
    if sql_query.endswith(";"):
        sql_query = sql_query[:-1]
    
    if not sql_query:
        return {"error": "Composite SQL query missing or marker not found"}
    
    try:
        # Execute the composite query
        result = await db.execute(text(sql_query), {"user_id": user_id, "cutoff": cutoff})
        row = result.fetchone()
        
        if not row:
            # Check if patient even has sessions
            meta_res = await db.execute(
                text("SELECT COUNT(*) FROM conversations WHERE user_id = :uid AND updated_at >= :c"),
                {"uid": user_id, "c": cutoff}
            )
            count = meta_res.scalar() or 0
            if count == 0:
                return {"error": "No sessions found in period"}
                
            return {
                "user_id": user_id,
                "cqs": 0,
                "predicted_stars": 0,
                "sessions": count,
                "total_messages": 0,
                "dimensions": {}
            }

        # We also need the raw counts (sessions, messages)
        meta_res = await db.execute(
            text("SELECT COUNT(*) as sessions, SUM(total_messages) as msgs FROM conversations WHERE user_id = :uid AND updated_at >= :c"),
            {"uid": user_id, "c": cutoff}
        )
        meta = meta_res.fetchone()

        # Map row to the expected structure
        report = {
            "user_id": user_id,
            "computed_at": datetime.utcnow().isoformat(),
            "cqs": round(float(row.cqs_composite or 0), 1),
            "predicted_stars": round(float(row.cqs_composite or 0) / 20.0, 1),
            "sessions": meta.sessions if meta else 0,
            "total_messages": meta.msgs if meta else 0,
            "dimensions": {
                "engagement": {
                    "score": round(float(row.dim_engagement or 0), 1),
                    "params": {
                        "star_rating": round(float(getattr(row, 'star_v', 60)), 1),
                        "elaboration_rate": round(float(getattr(row, 'elab_v', 0)), 1),
                        "session_return": round(float(getattr(row, 'return_v', 0)), 1)
                    }
                },
                "response_quality": {
                    "score": round(float(row.dim_response or 0), 1),
                    "params": {
                        "faithfulness": round(float(row.faith or 0), 1),
                        "relevancy": round(float(row.relev or 0), 1),
                        "confidence": round(float(row.conf or 0), 1)
                    }
                },
                "clinical_safety": {
                    "score": round(float(row.dim_clinical or 0), 1),
                    "params": {
                        "guardrail_compliance": round(float(row.guardrail or 0), 1),
                        "emergency_triggers": round(float(row.emg_sc or 0), 1)
                    }
                },
                "session_flow": {
                    "score": round(float(row.dim_session or 0), 1),
                    "params": {
                        "repeat_rate": round(float(row.rep_sc or 0), 1),
                        "skip_rate": round(float(row.skip_sc or 0), 1)
                    }
                },
                "format_variety": {
                    "score": round(float(row.dim_format or 0), 1),
                    "params": {
                        "rotation_score": round(float(row.rot_sc or 0), 1),
                        "length_appropriateness": round(float(row.len_sc or 0), 1)
                    }
                },
                "velocity": {
                    "score": round(float(row.dim_velocity or 0), 1),
                    "params": {
                        "p50_latency": round(float(row.p50_sc or 0), 1),
                        "p95_latency": round(float(row.p95_sc or 0), 1)
                    }
                }
            }
        }
        
        return report

    except Exception as e:
        logger.error(f"CQS Computation failed for {user_id}: {e}")
        return {"error": str(e)}

async def compute_quality_for_all_patients(db: AsyncSession, days: int = 15) -> List[Dict]:
    """Fetch all active patients and compute their CQS, ranked."""
    cutoff = datetime.utcnow() - timedelta(days=days)
    
    # 1. Get all unique users in the window
    users_res = await db.execute(
        text("SELECT DISTINCT user_id FROM conversations WHERE updated_at >= :c"),
        {"c": cutoff}
    )
    user_ids = [r[0] for r in users_res.fetchall()]
    
    results = []
    for uid in user_ids:
        q = await compute_quality_for_patient(uid, db, days)
        if "error" not in q:
            results.append(q)
            
    # Rank by CQS
    results.sort(key=lambda x: x.get("cqs", 0), reverse=True)
    return results


async def compute_admin_quality_summary(db: AsyncSession, days: int = 15) -> Dict[str, Any]:
    """Aggregate CQS across active patients for the admin quality dashboard."""
    results = await compute_quality_for_all_patients(db, days=days)
    if not results:
        return {"active_patients": 0, "avg_cqs": 0, "avg_stars": 0, "patients": [], "period_days": days}

    avg_cqs = round(sum(r["cqs"] for r in results) / len(results), 1)
    avg_stars = round(sum(r["predicted_stars"] for r in results) / len(results), 2)

    def avg_dim(key: str) -> float:
        vals = [r["dimensions"].get(key, {}).get("score", 0) for r in results]
        return round(sum(vals) / max(len(vals), 1), 1)

    return {
        "active_patients": len(results),
        "avg_cqs": avg_cqs,
        "avg_stars": avg_stars,
        "period_days": days,
        "dimensions": {
            "engagement": avg_dim("engagement"),
            "response_quality": avg_dim("response_quality"),
            "clinical_safety": avg_dim("clinical_safety"),
            "session_flow": avg_dim("session_flow"),
            "format_variety": avg_dim("format_variety"),
            "velocity": avg_dim("velocity"),
        },
        "patients": [
            {
                "user_id": r["user_id"],
                "cqs": r["cqs"],
                "predicted_stars": r["predicted_stars"],
                "sessions": r["sessions"],
            }
            for r in results[:20]
        ],
    }
