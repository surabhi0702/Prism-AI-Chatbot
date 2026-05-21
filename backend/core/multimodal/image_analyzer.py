# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/multimodal/image_analyzer.py
# PRISM Medical Image Analyzer — Agent-Specific Vision Analysis
# ───────────────────────────────────────────────────────────────────────────────
# After image_validator.py passes, this module:
#   1. Builds an agent-specific analysis prompt with the image
#   2. Sends image + text query to Claude Vision
#   3. Applies agent guardrails to the response
#   4. Returns structured clinical analysis
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
import anthropic
import re
from typing import Dict, List, Optional


# ─── Agent-specific image analysis instructions ────────────────────────────────
AGENT_IMAGE_INSTRUCTIONS: Dict[str, str] = {

    # ── Cancer Care ──────────────────────────────────────────────────────────
    "CA1": """Focus on: screening intervals visible, abnormal findings flagged,
recommendation sections, dates of tests, and whether follow-up is required.
Look for tumour marker values (PSA, CA-125, CEA, AFP), BIRADS scores, or
colonoscopy findings. Flag any values above normal ranges.""",

    "CA2": """Focus on: pathology grade and stage, biomarker status (HER2, ER/PR,
PD-L1, EGFR, KRAS), treatment response indicators, chemotherapy regimens
if visible, imaging findings (size of lesion, node involvement).
Extract all numeric values visible on the report.""",

    "CA3": """Focus on: symptom severity scales visible, supportive medication
names and doses, ECOG performance status if documented, nutritional
assessment values, pain scores, and any quality-of-life indicators.""",

    "CA4": """Focus on: surveillance schedule, late effects documented, relapse
indicators, survivorship care plan elements, hormonal therapy details,
and any health monitoring parameters visible.""",

    "CA5": """Focus on: gene variants identified, pathogenicity classification
(Pathogenic/VUS/Benign), family history pedigree if visible, risk
percentages stated, and recommended surveillance or prevention actions.""",

    "CA6": """As General Cancer Care agent, analyse ALL aspects of this medical
image relevant to cancer care. Identify the document type, extract all
key values, and provide comprehensive educational context.""",

    # ── Diabetes ──────────────────────────────────────────────────────────────
    "DM1": """Focus on: glucose readings (fasting, post-meal, bedtime),
HbA1c percentage, Time in Range percentage, glucose trend arrows,
high/low alerts, sensor accuracy indicators. Convert between mg/dL and
mmol/L if needed. Flag readings outside target ranges.""",

    "DM2": """Focus on: medication names and doses visible, drug classes,
frequency and timing instructions, any contraindications noted, insulin
type and units, refill information, and prescriber details.""",

    "DM3": """Focus on: nutritional information panels visible, carbohydrate
content per serving, portion sizes, glycaemic index indicators,
calorie counts, and any dietary recommendations documented.""",

    "DM4": """Focus on: eGFR/creatinine values, urine albumin/creatinine ratio,
retinopathy grading, IWGDF foot risk classification, HbA1c trend,
blood pressure readings, lipid values. Flag any values in danger ranges.""",

    "DM5": """Focus on: glucose targets for pregnancy visible, fetal measurements
if ultrasound, insulin dose adjustments, gestational age, HbA1c for
pregnancy, paediatric growth charts if applicable.""",

    "DM6": """As General Diabetes agent, analyse ALL aspects of this diabetes-
related image. Extract all values, explain what they mean in simple terms,
and provide educational context appropriate for a patient.""",

    # ── Cardiovascular ────────────────────────────────────────────────────────
    "CV1": """Focus on: rhythm interpretation, ST changes, axis deviation,
QTc interval, wall motion abnormalities on echo, ejection fraction,
BP readings, lipid values, BNP/NT-proBNP levels. Flag any STEMI
patterns, arrhythmias, or critical values immediately.""",

    "CV2": """CRITICAL SAFETY FIRST: If this shows STEMI, cardiac arrest
rhythm, or acute emergency → state this prominently.
Focus on: rhythm, rate, ST elevation/depression, PR interval, emergency
indicators, and any immediately life-threatening findings.""",

    "CV3": """Focus on: medication names and doses, drug classes,
INR/PT values for anticoagulants, electrolyte levels affecting cardiac
drugs, and any drug interaction warnings visible.""",

    "CV4": """Focus on: exercise capacity measurements, target heart rate
zones, 6MWT distance, METs achieved, VO2 max if available, and
rehabilitation programme milestones.""",

    "CV5": """Focus on: lipid panel values (LDL, HDL, TG, total),
dietary assessment scores, BMI/waist measurements, sodium intake,
and DASH diet adherence indicators if documented.""",

    "CV6": """As General Cardiovascular agent, analyse ALL aspects of this
cardiac-related image. Explain findings in patient-friendly terms,
extract all numeric values, and provide educational context.""",

    # ── Mental Health ─────────────────────────────────────────────────────────
    "MH1": """Focus on: PHQ-9 total score and item scores, depression
severity classification, suicidal ideation item (item 9 — flag if ≥1),
treatment response indicators, and any mood tracking data.""",

    "MH2": """Focus on: GAD-7 total score and severity, panic frequency,
anxiety trigger identification visible, CBT thought records,
medication names for anxiety, and avoidance behaviours documented.""",

    "MH3": """Focus on: sleep diary data (sleep onset, wake time, total sleep,
sleep efficiency), ISI score, actigraphy patterns if visible,
caffeine/alcohol intake logs, and CBT-I session progress.""",

    "MH4": """SAFETY FIRST: If any safety plan is visible or self-harm
indicators are present → acknowledge and provide crisis resources.
Focus on: trauma assessment scores, PTSD symptom clusters,
PCL-5 total, and treatment progress indicators.""",

    "MH5": """SAFETY OVERRIDE: Crisis resources first always.
Focus on: safety plan elements visible, crisis contact information,
C-SSRS risk level, emergency contacts documented, and any protective
factors listed.""",

    "MH6": """As General Mental Health agent, analyse ALL aspects of this
mental health document. Explain assessment scores in simple terms,
provide psychoeducation context, and always note if professional
support is recommended based on scores visible.""",

    # ── Respiratory ───────────────────────────────────────────────────────────
    "RS1": """Focus on: peak flow readings (% predicted, personal best),
asthma control level (GINA), inhaler technique checklist visible,
trigger diary, FeNO values, spirometry if present.""",

    "RS2": """Focus on: FEV1 % predicted, FEV1/FVC ratio, GOLD stage,
mMRC dyspnoea score, CAT score, exacerbation frequency,
LTOT criteria values, and 6MWT results.""",

    "RS3": """Focus on: exercise capacity measures, 6MWT distance improvement,
Borg breathlessness scale scores, respiratory muscle strength,
and pulmonary rehabilitation session progress.""",

    "RS4": """Focus on: inhaler device type, prescription details,
ICS dose (mcg per puff × puffs per day), technique checklist,
spacer type, and medication step-up/step-down indicators.""",

    "RS5": """Focus on: AHI (apnoea-hypopnoea index), oxygen desaturation
events, CPAP pressure and compliance data, REM vs NREM breakdown,
Epworth sleepiness scale score, and STOP-BANG risk factors visible.""",

    "RS6": """As General Respiratory agent, analyse ALL aspects of this lung
health image. Extract all measurements, explain in patient-friendly
terms, and identify which specialist respiratory agent would be
best suited for a deeper analysis.""",
}

