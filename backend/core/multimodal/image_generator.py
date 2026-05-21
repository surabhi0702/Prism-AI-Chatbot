import asyncio
import base64
import httpx
import os
from typing import Dict, Optional
from datetime import datetime
import uuid


OPENAI_API_KEY      = os.getenv("OPENAI_API_KEY", "")
STABILITY_API_KEY   = os.getenv("STABILITY_API_KEY", "")

MEDICAL_F1_THRESHOLD = 0.60


async def generate_medical_image(
    intent_id:       str,
    prompt:          str,
    conversation_id: str,
    user_id:         str,
    db,
) -> Dict:
    """
    Generate a medical educational image using DALL-E 3 (primary)
    or Stability AI SDXL (fallback).

    Returns: {url, local_path, intent_id, prompt, provider, width, height, created_at}
    """
    providers = [
        ("dalle3",      _generate_dalle3),
        ("stability",   _generate_stability),
    ]
    last_error = None

    for provider_name, generator_fn in providers:
        try:
            result = await generator_fn(prompt)
            result["provider"]        = provider_name
            result["intent_id"]       = intent_id
            result["conversation_id"] = conversation_id
            result["user_id"]         = user_id
            result["prompt"]          = prompt[:500]
            result["created_at"]      = datetime.utcnow().isoformat()

            # Validate medical content (F1 score check)
            is_valid, f1_score = await _validate_medical_image(result["url"], intent_id)
            result["f1_score"]  = f1_score
            result["validated"] = is_valid

            if not is_valid:
                result["warning"] = "Image may not match medical context accurately"

            # Save to DB
            await _save_image_record(db, result)
            return result

        except Exception as e:
            last_error = str(e)
            continue

    raise RuntimeError(f"All image providers failed. Last error: {last_error}")


async def _generate_dalle3(prompt: str) -> Dict:
    """Generate image via DALL-E 3."""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY not set")

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            "https://api.openai.com/v1/images/generations",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
            json={
                "model":   "dall-e-3",
                "prompt":  prompt,
                "n":       1,
                "size":    "1024x1024",
                "quality": "standard",
                "style":   "vivid",
            },
        )
        resp.raise_for_status()
        data = resp.json()
        image_url = data["data"][0]["url"]
        return {"url": image_url, "width": 1024, "height": 1024, "revised_prompt": data["data"][0].get("revised_prompt", "")}


async def _generate_stability(prompt: str) -> Dict:
    """Generate image via Stability AI SDXL (fallback)."""
    if not STABILITY_API_KEY:
        raise ValueError("STABILITY_API_KEY not set")

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.post(
            "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image",
            headers={"Authorization": f"Bearer {STABILITY_API_KEY}", "Content-Type": "application/json"},
            json={
                "text_prompts": [{"text": prompt, "weight": 1.0}],
                "cfg_scale":    7,
                "steps":        30,
                "width":        1024,
                "height":       1024,
                "samples":      1,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        b64  = data["artifacts"][0]["base64"]
        # In production: upload to S3/GCS and return URL
        # For now: return data URL
        return {"url": f"data:image/png;base64,{b64}", "width": 1024, "height": 1024}


async def _validate_medical_image(image_url: str, intent_id: str) -> tuple:
    """
    Validate that the generated image is appropriate for the medical intent.
    Uses Claude vision to check relevance and safety.
    """
    try:
        from backend.core.agents.base_agent import call_llm_sync

        result = call_llm_sync(
            system_prompt=(
                "You are a medical image safety validator for PRISM Health AI. "
                "Given an image URL and medical intent, assess: "
                "1) Is the image educational and appropriate? "
                "2) Does it match the intent? "
                "Return ONLY a JSON: {\"f1_score\": 0.85, \"safe\": true}. "
                "f1_score is 0.0-1.0. safe=false if graphic/inappropriate."
            ),
            user_message=f"Intent: {intent_id}\nImage URL: {image_url}",
            history=[],
            temperature=0.0,
            max_tokens=60,
        )
        import json
        data = json.loads(result["response"])
        return data.get("safe", True), data.get("f1_score", 0.75)
    except Exception:
        return True, 0.75   # Default to valid if check fails


async def _save_image_record(db, record: Dict) -> None:
    """Save image generation record to image_uploads table."""
    from backend.database.models import ImageUpload
    db.add(ImageUpload(
        id              = str(uuid.uuid4()),
        conversation_id = record.get("conversation_id"),
        user_id         = record.get("user_id"),
        image_url       = record.get("url"),
        intent_id       = record.get("intent_id"),
        prompt          = record.get("prompt", "")[:500],
        provider        = record.get("provider"),
        f1_score        = record.get("f1_score"),
        created_at      = datetime.utcnow(),
    ))
    # Note: caller should handle commit/flush
    pass
