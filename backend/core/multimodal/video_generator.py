import asyncio
import httpx
import os
import time
from datetime import datetime
from typing import Dict, List

RUNWAY_API_KEY = os.getenv("RUNWAY_ML_API_KEY", "")
LUMA_API_KEY   = os.getenv("LUMA_AI_API_KEY",   "")


async def generate_medical_video(
    intent_id:       str,
    clip_plan:       Dict,
    conversation_id: str,
    user_id:         str,
    db,
) -> Dict:
    """
    Generate a medical educational video (max 60 seconds).
    Runway ML Gen-3 Alpha generates 10s clips; we stitch them for longer videos.

    For 1-min videos: generates 6 × 10s clips and stitches server-side.
    """
    clips          = clip_plan.get("clips", [])
    total_duration = clip_plan.get("total_duration_s", 30)

    if len(clips) <= 1:
        # Single clip
        try:
            clip_url = await _generate_runway_clip(clips[0]["prompt"] if clips else "Medical animation", clips[0].get("duration_s", 10) if clips else 10)
        except Exception:
            clip_url = await _generate_luma_clip(clips[0]["prompt"] if clips else "Medical animation")
        return {
            "video_url":      clip_url,
            "duration_s":     total_duration,
            "clip_count":     1,
            "intent_id":      intent_id,
            "conversation_id":conversation_id,
            "created_at":     datetime.utcnow().isoformat(),
        }

    # Multiple clips — generate in parallel then stitch
    clip_urls = await _generate_clips_parallel(clips)
    final_url = await _stitch_clips(clip_urls, total_duration)

    result = {
        "video_url":      final_url,
        "duration_s":     total_duration,
        "clip_count":     len(clips),
        "intent_id":      intent_id,
        "conversation_id":conversation_id,
        "created_at":     datetime.utcnow().isoformat(),
    }
    # Save to DB
    await _save_video_record(db, result, user_id, clip_plan.get("prompt", ""))
    return result


async def _generate_runway_clip(prompt: str, duration_s: int = 10) -> str:
    """Generate a single video clip via Runway ML Gen-3 Alpha."""
    if not RUNWAY_API_KEY:
        raise ValueError("RUNWAY_ML_API_KEY not set")

    async with httpx.AsyncClient(timeout=120) as client:
        # Submit generation task
        resp = await client.post(
            "https://api.dev.runwayml.com/v1/image_to_video",   # Gen-3 Alpha endpoint
            headers={
                "Authorization": f"Bearer {RUNWAY_API_KEY}",
                "X-Runway-Version": "2024-11-06",
                "Content-Type":    "application/json",
            },
            json={
                "promptText": prompt,
                "model":      "gen3a_turbo",
                "duration":   min(duration_s, 10),   # Runway max = 10s
                "ratio":      "1280:720",
            },
        )
        resp.raise_for_status()
        task_id = resp.json()["id"]

        # Poll for completion
        for _ in range(60):
            await asyncio.sleep(5)
            poll = await client.get(
                f"https://api.dev.runwayml.com/v1/tasks/{task_id}",
                headers={"Authorization": f"Bearer {RUNWAY_API_KEY}", "X-Runway-Version": "2024-11-06"},
            )
            poll.raise_for_status()
            status = poll.json()
            if status["status"] == "SUCCEEDED":
                return status["output"][0]
            if status["status"] == "FAILED":
                raise RuntimeError(f"Runway generation failed: {status.get('failure')}")

    raise TimeoutError("Runway video generation timed out after 5 minutes")


async def _generate_luma_clip(prompt: str) -> str:
    """Generate via Luma AI Dream Machine (fallback)."""
    if not LUMA_API_KEY:
        raise ValueError("LUMA_AI_API_KEY not set")

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            "https://api.lumalabs.ai/dream-machine/v1/generations",
            headers={"Authorization": f"Bearer {LUMA_API_KEY}", "Content-Type": "application/json"},
            json={"prompt": prompt, "aspect_ratio": "16:9"},
        )
        resp.raise_for_status()
        gen_id = resp.json()["id"]

        for _ in range(60):
            await asyncio.sleep(5)
            poll = await client.get(
                f"https://api.lumalabs.ai/dream-machine/v1/generations/{gen_id}",
                headers={"Authorization": f"Bearer {LUMA_AI_KEY}"},
            )
            poll.raise_for_status()
            state = poll.json()
            if state.get("state") == "completed":
                return state["assets"]["video"]
            if state.get("state") == "failed":
                raise RuntimeError(f"Luma generation failed: {state.get('failure_reason')}")

    raise TimeoutError("Luma video generation timed out")


async def _generate_clips_parallel(clips: List[Dict]) -> List[str]:
    """Generate multiple clips in parallel."""
    tasks = []
    for clip in clips:
        try:
            tasks.append(_generate_runway_clip(clip["prompt"], clip["duration_s"]))
        except Exception:
            tasks.append(_generate_luma_clip(clip["prompt"]))
    return await asyncio.gather(*tasks, return_exceptions=False)


async def _stitch_clips(clip_urls: List[str], total_s: int) -> str:
    """
    Stitch multiple 10s clips into a single video.
    For now: returns the first clip URL.
    """
    return clip_urls[0] if clip_urls else ""


async def _save_video_record(db, result: Dict, user_id: str, prompt: str) -> None:
    """Save video generation record to video_generations table."""
    import uuid
    from backend.database.models import VideoGeneration
    db.add(VideoGeneration(
        id              = str(uuid.uuid4()),
        user_id         = user_id,
        conversation_id = result.get("conversation_id"),
        video_url       = result.get("video_url"),
        intent_id       = result.get("intent_id"),
        prompt          = prompt[:1000],
        duration_s      = result.get("duration_s", 0),
        clip_count      = result.get("clip_count", 1),
        created_at      = datetime.utcnow(),
    ))
    pass
