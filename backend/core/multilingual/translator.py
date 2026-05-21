# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/multilingual/translator.py
# PRISM Multilingual Translation Service
# ───────────────────────────────────────────────────────────────────────────────
# SUPPORTED LANGUAGES:
#   en  — English       (default, no translation)
#   hi  — Hindi         हिंदी
#   te  — Telugu        తెలుగు
#   es  — Spanish       Español
#   pa  — Punjabi       ਪੰਜਾਬੀ
#
# PIPELINE PER MESSAGE:
#   1. Detect language & transliteration mode (Roman script → native intent)
#   2. Convert Romanised input → native script (if needed)
#   3. Translate to English for RAG / LLM processing
#   4. LLM generates English answer
#   5. Translate answer → patient's chosen language + native script
#
# TRANSLATION ENGINE: Claude (primary) → Google Translate (fallback)
# MEDICAL TERMS: preserved in English inside brackets [like this]
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

class PRISMTranslator:
    """Backward compatibility class for legacy imports."""
    @staticmethod
    def translate(text: str, src: str = "en", tgt: str = "en") -> str:
        return translate_text(text, src, tgt)
    
    @staticmethod
    def detect(text: str) -> str:
        return detect_language(text)

import re
import json
import time
import hashlib
from typing import Dict, Optional, List, Tuple
from functools import lru_cache

# ─── Language Configuration ────────────────────────────────────────────────────
SUPPORTED_LANGUAGES: Dict[str, Dict] = {
    "en": {
        "name":        "English",
        "native_name": "English",
        "flag":        "🇬🇧",
        "script":      "latin",
        "bcp47":       "en-US",
        "rtl":         False,
        "greeting":    "Hello! How can I help you today?",
        "transliteration_hint": "Type in English",
    },
    "hi": {
        "name":        "Hindi",
        "native_name": "हिंदी",
        "flag":        "🇮🇳",
        "script":      "devanagari",
        "bcp47":       "hi-IN",
        "rtl":         False,
        "greeting":    "नमस्ते! मैं आपकी कैसे मदद कर सकता हूँ?",
        "transliteration_hint": "हिंदी में लिखें या Roman अक्षरों में टाइप करें (e.g. mujhe chest mein dard hai)",
    },
    "te": {
        "name":        "Telugu",
        "native_name": "తెలుగు",
        "flag":        "🇮🇳",
        "script":      "telugu",
        "bcp47":       "te-IN",
        "rtl":         False,
        "greeting":    "నమస్కారం! నేను మీకు ఎలా సహాయం చేయగలను?",
        "transliteration_hint": "తెలుగులో టైప్ చేయండి లేదా Roman లో రాయండి (e.g. naku chest lo noppi undi)",
    },
    "es": {
        "name":        "Spanish",
        "native_name": "Español",
        "flag":        "🇲🇽",
        "script":      "latin",
        "bcp47":       "es-MX",
        "rtl":         False,
        "greeting":    "¡Hola! ¿Cómo puedo ayudarte hoy?",
        "transliteration_hint": "Escribe en español (e.g. tengo dolor en el pecho)",
    },
    "pa": {
        "name":        "Punjabi",
        "native_name": "ਪੰਜਾਬੀ",
        "flag":        "🇮🇳",
        "script":      "gurmukhi",
        "bcp47":       "pa-IN",
        "rtl":         False,
        "greeting":    "ਸਤ ਸ੍ਰੀ ਅਕਾਲ! ਮੈਂ ਤੁਹਾਡੀ ਕਿਵੇਂ ਮਦਦ ਕਰ ਸਕਦਾ ਹਾਂ?",
        "transliteration_hint": "ਪੰਜਾਬੀ ਵਿੱਚ ਲਿਖੋ ਜਾਂ Roman ਵਿੱਚ ਟਾਈਪ ਕਰੋ (e.g. mera sugar level bahut zyada hai)",
    },
}

# ─── Medical terms to preserve across translation ──────────────────────────────
PRESERVE_MEDICAL_TERMS = [
    "HbA1c", "BMI", "ECG", "EKG", "MRI", "CT", "IV", "IM", "SC",
    "mg/dL", "mmol/L", "mmHg", "bpm", "SpO2", "FEV1", "FVC",
    "PHQ-9", "GAD-7", "PCL-5", "GINA", "GOLD", "NCCN", "ADA",
    "COVID-19", "HIV", "DNA", "RNA", "PCR",
]

