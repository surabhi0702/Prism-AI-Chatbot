# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/multimodal/visual_intent_detector.py
# PRISM Visual Intent Detector — 40 Medical Visual Intents Across 5 Diseases
# ───────────────────────────────────────────────────────────────────────────────
# Detects when a patient's query would benefit from image or video generation.
# Uses fast keyword matching first; LLM fallback for ambiguous cases.
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import re
from typing import Dict, List, Optional, Tuple

# ─── Supported media types ────────────────────────────────────────────────────
MEDIA_IMAGE = "image"
MEDIA_VIDEO = "video"
MEDIA_BOTH  = "both"

# ─── Prompt style categories ──────────────────────────────────────────────────
STYLE_MEDICAL_ILLUSTRATION  = "medical_illustration"
STYLE_INSTRUCTIONAL_DIAGRAM = "instructional_diagram"
STYLE_NUTRITION_INFOGRAPHIC = "nutrition_infographic"
STYLE_DATA_INFOGRAPHIC      = "data_infographic"
STYLE_SYMPTOM_DIAGRAM       = "symptom_diagram"
STYLE_ANATOMICAL_DIAGRAM    = "anatomical_diagram"
STYLE_AWARENESS_INFOGRAPHIC = "awareness_infographic"
STYLE_SCHEDULE_DIAGRAM      = "schedule_diagram"
STYLE_CONCEPTUAL_DIAGRAM    = "conceptual_diagram"
STYLE_SCIENCE_DIAGRAM       = "science_diagram"
STYLE_GUIDED_EXERCISE       = "guided_exercise"


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — VISUAL INTENT TAXONOMY (40 intents)
# ═══════════════════════════════════════════════════════════════════════════════

