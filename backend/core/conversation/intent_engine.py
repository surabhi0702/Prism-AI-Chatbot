# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/conversation/intent_engine.py
# PRISM Conversational AI Engine — Intent Recognition + Slot Filling
# ───────────────────────────────────────────────────────────────────────────────
# FLOW PER MESSAGE:
#   1. Classify intent of patient's query (first message only)
#   2. Extract any slot values from the latest message
#   3. Determine if we have enough context → generate a clarifying question
#   4. After ≤5 questions (or all critical slots filled) → fire full answer
#
# RESULT: Agents collect patient-specific context before answering, producing
#         answers with dramatically higher faithfulness, precision & recall.
#
# SKIP TRIGGERS: patient says "just answer", "enough questions", or similar
# MAX QUESTIONS: 5 per intent (configurable per agent)
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import re
import json
import uuid
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict
from datetime import datetime
from backend.core.conversation.frustration_detector import FrustrationDetector

# ─── Configuration ─────────────────────────────────────────────────────────────
MAX_CLARIFYING_QUESTIONS = 5

# Phrases that trigger immediate answer (skip remaining questions)
SKIP_KEYWORDS = [
    "just answer", "please answer", "skip", "enough questions",
    "stop asking", "just tell me", "answer now", "no more questions",
    "give me the answer", "just respond", "answer my question",
    "solo responde", "responde ya", "sin más preguntas",
    "bas poochho mat", "seedha jawab do",
]

# ─── INTENT DEFINITIONS PER DISEASE ───────────────────────────────────────────
# Each intent defines:
#   - description: what this intent covers
#   - critical_slots: MUST be filled before generating a complete answer
#   - optional_slots: nice to have, asked if time allows
#   - questions: mapping of slot → conversational question text