# ─── Romanised keyword banks for language detection ────────────────────────────
ROMANISED_HINTS: Dict[str, List[str]] = {
    "hi": [
        "mujhe", "mera", "meri", "mere", "hai", "hain", "tha", "thi",
        "kya", "kyun", "kaise", "bahut", "nahi", "aur", "bhi", "se",
        "ko", "ka", "ki", "ke", "par", "dard", "bimari", "dawai",
        "doctor", "khoon", "peshab", "seena", "pet", "sir", "bukhar",
        "sugar", "bp", "dil", "sans", "thakan", "neend", "khana",
    ],
    "te": [
        "naku", "nenu", "meeru", "mee", "ayindi", "undi", "unnanu",
        "cheyyadam", "cheppandi", "noppi", "vyadhi", "marundhu",
        "doctor", "netti", "rakt", "mootu", "cheyyi", "potta",
        "tala", "jvaram", "madhu", "bp", "gundelu", "upiriti",
        "neela", "nidra", "tindi", "kaadu", "avunu", "ela",
    ],
    "pa": [
        "mera", "meri", "mere", "sanu", "saade", "hai", "han",
        "ki", "kive", "kyon", "bahut", "nahi", "te", "de", "di",
        "da", "nu", "dard", "bimari", "dawai", "doctor", "lahu",
        "sugar", "bp", "dil", "sas", "thakan", "neend", "khana",
        "zyada", "ghabhat", "takleef", "pet", "sir", "bukhar",
    ],
    "es": [
        "tengo", "tengo", "siento", "me duele", "dolor", "estoy",
        "tiene", "quiero", "necesito", "puedo", "como", "cuando",
        "porque", "pero", "muy", "mucho", "poco", "también", "no",
        "si", "sí", "qué", "cuál", "cómo", "cuándo", "por qué",
        "médico", "medicina", "pastilla", "azúcar", "corazón",
    ],
}

# Simple in-memory translation cache (keyed by hash of text+lang)
_CACHE: Dict[str, Dict] = {}
CACHE_MAX = 500


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — LANGUAGE & TRANSLITERATION DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_language(text: str) -> str:
    """
    Detect the language of input text.
    Returns ISO 639-1 code: 'en', 'hi', 'te', 'es', 'pa'
    """
    if not text or len(text.strip()) < 2:
        return "en"

    # 1. Unicode script detection (Reliable)
    for char in text:
        cp = ord(char)
        if 0x0900 <= cp <= 0x097F:   return "hi"   # Devanagari
        if 0x0C00 <= cp <= 0x0C7F:   return "te"   # Telugu
        if 0x0A00 <= cp <= 0x0A7F:   return "pa"   # Gurmukhi
        if 0x00C0 <= cp <= 0x024F:   return "es"   # Extended Latin (ñ, é, etc.)

    # 2. Romanised language detection via keyword banks (Heuristic)
    # Use exact word boundaries to avoid matching substrings in English words (e.g. "se" in "glucose")
    words = set(re.findall(r'\b\w+\b', text.lower()))
    scores: Dict[str, int] = {}
    
    for lang, hints in ROMANISED_HINTS.items():
        # Exact word matches only
        matches = [w for w in words if w in hints]
        if len(matches) >= 2: # Require at least 2 matching keywords for confidence
            scores[lang] = len(matches)

    if scores:
        best = max(scores, key=scores.__getitem__)
        return best

    return "en"


def is_romanised_input(text: str, target_lang: str) -> bool:
    """
    Returns True if the text is written in Latin/Roman script
    but the target language uses a non-Latin script.
    """
    non_latin_langs = {"hi", "te", "pa"}
    if target_lang not in non_latin_langs:
        return False

    # Count Latin vs non-Latin characters
    latin_count = sum(1 for c in text if ord(c) < 0x0250 and c.isalpha())
    total_alpha  = sum(1 for c in text if c.isalpha())
    if total_alpha == 0:
        return False
    return (latin_count / total_alpha) > 0.7   # >70% Latin chars


def get_language_config(lang_code: str) -> Dict:
    """Get full language configuration dict."""
    return SUPPORTED_LANGUAGES.get(lang_code, SUPPORTED_LANGUAGES["en"])


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — CLAUDE-POWERED TRANSLATION ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def _cache_key(text: str, src: str, tgt: str) -> str:
    return hashlib.md5(f"{src}:{tgt}:{text[:200]}".encode()).hexdigest()