VISUAL_INTENTS: Dict[str, Dict] = {

    # ── DIABETES (DM) — 8 intents ─────────────────────────────────────────────
    "DM_INSULIN_INJECTION": {
        "label":       "Insulin injection technique",
        "media":       MEDIA_BOTH,
        "video_dur_s": 45,
        "style":       STYLE_MEDICAL_ILLUSTRATION,
        "agents":      ["DM2", "DM6"],
        "guardrail":   "no_blood",
        "triggers":    [
            "inject insulin", "insulin injection", "how to inject", "injection site",
            "subcutaneous", "fatty tissue", "abdomen injection", "thigh injection",
            "pinch technique", "needle angle", "insulin pen", "syringe technique",
        ],
        "negative_triggers": ["oral insulin", "inhaled insulin"],
    },
    "DM_BLOOD_GLUCOSE_MONITOR": {
        "label":       "Glucometer / finger-prick blood test",
        "media":       MEDIA_BOTH,
        "video_dur_s": 30,
        "style":       STYLE_INSTRUCTIONAL_DIAGRAM,
        "agents":      ["DM1", "DM6"],
        "guardrail":   "none",
        "triggers":    [
            "check blood sugar", "glucometer", "blood glucose test", "finger prick",
            "how to test", "blood test strip", "lancet", "glucose reading",
            "home blood test", "prick finger",
        ],
    },
    "DM_CGM_PLACEMENT": {
        "label":       "CGM sensor placement guide",
        "media":       MEDIA_BOTH,
        "video_dur_s": 30,
        "style":       STYLE_MEDICAL_ILLUSTRATION,
        "agents":      ["DM1"],
        "guardrail":   "none",
        "triggers":    [
            "cgm sensor", "continuous glucose monitor", "freestyle libre", "dexcom",
            "sensor placement", "where to place sensor", "insert sensor", "cgm site",
            "apply cgm", "cgm applicator",
        ],
    },
    "DM_DIABETES_PLATE": {
        "label":       "Diabetes plate method",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_NUTRITION_INFOGRAPHIC,
        "agents":      ["DM3"],
        "guardrail":   "none",
        "triggers":    [
            "plate method", "diabetes diet", "what to eat", "portion size",
            "diabetes plate", "meal plan visual", "food portions", "diabetic meal",
            "carbohydrate portion", "healthy eating diabetes",
        ],
    },
    "DM_FOOT_EXAMINATION": {
        "label":       "Diabetic foot care routine",
        "media":       MEDIA_BOTH,
        "video_dur_s": 30,
        "style":       STYLE_INSTRUCTIONAL_DIAGRAM,
        "agents":      ["DM4"],
        "guardrail":   "none",
        "triggers":    [
            "foot care", "check my feet", "diabetic foot", "foot examination",
            "inspect feet", "foot sore", "foot moisturiser", "nail care diabetes",
            "neuropathy foot care", "callus diabetes",
        ],
    },
    "DM_HYPOGLYCEMIA_SIGNS": {
        "label":       "Hypoglycaemia warning signs",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_SYMPTOM_DIAGRAM,
        "agents":      ["DM1", "DM6"],
        "guardrail":   "none",
        "triggers":    [
            "low blood sugar symptoms", "hypoglycemia signs", "hypo symptoms",
            "low sugar warning", "shaking dizziness", "signs of low sugar",
            "hypoglycaemia symptoms", "sugar drop symptoms",
        ],
    },
    "DM_HBA1C_CHART": {
        "label":       "HbA1c target range chart",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_DATA_INFOGRAPHIC,
        "agents":      ["DM1", "DM6"],
        "guardrail":   "none",
        "triggers":    [
            "hba1c chart", "hba1c levels", "hba1c range", "what is hba1c",
            "a1c normal range", "hba1c targets", "a1c chart", "hba1c scale",
        ],
    },
    "DM_EXERCISE_SAFETY": {
        "label":       "Safe exercise for diabetes",
        "media":       MEDIA_BOTH,
        "video_dur_s": 45,
        "style":       STYLE_INSTRUCTIONAL_DIAGRAM,
        "agents":      ["DM3"],
        "guardrail":   "none",
        "triggers":    [
            "exercise with diabetes", "safe exercise", "workout diabetes",
            "physical activity diabetes", "exercise blood sugar", "gym diabetes",
            "walking diabetes", "exercise plan diabetic",
        ],
    },

    # ── CARDIOVASCULAR (CV) — 8 intents ───────────────────────────────────────
    "CV_CPR_TECHNIQUE": {
        "label":       "CPR hand placement & technique",
        "media":       MEDIA_BOTH,
        "video_dur_s": 60,
        "style":       STYLE_MEDICAL_ILLUSTRATION,
        "agents":      ["CV2"],
        "guardrail":   "none",
        "triggers":    [
            "cpr technique", "how to do cpr", "chest compressions", "cardiopulmonary",
            "resuscitation", "cardiac arrest steps", "cpr hand placement",
            "rescue breathing", "cpr ratio", "how to save someone",
        ],
    },
    "CV_HEART_ANATOMY": {
        "label":       "Heart anatomy cross-section",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_ANATOMICAL_DIAGRAM,
        "agents":      ["CV1"],
        "guardrail":   "none",
        "triggers":    [
            "heart anatomy", "heart diagram", "heart chambers", "cardiac anatomy",
            "how does heart work", "heart structure", "heart valves diagram",
            "coronary arteries diagram",
        ],
    },
    "CV_BP_MEASUREMENT": {
        "label":       "Blood pressure measurement technique",
        "media":       MEDIA_BOTH,
        "video_dur_s": 30,
        "style":       STYLE_INSTRUCTIONAL_DIAGRAM,
        "agents":      ["CV1"],
        "guardrail":   "none",
        "triggers":    [
            "how to measure blood pressure", "bp measurement", "blood pressure cuff",
            "sphygmomanometer", "check blood pressure", "how to use bp monitor",
            "blood pressure correct technique",
        ],
    },
    "CV_STROKE_FAST": {
        "label":       "FAST stroke recognition guide",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_AWARENESS_INFOGRAPHIC,
        "agents":      ["CV2"],
        "guardrail":   "none",
        "triggers":    [
            "stroke signs", "stroke fast", "recognize stroke", "stroke symptoms",
            "face drooping", "stroke warning signs", "act fast stroke", "is it a stroke",
        ],
    },
    "CV_HEART_RATE_ZONES": {
        "label":       "Target heart rate zones chart",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_DATA_INFOGRAPHIC,
        "agents":      ["CV4"],
        "guardrail":   "none",
        "triggers":    [
            "heart rate zones", "target heart rate", "exercise heart rate",
            "aerobic zone", "fat burning zone", "maximum heart rate",
            "heart rate chart", "cardio zones",
        ],
    },
    "CV_CARDIAC_DIET": {
        "label":       "Heart-healthy food plate",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_NUTRITION_INFOGRAPHIC,
        "agents":      ["CV5"],
        "guardrail":   "none",
        "triggers":    [
            "heart healthy diet", "cardiac diet", "foods for heart", "heart healthy food",
            "mediterranean heart", "what to eat heart disease", "foods avoid heart",
        ],
    },
    "CV_MEDICATION_SCHEDULE": {
        "label":       "Cardiac medication timing schedule",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_SCHEDULE_DIAGRAM,
        "agents":      ["CV3"],
        "guardrail":   "none",
        "triggers":    [
            "medication schedule", "when to take pills", "pill timing", "medication chart",
            "heart medication timing", "beta blocker when to take", "statin timing",
        ],
    },
    "CV_ANGIOPLASTY": {
        "label":       "Angioplasty procedure overview",
        "media":       MEDIA_BOTH,
        "video_dur_s": 45,
        "style":       STYLE_MEDICAL_ILLUSTRATION,
        "agents":      ["CV1"],
        "guardrail":   "no_gore",
        "triggers":    [
            "angioplasty", "stent procedure", "balloon catheter", "how does stent work",
            "blocked artery treatment", "coronary intervention", "pci procedure",
        ],
    },

    # ── MENTAL HEALTH (MH) — 8 intents ───────────────────────────────────────
    "MH_478_BREATHING": {
        "label":       "4-7-8 breathing technique",
        "media":       MEDIA_BOTH,
        "video_dur_s": 30,
        "style":       STYLE_GUIDED_EXERCISE,
        "agents":      ["MH2", "MH3"],
        "guardrail":   "none",
        "triggers":    [
            "4-7-8 breathing", "breathing exercise", "breathe slowly", "calm breathing",
            "anxiety breathing", "breathing technique", "breathing for sleep",
            "box breathing", "diaphragm breathing anxiety", "inhale exhale exercise",
        ],
    },
    "MH_SLEEP_WINDOW": {
        "label":       "Sleep restriction window chart",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_SCHEDULE_DIAGRAM,
        "agents":      ["MH3"],
        "guardrail":   "none",
        "triggers":    [
            "sleep window", "sleep restriction", "sleep schedule chart",
            "cbti schedule", "bedtime chart", "sleep efficiency chart",
            "when to sleep", "sleep diary", "sleep timing",
        ],
    },
    "MH_PROGRESSIVE_RELAXATION": {
        "label":       "Progressive muscle relaxation",
        "media":       MEDIA_VIDEO,
        "video_dur_s": 60,
        "style":       STYLE_GUIDED_EXERCISE,
        "agents":      ["MH3", "MH2"],
        "guardrail":   "none",
        "triggers":    [
            "progressive muscle relaxation", "body scan", "muscle tension release",
            "relax my body", "pmr technique", "tense and release", "relaxation exercise",
        ],
    },
    "MH_GROUNDING_54321": {
        "label":       "5-4-3-2-1 grounding technique",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_AWARENESS_INFOGRAPHIC,
        "agents":      ["MH2", "MH4"],
        "guardrail":   "none",
        "triggers":    [
            "grounding technique", "5-4-3-2-1", "54321 method", "sensory grounding",
            "panic attack grounding", "anxiety grounding", "grounding exercise",
        ],
    },
    "MH_CBT_TRIANGLE": {
        "label":       "Cognitive triangle (CBT)",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_CONCEPTUAL_DIAGRAM,
        "agents":      ["MH1", "MH2"],
        "guardrail":   "none",
        "triggers":    [
            "cognitive triangle", "cbt thoughts feelings", "thought feeling behaviour",
            "cognitive model", "cbt diagram", "negative thought cycle",
        ],
    },
    "MH_CIRCADIAN_LIGHT": {
        "label":       "Circadian rhythm & light therapy chart",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_SCIENCE_DIAGRAM,
        "agents":      ["MH3"],
        "guardrail":   "none",
        "triggers":    [
            "circadian rhythm", "body clock", "light therapy", "melatonin chart",
            "sleep wake cycle", "circadian diagram", "morning light effect",
        ],
    },
    "MH_MOOD_SCALE": {
        "label":       "Mood / PHQ-9 visual scale",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_DATA_INFOGRAPHIC,
        "agents":      ["MH1"],
        "guardrail":   "none",
        "triggers":    [
            "phq-9", "mood scale", "depression scale", "mood chart", "mood tracker visual",
            "gad-7", "anxiety scale", "rate my mood", "mood rating",
        ],
    },
    "MH_STRESS_RESPONSE": {
        "label":       "Stress response pathway diagram",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_SCIENCE_DIAGRAM,
        "agents":      ["MH2"],
        "guardrail":   "none",
        "triggers":    [
            "stress response", "fight or flight", "cortisol response", "amygdala stress",
            "how stress works", "stress pathway", "physiological stress", "hpa axis",
        ],
    },

    # ── CANCER CARE (CA) — 8 intents ─────────────────────────────────────────
    "CA_BREAST_SELF_EXAM": {
        "label":       "Breast self-examination guide",
        "media":       MEDIA_BOTH,
        "video_dur_s": 45,
        "style":       STYLE_MEDICAL_ILLUSTRATION,
        "agents":      ["CA1"],
        "guardrail":   "clinical_only",
        "triggers":    [
            "breast self exam", "breast examination", "bse technique", "check breast",
            "breast lump", "breast self check", "how to examine breast",
        ],
    },
    "CA_CHEMO_CYCLE": {
        "label":       "Chemotherapy cycle timeline",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_SCHEDULE_DIAGRAM,
        "agents":      ["CA2"],
        "guardrail":   "none",
        "triggers":    [
            "chemo cycle", "chemotherapy schedule", "treatment timeline",
            "chemo rest days", "nadir chemotherapy", "chemo days", "cycle length chemo",
        ],
    },
    "CA_PORT_ACCESS": {
        "label":       "Port-a-cath access guide",
        "media":       MEDIA_BOTH,
        "video_dur_s": 30,
        "style":       STYLE_MEDICAL_ILLUSTRATION,
        "agents":      ["CA2", "CA3"],
        "guardrail":   "none",
        "triggers":    [
            "port access", "port-a-cath", "chemo port", "infusion port",
            "how does port work", "port needle", "access port chemotherapy",
        ],
    },
    "CA_CANCER_STAGES": {
        "label":       "Cancer staging guide (I–IV)",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_ANATOMICAL_DIAGRAM,
        "agents":      ["CA2"],
        "guardrail":   "none",
        "triggers":    [
            "cancer stages", "stage 1 2 3 4", "cancer staging", "what does stage mean",
            "cancer spread", "metastasis diagram", "tnm staging",
        ],
    },
    "CA_LYMPHEDEMA_MASSAGE": {
        "label":       "Lymphatic drainage massage",
        "media":       MEDIA_BOTH,
        "video_dur_s": 60,
        "style":       STYLE_MEDICAL_ILLUSTRATION,
        "agents":      ["CA3", "CA4"],
        "guardrail":   "none",
        "triggers":    [
            "lymphedema massage", "lymphatic drainage", "lymph massage", "mld technique",
            "swollen arm cancer", "lymph drainage how to", "drainage massage",
        ],
    },
    "CA_RADIATION_POSITIONING": {
        "label":       "Radiation therapy positioning",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_MEDICAL_ILLUSTRATION,
        "agents":      ["CA2"],
        "guardrail":   "none",
        "triggers":    [
            "radiation therapy", "radiotherapy position", "radiation treatment table",
            "radiation marks", "radiation setup", "linac radiotherapy",
        ],
    },
    "CA_NUTRITION_CANCER": {
        "label":       "Cancer treatment nutrition plate",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_NUTRITION_INFOGRAPHIC,
        "agents":      ["CA3"],
        "guardrail":   "none",
        "triggers":    [
            "cancer nutrition", "what to eat during chemo", "cancer diet", "food during treatment",
            "eating during chemotherapy", "cancer treatment food",
        ],
    },
    "CA_WOUND_CARE": {
        "label":       "Post-surgical wound care",
        "media":       MEDIA_BOTH,
        "video_dur_s": 30,
        "style":       STYLE_INSTRUCTIONAL_DIAGRAM,
        "agents":      ["CA3"],
        "guardrail":   "clinical_only",
        "triggers":    [
            "wound care", "surgical wound", "incision care", "dressing change",
            "post surgery care", "wound infection signs", "surgical site care",
        ],
    },

    # ── RESPIRATORY (RS) — 8 intents ─────────────────────────────────────────
    "RS_MDI_TECHNIQUE": {
        "label":       "MDI inhaler correct technique",
        "media":       MEDIA_BOTH,
        "video_dur_s": 45,
        "style":       STYLE_INSTRUCTIONAL_DIAGRAM,
        "agents":      ["RS1", "RS4"],
        "guardrail":   "none",
        "triggers":    [
            "how to use inhaler", "inhaler technique", "mdi technique", "puffer technique",
            "inhaler properly", "correct inhaler use", "spacer inhaler", "ventolin technique",
            "reliever inhaler how to", "preventer inhaler technique",
        ],
    },
    "RS_SPACER_USE": {
        "label":       "Spacer device with inhaler",
        "media":       MEDIA_BOTH,
        "video_dur_s": 30,
        "style":       STYLE_INSTRUCTIONAL_DIAGRAM,
        "agents":      ["RS1"],
        "guardrail":   "none",
        "triggers":    [
            "spacer device", "aerochamber", "spacer how to use", "spacer attachment",
            "inhaler with spacer", "chamber device",
        ],
    },
    "RS_PURSED_LIP": {
        "label":       "Pursed-lip breathing technique",
        "media":       MEDIA_BOTH,
        "video_dur_s": 30,
        "style":       STYLE_GUIDED_EXERCISE,
        "agents":      ["RS2", "RS3"],
        "guardrail":   "none",
        "triggers":    [
            "pursed lip breathing", "how to breathe copd", "slow breathing technique",
            "lips breathing", "controlled breathing copd", "breathing exercise copd",
        ],
    },
    "RS_PEAK_FLOW": {
        "label":       "Peak flow meter usage",
        "media":       MEDIA_BOTH,
        "video_dur_s": 20,
        "style":       STYLE_INSTRUCTIONAL_DIAGRAM,
        "agents":      ["RS1"],
        "guardrail":   "none",
        "triggers":    [
            "peak flow meter", "peak flow test", "how to use peak flow", "peak flow reading",
            "peak expiratory flow", "pefr meter",
        ],
    },
    "RS_CPAP_FITTING": {
        "label":       "CPAP mask fitting guide",
        "media":       MEDIA_BOTH,
        "video_dur_s": 45,
        "style":       STYLE_INSTRUCTIONAL_DIAGRAM,
        "agents":      ["RS5"],
        "guardrail":   "none",
        "triggers":    [
            "cpap mask", "cpap fitting", "sleep apnea mask", "cpap strap adjust",
            "nasal pillow mask", "full face mask cpap", "cpap seal", "bipap mask",
        ],
    },
    "RS_DIAPHRAGMATIC": {
        "label":       "Diaphragmatic belly breathing",
        "media":       MEDIA_BOTH,
        "video_dur_s": 30,
        "style":       STYLE_GUIDED_EXERCISE,
        "agents":      ["RS2", "RS3"],
        "guardrail":   "none",
        "triggers":    [
            "belly breathing", "diaphragmatic breathing", "abdominal breathing",
            "hand on belly breathing", "deep breathing technique", "breathing from belly",
        ],
    },
    "RS_ASTHMA_TRIGGERS": {
        "label":       "Common asthma trigger map",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_AWARENESS_INFOGRAPHIC,
        "agents":      ["RS1"],
        "guardrail":   "none",
        "triggers":    [
            "asthma triggers", "what triggers asthma", "asthma causes", "asthma allergens",
            "avoid asthma triggers", "asthma diary", "what makes asthma worse",
        ],
    },
    "RS_LUNG_ANATOMY": {
        "label":       "Lung anatomy cross-section",
        "media":       MEDIA_IMAGE,
        "video_dur_s": 0,
        "style":       STYLE_ANATOMICAL_DIAGRAM,
        "agents":      ["RS1", "RS6"],
        "guardrail":   "none",
        "triggers":    [
            "lung anatomy", "lung diagram", "lung structure", "alveoli diagram",
            "bronchial tree", "how do lungs work", "lung cross section",
        ],
    },
}

