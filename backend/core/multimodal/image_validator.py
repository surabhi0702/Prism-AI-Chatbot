# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/multimodal/image_validator.py
# PRISM Medical Image Validator
# ───────────────────────────────────────────────────────────────────────────────
# PIPELINE:
#   1. Load image → encode base64
#   2. Claude Vision classifies it as medical / non-medical (F1 scoring)
#   3. If medical → extract image_type and matched_domains
#   4. Check agent-domain compatibility → guardrail or proceed
#   5. Return: {is_medical, image_type, score, agent_compatible, redirect_agent}
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import base64
import json
import math
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─── Medical document type taxonomy ──────────────────────────────────────────────
MEDICAL_DOCUMENT_TYPES: Dict[str, Dict] = {

    # ── Prescriptions & Medications ──────────────────────────────────────────
    "prescription":     {"label": "Medical Prescription / Rx Slip",      "domains": ["CA","DM","CV","MH","RS"], "icon": "📜"},
    "medicine_pack":    {"label": "Medicine Packaging / Label",           "domains": ["CA","DM","CV","MH","RS"], "icon": "💊"},
    "tablet_capsule":   {"label": "Tablets / Capsules / Pills",           "domains": ["CA","DM","CV","MH","RS"], "icon": "💊"},
    "syrup_bottle":     {"label": "Syrup / Liquid Medicine",              "domains": ["CA","DM","CV","MH","RS"], "icon": "🧴"},
    "inhaler_device":   {"label": "Inhaler / Respiratory Device",         "domains": ["RS"],                    "icon": "🫁"},

    # ── Lab Reports & Blood Results ───────────────────────────────────────────
    "blood_report":     {"label": "Blood / Lab Test Report",              "domains": ["CA","DM","CV","MH","RS"], "icon": "🩸"},
    "hba1c_report":     {"label": "HbA1c / Glucose Report",               "domains": ["DM"],                    "icon": "📊"},
    "lipid_panel":      {"label": "Lipid Panel / Cholesterol Report",     "domains": ["CV","DM"],               "icon": "🩺"},
    "cbc_report":       {"label": "Complete Blood Count Report",          "domains": ["CA","DM","CV"],           "icon": "🔬"},
    "kidney_function":  {"label": "Kidney Function / eGFR Report",        "domains": ["DM","CV"],               "icon": "🫘"},
    "liver_function":   {"label": "Liver Function Report",                "domains": ["CA","DM","CV"],           "icon": "🫀"},
    "urine_report":     {"label": "Urine / Urinalysis Report",            "domains": ["DM","CV"],               "icon": "🧪"},
    "thyroid_report":   {"label": "Thyroid Function Report",              "domains": ["DM","MH"],               "icon": "📋"},
    "pathology_report": {"label": "Pathology / Biopsy Report",            "domains": ["CA"],                    "icon": "🔬"},
    "tumour_marker":    {"label": "Tumour Marker Report",                 "domains": ["CA"],                    "icon": "🎗"},

    # ── Imaging & Scans ───────────────────────────────────────────────────────
    "xray":             {"label": "Chest / Bone X-Ray",                   "domains": ["RS","CA","CV"],           "icon": "🩻"},
    "ct_scan":          {"label": "CT Scan / CAT Scan",                   "domains": ["CA","CV","RS"],           "icon": "🩻"},
    "mri_scan":         {"label": "MRI Scan",                             "domains": ["CA","MH","CV"],           "icon": "🩻"},
    "ecg_strip":        {"label": "ECG / EKG / Electrocardiogram",        "domains": ["CV"],                    "icon": "❤️"},
    "echo_report":      {"label": "Echocardiogram Report",                "domains": ["CV"],                    "icon": "❤️"},
    "ultrasound":       {"label": "Ultrasound / Sonogram",                "domains": ["CA","DM","CV"],           "icon": "📡"},
    "mammogram":        {"label": "Mammogram / Breast Imaging",           "domains": ["CA"],                    "icon": "🎗"},
    "spirometry":       {"label": "Spirometry / Lung Function Chart",     "domains": ["RS"],                    "icon": "🫁"},
    "peak_flow_chart":  {"label": "Peak Flow / Asthma Diary",             "domains": ["RS"],                    "icon": "🫁"},
    "fundus_image":     {"label": "Retinal / Eye Fundus Image",           "domains": ["DM","CV"],               "icon": "👁️"},
    "skin_lesion":      {"label": "Skin Lesion / Dermatology Image",      "domains": ["CA"],                    "icon": "🔍"},

    # ── Clinical Reports (New Multimodal Types) ──────────────────────────────
    "operative_report":   {"label": "Operative / Surgical Report",        "domains": ["CA","CV","RS"],           "icon": "🔪"},
    "discharge_summary":  {"label": "Hospital Discharge Summary",         "domains": ["CA","DM","CV","MH","RS"], "icon": "🏥"},
    "consultation_report":{"label": "Specialist Consultation Report",     "domains": ["CA","DM","CV","MH","RS"], "icon": "👨‍⚕️"},
    "imaging_report":     {"label": "Radiology / Imaging Text Report",    "domains": ["CA","CV","RS"],           "icon": "📝"},
    "lab_results":        {"label": "Laboratory Results (Full Report)",    "domains": ["CA","DM","CV","MH","RS"], "icon": "🧪"},

    # ── Devices & Readings ────────────────────────────────────────────────────
    "glucose_meter":    {"label": "Blood Glucose Meter / CGM Screenshot", "domains": ["DM"],                    "icon": "📊"},
    "bp_monitor":       {"label": "Blood Pressure Monitor Reading",       "domains": ["CV"],                    "icon": "💓"},
    "pulse_oximeter":   {"label": "Pulse Oximeter / SpO2 Reading",        "domains": ["RS","CV"],               "icon": "🩺"},
    "cpap_data":        {"label": "CPAP / Sleep Apnea Device Data",       "domains": ["RS"],                    "icon": "🌙"},
    "insulin_pen":      {"label": "Insulin Pen / Syringe",                "domains": ["DM"],                    "icon": "💉"},
    "wound_image":      {"label": "Wound / Foot Ulcer Image",             "domains": ["DM","CA"],               "icon": "🩹"},

    # ── Mental Health ─────────────────────────────────────────────────────────
    "phq_gad_score":    {"label": "PHQ-9 / GAD-7 Questionnaire",          "domains": ["MH"],                    "icon": "🧠"},
    "mood_tracker":     {"label": "Mood / Mental Health Tracker",          "domains": ["MH"],                    "icon": "💚"},
    "sleep_study":      {"label": "Sleep Study / Polysomnography Report", "domains": ["RS","MH"],               "icon": "😴"},
}