def translate_with_claude(
    text:     str,
    src_lang: str,
    tgt_lang: str,
    context:  str = "medical",
    is_response: bool = False,
) -> str:
    """
    Translate text using Claude.
    Medical context is preserved: drug names, values, units stay in English.
    Romanised input is first converted to native script then translated.
    """
    if src_lang == tgt_lang:
        return text
    if not text or len(text.strip()) < 2:
        return text

    # Check cache
    ck = _cache_key(text, src_lang, tgt_lang)
    if ck in _CACHE:
        return _CACHE[ck]["translated"]

    from backend.core.agents.base_agent import call_llm_sync

    LANG_NAMES = {
        "en": "English", "hi": "Hindi (Devanagari script)",
        "te": "Telugu (Telugu script)", "es": "Spanish",
        "pa": "Punjabi (Gurmukhi script)",
    }
    src_name = LANG_NAMES.get(src_lang, src_lang)
    tgt_name = LANG_NAMES.get(tgt_lang, tgt_lang)

    # Detect if input is Romanised (e.g., typing Hindi in English keyboard)
    roman_mode = is_romanised_input(text, src_lang) if src_lang != "en" else False

    if roman_mode:
        # First convert Romanised → native script → then translate to target
        system_prompt = f"""You are a multilingual medical translation expert for PRISM AI.

TASK: The patient typed in Roman/English keyboard but intended to write in {src_name}.
Step 1: Convert the Romanised text to proper {src_name} native script.
Step 2: Translate the native script version to {tgt_name}.

RULES:
- Medical terms: keep in English inside the translation (e.g., HbA1c, blood pressure, mg/dL)
- Drug names: always keep in English
- Numbers and units: keep as-is
- Tone: warm, patient-friendly, clinical but accessible
- Return ONLY the final {tgt_name} translation, nothing else"""

        user_message = f"Romanised {src_name} text: \"{text}\""

    elif is_response:
        # Translating AI response to patient's language — full medical translation
        system_prompt = f"""You are a medical translation expert for PRISM AI.

TASK: Translate this {src_name} medical response into {tgt_name}.

CRITICAL RULES:
1. Medical terms to keep in English (do NOT translate): {', '.join(PRESERVE_MEDICAL_TERMS[:15])}
2. Drug names: ALWAYS keep in English
3. Numbers, units (mg/dL, mmHg, %): keep as-is
4. Evidence grades (A/B/C): keep as-is
5. Maintain all formatting (bullet points, numbered lists, bold markers **)
6. Tone: warm, empathetic, patient-friendly
7. If {tgt_name} uses a non-Latin script, use ONLY that script (no Romanisation)
8. Do NOT add explanations — return ONLY the translated text

Return ONLY the {tgt_name} translation."""

        user_message = text

    else:
        # Translating patient query to English for RAG
        system_prompt = f"""You are a medical translation expert for PRISM AI.

TASK: Translate this {src_name} patient query to {tgt_name}.

RULES:
- Preserve the patient's exact medical intent
- Keep medical terms, drug names, values in English
- Translate conversational parts naturally
- Return ONLY the {tgt_name} text, no explanation"""

        user_message = f"Translate to {tgt_name}: \"{text}\""

    result = call_llm_sync(
        system_prompt=system_prompt,
        user_message=user_message,
        history=[],
        temperature=0.05,      # Low temperature for accuracy
        max_tokens=1500,
    )

    translated = result["response"].strip().strip('"')

    # Cache the result
    if len(_CACHE) >= CACHE_MAX:
        oldest = next(iter(_CACHE))
        del _CACHE[oldest]
    _CACHE[ck] = {"translated": translated, "ts": time.time()}

    return translated


def translate_text(text: str, src: str = "en", tgt: str = "en") -> str:
    """Public translate function — wraps Claude translation with Google fallback."""
    if src == tgt or not text:
        return text
    try:
        return translate_with_claude(text, src, tgt)
    except Exception:
        try:
            return _google_translate_fallback(text, src, tgt)
        except Exception:
            return text


def translate_response(text: str, tgt_lang: str) -> str:
    """Translate an AI-generated response to the patient's language."""
    if tgt_lang == "en" or not text:
        return text
    try:
        return translate_with_claude(text, "en", tgt_lang, is_response=True)
    except Exception:
        return text