# ─── Global request triggers (add visual intent to any query) ─────────────────
VISUAL_REQUEST_KEYWORDS = [
    "show me", "show how", "demonstrate", "can you show",
    "video of", "image of", "picture of", "visual",
    "illustrate", "diagram of", "animation", "watch",
    "see how", "visually", "step by step show",
]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — INTENT CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════════

def detect_visual_intent(
    message:  str,
    agent_id: str,
    conversation_history: list = None,
) -> Optional[Dict]:
    """
    Detect if the patient's message would benefit from image/video generation.

    Returns intent dict if a visual should be generated, or None if text-only.
    """
    msg_lower = message.lower().strip()

    # ── 1. Check if patient explicitly requested a visual ────────────────────
    explicit_request = any(kw in msg_lower for kw in VISUAL_REQUEST_KEYWORDS)

    # ── 2. Fast keyword match against all 40 intents ────────────────────────
    best_intent = None
    best_score  = 0
    agent_upper = (agent_id or "").upper()

    for intent_id, intent_def in VISUAL_INTENTS.items():
        # Agent scope check
        if agent_upper and agent_upper not in intent_def.get("agents", []):
            # Allow general agents (x6) to generate for their disease
            disease_prefix = agent_upper[:2]
            if not any(a.startswith(disease_prefix) for a in intent_def["agents"]):
                if "6" not in agent_upper:
                    continue

        triggers = intent_def.get("triggers", [])
        neg_triggers = intent_def.get("negative_triggers", [])

        # Skip if negative trigger matches
        if any(neg in msg_lower for neg in neg_triggers):
            continue

        score = sum(1 for t in triggers if t in msg_lower)

        # Boost if explicit visual request
        if explicit_request:
            score += 1

        if score > best_score:
            best_score  = score
            best_intent = intent_id

    if best_score >= 1:
        intent = VISUAL_INTENTS[best_intent].copy()
        intent["intent_id"] = best_intent
        intent["confidence"] = min(best_score / 3.0, 1.0)
        intent["explicit_request"] = explicit_request
        return intent

    # ── 3. LLM fallback for ambiguous cases (only if explicit request) ───────
    if explicit_request:
        return _llm_intent_fallback(message, agent_id)

    return None


