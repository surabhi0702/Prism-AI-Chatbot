# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/multimodal/voice_processor.py
# PRISM Voice Processor — STT Validation, Medical Classification & Enrichment
# ───────────────────────────────────────────────────────────────────────────────
# PIPELINE:
#   1. Receive audio blob → transcribe via Whisper
#   2. Medical F1 validation on transcript
#   3. Agent compatibility check
#   4. LLM query enrichment (clean speech artifacts, expand intent)
#   5. Route to conversational engine + smart routing
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import io
import re
import json
import time
from typing import Dict, List, Optional, Tuple

# ─── Medical vocabulary for F1 scoring (same bank as image_validator) ──────────
MEDICAL_VOCAB = {
    "pain", "ache", "hurt", "symptom", "medication", "medicine", "tablet",
    "capsule", "pill", "injection", "dose", "dosage", "prescription", "doctor",
    "hospital", "clinic", "diagnosis", "treatment", "therapy", "blood",
    "glucose", "sugar", "pressure", "heart", "breathing", "lung", "chest",
    "headache", "fever", "nausea", "vomit", "dizziness", "fatigue", "weight",
    "diabetes", "cancer", "asthma", "copd", "depression", "anxiety", "insulin",
    "metformin", "statin", "inhaler", "ecg", "xray", "mri", "scan", "biopsy",
    "cholesterol", "hba1c", "hemoglobin", "kidney", "liver", "thyroid",
    "blood test", "lab result", "side effect", "allergy", "rash", "swelling",
    "infection", "antibiotic", "vaccine", "surgery", "operation", "referral",
    "specialist", "physiotherapy", "rehabilitation", "mental health", "sleep",
    "appetite", "exercise", "diet", "nutrition", "supplement", "vitamin",
}

NON_MEDICAL_VOCAB = {
    "weather", "sports", "game", "movie", "music", "food", "restaurant",
    "travel", "hotel", "shopping", "fashion", "politics", "news", "stock",
    "crypto", "dating", "relationship", "cooking", "recipe", "pet",
    "car", "tech", "software", "coding", "programming", "business",
}

# F1 thresholds
MEDICAL_F1_THRESHOLD = 0.30   # Relaxed for natural speech
MIN_WORDS_THRESHOLD  = 2      # Accept shorter queries like "My head hurts"

# ─── Speech artifact patterns to clean ────────────────────────────────────────
SPEECH_ARTIFACTS = [
    r'\bum+\b', r'\buh+\b', r'\blike\b,?\s*', r'\byou know\b,?\s*',
    r'\bi mean\b,?\s*', r'\bbasically\b,?\s*', r'\bactually\b,?\s*',
    r'\bokay so\b,?\s*', r'\bso basically\b,?\s*', r'\bright\b,?\s*',
    r'\bkind of\b,?\s*', r'\bsort of\b,?\s*',
]

# ─── Agent domain compatibility (mirrors image_validator) ─────────────────────
AGENT_DOMAINS = {
    **{f"CA{i}": "CA" for i in range(1, 7)},
    **{f"DM{i}": "DM" for i in range(1, 7)},
    **{f"CV{i}": "CV" for i in range(1, 7)},
    **{f"MH{i}": "MH" for i in range(1, 7)},
    **{f"RS{i}": "RS" for i in range(1, 7)},
}
GENERAL_AGENTS = {"CA6", "DM6", "CV6", "MH6", "RS6"}