# ─── Agent domain mapping ──────────────────────────────────────────────────────
AGENT_DOMAINS: Dict[str, str] = {
    **{f"CA{i}": "CA" for i in range(1, 7)},
    **{f"DM{i}": "DM" for i in range(1, 7)},
    **{f"CV{i}": "CV" for i in range(1, 7)},
    **{f"MH{i}": "MH" for i in range(1, 7)},
    **{f"RS{i}": "RS" for i in range(1, 7)},
}

# General agents (index 6) can handle ANY medical image
GENERAL_AGENTS = {"CA6", "DM6", "CV6", "MH6", "RS6"}

# ─── Non-medical image keywords for F1 scoring ─────────────────────────────────
NON_MEDICAL_VOCAB = {
    "selfie", "landscape", "food", "restaurant", "animal", "pet", "cat", "dog",
    "car", "vehicle", "building", "nature", "sunset", "beach", "travel", "fashion",
    "clothing", "shoes", "accessory", "meme", "screenshot", "social media",
    "sports", "concert", "celebrity", "movie", "game", "toy", "furniture",
    "receipt", "invoice", "bank statement", "id card", "passport", "map",
    "qr code", "barcode", "artwork", "painting", "drawing", "comic",
}

MEDICAL_VOCAB = {
    "prescription", "medication", "medicine", "tablet", "capsule", "pill",
    "syrup", "injection", "blood", "glucose", "report", "diagnosis", "doctor",
    "hospital", "clinic", "pharmacy", "lab", "test", "result", "x-ray",
    "ecg", "mri", "scan", "ultrasound", "biopsy", "pathology", "radiology",
    "inhaler", "insulin", "dosage", "mg", "ml", "bp", "spo2", "hba1c",
    "cholesterol", "creatinine", "hemoglobin", "platelets", "spirometry",
    "operative", "surgical", "discharge", "summary", "consultation", "specialist",
    "findings", "impression", "assessment", "plan", "procedure", "anaesthesia",
    "phq", "gad", "mental", "depression", "anxiety", "questionnaire", "mood",
    "cognitive", "psychology", "scoring", "wellness", "symptoms"
}