# ─── Clinical guardrails for analysis ──────────────────────────────────────────
IMAGE_ANALYSIS_GUARDRAILS = """
UNIVERSAL ANALYSIS GUARDRAILS — MUST FOLLOW:
1. NEVER diagnose a condition from a document alone
2. ALWAYS state: "This AI analysis is for educational reference only — consult your doctor"
3. For any CRITICAL or EMERGENCY values → state "SEEK IMMEDIATE MEDICAL ATTENTION" prominently
4. NEVER recommend changing medication doses based on a report
5. For pathology/biopsy reports → never interpret results definitively
6. For prescriptions → read aloud values but don't change or endorse them
7. Always recommend the patient share findings with their treating physician
8. Patient privacy: do not retain or reference personal identifiers in analysis
"""


# Critical value triggers (immediately flag these)
CRITICAL_VALUE_PATTERNS = {
    "glucose_critical_low":  r'\b[1-5]\d\.?\d?\s*(mg/dl|mmol)',
    "glucose_critical_high": r'\b[4-9]\d\d\.?\d?\s*mg/dl',
    "bp_critical_high":      r'\b1[89]\d/\d\d',
    "spo2_critical_low":     r'spo2?\s*:?\s*[0-8]\d',
    "stemi_ecg":             r'st\s*elev|stemi|tombstoning',
    "suicidal_ideation":     r'suicid|self.harm|phq.9.item.9',
}