def _llm_intent_fallback(message: str, agent_id: str) -> Optional[Dict]:
    """
    Use Claude to classify intent when keyword matching is uncertain.
    Only called when patient explicitly asked for a visual.
    """
    try:
        from backend.core.agents.base_agent import call_llm_sync

        intent_list = "\n".join(
            f"- {iid}: {idef['label']}"
            for iid, idef in VISUAL_INTENTS.items()
        )
        result = call_llm_sync(
            system_prompt=(
                "You are a medical visual intent classifier for PRISM AI. "
                "Given a patient query, identify if it matches one of the 40 visual intents. "
                "Return ONLY the intent_id (e.g. 'DM_INSULIN_INJECTION') or 'NONE' if no match. "
                "Nothing else.\n\n"
                f"Available intents:\n{intent_list}"
            ),
            user_message=message,
            history=[],
            temperature=0.0,
            max_tokens=40,
        )
        intent_id = result["response"].strip().upper()
        if intent_id in VISUAL_INTENTS:
            intent = VISUAL_INTENTS[intent_id].copy()
            intent["intent_id"]       = intent_id
            intent["confidence"]      = 0.65
            intent["explicit_request"] = True
            return intent
    except Exception:
        pass
    return None


def should_offer_visual(intent_result: Optional[Dict]) -> bool:
    """True if we should offer to generate a visual (not always auto-generate)."""
    if not intent_result:
        return False
    # Auto-generate for explicit requests; offer for implicit
    return True