# ─── Medical image validation threshold ────────────────────────────────────────
MEDICAL_SCORE_THRESHOLD    = 0.55   # Below this → reject as non-medical
DOMAIN_MATCH_THRESHOLD     = 0.50   # Below this → redirect to general agent


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — IMAGE ENCODING
# ═══════════════════════════════════════════════════════════════════════════════

def encode_image_base64(image_bytes: bytes, media_type: str) -> Tuple[str, str]:
    """Encode image bytes to base64 and validate media type."""
    ALLOWED_TYPES = {
        "image/jpeg": "image/jpeg",
        "image/jpg":  "image/jpeg",
        "image/png":  "image/png",
        "image/gif":  "image/gif",
        "image/webp": "image/webp",
        "image/tiff": "image/png",  # TIFF → resampled to PNG for Claude
    }
    safe_type = ALLOWED_TYPES.get(media_type.lower(), "image/jpeg")
    encoded   = base64.standard_b64encode(image_bytes).decode("utf-8")
    return encoded, safe_type


def get_media_type_from_filename(filename: str) -> str:
    """Infer MIME type from file extension."""
    ext = Path(filename).suffix.lower()
    return {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png",  ".gif": "image/gif",
        ".webp": "image/webp", ".tiff": "image/tiff", ".tif": "image/tiff",
        ".bmp": "image/png",
    }.get(ext, "image/jpeg")


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — F1 / BERTSCORE-STYLE MEDICAL CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def compute_medical_f1_score(image_description: str) -> Dict:
    """
    BERTScore-style F1 classification using vocabulary overlap.
    Computes Precision, Recall, and F1 between image description tokens
    and the medical vocabulary set.

    Returns: {precision, recall, f1, is_medical}
    """
    tokens   = set(re.findall(r'\b\w+\b', image_description.lower()))

    # Precision: of all words in description, how many are medical?
    med_hits  = tokens & MEDICAL_VOCAB
    non_hits  = tokens & NON_MEDICAL_VOCAB

    precision = len(med_hits) / max(len(tokens), 1)

    # Recall: of all medical terms, how many are in the description?
    recall    = len(med_hits) / max(len(MEDICAL_VOCAB), 1) * 10  # scaled
    recall    = min(recall, 1.0)

    # F1
    f1 = (2 * precision * recall) / max(precision + recall, 1e-9)

    # Non-medical penalty
    non_medical_penalty = len(non_hits) / max(len(tokens), 1)
    adjusted_f1 = max(0.0, f1 - non_medical_penalty * 0.5)

    return {
        "precision":           round(precision, 3),
        "recall":              round(recall, 3),
        "f1":                  round(adjusted_f1, 3),
        "medical_terms_found": list(med_hits)[:10],
        "non_medical_found":   list(non_hits)[:5],
        "is_medical":          adjusted_f1 >= MEDICAL_SCORE_THRESHOLD or len(med_hits) >= 3,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — CLAUDE VISION CLASSIFIER
# ═══════════════════════════════════════════════════════════════════════════════

def classify_image_with_vision(
    image_b64: str,
    media_type: str,
    agent_id: str,
    patient_query: str = "",
) -> Dict:
    """
    Use Claude Vision to classify a medical image.

    Returns structured classification including:
    - is_medical: bool
    - image_type: one of MEDICAL_IMAGE_TYPES keys
    - description: detailed clinical description
    - matched_domains: list of disease domain codes
    - clinical_observations: key findings visible in the image
    - confidence: 0.0–1.0
    - rejection_reason: populated if not medical
    """
    from backend.config.settings import get_settings
    settings = get_settings()

    # Build the type options for the prompt
    type_options = "\n".join([
        f"- {k}: {v['label']} (domains: {', '.join(v['domains'])})"
        for k, v in MEDICAL_DOCUMENT_TYPES.items()
    ])


    agent_domain = AGENT_DOMAINS.get(agent_id.upper(), "UNKNOWN")
    is_general   = agent_id.upper() in GENERAL_AGENTS

    system_prompt = f"""You are PRISM's Medical Image Classification and Analysis System.
Your job has two stages:
STAGE 1: Determine if this image is medically relevant.
STAGE 2: If medical, classify it and extract clinical observations.

VALID IMAGE TYPES:
{type_options}

CURRENT AGENT: {agent_id} (Disease Domain: {agent_domain})
{"This is a GENERAL ASSISTANCE agent — it accepts all medical image types." if is_general else f"This agent specialises in the {agent_domain} domain."}

PATIENT QUERY: "{patient_query or 'No query provided'}"

Analyse the image and return ONLY this JSON object (no markdown, no explanation):
{{
  "is_medical": true_or_false,
  "confidence": 0.0_to_1.0,
  "image_type": "one_of_the_keys_above_or_null",
  "image_label": "human readable label",
  "description": "2-3 sentence clinical description of what is visible",
  "clinical_observations": [
    "Specific observable finding 1",
    "Specific observable finding 2"
  ],
  "matched_domains": ["CA", "DM", "CV", "MH", "RS"],
  "key_values_visible": {{
    "field_name": "value as shown in image"
  }},
  "rejection_reason": null_or_"reason this is not a medical image",
  "redirect_suggestion": null_or_"GA agent type that should handle this"
}}

CRITICAL RULES:
- If the image is NOT medical (selfie, food, landscape, ID card, etc.) → is_medical=false
- If medical but wrong type for this agent → still set is_medical=true but note mismatch
- Extract ANY numeric values visible: glucose readings, BP values, dates, dosage numbers
- For prescription images: extract drug names, dosages, doctor name if visible
- For reports: extract key abnormal values
- Be conservative: if unsure whether medical → set confidence < 0.7"""

    try:
        # Provider selection
        provider = settings.llm_provider
        if "sk-ant" not in str(settings.anthropic_api_key): # Check for placeholder
            provider = "openai"

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model=settings.llm_model if "claude" in settings.llm_model else "claude-3-5-sonnet-20240620",
                max_tokens=1200,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type":   "image",
                            "source": {
                                "type":       "base64",
                                "media_type": media_type,
                                "data":       image_b64,
                            },
                        },
                        {
                            "type": "text",
                            "text": "Please classify this image and return the JSON as instructed.",
                        },
                    ],
                }],
                system=system_prompt,
            )
            raw = response.content[0].text.strip()
        else:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Please classify this image and return the JSON as instructed."},
                            {
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{image_b64}"}
                            }
                        ]
                    }
                ],
                max_tokens=1200,
                response_format={"type": "json_object"}
            )
            raw = response.choices[0].message.content

        raw = re.sub(r'^```json?\s*', '', raw, flags=re.MULTILINE)
        raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)

        result = json.loads(raw)
        return result

    except json.JSONDecodeError:
        return {
            "is_medical":           False,
            "confidence":           0.0,
            "image_type":           None,
            "image_label":          "Unknown",
            "description":          "Could not parse image classification.",
            "clinical_observations": [],
            "matched_domains":       [],
            "key_values_visible":    {},
            "rejection_reason":      "Image classification failed — please try again.",
            "redirect_suggestion":   None,
        }
    except Exception as e:
        return {
            "is_medical":           False,
            "confidence":           0.0,
            "image_type":           None,
            "image_label":          "Error",
            "description":          str(e)[:200],
            "clinical_observations": [],
            "matched_domains":       [],
            "key_values_visible":    {},
            "rejection_reason":      "Image analysis service unavailable. Please try again.",
            "redirect_suggestion":   None,
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — AGENT COMPATIBILITY CHECKER
# ═══════════════════════════════════════════════════════════════════════════════

# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — SEMANTIC COMPATIBILITY AND AGENT ROUTING
# ═══════════════════════════════════════════════════════════════════════════════

def check_semantic_compatibility_with_llm(
    agent_id: str,
    document_text: str,
) -> Dict:
    """
    Evaluates semantic compatibility of the clinical content with the active agent's role & description using LLM.
    If mismatching, scans the registry to recommend the best matching agent.
    """
    from backend.config.agent_registry import ALL_AGENTS
    from backend.core.agents.base_agent import call_llm_sync

    active_agent = ALL_AGENTS.get(agent_id.upper())
    if not active_agent:
        return {
            "compatible": True,
            "redirect_to": None,
            "reason": f"Agent ID '{agent_id}' not found in registry."
        }

    # Format other primary agents as candidates
    candidate_list = []
    for aid, agent in ALL_AGENTS.items():
        if len(aid) <= 3 and not aid.endswith("-S") and not aid.endswith("-H"):
            candidate_list.append(f"- {aid}: {agent.agent_name} (Specialty: {agent.specialty}). Description: {agent.description}")
    
    candidate_agents_str = "\n".join(candidate_list)

    system_prompt = f"""You are PRISM's Clinical Document Routing and Semantic Compatibility System.
Your job is to judge if the content of an uploaded medical document (extracted text, prescription details, or report findings) is semantically and clinically compatible with the role, specialty, and description of the current active agent.

Compare the document content against the active agent:
Active Agent ID: {active_agent.agent_id}
Active Agent Name: {active_agent.agent_name}
Active Agent Domain: {active_agent.disease_domain}
Active Agent Specialty: {active_agent.specialty}
Active Agent Description: {active_agent.description}

PRISM Agents Registry (Candidate redirect targets if mismatching):
{candidate_agents_str}

CRITERIA:
1. If the document is generic (such as a discharge summary covering multiple conditions, general metabolic panels, or overall wellness plans) and has some logical relevance to the active agent, mark it as compatible.
2. If the document is highly specific to a completely different clinical specialty/domain (e.g. a cardiovascular prescription with Metoprolol or blood pressure logs uploaded under a Cancer Care agent; or a glucose log/HbA1c test uploaded under Chronic Respiratory), mark it as INCOMPATIBLE.
3. If incompatible, select the SINGLE most appropriate agent ID from the registry list that best matches the document content.

Return ONLY a valid JSON object. Do NOT include any backticks, code blocks, or preamble. Use this exact JSON structure:
{{
  "compatible": true_or_false,
  "reason": "Provide a clear, clinical explanation of the match or mismatch (e.g. 'Prescription contains anti-hypertensive medications Lisinopril and Metoprolol which are cardiovascular drugs')",
  "recommended_agent_id": "The best matching Agent ID if incompatible (e.g., CV3 or DM1), otherwise null"
}}"""

    user_message = f"Document Content:\n{document_text}"

    # Call the LLM synchronously
    llm_res = call_llm_sync(
        system_prompt=system_prompt,
        user_message=user_message,
        temperature=0.15,
        max_tokens=400
    )

    if not llm_res.get("success", False):
        return {
            "compatible": True,
            "redirect_to": None,
            "reason": "LLM call failed during semantic analysis. Defaulting to compatible."
        }

    try:
        raw_response = llm_res.get("response", "").strip()
        # Clean any markdown json wrapper
        raw_response = raw_response.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw_response)

        return {
            "compatible": parsed.get("compatible", True),
            "redirect_to": parsed.get("recommended_agent_id"),
            "reason": parsed.get("reason", "")
        }
    except Exception as e:
        print(f"[SEMANTIC_COMPATIBILITY] Parsing LLM response failed: {e}. Raw response: {llm_res.get('response')}")
        return {
            "compatible": True,
            "redirect_to": None,
            "reason": "Failed to parse compatibility response. Defaulting to compatible."
        }