def analyze_medical_image(
    image_b64:      str,
    media_type:     str,
    agent_id:       str,
    patient_query:  str,
    image_type:     Optional[str],
    image_label:    str,
    clinical_obs:   List[str],
    key_values:     Dict,
    conversation_history: List[Dict],
    language:       str = "en",
) -> Dict:
    """
    Core image analysis function — builds agent-specific prompt and
    sends image + query to Claude Vision.
    (Reload triggered: self-reference fixed)

    Returns: {response, critical_flags, key_values_extracted, citations, confidence}
    """

    from backend.config.settings import get_settings
    settings = get_settings()

    agent_instructions = AGENT_IMAGE_INSTRUCTIONS.get(
        agent_id.upper(),
        AGENT_IMAGE_INSTRUCTIONS.get("CA6", "Analyse this medical image comprehensively.")
    )

    # Build key values context
    kv_text = ""
    if key_values:
        kv_text = "\nValues already extracted from image: " + \
                  ", ".join(f"{k}: {v}" for k, v in key_values.items())

    # Build prior observations context
    obs_text = ""
    if clinical_obs:
        obs_text = "\nInitial clinical observations: " + "; ".join(clinical_obs[:5])

    # Conversation context (last 4 turns)
    conv_text = ""
    if conversation_history:
        recent = conversation_history[-4:]
        conv_text = "\nPRIOR CONVERSATION CONTEXT:\n" + "\n".join([
            f"{'Patient' if m['role'] == 'user' else 'PRISM'}: {m['content'][:200]}"
            for m in recent
        ])

    system_prompt = f"""You are PRISM's Medical Image Analysis AI for Agent {agent_id}.

IMAGE TYPE IDENTIFIED: {image_label or 'Medical Document'}
{IMAGE_ANALYSIS_GUARDRAILS}

AGENT-SPECIFIC ANALYSIS FOCUS:
{agent_instructions}

{kv_text}
{obs_text}
{conv_text}

RESPONSE FORMAT (use this exact structure):
---
**📋 Document Identified:** [document type in plain language]

**🔍 Severity Analysis:** [Select one: Normal | Low | Medium | High | Critical] - [1 sentence explanation]

**🔍 What I Can See / Extracted:**
[2-3 sentences describing the key information found in clear, patient-friendly language]

**📊 Key Values & Findings:**
[Bullet list of every important value or finding, with normal ranges where applicable]

**⚕️ Clinical Context:**
[What these findings mean in the context of the patient's query — personalised, specific]

**✅ Recommended Actions:**
[3-5 concrete next steps the patient should discuss with their doctor]

**❓ Suggested Follow-up Questions:**
- [Question 1: Specific to a value or finding in this report]
- [Question 2: Specific next step or management question]
- [Question 3: Question for your specialist about this finding]
- [Question 4: Clarification on a term found in this document]

**⚠️ Important Notice:**
This analysis is generated by AI for educational reference only. Always share these
findings with your treating physician before making any health decisions.
---


LANGUAGE: Respond in {language if language != 'en' else 'English'}.
CRITICAL VALUES: If you see any life-threatening values, state "⚠️ URGENT: Seek immediate medical attention" at the very top before anything else."""

    # Build the message with image
    user_content = [
        {
            "type": "image",
            "source": {
                "type":       "base64",
                "media_type": media_type,
                "data":       image_b64,
            },
        },
        {
            "type": "text",
            "text": f"Patient's question: {patient_query or 'Please analyse this medical image and explain what you see.'}\n\nPlease provide your analysis following the format specified.",
        },
    ]

    # Build conversation history for multi-turn context
    messages = []
    if conversation_history:
        for m in conversation_history[-6:]:
            if m["role"] in ("user", "assistant"):
                messages.append({"role": m["role"], "content": m["content"]})
    messages.append({"role": "user", "content": user_content})

    try:
        # Provider selection
        provider = settings.llm_provider
        if "sk-ant" not in str(settings.anthropic_api_key):
            provider = "openai"

        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            response = client.messages.create(
                model=settings.llm_model if "claude" in settings.llm_model else "claude-3-5-sonnet-20240620",
                max_tokens=2000,
                system=system_prompt,
                messages=messages,
            )
            analysis_text = response.content[0].text
        else:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            
            # Convert messages to OpenAI format
            openai_msgs = [{"role": "system", "content": system_prompt}]
            for m in messages:
                if isinstance(m["content"], list):
                    # User content with image
                    content_list = []
                    for c in m["content"]:
                        if c["type"] == "text":
                            content_list.append({"type": "text", "text": c["text"]})
                        elif c["type"] == "image":
                            # Note: OpenAI uses image_url, Anthropic uses image source
                            content_list.append({
                                "type": "image_url",
                                "image_url": {"url": f"data:{media_type};base64,{image_b64}"}
                            })
                    openai_msgs.append({"role": "user", "content": content_list})
                else:
                    openai_msgs.append({"role": m["role"], "content": m["content"]})

            response = client.chat.completions.create(
                model="gpt-4o",
                messages=openai_msgs,
                max_tokens=2000,
                temperature=0.2
            )
            analysis_text = response.choices[0].message.content

        # Check for critical flags
        critical_flags = []
        for flag, pattern in CRITICAL_VALUE_PATTERNS.items():
            if re.search(pattern, analysis_text.lower()):
                critical_flags.append(flag)

        return {
            "response":             analysis_text,
            "severity":             _extract_severity(analysis_text),
            "critical_flags":       critical_flags,

            "has_critical_values":  len(critical_flags) > 0 or "Critical" in analysis_text,
            "key_values_extracted": key_values,
            "prompt_tokens":        response.usage.input_tokens if provider == "anthropic" else response.usage.prompt_tokens,
            "completion_tokens":    response.usage.output_tokens if provider == "anthropic" else response.usage.completion_tokens,
            "model":                settings.llm_model if provider == "anthropic" else "gpt-4o",
            "citations": [
                {"source": "Patient-uploaded medical image", "type": image_label}
            ],
            "follow_up_questions": _extract_follow_ups(analysis_text)
        }

    except Exception as e:
        return {
            "response":             f"Image analysis encountered an error: {str(e)[:200]}. Please try again.",
            "critical_flags":       [],
            "has_critical_values":  False,
            "key_values_extracted": {},
            "prompt_tokens":        0,
            "completion_tokens":    0,
            "model":                settings.llm_model if "provider" in locals() and provider == "anthropic" else "gpt-4o",
            "citations":            [],
        }