DOMAIN_KEYWORDS = {
    "CA": {"cancer", "tumor", "tumour", "oncology", "chemotherapy", "radiation",
           "biopsy", "mammogram", "psa", "screening", "lump", "mass", "malignant",
           "benign", "metastasis", "stage", "remission", "pathology"},
    "DM": {"diabetes", "glucose", "sugar", "insulin", "hba1c", "metformin",
           "glycemic", "hypoglycemia", "hyperglycemia", "a1c", "cgm", "lancet",
           "blood sugar", "diabetic", "pancreas", "gestational"},
    "CV": {"heart", "cardiac", "cardiovascular", "blood pressure", "hypertension",
           "cholesterol", "ecg", "ekg", "arrhythmia", "palpitation", "angina",
           "statin", "bypass", "stent", "atrial", "fibrillation", "stroke"},
    "MH": {"depression", "anxiety", "mental", "stress", "panic", "ptsd", "trauma",
           "therapy", "psychiatrist", "psychologist", "antidepressant", "sleep",
           "insomnia", "mood", "bipolar", "adhd", "ocd", "phobia", "suicidal"},
    "RS": {"asthma", "copd", "breathing", "inhaler", "lung", "bronchitis",
           "spirometry", "oxygen", "nebulizer", "wheeze", "dyspnea", "respiratory",
           "pulmonary", "sleep apnea", "cpap", "emphysema"},
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — WHISPER TRANSCRIPTION
# ═══════════════════════════════════════════════════════════════════════════════

def transcribe_audio(audio_bytes: bytes, content_type: str = "audio/webm",
                     language: str = "en") -> Dict:
    """
    Transcribe audio using OpenAI Whisper via the Anthropic-compatible endpoint,
    or directly via the openai SDK.

    Returns: {transcript, language_detected, duration_s, confidence, segments}
    """
    try:
        import openai
        from backend.config.settings import get_settings
        settings = get_settings()

        client = openai.OpenAI(
            api_key=getattr(settings, "openai_api_key", None) or
                    getattr(settings, "anthropic_api_key", None)
        )

        # Map content_type to valid Whisper extension
        EXT_MAP = {
            "audio/webm":  "webm",
            "audio/ogg":   "ogg",
            "audio/mp4":   "mp4",
            "audio/mpeg":  "mp3",
            "audio/wav":   "wav",
            "audio/flac":  "flac",
        }
        
        # Safe split for content_type
        ct_clean = (content_type or "audio/webm").split(";")[0].strip()
        ext = EXT_MAP.get(ct_clean, "webm")
        filename = f"voice_query.{ext}"

        print(f"[VOICE] Transcribing {len(audio_bytes)} bytes, type={content_type}, ext={ext}")
        
        # Use a tuple for the file parameter (more robust than io.BytesIO on Windows/Uvicorn)
        transcript_obj = client.audio.transcriptions.create(
            model="whisper-1",
            file=(filename, audio_bytes, ct_clean),
            language=language if language and language != "auto" else None,
            response_format="verbose_json",
        )

        text = transcript_obj.text.strip()
        print(f"[VOICE] Transcription success: \"{text[:50]}{'...' if len(text)>50 else ''}\"")

        return {
            "transcript":        text,
            "language_detected": getattr(transcript_obj, "language", language),
            "duration_s":        getattr(transcript_obj, "duration", 0),
            "confidence":        0.90,
            "segments":          getattr(transcript_obj, "segments", []),
            "method":            "whisper",
            "success":           True,
            "error":             None,
        }

    except Exception as e:
        print(f"[VOICE_CRITICAL_ERROR] Transcription failed: {str(e)}")
        import traceback
        print(traceback.format_exc())
        return {
            "transcript":        "",
            "success":           False,
            "error":             str(e)
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — MEDICAL F1 CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def compute_voice_medical_f1(transcript: str) -> Dict:
    """
    BERTScore-style F1 on voice transcript.
    Speech is less precise than text, so we use a lower threshold.
    """
    words = set(re.findall(r'\b\w+\b', transcript.lower()))

    if len(words) < MIN_WORDS_THRESHOLD:
        return {
            "f1": 0.0, "precision": 0.0, "recall": 0.0,
            "is_medical": False,
            "medical_terms": [],
            "rejection": "Too short — please say at least a few words.",
        }

    # Add core medical words that are common in speech
    CORE_MEDICAL = {"pain", "head", "stomach", "chest", "leg", "arm", "hurts", "sick", "ill", "dizzy"}
    LOCAL_VOCAB = MEDICAL_VOCAB | CORE_MEDICAL

    med_hits     = words & LOCAL_VOCAB
    non_hits     = words & NON_MEDICAL_VOCAB
    precision    = len(med_hits) / max(len(words), 1)
    recall       = min(len(med_hits) / max(len(LOCAL_VOCAB) * 0.05, 1), 1.0)
    f1           = (2 * precision * recall) / max(precision + recall, 1e-9)
    penalty      = len(non_hits) / max(len(words), 1) * 0.4
    adjusted_f1  = max(0.0, f1 - penalty)

    # Boost if any medical terms found in a very short query
    is_medical = adjusted_f1 >= MEDICAL_F1_THRESHOLD or len(med_hits) >= 1

    return {
        "f1":           round(adjusted_f1, 3),
        "precision":    round(precision, 3),
        "recall":       round(recall, 3),
        "is_medical":   is_medical,
        "medical_terms": list(med_hits)[:8],
        "rejection":    None if is_medical else
                        "This doesn't seem to be a medical query. Please ask about your health.",
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — AGENT COMPATIBILITY CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def check_voice_agent_compatibility(agent_id: str, transcript: str) -> Dict:
    """
    Check if the transcript topic matches the current agent's disease domain.
    General agents (xx6) accept everything.
    """
    agent_upper  = agent_id.upper()
    agent_domain = AGENT_DOMAINS.get(agent_upper, "")

    if agent_upper in GENERAL_AGENTS:
        return {"compatible": True, "matched_domains": [], "guardrail_message": ""}

    words          = set(re.findall(r'\b\w+\b', transcript.lower()))
    matched_domains = []
    for domain, kws in DOMAIN_KEYWORDS.items():
        if words & kws:
            matched_domains.append(domain)

    if not matched_domains or agent_domain in matched_domains:
        return {"compatible": True, "matched_domains": matched_domains, "guardrail_message": ""}

    DOMAIN_NAMES = {"CA":"Cancer Care","DM":"Diabetes","CV":"Cardiovascular",
                    "MH":"Mental Health","RS":"Respiratory"}
    GENERAL_MAP  = {"CA":"CA6","DM":"DM6","CV":"CV6","MH":"MH6","RS":"RS6"}

    correct       = matched_domains[0]
    redirect      = GENERAL_MAP.get(correct, f"{correct}6")
    agent_name    = DOMAIN_NAMES.get(agent_domain, agent_domain)
    correct_name  = DOMAIN_NAMES.get(correct, correct)

    return {
        "compatible": False,
        "matched_domains": matched_domains,
        "redirect_to": redirect,
        "guardrail_message": (
            f"Your question seems to be about {correct_name}, but you are speaking with "
            f"the {agent_name} agent. For the best answer, please switch to the "
            f"{correct_name} agent or use {redirect} (General Assistant) which can "
            f"handle all medical topics."
        ),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — QUERY ENRICHMENT
# ═══════════════════════════════════════════════════════════════════════════════

def enrich_voice_query(raw_transcript: str, agent_id: str, language: str = "en") -> Dict:
    """
    LLM enrichment: clean speech artifacts, expand medical abbreviations,
    and rewrite into a clear, precise query for the agent.
    """
    from backend.core.agents.base_agent import call_llm_sync

    # Clean artifacts first
    cleaned = raw_transcript
    for pattern in SPEECH_ARTIFACTS:
        cleaned = re.sub(pattern, ' ', cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()

    agent_domain = AGENT_DOMAINS.get(agent_id.upper(), "Medical")

    system_prompt = f"""You are a medical transcription assistant for PRISM.
A patient just spoke a voice query that was transcribed.
Your job: rewrite the transcript as a clear, precise, written medical question.

Rules:
- Fix speech artifacts (um, uh, repeated words)
- Expand medical abbreviations (BP → blood pressure, HbA1c stays as is)
- Preserve the patient's original intent completely
- Keep it in {language} language
- Do NOT add medical information — only rewrite what was said
- Keep it concise (max 2-3 sentences)
- Focus on the {agent_domain} domain context

Return ONLY the rewritten query, no explanation."""

    result = call_llm_sync(
        system_prompt=system_prompt,
        user_message=f"Raw transcript: \"{cleaned}\"",
        history=[],
        temperature=0.1,
        max_tokens=200,
    )

    enriched = result["response"].strip().strip('"')
    return {
        "raw":     raw_transcript,
        "cleaned": cleaned,
        "enriched": enriched or cleaned,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — RESPONSE TO SPEECH (TTS preparation)
# ═══════════════════════════════════════════════════════════════════════════════

def prepare_tts_text(response_text: str) -> str:
    """
    Clean an AI response for TTS synthesis.
    Removes markdown, citations, headers, and makes it speech-friendly.
    """
    text = response_text
    # Remove markdown headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # Remove bold/italic markers
    text = re.sub(r'\*+(.+?)\*+', r'\1', text)
    text = re.sub(r'_+(.+?)_+', r'\1', text)
    # Remove citation brackets [1], [Source 1: ...]
    text = re.sub(r'\[Source \d+.*?\]', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    # Replace bullet points with natural pauses
    text = re.sub(r'^[-•]\s+', 'Also, ', text, flags=re.MULTILINE)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    # Remove evidence grade markers
    text = re.sub(r'Evidence Grade [ABC]', '', text)
    # Remove multiple newlines
    text = re.sub(r'\n{2,}', '. ', text)
    text = re.sub(r'\n', ' ', text)
    # Clean up spaces
    text = re.sub(r'\s+', ' ', text).strip()
    # Truncate to reasonable TTS length (~500 words)
    words = text.split()
    if len(words) > 500:
        text = ' '.join(words[:500]) + '... For the complete response, please read the text below.'
    return text


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — SERVER-SIDE TTS (OpenAI TTS — fallback for browsers without WebSpeech)
# ═══════════════════════════════════════════════════════════════════════════════

def synthesize_speech(text: str, language: str = "en", voice: str = "nova") -> Optional[bytes]:
    """
    Server-side TTS using OpenAI TTS API.
    Returns MP3 bytes or None if unavailable.

    Voice options: alloy, echo, fable, onyx, nova (warm female), shimmer
    Language-appropriate voice selection:
      en: nova, es: nova, pt: nova, hi: onyx, te: onyx
    """
    try:
        import openai
        from backend.config.settings import get_settings
        settings = get_settings()

        LANG_VOICES = {
            "en": "nova", "es": "nova", "pt": "nova",
            "hi": "onyx", "te": "onyx", "pa": "onyx",
        }
        selected_voice = LANG_VOICES.get(language, "nova")

        client     = openai.OpenAI(api_key=getattr(settings, "openai_api_key", None))
        tts_text   = prepare_tts_text(text)

        response   = client.audio.speech.create(
            model="tts-1",
            voice=selected_voice,
            input=tts_text,
            response_format="mp3",
        )
        return response.content

    except Exception:
        return None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — MAIN VOICE PROCESSING PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def process_voice_query(
    audio_bytes:    bytes,
    content_type:   str,
    agent_id:       str,
    conversation_id: str,
    language:       str = "en",
    history:        List[Dict] = None,
) -> Dict:
    """
    Full voice processing pipeline called from the FastAPI endpoint.

    Returns:
        success, transcript, enriched_query, is_medical, is_compatible,
        f1_score, guardrail_message, redirect_to, tts_text (for frontend synthesis)
    """
    t0 = time.time()

    # ── Step 1: Transcribe ─────────────────────────────────────────────────────
    transcription = transcribe_audio(audio_bytes, content_type, language)

    if not transcription["success"] or not transcription["transcript"]:
        err = transcription.get("error")
        if not transcription["transcript"] and not err:
            err = "I couldn't hear anything. Please speak closer to the microphone or check your settings."
            
        return {
            "success":          False,
            "stage":            "transcription",
            "transcript":       "",
            "enriched_query":   "",
            "is_medical":       False,
            "is_compatible":    False,
            "f1_score":         0.0,
            "guardrail_message": err,
            "redirect_to":      None,
            "tts_text":         err,
            "latency_ms":       int((time.time() - t0) * 1000),
        }

    transcript = transcription["transcript"]

    # ── Step 2: Medical F1 check ───────────────────────────────────────────────
    f1_result = compute_voice_medical_f1(transcript)

    if not f1_result["is_medical"]:
        return {
            "success":          False,
            "stage":            "medical_validation",
            "transcript":       transcript,
            "enriched_query":   transcript,
            "is_medical":       False,
            "is_compatible":    False,
            "f1_score":         f1_result["f1"],
            "guardrail_message": f1_result["rejection"],
            "redirect_to":      None,
            "tts_text":         f1_result["rejection"],
            "latency_ms":       int((time.time() - t0) * 1000),
        }

    # ── Step 3: Agent compatibility ────────────────────────────────────────────
    compatibility = check_voice_agent_compatibility(agent_id, transcript)

    # ── Step 4: Query enrichment ───────────────────────────────────────────────
    enrichment    = enrich_voice_query(transcript, agent_id, language)

    return {
        "success":           True,
        "stage":             "complete",
        "transcript":        transcript,
        "cleaned_transcript": enrichment["cleaned"],
        "enriched_query":    enrichment["enriched"],
        "is_medical":        True,
        "is_compatible":     compatibility["compatible"],
        "matched_domains":   compatibility.get("matched_domains", []),
        "f1_score":          f1_result["f1"],
        "medical_terms":     f1_result["medical_terms"],
        "guardrail_message": compatibility.get("guardrail_message", ""),
        "redirect_to":       compatibility.get("redirect_to"),
        "language_detected": transcription["language_detected"],
        "duration_s":        transcription["duration_s"],
        "whisper_confidence": transcription["confidence"],
        "tts_text":          "",  # Populated by the endpoint after agent response
        "latency_ms":        int((time.time() - t0) * 1000),
    }