def build_mismatch_guardrail_message(
    active_agent_id: str,
    target_agent_id: Optional[str],
    reason: str,
    doc_label: str = "document"
) -> str:
    from backend.config.agent_registry import ALL_AGENTS
    
    active_agent = ALL_AGENTS.get(active_agent_id.upper())
    active_domain_name = active_agent.disease_domain if active_agent else "current department"
    active_agent_name = active_agent.agent_name if active_agent else "active specialist"
    
    target_agent = ALL_AGENTS.get(target_agent_id.upper()) if target_agent_id else None
    
    domain_names = {
        "CA": "Cancer Care", "DM": "Diabetes",
        "CV": "Cardiovascular", "MH": "Mental Health", "RS": "Respiratory",
    }
    
    if target_agent:
        target_domain_name = domain_names.get(target_agent.disease_code, target_agent.disease_domain)
        target_desc = f"**{target_agent.agent_name}** ({target_agent_id})"
    else:
        target_domain_name = "another clinical area"
        target_desc = "the appropriate specialist"

    # Make the reason highly professional and clear
    clinical_reason = reason if reason else f"this record is better suited for {target_domain_name}."

    guardrail_message = (
        f"⚠️ **Clinical Focus Mismatch**\n\n"
        f"This **{doc_label}** is focused on clinical details matching another area: **{clinical_reason}**.\n\n"
        f"However, you are currently consulting the **{active_agent_name}** in the **{active_domain_name}** department.\n\n"
        f"**Our Recommendation:**\n"
        f"• 🔄 **Switch Agent**: For the most precise and specialized clinical interpretation, we recommend switching to the **{target_domain_name}** department to consult {target_desc}.\n"
        f"• **Continue Anyway**: We can analyze it in this session, but please note that the specialized tools of the current agent may not be optimized for these specific findings.\n\n"
        f"Would you like to switch to the correct disease area or continue with this analysis?"
    )
    return guardrail_message