DISEASE_INTENTS: Dict[str, Dict] = {

    # ═══════════════ CANCER CARE (CA) ═══════════════
    "CA_SCREENING_CONCERN": {
        "agents": ["CA1"],
        "description": "Patient asking about cancer screening, tests, or early detection",
        "critical_slots": ["age", "gender", "family_history", "symptoms"],
        "optional_slots": ["last_screening", "risk_factors"],
        "questions": {
            "age":          "To give you the most accurate screening guidance, how old are you?",
            "gender":       "Could you tell me your biological sex — this helps determine which screening tests apply to you?",
            "family_history": "Has anyone in your immediate family (parent, sibling, child) been diagnosed with cancer? If yes, which type?",
            "symptoms":     "Are you experiencing any symptoms that prompted this question, or is this purely for preventive screening?",
            "last_screening": "When was your last cancer screening test, if you've had one before?",
            "risk_factors": "Do you smoke, drink alcohol regularly, or have any other risk factors you are aware of?",
        },
    },
    "CA_TREATMENT_UNDERSTANDING": {
        "agents": ["CA2"],
        "description": "Patient asking about cancer treatment options, side effects, or treatment planning",
        "critical_slots": ["cancer_type", "stage", "current_treatment", "treatment_concern"],
        "optional_slots": ["age", "comorbidities", "previous_treatment"],
        "questions": {
            "cancer_type":       "What type of cancer have you or your loved one been diagnosed with?",
            "stage":             "Do you know the stage of the cancer — Stage I, II, III, or IV?",
            "current_treatment": "Is treatment already underway, or are you exploring options before starting?",
            "treatment_concern": "What is your main concern about treatment — side effects, effectiveness, cost, or something else?",
            "age":               "What is the patient's age? This helps understand which treatment protocols are most relevant.",
            "comorbidities":     "Are there any other health conditions alongside the cancer — heart disease, diabetes, or others?",
        },
    },
    "CA_SYMPTOM_MANAGEMENT": {
        "agents": ["CA3"],
        "description": "Patient asking about managing side effects or symptoms during cancer treatment",
        "critical_slots": ["symptom", "treatment_type", "severity", "duration"],
        "optional_slots": ["medications_tried", "impact_on_daily_life"],
        "questions": {
            "symptom":           "Which symptom or side effect is bothering you most right now?",
            "treatment_type":    "What type of cancer treatment are you currently receiving — chemotherapy, radiation, immunotherapy, surgery, or a combination?",
            "severity":          "On a scale of 1 to 10, how severe is this symptom (1 = mild, 10 = unbearable)?",
            "duration":          "How long have you been experiencing this symptom?",
            "medications_tried": "Have you tried anything to manage it already — any medications, home remedies, or dietary changes?",
        },
    },
    "CA_SURVIVORSHIP_CARE": {
        "agents": ["CA4"],
        "description": "Patient asking about life after cancer, surveillance, or long-term side effects",
        "critical_slots": ["cancer_type", "treatment_completed", "current_concerns", "last_followup"],
        "optional_slots": ["fear_of_recurrence", "lifestyle_changes"],
        "questions": {
            "cancer_type":          "What type of cancer did you receive treatment for?",
            "treatment_completed": "When did you complete your primary treatment (surgery, chemo, or radiation)?",
            "current_concerns":    "Are you experiencing any specific long-term side effects like fatigue, 'chemo brain', or physical changes?",
            "last_followup":       "When was your last follow-up appointment or scan with your oncologist?",
            "lifestyle_changes":     "Have you made any significant changes to your diet or exercise routine since finishing treatment?",
        },
    },
    "CA_HEREDITARY_GENETICS": {
        "agents": ["CA5"],
        "description": "Patient asking about genetic testing, BRCA, or family risk of cancer",
        "critical_slots": ["family_history", "reason_for_testing", "previous_testing"],
        "optional_slots": ["age", "ethnicity"],
        "questions": {
            "family_history":    "Could you describe your family history of cancer — specifically which relatives and at what ages they were diagnosed?",
            "reason_for_testing":"Are you looking to get tested because of a personal diagnosis, or because of your family history?",
            "previous_testing":  "Have you or anyone in your family already had genetic testing for cancer genes?",
        },
    },
    "CA_GENERAL_ASSISTANCE": {
        "agents": ["CA6"],
        "description": "General cancer support, navigation, caregiver assistance, or logistical questions",
        "critical_slots": ["concern_type", "patient_relation"],
        "optional_slots": ["location", "current_need"],
        "questions": {
            "concern_type":     "Are you looking for general information about a cancer journey, or is this about navigation and logistical support?",
            "patient_relation": "Are you asking for yourself, or are you supporting a friend or family member?",
            "location":         "Which city or region are you located in — this helps me find local navigation resources?",
            "current_need":     "What is your most immediate need right now — financial guidance, caregiver support, or just general understanding?",
        },
    },

    # ═══════════════ DIABETES (DM) ═══════════════
    "DM_MEDICATION_INQUIRY": {
        "agents": ["DM2"],
        "description": "Patient asking about diabetes medications, doses, or drug choices",
        "critical_slots": ["diabetes_type", "current_medications", "hba1c", "comorbidities"],
        "optional_slots": ["duration_of_diabetes", "medication_concerns", "age"],
        "questions": {
            "diabetes_type":       "Are you asking about Type 1, Type 2, gestational diabetes, or are you not sure of your type?",
            "current_medications": "Are you currently taking any diabetes medications, or are you exploring options for the first time?",
            "hba1c":               "Do you know your most recent HbA1c (blood sugar control) level? For example 7.2% or 58 mmol/mol.",
            "comorbidities":       "Do you have any other health conditions such as kidney disease, heart disease, high blood pressure, or liver problems?",
            "duration_of_diabetes":"How long have you been living with diabetes?",
            "medication_concerns": "What is your main concern about diabetes medication — side effects, cost, weight gain, or something else?",
        },
    },
    "DM_GLUCOSE_MONITORING": {
        "agents": ["DM1"],
        "description": "Patient asking about blood sugar levels, monitoring, CGM, or glucose targets",
        "critical_slots": ["glucose_value", "timing", "diabetes_type", "current_medications"],
        "optional_slots": ["symptoms", "diet_recent", "activity_recent"],
        "questions": {
            "glucose_value":    "What blood glucose reading are you concerned about? Please share the number and the unit (mg/dL or mmol/L).",
            "timing":           "When was this reading taken — fasting in the morning, before a meal, after a meal, or at bedtime?",
            "diabetes_type":    "Do you have Type 1, Type 2, or another type of diabetes?",
            "current_medications": "What diabetes medications or insulin are you currently taking?",
            "symptoms":         "Are you feeling any symptoms right now — dizziness, sweating, blurred vision, or excessive thirst?",
            "diet_recent":      "What did you eat in the few hours before this reading, if you remember?",
        },
    },
    "DM_NUTRITION_QUERY": {
        "agents": ["DM3"],
        "description": "Patient asking about diet, meal planning, foods to avoid, or weight management",
        "critical_slots": ["diabetes_type", "dietary_goal", "cultural_foods", "current_hba1c"],
        "optional_slots": ["medications", "weight_concern", "activity_level"],
        "questions": {
            "diabetes_type":   "Is this question for Type 1, Type 2, or gestational diabetes?",
            "dietary_goal":    "What is your main dietary goal — lowering blood sugar, losing weight, managing cholesterol, or general healthy eating?",
            "cultural_foods":  "What cuisine or cultural foods do you regularly eat? This helps me give you practical, realistic advice.",
            "current_hba1c":   "What is your current HbA1c level, if you know it?",
            "activity_level":  "How physically active are you currently — sedentary, lightly active, moderately active, or very active?",
        },
    },
    "DM_COMPLICATION_CONCERN": {
        "agents": ["DM4"],
        "description": "Patient worried about diabetes complications — neuropathy, retinopathy, nephropathy, foot",
        "critical_slots": ["complication_type", "duration_of_diabetes", "hba1c_history", "symptoms"],
        "optional_slots": ["current_medications", "blood_pressure", "kidney_function"],
        "questions": {
            "complication_type":  "Which complication concerns you most — numbness in feet, eye problems, kidney issues, or something else?",
            "duration_of_diabetes":"How many years have you been living with diabetes?",
            "hba1c_history":      "What has your HbA1c been averaging over the past year or two?",
            "symptoms":           "Are you currently experiencing any symptoms — numbness, tingling, blurred vision, swollen ankles, or frequent infections?",
            "blood_pressure":     "Do you have high blood pressure, and if so, is it currently controlled?",
            "kidney_function":    "Have you had a kidney function test recently? Do you know your eGFR or creatinine level?",
        },
    },
    "DM_SPECIAL_POPULATIONS": {
        "agents": ["DM5"],
        "description": "Gestational diabetes, pediatric diabetes, or elderly diabetes concerns",
        "critical_slots": ["population_type", "main_concern", "current_management"],
        "questions": {
            "population_type":   "Is this regarding gestational diabetes (pregnancy), a child/teen, or an elderly patient?",
            "main_concern":      "What is the most pressing concern right now — sugar targets, safety, or managing daily life?",
            "support_network":      "Do you have a support system at home or in your community to help with managing these special needs?",
        },
    },
    "DM_GENERAL_ASSISTANCE": {
        "agents": ["DM6"],
        "description": "General diabetes lifestyle, health literacy, navigation, or non-clinical assistance",
        "critical_slots": ["topic_of_interest", "patient_type"],
        "optional_slots": ["travel_status", "insurance_concern"],
        "questions": {
            "topic_of_interest": "Are you looking for general diabetes lifestyle tips, or help navigating health services?",
            "patient_type":      "Are you living with Type 1, Type 2, or another form of diabetes?",
            "travel_status":     "Are you planning a trip soon? I can provide specific guidance for traveling with diabetes.",
            "insurance_concern": "Do you have any specific concerns about insurance coverage or the cost of supplies?",
        },
    },

    # ═══════════════ CARDIOVASCULAR (CV) ═══════════════
    "CV_SYMPTOM_ASSESSMENT": {
        "agents": ["CV1"],
        "description": "Patient describing cardiac symptoms — chest pain, breathlessness, palpitations, dizziness",
        "critical_slots": ["symptom", "onset", "severity", "associated_symptoms"],
        "optional_slots": ["cardiac_history", "risk_factors", "current_medications"],
        "questions": {
            "symptom":            "Can you describe the symptom as specifically as possible — where exactly do you feel it, and what does it feel like?",
            "onset":              "When did this symptom start, and does it come and go or is it constant?",
            "severity":           "On a scale of 1 to 10, how severe is this symptom right now?",
            "associated_symptoms":"Do you have any other symptoms alongside it — sweating, nausea, arm pain, jaw pain, or shortness of breath?",
            "cardiac_history":    "Have you ever been diagnosed with a heart condition, or had a heart attack or procedure in the past?",
            "risk_factors":       "Do you have high blood pressure, high cholesterol, diabetes, or do you smoke?",
        },
    },
    "CV_MEDICATION_QUERY": {
        "agents": ["CV3"],
        "description": "Patient asking about heart medications — beta blockers, statins, blood thinners, ACE inhibitors",
        "critical_slots": ["medication_name", "concern", "cardiac_diagnosis", "current_medications"],
        "optional_slots": ["side_effects_experienced", "other_medications", "kidney_function"],
        "questions": {
            "medication_name":   "Which cardiac medication are you asking about specifically?",
            "concern":           "What is your concern about this medication — side effects, interactions, dosing, or whether you still need it?",
            "cardiac_diagnosis": "What heart condition have you been diagnosed with that this medication is for?",
            "current_medications":"What other medications are you currently taking alongside this cardiac drug?",
            "side_effects_experienced": "Are you experiencing any side effects right now from the medication?",
        },
    },
    "CV_RISK_ASSESSMENT": {
        "agents": ["CV1", "CV5"],
        "description": "Patient asking about their cardiovascular risk, prevention, or lifestyle",
        "critical_slots": ["age", "blood_pressure", "cholesterol", "smoking_status"],
        "optional_slots": ["diabetes_status", "family_history", "activity_level", "weight"],
        "questions": {
            "age":             "How old are you? Age is one of the most important cardiovascular risk factors.",
            "blood_pressure":  "Do you know your blood pressure reading? For example, '135/85 mmHg'.",
            "cholesterol":     "Do you know your cholesterol levels — particularly your LDL or total cholesterol?",
            "smoking_status":  "Do you currently smoke, have you smoked in the past, or have you never smoked?",
            "diabetes_status": "Have you been diagnosed with diabetes or pre-diabetes?",
            "family_history":  "Has anyone in your immediate family had a heart attack or stroke before age 60?",
        },
    },
    "CV_EMERGENCY_ADVICE": {
        "agents": ["CV2"],
        "description": "Patient experiencing symptoms that might be an emergency (chest pain, etc.)",
        "critical_slots": ["symptom_detail", "severity", "onset_time"],
        "questions": {
            "symptom_detail": "Can you describe exactly what you are feeling — is it pressure, sharp pain, or something else?",
            "severity":       "On a scale of 1 to 10, how severe is the pain or discomfort?",
            "onset_time":     "How many minutes or hours ago did this start?",
        },
    },
    "CV_REHAB_LIFESTYLE": {
        "agents": ["CV4"],
        "description": "Cardiac rehabilitation, exercise, or heart-healthy nutrition",
        "critical_slots": ["cardiac_event", "activity_level", "dietary_habits"],
        "questions": {
            "cardiac_event":   "Have you recently had a heart attack, surgery, or a new diagnosis that brings you here?",
            "activity_level":  "How much physical activity are you currently able to do without feeling short of breath?",
            "dietary_habits":  "What are your typical eating habits like — are you following a specific heart-healthy diet like DASH or Mediterranean?",
        },
    },
    "CV_GENERAL_ASSISTANCE": {
        "agents": ["CV6"],
        "description": "General heart health wellness, prevention, literacy, and domain navigation",
        "critical_slots": ["goal", "risk_awareness"],
        "optional_slots": ["smoking_status", "activity_level"],
        "questions": {
            "goal":           "Are you looking to improve your overall heart health, or do you need help navigating our cardiovascular specialists?",
            "risk_awareness": "Do you have any known heart conditions or a family history of heart disease?",
            "smoking_status": "Do you currently smoke or have you recently quit? We have specific resources for heart-healthy cessation.",
            "activity_level": "How would you describe your current physical activity level — sedentary, moderate, or active?",
        },
    },

    # ═══════════════ MENTAL HEALTH (MH) ═══════════════
    "MH_DEPRESSION_ASSESSMENT": {
        "agents": ["MH1"],
        "description": "Patient experiencing low mood, sadness, hopelessness, or loss of interest",
        "critical_slots": ["duration", "severity", "impact_on_life", "sleep_appetite"],
        "optional_slots": ["previous_treatment", "life_events", "support_system"],
        "questions": {
            "duration":        "How long have you been feeling this way — days, weeks, or months?",
            "severity":        "On a scale of 1 to 10, how much is this affecting your ability to get through the day?",
            "impact_on_life":  "Which areas of your life are being most affected — work, relationships, self-care, or all of them?",
            "sleep_appetite":  "Has your sleep or appetite changed significantly? Are you sleeping too much or too little?",
            "previous_treatment": "Have you spoken to a doctor or therapist about this before, or tried any treatment?",
            "life_events":     "Has anything significant happened recently that may have triggered or worsened these feelings?",
        },
    },
    "MH_ANXIETY_CONCERN": {
        "agents": ["MH2"],
        "description": "Patient experiencing anxiety, worry, panic attacks, or fear",
        "critical_slots": ["anxiety_type", "triggers", "severity", "impact_on_daily"],
        "optional_slots": ["physical_symptoms", "duration", "previous_treatment"],
        "questions": {
            "anxiety_type":    "Can you describe what your anxiety feels like — constant worry, panic attacks, social anxiety, or specific fears?",
            "triggers":        "Are there specific situations, places, or thoughts that trigger your anxiety, or does it feel constant?",
            "severity":        "How often does the anxiety significantly interfere with your daily life — daily, a few times a week, or occasionally?",
            "impact_on_daily": "What activities or situations are you avoiding because of anxiety?",
            "physical_symptoms": "Do you experience physical symptoms during anxious moments — racing heart, sweating, dizziness, or difficulty breathing?",
        },
    },
    "MH_SLEEP_ISSUE": {
        "agents": ["MH3"],
        "description": "Patient experiencing insomnia, poor sleep quality, or sleep-related problems",
        "critical_slots": ["sleep_problem_type", "duration", "sleep_schedule", "daytime_impact"],
        "optional_slots": ["sleep_environment", "caffeine_alcohol", "stress_level"],
        "questions": {
            "sleep_problem_type": "What exactly is happening with your sleep — difficulty falling asleep, waking up in the night, waking too early, or not feeling rested?",
            "duration":           "How long has this sleep problem been going on?",
            "sleep_schedule":     "What time do you typically go to bed and wake up? And how many hours of sleep do you actually get?",
            "daytime_impact":     "How is poor sleep affecting you during the day — fatigue, difficulty concentrating, mood changes, or performance?",
            "stress_level":       "Would you say your stress levels are high right now? Are there particular worries keeping you awake?",
        },
    },
    "MH_TRAUMA_PTSD": {
        "agents": ["MH4"],
        "description": "Patient experiencing trauma-related symptoms or PTSD",
        "critical_slots": ["symptoms", "duration", "safety_concern"],
        "questions": {
            "symptoms":       "What kind of symptoms are you having — flashbacks, nightmares, feeling on edge, or avoiding certain places?",
            "duration":       "How long has this been affecting you?",
            "safety_concern": "Do you currently feel safe in your environment?",
        },
    },
    "MH_CRISIS_SUPPORT": {
        "agents": ["MH5"],
        "description": "Urgent mental health crisis or suicidal thoughts",
        "critical_slots": ["immediate_safety", "support_system"],
        "questions": {
            "immediate_safety": "Are you in a safe place right now? It's important to ensure your safety first.",
            "acknowledged":         "Thank you for sharing. I'm here to support you. Would you like to start by talking about warning signs or coping strategies?",
        },
    },
    "MH_GENERAL_ASSISTANCE": {
        "agents": ["MH6"],
        "description": "General mental well-being, mindfulness, stress reduction, and domain navigation",
        "critical_slots": ["wellness_goal", "current_state"],
        "optional_slots": ["mindfulness_experience", "support_preference"],
        "questions": {
            "wellness_goal":     "Are you looking for ways to improve your daily mental well-being, or do you need help finding a specialized mental health agent?",
            "current_state":      "How have you been feeling lately — overwhelmed, stressed, or just looking for general resilience tips?",
            "mindfulness_experience": "Have you ever practiced mindfulness or meditation before?",
            "support_preference": "Do you prefer self-help resilience techniques or are you looking for guidance on finding a professional therapist?",
        },
    },

    # ═══════════════ RESPIRATORY (RS) ═══════════════
    "RS_ASTHMA_MANAGEMENT": {
        "agents": ["RS1"],
        "description": "Patient asking about asthma symptoms, triggers, inhalers, or control",
        "critical_slots": ["symptom_pattern", "trigger", "current_inhalers", "frequency"],
        "optional_slots": ["severity_of_attacks", "peak_flow", "environmental_factors"],
        "questions": {
            "symptom_pattern": "Describe your asthma symptoms — is it mainly coughing, wheezing, chest tightness, or shortness of breath?",
            "trigger":         "What seems to trigger your asthma — exercise, cold air, dust, smoke, pollen, stress, or something else?",
            "current_inhalers":"What inhalers are you currently using? Please name them if you can (e.g. Ventolin, Seretide, Symbicort).",
            "frequency":       "How often do you need to use your reliever inhaler in a typical week?",
            "severity_of_attacks": "When an attack happens, how severe does it get — mild discomfort or unable to speak?",
        },
    },
    "RS_BREATHING_DIFFICULTY": {
        "agents": ["RS2", "RS3"],
        "description": "Patient experiencing breathlessness, shortness of breath, or reduced exercise tolerance",
        "critical_slots": ["onset", "severity", "associated_symptoms", "activity_level"],
        "optional_slots": ["smoking_history", "known_lung_condition", "oxygen_use"],
        "questions": {
            "onset":              "Did your breathing difficulty start suddenly or has it been gradually getting worse over time?",
            "severity":           "Does the breathlessness happen at rest, with light activity, or only with strenuous exercise?",
            "associated_symptoms":"Do you have any other symptoms alongside the breathlessness — cough, wheezing, chest pain, or swollen ankles?",
            "activity_level":     "Before the breathing problem started, how active were you normally?",
            "smoking_history":    "Do you currently smoke or have you smoked in the past? If so, for how many years and how many cigarettes per day?",
        },
    },
    "RS_LUNG_MEDICATION": {
        "agents": ["RS4"],
        "description": "Respiratory medications, inhalers, or oxygen therapy",
        "critical_slots": ["medication_name", "usage_frequency", "technique_concern"],
        "questions": {
            "medication_name":    "Which respiratory medication or inhaler are you asking about?",
            "usage_frequency":    "How often do you use this medication in a typical day or week?",
            "technique_concern": "Do you have any concerns about how to use your inhaler correctly?",
        },
    },
    "RS_SLEEP_APNEA": {
        "agents": ["RS5"],
        "description": "Sleep apnea, snoring, or CPAP usage",
        "critical_slots": ["symptoms", "cpap_use", "weight_concern"],
        "questions": {
            "symptoms":       "Do you experience heavy snoring, gasping for air at night, or excessive daytime sleepiness?",
            "cpap_use":       "If you've been prescribed CPAP, how are you finding the treatment so far?",
            "weight_concern": "Has your weight changed recently, or are you concerned about how it affects your breathing?",
        },
    },
    "RS_GENERAL_ASSISTANCE": {
        "agents": ["RS6"],
        "description": "General lung health, air quality awareness, and respiratory domain navigation",
        "critical_slots": ["breathing_concern", "environment"],
        "optional_slots": ["exercise_habits", "specialist_need"],
        "questions": {
            "breathing_concern": "Are you looking for general lung health tips, or do you have a specific concern about your breathing?",
            "environment":       "Do you live in an area with air quality concerns, such as high pollution or smoke?",
            "exercise_habits":   "Do you currently engage in any regular physical activity or breathing exercises?",
            "specialist_need":   "Are you looking for a specialized agent for conditions like Asthma or COPD, or do you need general guidance first?",
        },
    },

    # ═══════════════ GENERAL / CATCH-ALL ═══════════════
    "GENERAL_HEALTH_QUERY": {
        "agents": ["CA6", "DM6", "CV6", "MH6", "RS6"],
        "description": "General health query not fitting a specific intent",
        "critical_slots": ["main_concern", "duration", "context"],
        "optional_slots": ["age", "existing_conditions", "what_tried"],
        "questions": {
            "main_concern": "Could you tell me a bit more about your main concern so I can give you the most relevant information?",
            "duration":     "How long have you been dealing with this issue?",
            "context":      "Is this question for yourself or for a family member, and roughly what is your age?",
            "existing_conditions": "Do you have any existing health conditions that might be relevant?",
            "what_tried":   "Have you already tried anything to address this, or spoken to a doctor about it?",
        },
    },
}

