# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/multimodal/medical_prompt_builder.py
# PRISM Medical Visual Prompt Builder
# ───────────────────────────────────────────────────────────────────────────────
# Builds safe, clinically accurate, educational prompts for DALL-E 3 / Runway ML.
# All prompts use medical illustration style (not photorealistic) to avoid
# graphic content while maintaining educational value.
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations
from typing import Dict, Optional


# ─── Base style modifiers ─────────────────────────────────────────────────────
STYLE_PREFIXES = {
    "medical_illustration":   "Clean medical illustration, clinical educational style, "
                              "blue and white colour scheme, cross-section view, professional "
                              "medical textbook quality, annotated diagram, no blood or gore, ",
    "instructional_diagram":  "Step-by-step instructional diagram, clean infographic style, "
                              "numbered steps with arrows, friendly approachable illustration, "
                              "pastel colours, clear labels, educational health poster, ",
    "nutrition_infographic":  "Bright colourful nutrition infographic, food illustration style, "
                              "plate diagram, portion guide, vector art style, white background, "
                              "clean and modern design, ",
    "data_infographic":       "Clean data visualisation, medical chart, colour-coded ranges, "
                              "professional healthcare design, white background, clear typography, "
                              "easy to read scale, ",
    "symptom_diagram":        "Medical symptom diagram, human body silhouette with annotations, "
                              "educational illustration, soft blue and white palette, "
                              "clinical informational poster style, ",
    "anatomical_diagram":     "Detailed anatomical cross-section diagram, medical textbook style, "
                              "labelled components, blue-grey colour scheme, clean white background, "
                              "educational anatomy illustration, ",
    "awareness_infographic":  "Health awareness infographic, bold friendly design, "
                              "clear icons, high contrast, accessible layout, "
                              "public health poster style, ",
    "schedule_diagram":       "Clean timeline infographic, schedule chart, horizontal layout, "
                              "colour-coded segments, minimal design, healthcare planner style, ",
    "conceptual_diagram":     "Simple conceptual diagram, triangle or cycle illustration, "
                              "three connected components, soft colours, psychology textbook style, "
                              "clean vector art, ",
    "science_diagram":        "Scientific diagram, biological cycle illustration, "
                              "clean educational poster, labelled arrows, neutral palette, "
                              "science textbook quality, ",
    "guided_exercise":        "Step-by-step exercise guide illustration, human figure silhouette, "
                              "numbered steps, breathing arrows, calming blue and white design, "
                              "clinical exercise poster style, ",
}

STYLE_SUFFIXES = {
    "no_blood":      "no blood, no needles visible, focus on body positioning only, ",
    "no_gore":       "educational cutaway view, no graphic content, simplified schematic, ",
    "clinical_only": "clinical educational tone, tasteful medical illustration, "
                     "anatomically accurate but not explicit, ",
    "none":          "",
}