def check_agent_compatibility(
    agent_id:       str,
    image_type:     Optional[str],
    matched_domains: List[str],
    document_text:  str = "",
) -> Dict:
    """
    Check if the image type/content is appropriate for the current agent.
    """
    agent_upper  = agent_id.upper()
    agent_domain = AGENT_DOMAINS.get(agent_upper, "")

    # General agents accept ALL medical images
    if agent_upper in GENERAL_AGENTS:
        return {
            "compatible":       True,
            "reason":           "General Assistance Agent accepts all medical image types.",
            "redirect_to":      None,
            "guardrail_message": "",
        }

    if not image_type:
        return {
            "compatible":       True,
            "reason":           "Image type could not be determined — proceeding with general analysis.",
            "redirect_to":      None,
            "guardrail_message": "",
        }

    image_config   = MEDICAL_DOCUMENT_TYPES.get(image_type, {})
    image_label    = image_config.get("label", image_type)

    # 🆕 Execute Semantic Similarity check if description/text is provided
    if document_text:
        semantic_res = check_semantic_compatibility_with_llm(agent_id, document_text)
        if not semantic_res["compatible"]:
            target_aid = semantic_res["redirect_to"]
            guardrail = build_mismatch_guardrail_message(
                active_agent_id=agent_id,
                target_agent_id=target_aid,
                reason=semantic_res["reason"],
                doc_label=image_label
            )
            return {
                "compatible":        False,
                "is_critical_mismatch": True,
                "reason":            semantic_res["reason"],
                "redirect_to":       target_aid,
                "guardrail_message": guardrail,
            }
        else:
            return {
                "compatible":       True,
                "reason":           semantic_res["reason"],
                "redirect_to":      None,
                "guardrail_message": "",
            }

    # Fallback to category-level check if no description/text is available
    allowed_domains = image_config.get("domains", [])

    # Check domain match
    if agent_domain in allowed_domains or agent_domain in matched_domains:
        return {
            "compatible":       True,
            "reason":           f"Image type '{image_label}' is appropriate for {agent_domain} domain.",
            "redirect_to":      None,
            "guardrail_message": "",
        }

    # Incompatible — build helpful redirect message
    # Find the best general agent for this domain
    domain_general_agents = {
        "CA": "CA6", "DM": "DM6", "CV": "CV6", "MH": "MH6", "RS": "RS6",
    }
    best_redirect = None
    if matched_domains:
        best_domain   = matched_domains[0]
        best_redirect = domain_general_agents.get(best_domain)

    domain_names = {
        "CA": "Cancer Care", "DM": "Diabetes",
        "CV": "Cardiovascular", "MH": "Mental Health", "RS": "Respiratory",
    }
    agent_domain_name   = domain_names.get(agent_domain, agent_domain)
    correct_domain_name = domain_names.get(matched_domains[0], matched_domains[0]) if matched_domains else "another domain"

    # Strictness level: if it's a completely different domain, mark as 'critical_mismatch'
    is_critical_mismatch = matched_domains and agent_domain not in matched_domains and agent_domain != "UNKNOWN"

    guardrail_message = (
        f"⚠️ **Clinical Domain Mismatch**\n\n"
        f"You have uploaded a **{image_label}** while in the **{agent_domain_name}** section. "
        f"This type of record is better suited for **{correct_domain_name}** specialists.\n\n"
        f"**Our Recommendation:**\n"
        f"• 🔄 **Switch Agent**: Please move to the **{correct_domain_name}** section (e.g., {best_redirect or 'General Assistant'}) to get the most accurate and specialized clinical analysis for this specific document.\n"
        f"• **Stay Here**: You can continue in this session, but please note that my specialized {agent_domain_name} logic might not provide the full clinical depth required for {correct_domain_name} records.\n\n"
        f"Would you like to switch now or proceed with a general overview here?"
    )

    return {
        "compatible":        False,
        "is_critical_mismatch": is_critical_mismatch,
        "reason":            f"Image type '{image_label}' does not match {agent_domain} domain.",
        "redirect_to":       best_redirect,
        "guardrail_message": guardrail_message,
    }