def get_visual_offer_text(intent_result: Dict, lang: str = "en") -> str:
    """Generate the offer text to show alongside the text response."""
    TEXTS = {
        "en": {
            "image": f"📸 I can generate a medical illustration of **{intent_result['label']}**. Would you like to see it?",
            "video": f"🎬 I can generate a short video demonstrating **{intent_result['label']}**. Would you like to see it? (~{intent_result.get('video_dur_s', 30)}s)",
            "both":  f"📸🎬 I can generate an image or video demonstrating **{intent_result['label']}**.",
        },
        "hi": {
            "image": f"📸 मैं **{intent_result['label']}** का चिकित्सा चित्र बना सकता हूँ। क्या आप देखना चाहते हैं?",
            "video": f"🎬 मैं **{intent_result['label']}** का एक छोटा वीडियो बना सकता हूँ। क्या आप देखना चाहते हैं?",
            "both":  f"📸🎬 मैं **{intent_result['label']}** का चित्र या वीडियो बना सकता हूँ।",
        },
        "te": {
            "image": f"📸 నేను **{intent_result['label']}** యొక్క వైద్య చిత్రాన్ని రూపొందించగలను. మీరు చూడాలనుకుంటున్నారా?",
            "video": f"🎬 నేను **{intent_result['label']}** యొక్క చిన్న వీడియోను రూపొందించగలను.",
            "both":  f"📸🎬 నేను **{intent_result['label']}** యొక్క చిత్రం లేదా వీడియో రూపొందించగలను.",
        },
        "es": {
            "image": f"📸 Puedo generar una ilustración médica de **{intent_result['label']}**. ¿Te gustaría verla?",
            "video": f"🎬 Puedo generar un video corto que demuestra **{intent_result['label']}**.",
            "both":  f"📸🎬 Puedo generar una imagen o video de **{intent_result['label']}**.",
        },
        "pa": {
            "image": f"📸 ਮੈਂ **{intent_result['label']}** ਦੀ ਡਾਕਟਰੀ ਤਸਵੀਰ ਬਣਾ ਸਕਦਾ ਹਾਂ। ਕੀ ਤੁਸੀਂ ਦੇਖਣਾ ਚਾਹੋਗੇ?",
            "video": f"🎬 ਮੈਂ **{intent_result['label']}** ਦਾ ਇੱਕ ਛੋਟਾ ਵੀਡੀਓ ਬਣਾ ਸਕਦਾ ਹਾਂ।",
            "both":  f"📸🎬 ਮੈਂ **{intent_result['label']}** ਦੀ ਤਸਵੀਰ ਜਾਂ ਵੀਡੀਓ ਬਣਾ ਸਕਦਾ ਹਾਂ।",
        },
    }
    lang_texts = TEXTS.get(lang, TEXTS["en"])
    media      = intent_result.get("media", MEDIA_IMAGE)
    return lang_texts.get(media, lang_texts["image"])