# ─── Per-intent prompt templates ─────────────────────────────────────────────
PROMPT_TEMPLATES: Dict[str, str] = {
    "DM_INSULIN_INJECTION": (
        "A medical illustration showing subcutaneous insulin injection technique. "
        "Shows: 1) Pinch of abdominal skin forming fatty tissue fold, 2) 45-degree needle angle, "
        "3) Rotation sites marked on abdomen and thigh as a body diagram. "
        "Numbered steps 1-3 with arrows. No blood. Blue medical illustration style."
    ),
    "DM_BLOOD_GLUCOSE_MONITOR": (
        "Step-by-step instructional diagram: 1) Lancet on fingertip (side), "
        "2) Small blood droplet on test strip, 3) Strip inserted in glucometer, "
        "4) Glucometer screen showing reading 126 mg/dL. "
        "Clean 4-panel infographic. Numbered steps. Friendly healthcare illustration."
    ),
    "DM_CGM_PLACEMENT": (
        "Medical illustration of continuous glucose monitor (CGM) sensor placement. "
        "Shows: back of upper arm placement site highlighted, sensor applicator device, "
        "inserted sensor profile view (cross-section showing subcutaneous layer), "
        "and reader device scanning sensor. Clean blue medical diagram with labels."
    ),
    "DM_DIABETES_PLATE": (
        "Diabetes plate method infographic. Dinner plate divided into sections: "
        "1/2 plate non-starchy vegetables (broccoli, spinach, peppers), "
        "1/4 plate lean protein (grilled chicken), "
        "1/4 plate complex carbohydrates (brown rice). "
        "Glass of water alongside. Bright colourful food illustration. Clean white background."
    ),
    "DM_FOOT_EXAMINATION": (
        "Daily diabetic foot care instructional diagram. "
        "Six numbered steps: 1) Inspect soles with mirror, 2) Check between toes, "
        "3) Apply moisturiser (avoiding between toes), 4) Proper nail trimming, "
        "5) Wear well-fitted shoes, 6) Never walk barefoot. "
        "Friendly illustration, pastel colours."
    ),
    "DM_HYPOGLYCEMIA_SIGNS": (
        "Medical symptom diagram of hypoglycaemia warning signs. "
        "Human body outline with annotated symptoms: shakiness (hands), "
        "sweating (forehead), rapid heartbeat (chest), confusion (head/brain), "
        "pale skin, hunger. Colour-coded annotations. Clinical educational poster."
    ),
    "DM_HBA1C_CHART": (
        "HbA1c range infographic showing a horizontal colour-coded scale: "
        "green zone below 5.7% (normal), yellow zone 5.7-6.4% (pre-diabetes), "
        "orange zone 6.5-8% (diabetes, managed), red zone above 8% (high risk). "
        "Target line at 7%. Clean modern healthcare data visualisation."
    ),
    "DM_EXERCISE_SAFETY": (
        "Safe exercise guide for people with diabetes. "
        "Four illustrated activities: brisk walking (30 min), swimming, "
        "resistance band exercises, cycling. "
        "Blood glucose check reminder before and after exercise symbol. "
        "Friendly instructional poster, pastel colours, numbered guidelines."
    ),
    "CV_CPR_TECHNIQUE": (
        "CPR technique instructional diagram. Three steps: "
        "1) Position — heel of hand on lower sternum, second hand on top, elbows straight, "
        "2) Compressions — push down 5-6cm at 100-120 per minute, "
        "3) Rescue breaths — tilt head, lift chin, 2 breaths. "
        "30:2 ratio badge. Simple clear line art medical illustration."
    ),
    "CV_HEART_ANATOMY": (
        "Detailed labelled heart anatomy cross-section. "
        "Labels: right atrium, right ventricle, left atrium, left ventricle, "
        "pulmonary valve, aortic valve, mitral valve, tricuspid valve, "
        "coronary arteries, aorta, pulmonary artery. "
        "Directional blood flow arrows (red = oxygenated, blue = deoxygenated). "
        "Medical textbook illustration style."
    ),
    "CV_BP_MEASUREMENT": (
        "Blood pressure measurement instructional diagram. "
        "Steps: 1) Sit upright, feet flat, arm at heart level, "
        "2) Cuff placed 2cm above elbow crease, "
        "3) Digital monitor showing 120/80 mmHg reading. "
        "Dos and don'ts panel below. Clean infographic style."
    ),
    "CV_STROKE_FAST": (
        "FAST stroke recognition awareness infographic. "
        "Four illustrated panels: F-Face (person with asymmetric smile), "
        "A-Arms (one arm drifting down), S-Speech (confused speech bubbles), "
        "T-Time (clock and phone 999/911). Bold colours, clear icons, "
        "health awareness campaign style."
    ),
    "CV_HEART_RATE_ZONES": (
        "Target heart rate zones chart. Horizontal stacked bar or zones diagram: "
        "Zone 1 (50-60%): grey 'Resting', Zone 2 (60-70%): blue 'Fat burn', "
        "Zone 3 (70-80%): green 'Aerobic', Zone 4 (80-90%): orange 'Anaerobic', "
        "Zone 5 (90-100%): red 'Max'. BPM scale on axis. "
        "Formula 220-age shown. Clean data visualisation."
    ),
    "CV_CARDIAC_DIET": (
        "Heart-healthy Mediterranean diet plate infographic. "
        "Plate showing: extra virgin olive oil drizzle, grilled fish (salmon), "
        "colourful vegetables (tomatoes, peppers, olives), whole grain bread, "
        "nuts (almonds, walnuts), fresh fruit. "
        "Red cross over processed meats and high-sodium foods. "
        "Bright food illustration, white background."
    ),
    "CV_MEDICATION_SCHEDULE": (
        "Daily cardiac medication schedule chart. "
        "Morning row: aspirin, statin, beta-blocker icons with meal indicator. "
        "Evening row: medication icons. "
        "Colour-coded pills, clock icons for timing, food/empty stomach indicators. "
        "Clean healthcare schedule design."
    ),
    "CV_ANGIOPLASTY": (
        "Educational angioplasty procedure illustration. "
        "Three stages: 1) Blocked coronary artery cross-section (plaque buildup), "
        "2) Balloon catheter inserted and inflated (simplified schematic), "
        "3) Stent deployed, artery open (cross-section). "
        "No blood. Blue medical schematic style with labels."
    ),
    "MH_478_BREATHING": (
        "4-7-8 breathing technique instructional diagram. "
        "Three-panel illustration: "
        "1) Inhale through nose — 4 counts (lung expanding animation frame), "
        "2) Hold breath — 7 counts (lungs full), "
        "3) Exhale through mouth — 8 counts (pursed lips, lungs deflating). "
        "Timer circles for each count. Calming blue and white palette."
    ),
    "MH_SLEEP_WINDOW": (
        "Sleep restriction / CBT-I schedule chart. "
        "Timeline from 10pm to 10am showing: "
        "current schedule (red block 3am-10am), "
        "week 1 target (orange 2:45am-10am), "
        "week 4 target (green 11pm-6am). "
        "Arrow showing gradual advance. Clean schedule infographic."
    ),
    "MH_PROGRESSIVE_RELAXATION": (
        "Progressive muscle relaxation body map diagram. "
        "Human body outline with numbered muscle groups highlighted in sequence: "
        "1) Feet and calves, 2) Thighs, 3) Abdomen, 4) Hands and arms, "
        "5) Shoulders, 6) Face. "
        "Tense-and-release icons alongside each group. "
        "Calming green and blue palette, clinical exercise style."
    ),
    "MH_GROUNDING_54321": (
        "5-4-3-2-1 grounding technique infographic. "
        "Five numbered cards: 5 things you SEE (eyes icon), "
        "4 things you HEAR (ear icon), 3 things you can TOUCH (hand icon), "
        "2 things you SMELL (nose icon), 1 thing you TASTE (lips icon). "
        "Calming earth tones, soft rounded design, mindfulness poster style."
    ),
    "MH_CBT_TRIANGLE": (
        "Cognitive behavioural triangle diagram. "
        "Equilateral triangle with three labelled nodes: "
        "THOUGHTS (top — thought bubble), FEELINGS (bottom left — heart), "
        "BEHAVIOURS (bottom right — person walking). "
        "Bidirectional arrows connecting all three. "
        "Example pathway shown: 'I am worthless' → anxiety → avoidance. "
        "Clean psychology diagram, teal and grey palette."
    ),
    "MH_CIRCADIAN_LIGHT": (
        "Circadian rhythm 24-hour body clock diagram. "
        "Circle clock showing: morning (sunrise) — optimal light therapy window, "
        "noon — cortisol peak, evening (moon) — melatonin rise, "
        "night — deep sleep phase. "
        "Melatonin curve overlaid as line graph. "
        "Light therapy lamp icon in morning zone. Science diagram style."
    ),
    "MH_MOOD_SCALE": (
        "Visual mood rating scale infographic. "
        "Horizontal scale 0-10 with colour gradient (red to green). "
        "Anchors: 0-2 Severe (dark red), 3-4 Moderate (orange), "
        "5-6 Mild (yellow), 7-8 Manageable (light green), 9-10 Thriving (green). "
        "Simple face emojis as mood indicators. Clean healthcare assessment tool style."
    ),
    "MH_STRESS_RESPONSE": (
        "Stress response pathway diagram. "
        "Top: stressor trigger → amygdala highlighted in brain icon → "
        "HPA axis arrow → adrenal glands → cortisol release → "
        "fight-or-flight response (increased heart rate, muscle tension). "
        "Counter pathway: prefrontal cortex → calm response. "
        "Clean science diagram, blue and orange palette."
    ),
    "CA_BREAST_SELF_EXAM": (
        "Breast self-examination instructional poster. "
        "Five steps illustrated with clinical body diagram: "
        "1) Mirror visual inspection — arms at sides, "
        "2) Arms raised — check shape changes, "
        "3) Lying down — circular motion pattern (clock diagram), "
        "4) Standing — repeat circular motion, "
        "5) Underarm check. "
        "Clinical educational style, blue and white, no explicit content."
    ),
    "CA_CHEMO_CYCLE": (
        "Chemotherapy cycle timeline infographic. "
        "Horizontal bar showing 21-day cycle: "
        "Day 1 (treatment, green), Days 2-7 (side effect window, yellow), "
        "Day 7-14 (nadir — lowest blood counts, red zone), "
        "Days 14-21 (recovery, green gradient). "
        "Next cycle starting day 22. "
        "Clean healthcare schedule design with legend."
    ),
    "CA_PORT_ACCESS": (
        "Port-a-cath anatomy and access diagram. "
        "Left: location under right clavicle skin surface. "
        "Cross-section: septum disc under skin, catheter to vein. "
        "Access sequence: 1) Palpate port, 2) Clean with antiseptic, "
        "3) Non-coring Huber needle insertion. "
        "No blood. Blue medical illustration."
    ),
    "CA_CANCER_STAGES": (
        "Cancer staging diagram, four panels (Stage I-IV). "
        "Simplified organ cross-sections: "
        "Stage I — small tumour, contained; "
        "Stage II — larger, approaching tissue boundary; "
        "Stage III — lymph node involvement shown; "
        "Stage IV — distant metastasis arrows. "
        "Colour scale from yellow to red. Educational medical diagram."
    ),
    "CA_LYMPHEDEMA_MASSAGE": (
        "Manual lymphatic drainage massage instructional diagram for arm lymphedema. "
        "Body outline showing lymph node regions. "
        "Numbered circular massage stroke sequence with arrows: "
        "proximal to distal clearing, then distal-to-proximal drainage strokes. "
        "Light pressure indicator. Clinical instructional style, blue arrows."
    ),
    "CA_RADIATION_POSITIONING": (
        "Radiation therapy setup educational diagram. "
        "Patient lying on treatment table, immobilisation mask or mould. "
        "Linear accelerator (LINAC) machine schematic. "
        "Radiation field markings on skin (pen marks). "
        "Shield blocking healthy tissue shown. "
        "No graphic content. Blue medical schematic."
    ),
    "CA_NUTRITION_CANCER": (
        "Cancer treatment nutrition plate infographic. "
        "Plate showing high-protein easy-digest foods: "
        "eggs, Greek yogurt, fish, fortified protein shake, "
        "soft cooked vegetables, small portions. "
        "'Eat little and often' key message. "
        "Side panel: foods to avoid during nausea. "
        "Bright friendly nutrition poster."
    ),
    "CA_WOUND_CARE": (
        "Post-surgical wound care instructional diagram. "
        "Steps: 1) Wash hands first, 2) Remove old dressing gently, "
        "3) Clean wound with saline — gentle circular motion, "
        "4) Apply new sterile dressing, 5) Warning signs panel "
        "(redness, warmth, discharge, fever). "
        "No graphic content. Clinical instructional style."
    ),
    "RS_MDI_TECHNIQUE": (
        "MDI pressurised inhaler correct technique instructional poster. "
        "Steps: 1) Shake inhaler 5 times, 2) Exhale fully away from inhaler, "
        "3) Seal lips around mouthpiece, 4) Press canister — breathe in slowly (3-5 sec), "
        "5) Hold breath 10 seconds, 6) Wait 30 seconds before next puff. "
        "Common mistakes panel (bottom). Clean infographic."
    ),
    "RS_SPACER_USE": (
        "Spacer device with MDI inhaler instructional diagram. "
        "Steps: 1) Attach MDI to spacer end, 2) Exhale fully, "
        "3) Seal lips on spacer mouthpiece, 4) Press canister once, "
        "5) Breathe in slowly and deeply, 6) Breathe in and out 5 times in spacer. "
        "Spacer cross-section showing aerosol cloud held in chamber. "
        "Clean numbered infographic."
    ),
    "RS_PURSED_LIP": (
        "Pursed-lip breathing technique instructional diagram. "
        "Two-step illustrated guide: "
        "1) Inhale through nose — 2 counts (nasal passages diagram), "
        "2) Exhale slowly through pursed lips — 4 counts (lips diagram). "
        "Timer circles (2 and 4). Reduction in breathing rate benefit shown. "
        "Calming blue and white design."
    ),
    "RS_PEAK_FLOW": (
        "Peak flow meter usage instructional diagram. "
        "Steps: 1) Stand upright, 2) Set marker to zero, 3) Deep breath, "
        "4) Seal lips on mouthpiece, 5) Blast as fast and hard as possible, "
        "6) Read result — record highest of 3 attempts. "
        "Traffic light peak flow zones: green (80%+ personal best), "
        "amber (50-80%), red (below 50%). Clean instructional poster."
    ),
    "RS_CPAP_FITTING": (
        "CPAP mask fitting guide infographic. "
        "Three mask types illustrated: full face (covers nose and mouth), "
        "nasal mask, nasal pillow. "
        "Strap adjustment sequence for nasal mask. "
        "Seal check: no air leaks around edges indicator. "
        "Pressure ramp setting on device. Clean instructional diagram."
    ),
    "RS_DIAPHRAGMATIC": (
        "Diaphragmatic belly breathing instructional diagram. "
        "Person lying down, one hand on chest (stays still), "
        "one hand on belly (rises). "
        "Inhale: belly pushes out; Exhale: belly falls. "
        "Diaphragm muscle cross-section (flattens on inhale). "
        "Breathing count: in 4, out 6. Blue and white calming design."
    ),
    "RS_ASTHMA_TRIGGERS": (
        "Asthma trigger awareness infographic. "
        "Central lung icon surrounded by 8 trigger categories: "
        "dust mites (microscope icon), pollen (flower), exercise (runner), "
        "cold air (snowflake), smoke (cigarette — red X), "
        "pets/dander (cat/dog icon), mould (spore cloud), "
        "strong smells (spray can). "
        "Each trigger with brief avoidance tip. "
        "Bright awareness poster, orange and blue."
    ),
    "RS_LUNG_ANATOMY": (
        "Detailed lung anatomy cross-section diagram. "
        "Labels: trachea, right and left bronchi, bronchioles, alveolar sacs, "
        "alveoli (magnified inset showing gas exchange — O2 in, CO2 out), "
        "diaphragm, pleural cavity. "
        "Blue = deoxygenated, red = oxygenated blood. "
        "Medical textbook illustration style."
    ),
}