def check_document_compatibility(
    agent_id: str,
    doc_type: str,
    extracted_text: str = ""
) -> Dict:
    """
    Check if a text-based document (PDF/Excel/Word) is compatible with the agent.
    """
    agent_upper = agent_id.upper()
    agent_domain = AGENT_DOMAINS.get(agent_upper, "")

    if agent_upper in GENERAL_AGENTS:
        return {
            "compatible": True, 
            "reason": "General Assistance Agent accepts all medical document types.", 
            "redirect_to": None,
            "guardrail_message": ""
        }

    doc_config = MEDICAL_DOCUMENT_TYPES.get(doc_type, {})
    doc_label = doc_config.get("label", "Medical Document")

    # 🆕 Execute Semantic Similarity check if text is provided
    if extracted_text:
        semantic_res = check_semantic_compatibility_with_llm(agent_id, extracted_text)
        if not semantic_res["compatible"]:
            target_aid = semantic_res["redirect_to"]
            guardrail = build_mismatch_guardrail_message(
                active_agent_id=agent_id,
                target_agent_id=target_aid,
                reason=semantic_res["reason"],
                doc_label=doc_label
            )
            return {
                "compatible": False,
                "reason": semantic_res["reason"],
                "redirect_to": target_aid,
                "guardrail_message": guardrail,
                "image_label": doc_label
            }
        else:
            return {
                "compatible": True, 
                "reason": semantic_res["reason"], 
                "redirect_to": None,
                "guardrail_message": ""
            }

    # Fallback to category-level check if no text is provided
    allowed_domains = doc_config.get("domains", [])

    if agent_domain in allowed_domains:
        return {
            "compatible": True, 
            "reason": f"Document type '{doc_type}' matches {agent_domain} domain.", 
            "redirect_to": None,
            "guardrail_message": ""
        }

    # Keyword heuristic for domain detection in text
    domain_keywords = {
        "DM": ["glucose", "insulin", "hba1c", "diabetes", "diabetic", "sugar", "pancreas"],
        "CV": ["heart", "cardiac", "blood pressure", "cholesterol", "ecg", "ekg", "artery", "stent"],
        "MH": ["mental", "anxiety", "depression", "sleep", "insomnia", "mood", "psychiatry", "gad-7", "phq-9"],
        "RS": ["lung", "respiratory", "asthma", "copd", "breathing", "oxygen", "spirometry", "inhaler"],
        "CA": ["cancer", "oncology", "tumour", "biopsy", "chemotherapy", "carcinoma", "malignant", "metastasis"],
    }
    
    text_lower = extracted_text.lower()
    matched_domains = [d for d, keywords in domain_keywords.items() if any(k in text_lower for k in keywords)]
    
    if agent_domain in matched_domains:
        return {
            "compatible": True, 
            "reason": "Contextual keyword match with active agent domain.", 
            "redirect_to": None,
            "guardrail_message": ""
        }

    # Incompatible — build redirect
    domain_general_agents = {
        "CA": "CA6", "DM": "DM6", "CV": "CV6", "MH": "MH6", "RS": "RS6",
    }
    
    best_redirect = None
    detected_domain_name = "another medical area"
    
    if matched_domains:
        best_domain = matched_domains[0]
        best_redirect = domain_general_agents.get(best_domain)
        domain_names = {
            "CA": "Cancer Care", "DM": "Diabetes",
            "CV": "Cardiovascular", "MH": "Mental Health", "RS": "Respiratory",
        }
        detected_domain_name = domain_names.get(best_domain, best_domain)

    domain_names = {
        "CA": "Cancer Care", "DM": "Diabetes",
        "CV": "Cardiovascular", "MH": "Mental Health", "RS": "Respiratory",
    }
    agent_domain_name = domain_names.get(agent_domain, agent_domain)

    guardrail_message = (
        f"⚠️ **Medical Report Mismatch**\n\n"
        f"This document content appears to be focused on **{detected_domain_name}**, but you are currently in the **{agent_domain_name}** department.\n\n"
        f"**Our Recommendation:**\n"
        f"• 🔄 **Switch Context**: For the most precise clinical interpretation, please switch to a **{detected_domain_name}** agent (e.g., {best_redirect or 'General Assistant'}).\n"
        f"• **Continue Anyway**: We can analyze it here, but the specialized {agent_domain_name} tools may not be fully optimized for {detected_domain_name} specific metrics.\n\n"
        f"Would you like to switch to the correct disease area or continue with this analysis?"
    )

    return {
        "compatible": False,
        "reason": f"Document content mismatch: {detected_domain_name} vs {agent_domain}",
        "redirect_to": best_redirect,
        "guardrail_message": guardrail_message,
        "image_label": doc_label
    }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — MAIN VALIDATION FUNCTION (PUBLIC API)