# ─── Intent → primary intent mapping for quick lookup ─────────────────────────
AGENT_INTENT_MAP: Dict[str, List[str]] = {}
for intent_key, intent_def in DISEASE_INTENTS.items():
    for agent_id in intent_def.get("agents", []):
        if agent_id not in AGENT_INTENT_MAP:
            AGENT_INTENT_MAP[agent_id] = []
        AGENT_INTENT_MAP[agent_id].append(intent_key)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — CONVERSATION STATE
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ConversationState:
    """Tracks the conversational state for a single patient conversation."""

    conversation_id:    str
    agent_id:           str
    intent:             Optional[str]       = None    # e.g. "DM_MEDICATION_INQUIRY"
    intent_confidence:  float               = 0.0
    intent_description: str                 = ""

    # Slot tracking
    slots_filled:       Dict[str, Any]      = field(default_factory=dict)
    slots_critical:     List[str]           = field(default_factory=list)
    slots_optional:     List[str]           = field(default_factory=list)

    # Question tracking
    questions_asked:    int                 = 0
    max_questions:      int                 = MAX_CLARIFYING_QUESTIONS
    question_log:       List[Dict]          = field(default_factory=list)

    # State flags
    is_clarifying:      bool                = False   # True while asking questions
    is_ready_to_answer: bool                = False   # True when enough context gathered
    skip_requested:     bool                = False   # Patient said "just answer"
    first_message_done: bool                = False   # Intent classified

    # Context for final answer
    gathered_context:   str                 = ""      # Human-readable summary of slots
    created_at:         str                 = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    updated_at:         str                 = field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )

    def to_dict(self) -> Dict:
        d = asdict(self)
        d["updated_at"] = datetime.utcnow().isoformat()
        return d

    @classmethod
    def from_dict(cls, data: Dict) -> "ConversationState":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def critical_slots_filled_count(self) -> int:
        return sum(1 for s in self.slots_critical if self.slots_filled.get(s))

    def critical_slots_filled_pct(self) -> float:
        if not self.slots_critical:
            return 1.0
        return self.critical_slots_filled_count() / len(self.slots_critical)

    def next_missing_slot(self) -> Optional[str]:
        """Returns the highest-priority unfilled slot."""
        # Critical slots first
        for s in self.slots_critical:
            if not self.slots_filled.get(s):
                return s
        # Then optional
        for s in self.slots_optional:
            if not self.slots_filled.get(s):
                return s
        return None

    def build_context_summary(self) -> str:
        """Build a human-readable context string to inject into the answer prompt."""
        if not self.slots_filled:
            return ""
        lines = ["PATIENT CONTEXT GATHERED THROUGH CONVERSATION:"]
        for slot, value in self.slots_filled.items():
            if value:
                label = slot.replace("_", " ").title()
                lines.append(f"• {label}: {value}")
        return "\n".join(lines)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — INTENT RECOGNIZER