def build_image_prompt(intent_id: str, patient_context: Optional[Dict] = None) -> str:
    """Build a complete DALL-E 3 prompt for the given medical intent."""
    intent   = __import__("backend.core.multimodal.visual_intent_detector", fromlist=["VISUAL_INTENTS"]).VISUAL_INTENTS.get(intent_id)
    if not intent:
        return f"Clean medical educational illustration about {intent_id.replace('_', ' ').lower()}"

    style_key    = intent.get("style",     "instructional_diagram")
    guardrail_key = intent.get("guardrail", "none")
    template     = PROMPT_TEMPLATES.get(intent_id, intent.get("label", "medical procedure"))

    prefix   = STYLE_PREFIXES.get(style_key, STYLE_PREFIXES["instructional_diagram"])
    suffix   = STYLE_SUFFIXES.get(guardrail_key, "")

    # Global safety suffix
    safety = (
        "high quality medical illustration, educational purpose only, "
        "no graphic violence, no explicit content, clinical and professional, "
        "white background, 1024x1024, sharp and clear"
    )

    return f"{prefix}{template} {suffix}{safety}"


def build_video_prompt(intent_id: str, patient_context: Optional[Dict] = None) -> Dict:
    """
    Build Runway ML / Luma AI video prompt for the given medical intent.
    Returns dict with prompt, negative_prompt, duration_seconds, and clip_plan.
    """
    intent = __import__("backend.core.multimodal.visual_intent_detector", fromlist=["VISUAL_INTENTS"]).VISUAL_INTENTS.get(intent_id)
    if not intent:
        return {"prompt": f"Educational medical animation about {intent_id}", "duration_s": 30}

    dur_s    = intent.get("video_dur_s", 30)
    template = PROMPT_TEMPLATES.get(intent_id, "Medical procedure demonstration")

    # Runway ML Gen-3 expects short, vivid prompts
    prompt = (
        f"Educational medical animation. {template[:200]} "
        "Smooth camera movement. Clean medical illustration aesthetic. "
        "Labels fade in at each step. Professional healthcare production."
    )

    negative_prompt = (
        "blood, gore, graphic content, violence, real surgery footage, "
        "explicit content, poor quality, blurry, text errors, distorted anatomy"
    )

    # For videos > 10s (Runway max per clip = 10s), plan clip stitching
    clip_count = max(1, round(dur_s / 10))
    clips = []
    if clip_count > 1:
        step_labels = _extract_steps(template)
        for i in range(clip_count):
            step_label = step_labels[i] if i < len(step_labels) else f"Step {i+1}"
            clips.append({
                "clip_index":  i + 1,
                "prompt":      f"{step_label}. {prompt[:150]} Clip {i+1} of {clip_count}.",
                "duration_s":  10,
            })

    return {
        "prompt":          prompt,
        "negative_prompt": negative_prompt,
        "total_duration_s": dur_s,
        "clip_count":      clip_count,
        "clips":           clips or [{"clip_index": 1, "prompt": prompt, "duration_s": dur_s}],
    }


def _extract_steps(template: str) -> list:
    """Extract numbered steps from a template for clip planning."""
    steps = []
    import re
    for match in re.finditer(r'\d+\)\s+([^,\.]+)', template):
        steps.append(match.group(1).strip())
    return steps or [template[:80]]