# ═══════════════════════════════════════════════════════════════════════════════

def validate_and_classify_image(
    image_bytes:   bytes,
    filename:      str,
    agent_id:      str,
    patient_query: str = "",
) -> Dict:
    """
    Full pipeline: encode → classify → score → compatibility check.

    Args:
        image_bytes:   Raw file bytes from upload
        filename:      Original filename (for MIME type detection)
        agent_id:      Active agent ID (e.g., "DM2")
        patient_query: Patient's accompanying text question

    Returns complete validation result:
        is_valid:          bool   — True if medical and compatible
        is_medical:        bool   — True if medical image at all
        is_compatible:     bool   — True if right agent for this image
        image_type:        str    — Classified image type key
        image_label:       str    — Human readable label
        description:       str    — Clinical description
        clinical_obs:      list   — Key clinical observations
        key_values:        dict   — Extracted numeric values
        f1_score:          float  — BERTScore-style medical score
        vision_confidence: float  — Claude vision confidence
        guardrail_message: str    — Shown to patient if invalid
        rejection_reason:  str    — If not medical
        redirect_to:       str    — Suggested redirect agent
        image_b64:         str    — Base64 encoded image (for LLM chain)
        media_type:        str    — MIME type
    """
    media_type        = get_media_type_from_filename(filename)
    image_b64, safe_type = encode_image_base64(image_bytes, media_type)

    # ── Stage 1: Claude Vision classification ─────────────────────────────────
    vision_result = classify_image_with_vision(
        image_b64=image_b64,
        media_type=safe_type,
        agent_id=agent_id,
        patient_query=patient_query,
    )

    # ── Stage 2: F1 Score on the vision description ───────────────────────────
    description  = vision_result.get("description", "")
    f1_result    = compute_medical_f1_score(description)

    # ── Stage 3: Final medical determination ──────────────────────────────────
    vision_is_medical = vision_result.get("is_medical", False)
    f1_is_medical     = f1_result["is_medical"]
    is_medical        = vision_is_medical or f1_is_medical

    if not is_medical:
        return {
            "is_valid":          False,
            "is_medical":        False,
            "is_compatible":     False,
            "image_type":        None,
            "image_label":       "Non-medical image",
            "description":       vision_result.get("description", ""),
            "clinical_obs":      [],
            "key_values":        {},
            "f1_score":          f1_result["f1"],
            "vision_confidence": vision_result.get("confidence", 0.0),
            "guardrail_message": (
                f"🚫 **Non-Medical Image Detected**\n\n"
                f"The image you uploaded does not appear to be medically related. "
                f"PRISM only accepts medical images such as:\n"
                f"• Prescriptions or medicine packaging\n"
                f"• Lab reports (blood tests, HbA1c, lipid panel, etc.)\n"
                f"• Medical scans (X-ray, ECG, MRI, ultrasound)\n"
                f"• Device readings (glucose meter, BP monitor, spirometry)\n"
                f"• Pathology or radiology reports\n\n"
                f"**Medical relevance score: {f1_result['f1']:.0%}** "
                f"(minimum required: {MEDICAL_SCORE_THRESHOLD:.0%})\n\n"
                f"Please upload a medically relevant image to continue."
            ),
            "rejection_reason":  vision_result.get("rejection_reason", "Not a medical image."),
            "redirect_to":       None,
            "image_b64":         None,    # Don't pass non-medical images further
            "media_type":        safe_type,
        }

    # ── Stage 4: Agent compatibility check ────────────────────────────────────
    image_type       = vision_result.get("image_type")
    matched_domains  = vision_result.get("matched_domains", [])
    compatibility    = check_agent_compatibility(agent_id, image_type, matched_domains, document_text=description)

    image_config = MEDICAL_DOCUMENT_TYPES.get(image_type, {}) if image_type else {}


    return {
        "is_valid":          compatibility["compatible"],
        "is_medical":        True,
        "is_compatible":     compatibility["compatible"],
        "image_type":        image_type,
        "image_label":       vision_result.get("image_label", image_config.get("label", "Medical Image")),
        "description":       description,
        "clinical_obs":      vision_result.get("clinical_observations", []),
        "key_values":        vision_result.get("key_values_visible", {}),
        "matched_domains":   matched_domains,
        "f1_score":          f1_result["f1"],
        "vision_confidence": vision_result.get("confidence", 0.0),
        "guardrail_message": compatibility["guardrail_message"],
        "rejection_reason":  None,
        "redirect_to":       compatibility["redirect_to"],
        "image_b64":         image_b64,
        "media_type":        safe_type,
        "compatibility_reason": compatibility["reason"],
    }