def _google_translate_fallback(text: str, src: str, tgt: str) -> str:
    """
    Google Translate fallback via requests (no SDK needed).
    Uses the free web endpoint — for production use the Cloud Translation API.
    """
    try:
        import urllib.request, urllib.parse
        url = (
            f"https://translate.googleapis.com/translate_a/single"
            f"?client=gtx&sl={src}&tl={tgt}&dt=t&q={urllib.parse.quote(text[:4000])}"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            parts = data[0]
            return "".join(p[0] for p in parts if p[0])
    except Exception:
        return text


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — ROMANISED INPUT CONVERTER
# ═══════════════════════════════════════════════════════════════════════════════

def convert_romanised_to_native(romanised_text: str, target_lang: str) -> str:
    """
    Convert Roman-script input into native script using Claude.
    Used when patient types Hindi/Telugu/Punjabi using English keyboard.

    Example: "mujhe seene mein dard hai" → "मुझे सीने में दर्द है"
    Example: "naku chest lo noppi undi" → "నాకు ఛేస్ట్ లో నొప్పి ఉంది"
    """
    if not is_romanised_input(romanised_text, target_lang):
        return romanised_text

    from backend.core.agents.base_agent import call_llm_sync

    LANG_NAMES = {
        "hi": "Hindi Devanagari",
        "te": "Telugu script",
        "pa": "Punjabi Gurmukhi",
    }
    script_name = LANG_NAMES.get(target_lang, target_lang)

    result = call_llm_sync(
        system_prompt=(
            f"You are a transliteration engine. Convert the following Romanised text "
            f"to {script_name}. Keep medical terms, drug names, and numbers in English. "
            f"Return ONLY the {script_name} text, nothing else."
        ),
        user_message=romanised_text,
        history=[],
        temperature=0.05,
        max_tokens=400,
    )
    return result["response"].strip()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — FULL MULTILINGUAL PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

def process_multilingual_input(
    user_message:    str,
    selected_lang:   str,
    conversation_history: List[Dict] = None,
) -> Dict:
    """
    Process patient input through the full multilingual pipeline.

    Returns:
        english_query:    str  — translated to English for RAG/LLM
        native_display:   str  — patient's input in native script (for display)
        detected_lang:    str  — detected language code
        is_romanised:     bool — True if patient typed using Roman keyboard
        selected_lang:    str  — the language patient chose
    """
    # Detect actual language
    detected = detect_language(user_message)

    # ── Determine Effective Language ───────────────────────────────────────────
    # We respect the selected_lang more strictly to avoid false positive switches.
    
    # Check if input contains non-Latin script (reliable indicator)
    has_native_script = False
    for char in user_message:
        cp = ord(char)
        if (0x0900 <= cp <= 0x097F) or (0x0C00 <= cp <= 0x0C7F) or (0x0A00 <= cp <= 0x0A7F):
            has_native_script = True
            break

    if selected_lang == "en":
        # If English is selected, only switch if we see native script.
        # This prevents Romanised detection (which is heuristic) from overriding explicit selection.
        effective_lang = detected if has_native_script else "en"
    else:
        # If a specific local language is selected, trust that choice.
        effective_lang = selected_lang

    # ── Transliteration & Translation ──────────────────────────────────────────
    
    # Check for romanised input
    romanised = is_romanised_input(user_message, effective_lang)

    # Convert romanised to native script for display
    native_display = user_message
    if romanised and effective_lang in ("hi", "te", "pa"):
        native_display = convert_romanised_to_native(user_message, effective_lang)

    # Translate to English for processing
    english_query = user_message
    if effective_lang != "en":
        english_query = translate_text(
            native_display if romanised else user_message,
            src=effective_lang,
            tgt="en",
        )

    return {
        "english_query":  english_query,
        "native_display": native_display,
        "detected_lang":  detected,
        "selected_lang":  selected_lang,
        "effective_lang": effective_lang,
        "is_romanised":   romanised,
        "original":       user_message,
    }


def process_multilingual_response(
    english_response: str,
    target_lang:      str,
) -> Dict:
    """
    Translate an English AI response into the patient's language.

    Returns:
        translated:       str  — response in target language
        target_lang:      str  — language code
        lang_config:      dict — full language config
    """
    translated = translate_response(english_response, target_lang)
    return {
        "translated":  translated,
        "english":     english_response,
        "target_lang": target_lang,
        "lang_config": get_language_config(target_lang),
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — UTILITY FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def get_all_languages() -> List[Dict]:
    """Return list of all supported languages for the frontend selector."""
    return [
        {
            "code":             code,
            "name":             cfg["name"],
            "native_name":      cfg["native_name"],
            "flag":             cfg["flag"],
            "script":           cfg["script"],
            "bcp47":            cfg["bcp47"],
            "transliteration_hint": cfg["transliteration_hint"],
            "greeting":         cfg["greeting"],
        }
        for code, cfg in SUPPORTED_LANGUAGES.items()
    ]


def get_ui_strings(lang: str) -> Dict:
    """
    Return UI strings in the patient's language for a fully localised interface.
    """
    STRINGS: Dict[str, Dict] = {
        "en": {
            "placeholder":     "Type your medical question…",
            "send":            "Send",
            "speak":           "Speak",
            "scan":            "Scan Image",
            "thinking":        "PRISM is thinking…",
            "disclaimer":      "Not a substitute for professional medical advice.",
            "language_label":  "Language",
            "rate_response":   "Rate this response",
            "request_prescription": "Request prescription",
            "skip":            "Skip → Just answer",
            "question_of":     "Question {n} of {max}",
            "feedback_thanks": "Thank you for your feedback!",
        },
        "hi": {
            "placeholder":     "अपना स्वास्थ्य संबंधी प्रश्न टाइप करें…",
            "send":            "भेजें",
            "speak":           "बोलें",
            "scan":            "छवि स्कैन करें",
            "thinking":        "PRISM सोच रहा है…",
            "disclaimer":      "यह पेशेवर चिकित्सा सलाह का विकल्प नहीं है।",
            "language_label":  "भाषा",
            "rate_response":   "इस उत्तर को रेटिंग दें",
            "request_prescription": "प्रिस्क्रिप्शन का अनुरोध करें",
            "skip":            "छोड़ें → सीधे उत्तर दें",
            "question_of":     "प्रश्न {n} / {max}",
            "feedback_thanks": "आपकी प्रतिक्रिया के लिए धन्यवाद!",
        },
        "te": {
            "placeholder":     "మీ వైద్య ప్రశ్నను టైప్ చేయండి…",
            "send":            "పంపండి",
            "speak":           "మాట్లాడండి",
            "scan":            "చిత్రం స్కాన్ చేయండి",
            "thinking":        "PRISM ఆలోచిస్తోంది…",
            "disclaimer":      "ఇది వృత్తిపరమైన వైద్య సలహాకు ప్రత్యామ్నాయం కాదు.",
            "language_label":  "భాష",
            "rate_response":   "ఈ సమాధానాన్ని రేట్ చేయండి",
            "request_prescription": "ప్రిస్క్రిప్షన్ అభ్యర్థించండి",
            "skip":            "దాటవేయి → సమాధానం చెప్పు",
            "question_of":     "ప్రశ్న {n} / {max}",
            "feedback_thanks": "మీ అభిప్రాయానికి ధన్యవాదాలు!",
        },
        "es": {
            "placeholder":     "Escribe tu pregunta médica…",
            "send":            "Enviar",
            "speak":           "Hablar",
            "scan":            "Escanear imagen",
            "thinking":        "PRISM está pensando…",
            "disclaimer":      "No sustituye el consejo médico profesional.",
            "language_label":  "Idioma",
            "rate_response":   "Califica esta respuesta",
            "request_prescription": "Solicitar receta",
            "skip":            "Saltar → Responder ahora",
            "question_of":     "Pregunta {n} de {max}",
            "feedback_thanks": "¡Gracias por tu opinión!",
        },
        "pa": {
            "placeholder":     "ਆਪਣਾ ਡਾਕਟਰੀ ਸਵਾਲ ਟਾਈਪ ਕਰੋ…",
            "send":            "ਭੇਜੋ",
            "speak":           "ਬੋਲੋ",
            "scan":            "ਤਸਵੀਰ ਸਕੈਨ ਕਰੋ",
            "thinking":        "PRISM ਸੋਚ ਰਿਹਾ ਹੈ…",
            "disclaimer":      "ਇਹ ਪੇਸ਼ੇਵਰ ਡਾਕਟਰੀ ਸਲਾਹ ਦਾ ਬਦਲ ਨਹੀਂ ਹੈ।",
            "language_label":  "ਭਾਸ਼ਾ",
            "rate_response":   "ਇਸ ਜਵਾਬ ਨੂੰ ਰੇਟ ਕਰੋ",
            "request_prescription": "ਨੁਸਖਾ ਮੰਗੋ",
            "skip":            "ਛੱਡੋ → ਸਿੱਧਾ ਜਵਾਬ ਦਿਓ",
            "question_of":     "ਸਵਾਲ {n} / {max}",
            "feedback_thanks": "ਤੁਹਾਡੀ ਰਾਏ ਲਈ ਧੰਨਵਾਦ!",
        },
    }
    return STRINGS.get(lang, STRINGS["en"])