def _extract_severity(text: str) -> str:
    """Helper to pull severity label from the formatted response."""
    match = re.search(r'\*\*🔍 Severity Analysis:\*\* (Normal|Low|Medium|High|Critical)', text)
    return match.group(1) if match else "Unknown"


def _extract_follow_ups(text: str) -> List[str]:
    """Helper to extract suggested follow-up questions from the response."""
    questions = []
    if "**❓ Suggested Follow-up Questions:**" in text:
        section = text.split("**❓ Suggested Follow-up Questions:**")[1].split("**⚠️ Important Notice:**")[0]
        # Look for bullet points
        lines = section.strip().split("\n")
        for line in lines:
            line = line.strip().lstrip("- ").lstrip("* ").strip()
            if line and len(line) > 5:
                # Remove brackets if AI left them
                line = re.sub(r'\[|\]', '', line)
                questions.append(line)
    return questions[:4]


def analyze_medical_document(
    extracted_text: str,
    doc_type:       str,
    agent_id:       str,
    patient_query:  str,
    conversation_history: List[Dict],
    language:       str = "en",
) -> Dict:
    """
    Analyzes extracted text from medical documents (PDF/Excel/Word).
    Similar to analyze_medical_image but uses text-only LLM call.
    """
    from backend.config.settings import get_settings
    settings = get_settings()

    agent_instructions = AGENT_IMAGE_INSTRUCTIONS.get(
        agent_id.upper(),
        AGENT_IMAGE_INSTRUCTIONS.get("CA6", "Analyse this medical document comprehensively.")
    )

    conv_text = ""
    if conversation_history:
        recent = conversation_history[-4:]
        conv_text = "\nPRIOR CONVERSATION CONTEXT:\n" + "\n".join([
            f"{'Patient' if m['role'] == 'user' else 'PRISM'}: {m['content'][:200]}"
            for m in recent
        ])

    system_prompt = f"""You are PRISM's Medical Document Analysis AI for Agent {agent_id}.

DOCUMENT TYPE: {doc_type}
{IMAGE_ANALYSIS_GUARDRAILS}

AGENT-SPECIFIC ANALYSIS FOCUS:
{agent_instructions}

{conv_text}

EXTRACTED TEXT FROM DOCUMENT:
---
{extracted_text[:4000]}
---

RESPONSE FORMAT (use this exact structure):
---
**📋 Document Identified:** [document type in plain language]

**🔍 Severity Analysis:** [Select one: Normal | Low | Medium | High | Critical] - [1 sentence explanation]

**🔍 Key Information Extracted:**
[2-3 sentences describing the most important findings found in the text]

**📊 Detailed Values & Findings:**
[Bullet list of every important numeric value or clinical finding found in the text]

**⚕️ Clinical Context:**
[What these findings mean in the context of the patient's query — personalised, specific]

**✅ Recommended Actions:**
[3-5 concrete next steps the patient should discuss with their doctor]

**❓ Suggested Follow-up Questions:**
- [Question 1: Specific to a value or finding in this report]
- [Question 2: Specific next step or management question]
- [Question 3: Question for your specialist about this finding]
- [Question 4: Clarification on a term found in this document]

**⚠️ Important Notice:**
This analysis is generated by AI for educational reference only. Always share these
findings with your treating physician before making any health decisions.
---

LANGUAGE: Respond in {language if language != 'en' else 'English'}.
"""

    try:
        from openai import OpenAI
        client = OpenAI(api_key=settings.openai_api_key)
        
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Patient's question: {patient_query or 'Please analyse this medical report.'}"}
            ],
            temperature=0.2
        )
        analysis_text = response.choices[0].message.content

        return {
            "response":             analysis_text,
            "severity":             _extract_severity(analysis_text),
            "critical_flags":       [],
            "has_critical_values":  "Critical" in analysis_text,
            "key_values_extracted": {},
            "latency_ms":           0,
            "citations":            [{"source": "Patient-uploaded document", "type": doc_type}],
            "follow_up_questions": _extract_follow_ups(analysis_text)
        }
    except Exception as e:
        return {
            "response":             f"Document analysis failed: {str(e)[:200]}",
            "severity":             "Error",
            "critical_flags":       [],
            "has_critical_values":  False,
            "citations":            [],
        }