# ═══════════════════════════════════════════════════════════════════════════════

def recognize_intent(
    message: str,
    agent_id: str,
    conversation_history: List[Dict],
    language: str = "en",
) -> Dict:
    """
    Use LLM to classify the intent of the patient's query
    and extract any slot values already present in the message.

    Returns: {intent, confidence, description, slots_extracted, immediately_answerable}
    """
    from backend.core.agents.base_agent import call_llm_sync

    # Get valid intents for this agent
    valid_intents = AGENT_INTENT_MAP.get(agent_id.upper(), list(DISEASE_INTENTS.keys()))
    intent_options = "\n".join([
        f"- {k}: {v['description']}"
        for k, v in DISEASE_INTENTS.items()
        if k in valid_intents or "GENERAL" in k
    ])

    # Build recent history snippet
    recent = "\n".join([
        f"{'Patient' if m['role'] == 'user' else 'PRISM'}: {m['content'][:150]}"
        for m in conversation_history[-4:]
    ]) if conversation_history else "No prior history."

    system_prompt = f"""You are a medical intent classifier for PRISM AI.
Classify the patient's query into one of these intents AND extract any information
already present in the query that can fill slots for that intent.

VALID INTENTS:
{intent_options}
- GENERAL_HEALTH_QUERY: General health query not fitting other intents

CONVERSATION HISTORY:
{recent}

PATIENT MESSAGE: "{message}"

Return ONLY a JSON object (no markdown, no explanation):
{{
  "intent": "INTENT_KEY",
  "confidence": 0.0_to_1.0,
  "description": "one sentence description of what patient needs",
  "immediately_answerable": true_or_false,
  "slots_extracted": {{
    "slot_name": "extracted value or null"
  }}
}}

Set immediately_answerable=true ONLY if:
- The query is extremely simple and general (e.g. "what is diabetes?")
- All critical information is already in the message
- This is clearly a factual/educational question needing no personalisation

For all clinical/personal queries, set immediately_answerable=false."""

    result = call_llm_sync(
        system_prompt=system_prompt,
        user_message=message,
        history=[],
        temperature=0.05,
        max_tokens=400,
    )

    raw = result["response"].strip()
    raw = re.sub(r'^```json?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)

    try:
        parsed = json.loads(raw)
        # Validate intent key
        intent_key = parsed.get("intent", "GENERAL_HEALTH_QUERY")
        if intent_key not in DISEASE_INTENTS:
            intent_key = "GENERAL_HEALTH_QUERY"
        parsed["intent"] = intent_key
        return parsed
    except json.JSONDecodeError:
        return {
            "intent":                "GENERAL_HEALTH_QUERY",
            "confidence":            0.5,
            "description":           message[:100],
            "immediately_answerable": False,
            "slots_extracted":        {},
        }


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — SLOT EXTRACTOR
# ═══════════════════════════════════════════════════════════════════════════════

def extract_slots_from_response(
    patient_message: str,
    intent: str,
    question_just_asked: Optional[str],
    existing_slots: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Extract slot values from the patient's latest message.
    Uses the question just asked as context to interpret the answer.
    Returns updated slots dict.
    """
    from backend.core.agents.base_agent import call_llm_sync

    intent_def   = DISEASE_INTENTS.get(intent, DISEASE_INTENTS["GENERAL_HEALTH_QUERY"])
    all_slots    = intent_def["critical_slots"] + intent_def.get("optional_slots", [])
    unfilled     = [s for s in all_slots if not existing_slots.get(s)]

    if not unfilled:
        return existing_slots

    system_prompt = f"""You are extracting medical information slots from a patient's message.
Intent: {intent}
Slots to fill: {', '.join(unfilled)}
Question that was just asked: "{question_just_asked or 'None'}"
Patient's response: "{patient_message}"
Existing slots already filled: {json.dumps(existing_slots)}

Extract values from the patient's response. Return ONLY a JSON object:
{{
  "slot_name": "extracted value as stated by patient, or null if not mentioned"
}}

Rules:
- Only extract slots that are clearly answered in this message
- Keep the patient's exact words/values where possible
- For numeric values, include the unit (e.g. "8.2%" not just "8.2")
- For yes/no questions, capture "yes", "no", or the detailed response
- Do not invent values — null if not stated"""

    result = call_llm_sync(
        system_prompt=system_prompt,
        user_message=patient_message,
        history=[],
        temperature=0.05,
        max_tokens=300,
    )

    raw = result["response"].strip()
    raw = re.sub(r'^```json?\s*', '', raw, flags=re.MULTILINE)
    raw = re.sub(r'\s*```$', '', raw, flags=re.MULTILINE)

    try:
        extracted = json.loads(raw)
        # Merge with existing, only update if new value is non-null
        updated = dict(existing_slots)
        for slot, value in extracted.items():
            if value is not None and value != "" and slot in all_slots:
                updated[slot] = value
        return updated
    except json.JSONDecodeError:
        return existing_slots


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — QUESTION GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

def generate_clarifying_question(
    state: ConversationState,
    patient_name: str = "there",
    language: str = "en",
) -> str:
    """
    Generate a ChatGPT-style natural, warm, and varied clarifying question.
    Uses the full conversation history and missing slots to ensure a perfect flow.
    """
    from backend.core.agents.base_agent import call_llm_sync

    intent_def    = DISEASE_INTENTS.get(state.intent, DISEASE_INTENTS["GENERAL_HEALTH_QUERY"])
    next_slot     = state.next_missing_slot()
    
    if not next_slot:
        return ""

    # Get description of what we need
    slot_desc = next_slot.replace("_", " ")
    
    # Context for the LLM
    slots_summary = ", ".join([f"{k}: {v}" for k, v in state.slots_filled.items()])
    unfilled = [s for s in state.slots_critical + state.slots_optional if not state.slots_filled.get(s)]
    
    system_prompt = f"""You are a warm, empathetic clinical assistant at PRISM. 
Your goal is to ask a SINGLE clarifying question to help understand the patient's {state.intent.lower()} concern.

CURRENT STATE:
- Patient Name: {patient_name}
- Intent: {state.intent}
- Information already gathered: {slots_summary if slots_summary else 'None yet'}
- Next piece of information needed: {slot_desc}
- Other missing information: {', '.join(unfilled[1:]) if len(unfilled) > 1 else 'None'}

RULES:
1. Ask ONLY ONE question.
2. Be extremely conversational and warm (ChatGPT style).
3. Do NOT mention "Question X of 5" or any numbering.
4. Acknowledge what they just said naturally.
5. If this is the first question, start with a warm welcome and explain why you're asking.
6. If it's a follow-up, use a natural transition.
7. Include a small, encouraging clinical tidbit to increase awareness.
8. Tone: Professional but very caring and human.
9. Language: {language}

Example of bad (robotic): "Question 2 of 5: What is your severity?"
Example of good (ChatGPT style): "Thank you for sharing that. It helps me understand the timeline. To get a better sense of how you're feeling right now, could you describe the severity of the pain on a scale of 1 to 10? Also, remember that keeping a daily log can really help your doctor see the patterns."

Return ONLY the question text."""

    result = call_llm_sync(
        system_prompt=system_prompt,
        user_message=f"Generate the next question for the patient in {language}.",
        history=[],
        temperature=0.7,
        max_tokens=400,
    )

    return result["response"].strip()


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — SKIP DETECTOR
# ═══════════════════════════════════════════════════════════════════════════════

def detect_skip_request(message: str) -> bool:
    """Returns True if patient is asking to skip questions and get the answer now."""
    msg_lower = message.lower()
    return any(kw in msg_lower for kw in SKIP_KEYWORDS)


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — READINESS CHECK
# ═══════════════════════════════════════════════════════════════════════════════

def should_answer_now(state: ConversationState, message: str, force_immediate: bool = False) -> bool:
    """
    Determine if we have enough context to generate a full answer.
    """
    if force_immediate or detect_skip_request(message):
        return True
    if state.questions_asked >= state.max_questions:
        return True
    # Only answer if 100% of critical slots are filled
    if state.critical_slots_filled_pct() >= 1.0:
        return True
    return False


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — MAIN CONVERSATIONAL ENGINE (PUBLIC API)
# ═══════════════════════════════════════════════════════════════════════════════

def process_conversational_turn(
    message:              str,
    agent_id:             str,
    conversation_id:      str,
    conversation_history: List[Dict],
    state_dict:           Optional[Dict],   # Loaded from DB/cache
    patient_name:         str = "there",
    language:             str = "en",
    force_immediate_answer: bool = False,
) -> Dict:
    """
    Main entry point — called from the FastAPI chat endpoint before LangGraph.

    Returns:
        response_type:   "question" | "answer"
        question_text:   populated if response_type == "question"
        state:           updated ConversationState dict (save this to DB)
        context_summary: populated if response_type == "answer"
        question_number: current question index
        max_questions:   always MAX_CLARIFYING_QUESTIONS
        intent:          detected intent key
        slots_filled:    dict of gathered slot values
        skip_requested:  bool
    """

    # ── Load or initialise state ───────────────────────────────────────────────
    if state_dict:
        state = ConversationState.from_dict(state_dict)
    else:
        state = ConversationState(
            conversation_id=conversation_id,
            agent_id=agent_id.upper(),
        )

    # ── Detect Frustration early ──────────────────────────────────────────────
    detector = FrustrationDetector()
    frustration_res = detector.compute(message, conversation_history)
    is_frustrated   = frustration_res["is_frustrated"]

    if is_frustrated:
        state.is_ready_to_answer = True
        state.gathered_context   = state.build_context_summary()
        return {
            "response_type":   "answer",
            "question_text":   None,
            "state":           state.to_dict(),
            "context_summary": state.gathered_context,
            "question_number": state.questions_asked,
            "max_questions":   state.max_questions,
            "intent":          state.intent or "GENERAL_HEALTH_QUERY",
            "slots_filled":    state.slots_filled,
            "skip_requested":  False,
            "is_frustrated":   True,
        }

    # ── Check for skip request ─────────────────────────────────────────────────
    if detect_skip_request(message):
        state.skip_requested    = True
        state.is_ready_to_answer = True
        state.gathered_context  = state.build_context_summary()
        return {
            "response_type":  "answer",
            "question_text":  None,
            "state":          state.to_dict(),
            "context_summary": state.gathered_context,
            "question_number": state.questions_asked,
            "max_questions":  state.max_questions,
            "intent":         state.intent,
            "slots_filled":   state.slots_filled,
            "skip_requested": True,
        }

    # ── FIRST message: classify intent ────────────────────────────────────────
    if not state.first_message_done:
        intent_result  = recognize_intent(message, agent_id, conversation_history, language)
        intent_key     = intent_result.get("intent", "GENERAL_HEALTH_QUERY")
        intent_def     = DISEASE_INTENTS.get(intent_key, DISEASE_INTENTS["GENERAL_HEALTH_QUERY"])

        state.intent             = intent_key
        state.intent_confidence  = intent_result.get("confidence", 0.5)
        state.intent_description = intent_result.get("description", "")
        state.slots_critical     = list(intent_def.get("critical_slots", []))
        state.slots_optional     = list(intent_def.get("optional_slots", []))
        state.first_message_done = True

        # Merge any slots already extracted from the first message
        extracted = intent_result.get("slots_extracted", {})
        for slot, value in extracted.items():
            if value:
                state.slots_filled[slot] = value

        # If intent is immediately answerable, skip questions
        if force_immediate_answer or intent_result.get("immediately_answerable", False):
            state.is_ready_to_answer = True
            state.gathered_context   = state.build_context_summary()
            return {
                "response_type":   "answer",
                "question_text":   None,
                "state":           state.to_dict(),
                "context_summary": state.gathered_context,
                "question_number": 0,
                "max_questions":   state.max_questions,
                "intent":          state.intent,
                "slots_filled":    state.slots_filled,
                "skip_requested":  False,
            }

    else:
        # ── SUBSEQUENT messages: extract slot values from patient's reply ───────
        last_question = (
            state.question_log[-1]["question"] if state.question_log else None
        )
        state.slots_filled = extract_slots_from_response(
            patient_message=message,
            intent=state.intent,
            question_just_asked=last_question,
            existing_slots=state.slots_filled,
        )

    # ── Decide: ask next question OR generate final answer ───────────────────
    if should_answer_now(state, message, force_immediate=force_immediate_answer):
        state.is_ready_to_answer = True
        state.gathered_context   = state.build_context_summary()
        return {
            "response_type":   "answer",
            "question_text":   None,
            "state":           state.to_dict(),
            "context_summary": state.gathered_context,
            "question_number": state.questions_asked,
            "max_questions":   state.max_questions,
            "intent":          state.intent,
            "slots_filled":    state.slots_filled,
            "skip_requested":  state.skip_requested,
        }

    # ── Generate next clarifying question ─────────────────────────────────────
    question_text = generate_clarifying_question(state, patient_name, language)

    if not question_text:
        # No more slots to ask about — answer now
        state.is_ready_to_answer = True
        state.gathered_context   = state.build_context_summary()
        return {
            "response_type":   "answer",
            "question_text":   None,
            "state":           state.to_dict(),
            "context_summary": state.gathered_context,
            "question_number": state.questions_asked,
            "max_questions":   state.max_questions,
            "intent":          state.intent,
            "slots_filled":    state.slots_filled,
            "skip_requested":  False,
        }

    # Log the question
    state.questions_asked += 1
    state.is_clarifying   = True
    state.question_log.append({
        "number":   state.questions_asked,
        "question": question_text,
        "slot":     state.next_missing_slot() or "general",
        "asked_at": datetime.utcnow().isoformat(),
    })

    return {
        "response_type":  "question",
        "question_text":  question_text,
        "state":          state.to_dict(),
        "context_summary": "",
        "question_number": state.questions_asked,
        "max_questions":  state.max_questions,
        "intent":         state.intent,
        "slots_filled":   state.slots_filled,
        "skip_requested": False,
    }