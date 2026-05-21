# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/conversation/response_engine.py
# PRISM Response Engine — Varied, Intent-Driven, Anti-Repetitive Responses
# ───────────────────────────────────────────────────────────────────────────────
# PROBLEMS SOLVED (from real chat logs analysis):
#   ✗ BEFORE: Same 1-6 numbered format every single response
#   ✗ BEFORE: Generic content repeated across agents and diseases
#   ✗ BEFORE: Patient gets identical answer after 3-4 clarifying questions
#   ✗ BEFORE: No follow-up questions to keep patient engaged
#   ✗ BEFORE: Low confidence → more generic → worse experience
#   ✗ BEFORE: No memory → same topic answered multiple times
#
#   ✓ AFTER: 8 response formats rotated intelligently per intent
#   ✓ AFTER: Intent-specific content that feels tailored
#   ✓ AFTER: 2-3 clickable follow-up questions after every AI response
#   ✓ AFTER: Memory of covered topics → "I mentioned X earlier, let me add..."
#   ✓ AFTER: Progressive disclosure → short response + offer to expand
#   ✓ AFTER: Reminder when patient re-asks something already covered
# ═══════════════════════════════════════════════════════════════════════════════

from __future__ import annotations

import re
import json
import hashlib
import random
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field, asdict
from datetime import datetime
from backend.core.conversation.chip_deduplication import process_chips_for_response
from backend.core.conversation.frustration_detector import FrustrationDetector
from backend.core.quality.conversation_quality import QualityScorer, get_quality_recommendation
from backend.database.models import AgentQuestion, AsyncSession
from sqlalchemy import select, update, func
import asyncio

# ─── How many previous responses to remember for anti-repetition ──────────────
MEMORY_WINDOW = 10

# ─── Minimum words before offering progressive expansion ──────────────────────
PROGRESSIVE_THRESHOLD = 180  # words — above this, split into chunk + "tell me more"

# ─── Confidence below which we switch to a different response strategy ─────────
LOW_CONFIDENCE_THRESHOLD = 0.55


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 1 — FULL INTENT TAXONOMY (all 5 diseases, all agents)
# ═══════════════════════════════════════════════════════════════════════════════

INTENT_TAXONOMY: Dict[str, Dict] = {

    # ── DIABETES (DM) ──────────────────────────────────────────────────────────
    "DM_LIFESTYLE_INTRO": {
        "agents": ["DM3", "DM6"],
        "label": "Lifestyle introduction for new diabetes patient",
        "triggers": ["healthy life", "lifestyle", "protect from diabetes", "what to eat",
                     "what to avoid", "how to live", "starting out", "new patient", "habits"],
        "follow_up_questions": [
            "Do you know what type of diabetes you have — Type 1, Type 2, or pre-diabetes?",
            "How long have you been diagnosed, and what has your day-to-day routine been like?",
            "Are there any specific areas you want to start with — diet, exercise, or monitoring?",
            "What meals do you eat most often in a week?",
            "Has your doctor mentioned anything about your HbA1c level recently?",
        ],
        "response_themes": ["empowerment", "small_steps", "personalised_first"],
        "max_response_words": 140,
    },
    "DM_HYPOGLYCEMIA": {
        "agents": ["DM1", "DM2", "DM6"],
        "label": "Hypoglycemia — low blood sugar management",
        "triggers": ["low sugar", "hypoglycemia", "dizzy", "shaking", "sweating",
                     "sugar dropped", "feeling faint", "low glucose", "below 70"],
        "follow_up_questions": [
            "When you have a low blood sugar episode, what do you usually do first?",
            "How often does this happen in a typical week, and at what time of day?",
            "Are you on any insulin or medications that could be causing these lows?",
            "Do you carry anything with you in case of a low episode — glucose tablets, juice?",
            "Have you been able to identify any patterns — after exercise, skipping meals?",
        ],
        "response_themes": ["safety_first", "practical_steps", "pattern_recognition"],
        "max_response_words": 120,
    },
    "DM_MEDICATION_CONCERN": {
        "agents": ["DM2", "DM6"],
        "label": "Medication frustration or treatment not working",
        "triggers": ["nothing happened", "same response", "not working", "frustrated",
                     "seen specialist", "tried everything", "no improvement", "getting worse"],
        "follow_up_questions": [
            "Which medications have you tried so far, and how long did you take them for?",
            "What was the specialist's explanation when you felt nothing changed?",
            "Have you had a chance to try CGM (continuous glucose monitoring) yet?",
            "How would you describe your blood sugar patterns over the past month?",
            "On a scale of 1-10, how frustrated are you with your current situation?",
        ],
        "response_themes": ["validation_first", "fresh_angle", "actionable_pivot"],
        "max_response_words": 130,
    },
    "DM_MONITORING_QUERY": {
        "agents": ["DM1"],
        "label": "Blood glucose monitoring and targets",
        "triggers": ["blood sugar", "glucose level", "hba1c", "check sugar", "cgm",
                     "meter reading", "target range", "testing", "monitor"],
        "follow_up_questions": [
            "Are you currently checking your blood sugar with a finger-prick meter or a CGM sensor?",
            "What reading did you last see, and when was it taken?",
            "Do you know your HbA1c from your last doctor's visit?",
            "At what time of day do your readings tend to be highest or lowest?",
        ],
        "response_themes": ["data_focused", "practical", "target_setting"],
        "max_response_words": 130,
    },
    "DM_NUTRITION": {
        "agents": ["DM3"],
        "label": "Diabetes diet and nutrition guidance",
        "triggers": ["what to eat", "food", "diet", "carbs", "carbohydrates", "meal",
                     "sugar in food", "rice", "bread", "glycaemic", "gi index"],
        "follow_up_questions": [
            "What does a typical day of meals look like for you right now?",
            "Are there cultural foods you eat regularly that you're worried about?",
            "Do you find it harder to manage blood sugar after breakfast, lunch, or dinner?",
            "Are you vegetarian, vegan, or do you have any food restrictions I should know about?",
        ],
        "response_themes": ["cultural_aware", "practical_swaps", "not_deprivation"],
        "max_response_words": 140,
    },
    "DM_COMPLICATION_AWARENESS": {
        "agents": ["DM4"],
        "label": "Diabetes complications concern",
        "triggers": ["neuropathy", "numbness", "tingling", "kidney", "eye", "retinopathy",
                     "foot", "wound", "complications", "long term damage", "egfr"],
        "follow_up_questions": [
            "Which complication are you most concerned about — kidneys, eyes, feet, or nerves?",
            "Have you noticed any new symptoms recently — tingling, blurred vision, swelling?",
            "When was your last kidney function test or eye check?",
            "What does your average HbA1c look like over the last year or two?",
        ],
        "response_themes": ["prevention_focused", "monitoring_plan", "early_detection"],
        "max_response_words": 130,
    },

    # ── CARDIOVASCULAR (CV) ────────────────────────────────────────────────────
    "CV_CHEST_PAIN_TRIAGE": {
        "agents": ["CV1", "CV2", "CV6"],
        "label": "Chest pain initial assessment",
        "triggers": ["chest pain", "chest tightness", "pressure in chest", "heart pain",
                     "left chest", "right chest", "chest discomfort", "ache in chest"],
        "follow_up_questions": [
            "On a scale of 1 to 10, how would you rate the pain right now?",
            "Does anything make it better or worse — rest, movement, breathing deeply?",
            "Do you have any other symptoms alongside the chest pain — shortness of breath, dizziness, arm pain?",
            "Have you ever had chest pain like this before, or is this new?",
        ],
        "response_themes": ["safety_triage_first", "symptom_mapping", "no_alarm_but_vigilant"],
        "max_response_words": 110,
        "emergency_check": True,
    },
    "CV_STRESS_CARDIAC": {
        "agents": ["CV1", "CV5", "CV6"],
        "label": "Work stress and heart health connection",
        "triggers": ["job stress", "work stress", "anxiety chest", "stress chest pain",
                     "heart racing", "palpitations stress", "overworked", "pressure at work"],
        "follow_up_questions": [
            "Would you say your stress level is worse than usual recently, or has it been building for months?",
            "Are you getting any regular exercise or time to decompress after work?",
            "Have you been checked for high blood pressure or had any cardiac tests done recently?",
            "On top of the chest pain, how is your sleep quality and energy level?",
        ],
        "response_themes": ["mind_body_link", "practical_stress_tools", "when_to_escalate"],
        "max_response_words": 130,
    },
    "CV_MEDICATION_QUERY": {
        "agents": ["CV3"],
        "label": "Cardiac medication question",
        "triggers": ["beta blocker", "statin", "warfarin", "aspirin", "blood thinner",
                     "lisinopril", "metoprolol", "side effects medication", "heart medication"],
        "follow_up_questions": [
            "Which medication specifically is causing you concern — the name if you know it?",
            "What side effect are you experiencing, and how long has it been happening?",
            "Are you taking any other medications, supplements, or herbal remedies alongside it?",
            "Has your doctor mentioned your kidney function or liver tests recently?",
        ],
        "response_themes": ["pharmacology_plain_language", "safety_monitoring", "when_to_call_doctor"],
        "max_response_words": 130,
    },
    "CV_RISK_PREVENTION": {
        "agents": ["CV1", "CV5", "CV6"],
        "label": "Cardiovascular risk and prevention",
        "triggers": ["heart disease risk", "prevent heart attack", "lower cholesterol",
                     "blood pressure control", "cardiovascular health", "risk factors"],
        "follow_up_questions": [
            "Do you know your current blood pressure and cholesterol numbers?",
            "Do you smoke, or have you smoked in the past?",
            "Is there a family history of heart disease or stroke that worries you?",
            "How would you describe your current activity level — sedentary, lightly active, or regularly exercising?",
        ],
        "response_themes": ["risk_score_education", "modifiable_factors", "lifestyle_wins"],
        "max_response_words": 130,
    },

    # ── MENTAL HEALTH (MH) ────────────────────────────────────────────────────
    "MH_INSOMNIA_INITIAL": {
        "agents": ["MH3"],
        "label": "Insomnia — initial presentation",
        "triggers": ["can't sleep", "insomnia", "sleep problem", "not sleeping",
                     "trouble sleeping", "fix sleep", "sleeping pills", "wake up"],
        "follow_up_questions": [
            "Is it mainly falling asleep that's hard, staying asleep, or waking far too early?",
            "How many hours of sleep do you actually get versus how many you'd like?",
            "How long has this been going on — weeks, months, or years?",
            "What's typically going through your mind when you're lying awake?",
        ],
        "response_themes": ["validating_exhaustion", "pattern_first", "small_wins"],
        "max_response_words": 120,
    },
    "MH_SLEEP_SCHEDULE": {
        "agents": ["MH3"],
        "label": "Delayed sleep phase or irregular sleep schedule",
        "triggers": ["3 am", "late night", "sleep late", "wake late", "delayed sleep",
                     "sleep schedule", "circadian", "night owl", "can't sleep early"],
        "follow_up_questions": [
            "If you could wake up at any time without an alarm, what time would that naturally be?",
            "Do you work shifts, or do you have a fixed 9-to-5 schedule you need to meet?",
            "Have you tried shifting your sleep time earlier before — what happened?",
            "How is your exposure to sunlight in the morning — do you go outside or stay indoors?",
        ],
        "response_themes": ["circadian_science_simple", "light_therapy", "gradual_shift"],
        "max_response_words": 130,
    },
    "MH_CBTI_GUIDANCE": {
        "agents": ["MH3"],
        "label": "CBT-I — Cognitive Behavioural Therapy for Insomnia",
        "triggers": ["cbt", "therapy sleep", "cognitive therapy", "sleep restriction",
                     "sleep compression", "sleep efficiency", "stimulus control"],
        "follow_up_questions": [
            "Have you ever worked with a therapist or sleep coach on your sleep before?",
            "How do you feel about the idea of temporarily restricting your time in bed to improve sleep quality?",
            "What do you usually do in bed besides sleeping — phone, TV, reading?",
            "How consistent is your wake time — do you wake at the same time even on weekends?",
        ],
        "response_themes": ["protocol_practical", "week_by_week", "realistic_expectations"],
        "max_response_words": 140,
    },
    "MH_DEPRESSION_CONCERN": {
        "agents": ["MH1"],
        "label": "Depression symptoms or low mood",
        "triggers": ["feeling low", "sad", "depressed", "hopeless", "no motivation",
                     "not enjoying", "empty", "exhausted emotionally", "crying"],
        "follow_up_questions": [
            "How long have you been feeling this way — was there a specific trigger, or did it build gradually?",
            "Are there moments in the day when you feel slightly better, or is it pretty constant?",
            "How is your sleep and appetite been alongside these feelings?",
            "Have you spoken to anyone — a friend, family member, or doctor — about how you've been feeling?",
        ],
        "response_themes": ["non_judgemental", "normalise_then_inform", "clear_next_step"],
        "max_response_words": 120,
    },
    "MH_ANXIETY_CONCERN": {
        "agents": ["MH2"],
        "label": "Anxiety, worry, or panic",
        "triggers": ["anxious", "anxiety", "panic", "worry", "racing heart", "scared",
                     "fear", "nervous", "overthinking", "can't relax"],
        "follow_up_questions": [
            "Does the anxiety come on in specific situations, or is it more of a constant background hum?",
            "Have you experienced panic attacks — sudden intense fear with physical symptoms like racing heart?",
            "Is the anxiety stopping you from doing things you used to do normally?",
            "What tends to make it better, even a little — distraction, breathing, talking to someone?",
        ],
        "response_themes": ["grounding_first", "understanding_anxiety_cycle", "practical_tools"],
        "max_response_words": 120,
    },

    # ── CANCER CARE (CA) ──────────────────────────────────────────────────────
    "CA_NEW_DIAGNOSIS": {
        "agents": ["CA6"],
        "label": "Newly diagnosed with cancer — orientation",
        "triggers": ["just diagnosed", "newly diagnosed", "found out I have cancer",
                     "cancer diagnosis", "what now", "where to start", "overwhelmed cancer"],
        "follow_up_questions": [
            "What type of cancer have you or your loved one been diagnosed with?",
            "How are you feeling emotionally right now — and is there someone supporting you?",
            "What is your biggest question or worry at this moment?",
            "Have you been told about the next steps by your doctor, or are you still waiting?",
        ],
        "response_themes": ["compassion_first", "orient_without_overwhelm", "one_step"],
        "max_response_words": 120,
    },
    "CA_SCREENING_QUERY": {
        "agents": ["CA1"],
        "label": "Cancer screening and early detection",
        "triggers": ["screening", "mammogram", "colonoscopy", "psa", "pap smear",
                     "cancer test", "early detection", "check for cancer", "biopsy"],
        "follow_up_questions": [
            "What type of cancer screening are you asking about?",
            "How old are you, and do you have any family history of that cancer type?",
            "Have you had this screening before, or would this be your first time?",
            "Are you asking because you have a specific symptom, or purely for prevention?",
        ],
        "response_themes": ["age_risk_based", "guidelines_simplified", "next_step_clear"],
        "max_response_words": 130,
    },
    "CA_TREATMENT_QUESTION": {
        "agents": ["CA2"],
        "label": "Cancer treatment options and side effects",
        "triggers": ["chemotherapy", "radiation", "immunotherapy", "surgery cancer",
                     "treatment options", "side effects cancer", "targeted therapy"],
        "follow_up_questions": [
            "Which treatment are you currently on or considering?",
            "Is the question about effectiveness, side effects, or what to expect day-to-day?",
            "What stage has the cancer been diagnosed at, if you know?",
            "Are you looking for information to discuss with your oncologist, or has treatment already started?",
        ],
        "response_themes": ["treatment_context_first", "plain_language_science", "patient_questions_for_doctor"],
        "max_response_words": 130,
    },

    # ── RESPIRATORY (RS) ──────────────────────────────────────────────────────
    "RS_ASTHMA_SYMPTOMS": {
        "agents": ["RS1"],
        "label": "Asthma symptoms and management",
        "triggers": ["asthma", "wheeze", "inhaler", "breathing difficulty", "rescue inhaler",
                     "asthma attack", "tight chest breathing", "puffer"],
        "follow_up_questions": [
            "How often are you using your reliever inhaler in a typical week?",
            "What are your main triggers — exercise, cold air, dust, pollen, stress?",
            "Do you have a preventer inhaler as well as a reliever?",
            "When was your last asthma review with a nurse or doctor?",
        ],
        "response_themes": ["trigger_identification", "controller_vs_reliever", "action_plan"],
        "max_response_words": 120,
    },
    "RS_BREATHING_GENERAL": {
        "agents": ["RS2", "RS3", "RS6"],
        "label": "General breathlessness or COPD concern",
        "triggers": ["shortness of breath", "breathless", "copd", "can't breathe",
                     "out of breath", "laboured breathing", "lung problem", "spirometry"],
        "follow_up_questions": [
            "Does the breathlessness happen at rest, with light activity, or only with effort?",
            "Do you currently smoke or have you smoked in the past?",
            "Have you ever had a breathing test (spirometry) done?",
            "Is it getting gradually worse over time, or did it come on suddenly?",
        ],
        "response_themes": ["severity_staging", "smoking_history_link", "rehab_potential"],
        "max_response_words": 120,
    },

    # ── GENERAL CATCH-ALL ─────────────────────────────────────────────────────
    "GENERAL_WELLBEING": {
        "agents": ["CA6", "DM6", "CV6", "MH6", "RS6"],
        "label": "General health and wellbeing question",
        "triggers": ["healthy", "wellbeing", "general health", "lifestyle", "wellness"],
        "follow_up_questions": [
            "What area of your health is your top priority right now?",
            "Is this a new concern or something you've been thinking about for a while?",
            "Are you looking for information, or do you need help deciding what to do next?",
        ],
        "response_themes": ["broad_then_focus", "empowering", "agent_routing"],
        "max_response_words": 110,
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 2 — RESPONSE FORMAT LIBRARY
# 8 formats rotated per conversation to prevent monotony
# ═══════════════════════════════════════════════════════════════════════════════

RESPONSE_FORMATS = {

    # Format 1: Short + Expand (progressive disclosure)
    "progressive": {
        "description": "Start with a 2-sentence direct answer, then offer to go deeper",
        "system_instruction": """
Response format: PROGRESSIVE DISCLOSURE
- Give a SHORT, direct answer in 2-3 sentences first (no headers, no bullets)
- Then write ONE short paragraph with the key clinical point
- End with: "Want me to go deeper into [specific aspect]?"
- Maximum 3 short paragraphs total. No numbered lists. No bold headers.
- Conversational, warm tone — like a knowledgeable friend explaining clearly.""",
    },

    # Format 2: Narrative (story-led, most engaging)
    "narrative": {
        "description": "Story-led explanation, no bullets, reads like conversation",
        "system_instruction": """
Response format: NARRATIVE
- Write as flowing prose — NO numbered lists, NO bullet points, NO bold headers
- Start with a relatable hook or analogy that connects to the patient's situation
- Weave the clinical information naturally into the explanation
- Maximum 150 words. One clear action at the end.
- Warm, engaging, conversational — like a caring doctor explaining at the bedside.""",
    },

    # Format 3: Quick Tips (highly scannable)
    "quick_tips": {
        "description": "3 short, actionable tips — ultra scannable",
        "system_instruction": """
Response format: QUICK TIPS (max 3)
- Start with one acknowledging sentence
- Give exactly 3 tips, each ONE sentence, marked with ✓
- Each tip must be specific and immediately actionable (not generic)
- End with ONE follow-up sentence offering more detail on any tip
- No numbered lists. No paragraphs. Easy to read in 20 seconds.""",
    },

    # Format 4: Comparison (before/after or A vs B)
    "comparison": {
        "description": "Compare two approaches or before/after state",
        "system_instruction": """
Response format: COMPARISON
- Briefly acknowledge the patient's situation (1 sentence)
- Present a clear comparison using simple language: 
  "Without [X]: ..." vs "With [X]: ..."
  OR "Option A (what most people try): ... — Option B (what actually works): ..."
- Recommendation in 1 sentence
- No generic lists. Specific to this patient's situation.""",
    },

    # Format 5: Real-Talk (validating + honest)
    "real_talk": {
        "description": "Direct, empathetic, cuts through medical jargon",
        "system_instruction": """
Response format: REAL TALK
- Open by validating exactly what the patient said (reference their words)
- Give the honest, direct answer — no hedging, no "it depends on many factors"
- If something isn't working, say so clearly and explain why
- One concrete thing to try in the next 24 hours
- Tone: warm, direct, like a trusted friend who happens to be a doctor
- Max 120 words, no bullet points or numbered lists.""",
    },

    # Format 6: Staged Guidance (when protocol is needed)
    "staged": {
        "description": "Step-by-step only when a protocol genuinely applies",
        "system_instruction": """
Response format: STAGED GUIDANCE
- Use ONLY when the question genuinely requires sequential steps
- Max 3 stages, each named with a vivid label (not "Step 1")
- Each stage: name + ONE sentence of instruction
- No long paragraphs within each stage
- End: what success looks like at each stage
- If the question doesn't need stages, switch to narrative format.""",
    },

    # Format 7: Myth-Bust (correcting misconceptions)
    "myth_bust": {
        "description": "Challenge a misconception the patient might have",
        "system_instruction": """
Response format: MYTH-BUST
- Identify the underlying misconception in the patient's question (1 sentence)
- "Here's what actually happens:" — explain the truth in plain language
- "What this means for you:" — personalised implication
- Max 100 words. No numbered lists. Direct and empowering.""",
    },

    # Format 8: Bridge (when changing direction or building on prior response)
    "bridge": {
        "description": "Links to something already said and builds on it",
        "system_instruction": """
Response format: BRIDGE
- Start with: "Earlier I mentioned [X]. Let me add something important to that."
- Build genuinely on the previous answer — no repetition
- Add ONE new angle, piece of evidence, or practical step
- Max 100 words. Conversational. No lists.
- This format is used when the patient's new message relates to a prior answer.""",
    },
}

# Format rotation order (prevents same format appearing consecutively)
FORMAT_ROTATION = [
    "progressive", "narrative", "quick_tips", "real_talk",
    "comparison", "staged", "myth_bust", "bridge",
]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 3 — FOLLOW-UP QUESTION GENERATOR
# ═══════════════════════════════════════════════════════════════════════════════

# ─── Fallback questions pool for when no intent is matched ─────────────────────
FALLBACK_QUESTIONS = [
    "Can you tell me more about what's most worrying you right now?",
    "How long has this been going on?",
    "Have you spoken to a doctor about this before?",
    "Are there any specific symptoms you've noticed recently?",
    "What are you hoping to achieve through our conversation today?",
    "How has this been affecting your daily life or routine?",
    "Have you tried any treatments or remedies on your own yet?",
    "Is there anything else in your health history I should know about?",
    "Do you have any specific goals for your health in the next month?",
    "What is your biggest question about your health right now?",
]

# ─── Disease-specific empathetic questions for frustration ───────────────────
DISEASE_EMPATHY_QUESTIONS = {
    "DM": [
        "Managing blood sugar daily can be exhausting. Would you like to talk about how to handle 'diabetes burnout' and find some relief?",
        "It's incredibly frustrating when readings don't match your hard work. Should we explore what might be causing these patterns together?",
        "You're doing a lot to stay on top of this. Would you like some tips for making the routine feel a bit less heavy today?",
        "I understand this is a lot to carry. Would you like to talk about simple ways to reduce the mental load of managing your diabetes?"
    ],
    "CV": [
        "It's completely natural to feel anxious about heart health. Would you like to talk about some heart-safe relaxation techniques to help you feel more at ease?",
        "Heart management is a marathon, and it's okay to feel tired. Would you like to discuss how to pace yourself and manage the stress?",
        "Feeling worried about your heart is very common and valid. Would you like to explore ways to stay calm and focused on your well-being?",
        "I hear your concern. Would you like to talk about how others manage the daily stress of cardiac care and find peace of mind?"
    ],
    "MH": [
        "It sounds like things are really heavy and overwhelming right now. Would you like to talk about some immediate grounding exercises to help you feel centered?",
        "I can hear the exhaustion in your words, and it's okay to feel this way. Would you like to explore some gentle ways to care for yourself today?",
        "You're not alone in feeling this way. Would you like to ask about small, manageable steps to handle this overwhelm?",
        "I'm here for you. Would you like to discuss how to navigate these difficult moments with more support and kindness toward yourself?"
    ],
    "RS": [
        "Breathing difficulties can be very distressing and scary. Would you like to talk about some calming breathing techniques to help you feel more in control?",
        "It's frustrating when you can't do the things you want because of your breathing. Should we talk about pacing your activities to save energy?",
        "Managing lung health takes a lot of patience and strength. Would you like to explore some ways to make the daily routine a bit easier?",
        "I understand how scary flare-ups can be. Would you like to talk about techniques to stay calm and steady when things feel difficult?"
    ],
    "CA": [
        "A cancer journey is incredibly tough, and it's okay to feel however you're feeling. Would you like to talk about ways to manage the emotional weight?",
        "It's completely okay to feel overwhelmed by all this information. Would you like to ask about finding extra support or resources to help you navigate this?",
        "You're showing a lot of strength just being here. Would you like to talk about how to handle the uncertainty of treatment with more support?",
        "I hear you. Would you like to explore some supportive care options that focus purely on your comfort and well-being right now?"
    ],
    "GENERAL": [
        "I can hear how frustrated you are, and I'm sorry if I haven't been as helpful as you needed. Would it help to focus on a small, manageable win today?",
        "Your feelings are completely valid. Would you like to ask about how others manage these same challenges and find their way through?",
        "I'm here to support you in whatever way you need. Would you like to talk about what's making you feel most stuck right now?",
        "I understand this is difficult. Would you like to explore some ways to make our interaction more helpful and supportive for you?"
    ]
}

# ─── Generic Support Queries (3-5 items) ──────────────────────────────────────
GENERIC_SUPPORT_QUERIES = {
    "DM": [
        {"text": "A complete blood sugar stabilization guide", "grade": "A", "citation": "ADA Standards 2024"},
        {"text": "Diabetes-friendly exercise plan for beginners", "grade": "A", "citation": "ACSM Guidelines"},
        {"text": "Hypoglycemia prevention and management protocol", "grade": "A", "citation": "Endocrine Society 2023"},
        {"text": "Carbohydrate counting cheat sheet for cultural foods", "grade": "B", "citation": "Clinical Nutrition Journal"},
        {"text": "Diabetes burnout recovery framework", "grade": "A", "citation": "Diabetes Care 2024"}
    ],
    "CV": [
        {"text": "Heart-healthy DASH diet transition plan", "grade": "A", "citation": "AHA/ACC Guidelines 2024"},
        {"text": "Safe cardiac exercise intensity guide (METs)", "grade": "A", "citation": "ESC Prevention Guidelines"},
        {"text": "Blood pressure monitoring best practices", "grade": "A", "citation": "JNC 8 Protocol"},
        {"text": "Stress reduction techniques for heart health", "grade": "B", "citation": "Harvard Health Review"},
        {"text": "Cardiac emergency response checklist", "grade": "A", "citation": "Resuscitation Council UK"}
    ],
    "MH": [
        {"text": "A complete insomnia recovery routine", "grade": "A", "citation": "AASM Clinical Practice 2024"},
        {"text": "Sleep schedule reset plan for chronic fatigue", "grade": "A", "citation": "Sleep Research Society"},
        {"text": "Night anxiety reduction techniques", "grade": "A", "citation": "APA Treatment Manual"},
        {"text": "Insomnia plan for office workers", "grade": "B", "citation": "Occupational Health Journal"},
        {"text": "Daily mindfulness grounding exercises", "grade": "A", "citation": "Oxford Mindfulness Centre"}
    ],
    "RS": [
        {"text": "Asthma trigger identification and avoidance guide", "grade": "A", "citation": "GINA Strategy 2024"},
        {"text": "Pursed-lip breathing technique for COPD", "grade": "A", "citation": "ATS/ERS Guidelines"},
        {"text": "Lung capacity improvement exercise routine", "grade": "B", "citation": "Cochrane Review 2023"},
        {"text": "Air quality awareness and protection protocol", "grade": "A", "citation": "WHO Air Quality Guidelines"},
        {"text": "Inhaler technique masterclass", "grade": "A", "citation": "BTS/SIGN Asthma Guideline"}
    ],
    "CA": [
        {"text": "Chemotherapy side-effect management framework", "grade": "A", "citation": "ASCO/ESMO Consensus 2024"},
        {"text": "Cancer survivorship nutrition and wellness guide", "grade": "A", "citation": "ACS Nutrition Guidelines"},
        {"text": "Energy conservation techniques for cancer fatigue", "grade": "A", "citation": "NCCN Guidelines v2.2024"},
        {"text": "Emotional support navigation for caregivers", "grade": "B", "citation": "Cancer Care Ontario"},
        {"text": "Integrative oncology basics", "grade": "B", "citation": "SIO Guidelines"}
    ],
    "GENERAL": [
        {"text": "Universal health literacy improvement guide", "grade": "A", "citation": "Healthy People 2030"},
        {"text": "Daily wellness check-in and goal setting", "grade": "B", "citation": "WHO Wellness Framework"},
        {"text": "Stress management and resilience framework", "grade": "A", "citation": "Mayo Clinic Wellness"},
        {"text": "Healthy lifestyle transition for families", "grade": "B", "citation": "CDC Health Living"},
        {"text": "Medical appointment preparation checklist", "grade": "A", "citation": "AHRQ Patient Safety"}
    ]
}

def select_follow_up_questions(
    intent:           str,
    slots_filled:     Dict,
    shown_questions:  List[str],
    conversation_topics: List[str],
    n:                int = 3,
    avoided:          bool = False,
    is_frustrated:    bool = False,
    agent_id:         str = "",
) -> List[str]:
    """
    Select 2-3 follow-up questions to show after each AI response.
    If is_frustrated is True, pivots to empathetic questions and strictly avoids repeats.
    """
    # 1. Determine the pool
    if is_frustrated:
        # Map agent_id to disease prefix (e.g., DM1 -> DM)
        prefix = agent_id[:2].upper() if agent_id else "GENERAL"
        all_pool = DISEASE_EMPATHY_QUESTIONS.get(prefix, DISEASE_EMPATHY_QUESTIONS["GENERAL"])
    else:
        intent_def = INTENT_TAXONOMY.get(intent)
        if not intent_def:
            all_pool = FALLBACK_QUESTIONS
        else:
            all_pool = intent_def.get("follow_up_questions", [])
            if len(all_pool) < 6:
                all_pool = all_pool + [q for q in FALLBACK_QUESTIONS if q not in all_pool]

    # 2. Filter: don't repeat questions already shown
    shown_lower = {q.lower()[:40].strip() for q in shown_questions}
    available   = [
        q for q in all_pool
        if q.lower()[:40].strip() not in shown_lower
    ]

    # 3. Handling empty pool
    if not available:
        if is_frustrated:
            # Even if frustrated, if we ran out of empathetic ones, use generic ones
            available = [q for q in DISEASE_EMPATHY_QUESTIONS["GENERAL"] if q.lower()[:40].strip() not in shown_lower]
            if not available:
                # Absolute fallback: reset but shuffle
                available = list(all_pool)
        else:
            # For normal mode, reset and allow repeats but shuffle
            available = list(all_pool)
        
        import random
        random.shuffle(available)

    # 4. Sorting / Prioritization
    if avoided or is_frustrated:
        import random
        random.shuffle(available)
    else:
        # Prioritise questions about unfilled slots
        intent_def = INTENT_TAXONOMY.get(intent)
        unfilled_slots = [k for k in (intent_def.get("critical_slots", []) if intent_def else []) if not slots_filled.get(k)]
        prioritised = []
        rest        = []
        for q in available:
            q_lower = q.lower()
            if any(slot.replace("_", " ") in q_lower for slot in unfilled_slots):
                prioritised.append(q)
            else:
                rest.append(q)
        available = prioritised + rest

    return available[:n]


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 4 — CONVERSATION MEMORY & ANTI-REPETITION
# ═══════════════════════════════════════════════════════════════════════════════

@dataclass
class ConversationMemory:
    """Tracks topics covered, formats used, and questions asked."""
    conversation_id:     str
    covered_topics:      List[str]           = field(default_factory=list)
    formats_used:        List[str]           = field(default_factory=list)
    follow_up_asked:     List[str]           = field(default_factory=list)
    questions_avoided_count: int             = 0
    response_count:      int                 = 0
    last_intent:         Optional[str]       = None
    key_facts_mentioned: List[str]           = field(default_factory=list)
    patient_shared:      Dict[str, str]      = field(default_factory=dict)

    def to_dict(self) -> Dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: Dict) -> "ConversationMemory":
        d_copy = dict(d or {})
        if "conversation_id" not in d_copy:
            d_copy["conversation_id"] = "temp"
        return cls(**{k: v for k, v in d_copy.items() if k in cls.__dataclass_fields__})

    def is_topic_covered(self, topic: str) -> bool:
        t = topic.lower()
        return any(t in c.lower() for c in self.covered_topics)

    def next_format(self) -> str:
        """Rotate through formats, never using the same twice in a row."""
        if not self.formats_used:
            return FORMAT_ROTATION[0]
        last = self.formats_used[-1]
        available = [f for f in FORMAT_ROTATION if f != last]
        # After 4+ responses, prefer "bridge" if intent is same
        if self.response_count >= 3 and self.last_intent == self.last_intent:
            if "bridge" in available:
                return "bridge"
        idx = (self.response_count) % len(available)
        return available[idx]

    def add_response(self, format_used: str, topics: List[str], intent: str):
        self.formats_used.append(format_used)
        self.covered_topics.extend(topics)
        self.covered_topics = self.covered_topics[-MEMORY_WINDOW * 3:]
        self.response_count += 1
        self.last_intent = intent

    def add_follow_up_shown(self, questions: List[str]):
        self.follow_up_asked.extend(questions)
        self.follow_up_asked = self.follow_up_asked[-30:]


def detect_repetition(
    new_message:         str,
    memory:              ConversationMemory,
    conversation_history: List[Dict],
) -> Dict:
    """
    Detect if the patient is asking about something already covered.

    Returns:
        is_repeat: bool
        reminder:  str — brief acknowledgement of what was already said
        pivot:     str — suggestion for what to explore next
    """
    if memory.response_count < 2:
        return {"is_repeat": False, "reminder": "", "pivot": ""}

    msg_lower    = new_message.lower()
    covered_lower = [c.lower() for c in memory.covered_topics]

    # Keyword overlap check
    msg_words   = set(re.findall(r'\b\w{4,}\b', msg_lower))
    covered_all = " ".join(covered_lower)
    covered_words = set(re.findall(r'\b\w{4,}\b', covered_all))
    overlap     = msg_words & covered_words
    overlap_pct = len(overlap) / max(len(msg_words), 1)

    if overlap_pct > 0.50 and memory.response_count >= 2:
        covered_context = ", ".join(list(overlap)[:4])
        reminder = (
            f"We've already touched on {covered_context} — let me add something new this time."
        )
        pivot = "Is there a specific part of that you'd like me to dig deeper into?"
        return {"is_repeat": True, "reminder": reminder, "pivot": pivot}

    return {"is_repeat": False, "reminder": "", "pivot": ""}


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 5 — INTENT CLASSIFIER (faster than LLM for common cases)
# ═══════════════════════════════════════════════════════════════════════════════

def classify_intent_fast(message: str, agent_id: str) -> Optional[str]:
    """
    Fast keyword-based intent classification.
    Falls back to LLM only when no clear match.
    """
    msg_lower = message.lower()
    agent_upper = agent_id.upper()

    best_intent = None
    best_score  = 0

    for intent_key, intent_def in INTENT_TAXONOMY.items():
        # Check agent relevance
        if agent_upper not in intent_def.get("agents", []) and \
           agent_upper[:2] not in [a[:2] for a in intent_def.get("agents", [])]:
            if not any(agent_upper[:2] in a for a in intent_def.get("agents", [])):
                # Allow general agents for any intent
                if "6" not in agent_upper:
                    continue

        triggers = intent_def.get("triggers", [])
        score    = sum(1 for t in triggers if t in msg_lower)
        if score > best_score:
            best_score  = score
            best_intent = intent_key

    return best_intent if best_score >= 1 else None


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 6 — SYSTEM PROMPT BUILDER
# Builds the complete system prompt with format + memory + intent injection
# ═══════════════════════════════════════════════════════════════════════════════

def build_enriched_system_prompt(
    base_system_prompt: str,
    intent:             str,
    memory:             ConversationMemory,
    context_summary:    str,
    confidence:         float,
    format_override:    Optional[str] = None,
    is_frustrated:      bool = False,
) -> Tuple[str, str]:
    """
    Build an enriched system prompt that:
    1. Injects the chosen response format instructions
    2. Adds memory context (what was covered, what facts patient shared)
    3. Adjusts for confidence level
    4. Adds intent-specific response guidance

    Returns: (enriched_system_prompt, format_used)
    """
    intent_def   = INTENT_TAXONOMY.get(intent, {})
    chosen_format = format_override or memory.next_format()
    format_def   = RESPONSE_FORMATS.get(chosen_format, RESPONSE_FORMATS["progressive"])

    # Build frustration-aware empathy block
    frustration_block = ""
    if is_frustrated:
        frustration_block = """
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚨 PATIENT FRUSTRATION DETECTED — ENTERING EMPATHY MODE 🚨
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
The patient is currently feeling frustrated or unheard. 
YOUR PRIMARY GOAL: Calm the patient and validate their feelings.

1. ACKNOWLEDGE & VALIDATE: Start by acknowledging their frustration. Use phrases like "I can hear how frustrating this is," or "It's completely understandable that you feel overwhelmed."
2. NO MORE QUESTIONS: Do NOT ask any clinical data-gathering questions. 
3. DO NOT REPEAT: If the patient is upset because of a previous question, do NOT repeat it or try to explain why you asked it. Just move on.
4. PIVOT TO SUPPORT: Focus on providing immediate relief or a more supportive perspective.
5. KEEP IT SIMPLE: Avoid complex medical jargon or long explanations.
6. DISEASE-SPECIFIC COMFORT: Connect your empathy to their clinical context (e.g., if it's diabetes, acknowledge the heavy burden of daily management).

Shift your tone to be 100% supportive, 0% investigative.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    # Build memory injection
    memory_block = ""
    if memory.response_count > 0 and memory.covered_topics:
        unique_topics = list(dict.fromkeys(memory.covered_topics))[:6]
        memory_block = f"""
CONVERSATION MEMORY (already covered in this session — DO NOT repeat these):
{chr(10).join(f'  • {t}' for t in unique_topics)}

If the patient's question touches something already covered, acknowledge it briefly
and pivot to a new angle or deeper detail."""

    if memory.patient_shared:
        shared = memory.patient_shared
        memory_block += f"""

WHAT THIS PATIENT HAS SHARED:
{chr(10).join(f'  • {k}: {v}' for k, v in list(shared.items())[:5])}
Reference these facts naturally in your response to show you listened."""

    # Build confidence-aware instruction
    confidence_block = ""
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        confidence_block = """
CONFIDENCE NOTE: Retrieval confidence is lower than ideal.
- Focus on what you know well rather than trying to cover everything
- Be honest when you're less certain: "Based on what you've told me..."
- Offer to explore a specific narrower sub-topic in depth
- DO NOT give a generic overview — give a specific, focused answer"""

    # Build intent-specific instruction
    intent_block = ""
    if intent_def:
        themes    = intent_def.get("response_themes", [])
        max_words = intent_def.get("max_response_words", 140)
        intent_block = f"""
INTENT: {intent_def.get('label', intent)}
Response themes to embody: {', '.join(themes)}
Hard word limit: {max_words} words for the main response body.
DO NOT exceed this — if more detail is needed, end with "Want me to continue with [X]?" """

        if intent_def.get("emergency_check"):
            intent_block += """
EMERGENCY CHECK REQUIRED: Before anything else, confirm no emergency symptoms.
If patient mentions severe symptoms → lead with "If you have severe pain/breathlessness/etc. right now, call 999/112/SAMU immediately." """

    context_block = ""
    if context_summary:
        context_block = f"""
PATIENT CONTEXT COLLECTED THROUGH CONVERSATION:
{context_summary}
Use these specific details to make your response feel individually crafted, not generic."""

    full_prompt = f"""{base_system_prompt}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{format_def['system_instruction']}

{frustration_block}
{intent_block}
{memory_block}
{context_block}
{confidence_block}

FINAL RULES:
• Vary your opening — never start with "Great question!" or "Certainly!"
• Never use a numbered 1-2-3-4-5-6 format — this looks generic and patients hate it
• Never repeat the same structure as the previous response in this conversation
• End your response naturally — the follow-up questions are added separately
• One disclaimer is enough — don't repeat the medical advice disclaimer in every response
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"""

    return full_prompt, chosen_format


# ═══════════════════════════════════════════════════════════════════════════════
# SECTION 7 — TOPIC EXTRACTOR (for memory building)
# ═══════════════════════════════════════════════════════════════════════════════

def extract_topics_from_response(response_text: str, intent: str) -> List[str]:
    """
    Extract key topics from an AI response for memory tracking.
    Uses keyword matching against the intent taxonomy.
    """
    text_lower = response_text.lower()
    topics = []

    # Extract medical terms and concepts
    medical_concepts = [
        "blood sugar", "glucose", "hba1c", "insulin", "medication",
        "diet", "exercise", "stress", "sleep", "chest pain", "breathing",
        "hypoglycemia", "blood pressure", "cholesterol", "ecg",
        "cbt-i", "sleep restriction", "light therapy", "circadian",
        "cbti", "mediterranean diet", "cgm", "metformin", "sglt2",
        "screening", "biopsy", "chemotherapy", "radiation", "spirometry",
    ]
    for concept in medical_concepts:
        if concept in text_lower:
            topics.append(concept)

    # Add intent label as a topic
    intent_def = INTENT_TAXONOMY.get(intent, {})
    if intent_def.get("label"):
        topics.append(intent_def["label"].lower()[:40])

    return topics[:8]

def select_generic_support(agent_id: str, count: int = 4) -> List[Dict]:
    """Select 3-5 generic support queries for the patient."""
    prefix = agent_id[:2].upper() if agent_id else "GENERAL"
    pool = GENERIC_SUPPORT_QUERIES.get(prefix, GENERIC_SUPPORT_QUERIES["GENERAL"])
    selected = random.sample(pool, min(len(pool), count))
    return selected


async def get_active_agent_questions(agent_id: str, db: AsyncSession) -> List[str]:
    """Fetch active initial questions for an agent from the database."""
    res = await db.execute(
        select(AgentQuestion.text)
        .where(AgentQuestion.agent_id == agent_id, AgentQuestion.is_active == True)
        .order_by(func.random()) # Return in random order for variety
        .limit(5)
    )
    questions = res.scalars().all()
    
    # Fallback to hardcoded if DB is empty
    if not questions:
        from backend.config.agent_registry import ALL_AGENTS
        agent = ALL_AGENTS.get(agent_id)
        if agent:
            # Shuffle hardcoded ones too
            qs = list(agent.top5_questions)
            import random
            random.shuffle(qs)
            return qs
    
    return list(questions)


def normalize_q_text(text: str) -> str:
    """Normalize question text for comparison by removing punctuation and extra whitespace."""
    # Remove non-alphanumeric chars (except spaces) and lowercase
    clean = re.sub(r'[^\w\s]', '', text.lower())
    return " ".join(clean.split())


async def track_agent_question_usage(agent_id: str, selected_text: str, db: AsyncSession):
    """
    Track which initial question was selected.
    If none selected (user typed custom), increment misses for all active ones.
    If misses >= 5, rotate.
    Added: 20% chance for periodical rotation even if misses < 5 to keep it fresh.
    """
    import random
    # 1. Get current active questions
    res = await db.execute(
        select(AgentQuestion)
        .where(AgentQuestion.agent_id == agent_id, AgentQuestion.is_active == True)
    )
    active_qs = res.scalars().all()
    if not active_qs:
        return

    selected_any = False
    to_rotate = []
    
    norm_selected = normalize_q_text(selected_text)

    for q in active_qs:
        norm_q = normalize_q_text(q.text)
        if norm_q == norm_selected:
            q.selection_count += 1
            q.consecutive_misses = 0
            selected_any = True
        else:
            q.consecutive_misses += 1
            if q.consecutive_misses >= 5:
                to_rotate.append(q)

    # 2. Periodical Rotation Trigger (20% chance per new conversation)
    # If no one hit the 5-miss threshold, we might still rotate one for variety
    if not to_rotate and not selected_any and random.random() < 0.2:
        # Pick the active question with the highest misses (most ignored) to rotate
        candidate = sorted(active_qs, key=lambda x: x.consecutive_misses, reverse=True)[0]
        to_rotate.append(candidate)

    # 3. Rotate questions
    for old_q in to_rotate:
        old_q.is_active = False
        
        # Pick a new one from the pool
        # Strategy: Pick one that is NOT active and has the fewest misses
        pool_res = await db.execute(
            select(AgentQuestion)
            .where(
                AgentQuestion.agent_id == agent_id, 
                AgentQuestion.is_active == False
            )
            .order_by(AgentQuestion.consecutive_misses.asc(), func.random())
            .limit(1)
        )
        new_q = pool_res.scalar_one_or_none()
        
        if new_q:
            new_q.is_active = True
            new_q.consecutive_misses = 0
        else:
            # If no inactive ones exist, just reset the old one (safety fallback)
            old_q.is_active = True
            old_q.consecutive_misses = 0

    await db.commit()


def extract_patient_shared(message: str, slots_filled: Dict) -> Dict[str, str]:
    """
    Extract facts the patient has shared to personalise future responses.
    """
    shared = {}
    msg_lower = message.lower()

    # Age
    age_match = re.search(r'\b(\d{2})\s*(?:years old|yr|yo)\b', msg_lower)
    if age_match:
        shared["age"] = age_match.group(1) + " years old"

    # Duration
    duration_match = re.search(r'\bsince\s+(\w+\s+\w+|\d+\s+\w+)\b', msg_lower)
    if duration_match:
        shared["duration"] = "Since " + duration_match.group(1)

    # Specific values
    glucose_match = re.search(r'\b(\d{2,3})\s*(?:mg/dl|mmol|mg)\b', msg_lower)
    if glucose_match:
        shared["glucose_reading"] = glucose_match.group(0)

    bp_match = re.search(r'\b(\d{2,3}/\d{2,3})\b', msg_lower)
    if bp_match:
        shared["blood_pressure"] = bp_match.group(1)

    # Merge with existing slots
    for k, v in slots_filled.items():
        if v and k not in shared:
            shared[k] = str(v)

    return shared


def update_memory_after_response(
    memory_dict: Dict,
    response_text: str,
    format_used: str,
    intent: str,
    slots_filled: Dict,
) -> Dict:
    """
    Update conversation memory after the LLM has generated its response.
    """
    memory = ConversationMemory.from_dict(memory_dict)
    topics = extract_topics_from_response(response_text, intent)
    memory.add_response(format_used, topics, intent)
    
    # Also update patient shared facts
    new_facts = extract_patient_shared(response_text, slots_filled)
    memory.patient_shared.update(new_facts)
    
    return memory.to_dict()


def elaborate_follow_up_questions(questions: List[str]) -> List[Dict]:
    """
    Return questions in a structured format without shortening them.
    """
    if not questions: return []
    
    # We no longer shorten questions to avoid confusion.
    # We just return them as {text, elaboration} where text is the full question.
    return [{"text": q, "elaboration": ""} for q in questions]


def validate_intent_scope(agent_id: str, intent: str) -> Optional[str]:
    """
    Check if the detected intent belongs to the same clinical domain as the agent.
    """
    domain_map = {
        "DM": "Diabetes",
        "CV": "Cardiovascular",
        "MH": "Mental Health",
        "RS": "Respiratory",
        "CA": "Cancer Care"
    }
    
    agent_domain = agent_id[:2].upper()
    intent_domain = intent[:2].upper()
    
    if agent_domain in domain_map and intent_domain in domain_map:
        if agent_domain != intent_domain:
            target_domain_name  = domain_map.get(intent_domain, "another clinical")
            current_domain_name = domain_map.get(agent_domain, "this")
            return (
                f"It looks like your question is related to **{target_domain_name}** management. "
                f"As your {current_domain_name} specialist assistant, I am optimized to provide "
                f"precise guidance specifically for {current_domain_name.lower()} health concerns. "
                f"\n\nTo ensure you get the most accurate and specialized evidence-based information, "
                f"please switch to the **{target_domain_name}** section in the main menu."
            )
            
    return None


def enrich_response_context(
    agent_id: str,
    user_message: str,
    base_system_prompt: str,
    intent: str,
    memory_dict: Optional[Dict],
    slots_filled: Dict,
    context_summary: str,
    confidence: float,
    conversation_history: List[Dict],
) -> Dict:
    # ─── 1. Detect Frustration ──────────────────────────────────────────────────
    detector = FrustrationDetector()
    frustration_res = detector.compute(user_message, conversation_history)
    is_frustrated   = frustration_res["is_frustrated"]

    memory = ConversationMemory.from_dict(memory_dict or {"conversation_id": "temp"})
    if is_frustrated:
        memory.questions_avoided_count += 2 # Strong avoidance signal

    repetition_info = detect_repetition(user_message, memory, conversation_history)
    repetition_detected = repetition_info["is_repeat"]
    repetition_reminder = repetition_info["reminder"]

    enriched_system_prompt, format_used = build_enriched_system_prompt(
        base_system_prompt=base_system_prompt,
        intent=intent,
        memory=memory,
        context_summary=context_summary,
        confidence=confidence,
        is_frustrated=is_frustrated
    )
    
    # ─── 2. Get candidate questions ─────────────────────────────────────────────
    # If frustrated, we get empathetic ones immediately
    candidates = select_follow_up_questions(
        intent=intent,
        slots_filled=slots_filled,
        shown_questions=memory.follow_up_asked,
        conversation_topics=memory.covered_topics,
        n=8, 
        is_frustrated=is_frustrated,
        agent_id=agent_id
    )
    
    # ─── 3. Process chips (deduplicate, detect echoes) ──────────────────────────
    chip_results = process_chips_for_response(
        candidate_chips=candidates,
        conversation_memory_dict=memory.to_dict(),
        patient_message=user_message,
        conversation_history=conversation_history,
        slots_filled=slots_filled,
        intent=intent,
    )
    
    follow_ups_raw = chip_results["final_chips"]
    echo_detected  = chip_results["chip_echo_detected"]
    
    # ─── 4. Avoidance logic ─────────────────────────────────────────────────────
    if not echo_detected and len(user_message.strip()) > 10 and not is_frustrated:
        memory.questions_avoided_count += 1
        follow_ups_raw = select_follow_up_questions(
            intent=intent,
            slots_filled=slots_filled,
            shown_questions=memory.follow_up_asked,
            conversation_topics=memory.covered_topics,
            n=len(follow_ups_raw),
            avoided=True,
            agent_id=agent_id
        )

    # ─── 5. Update memory with what's being shown now ───────────────────────────
    memory.add_follow_up_shown(follow_ups_raw)
    
    follow_up_questions = elaborate_follow_up_questions(follow_ups_raw)

    # 🆕 Select Generic Support Queries
    generic_support_raw = select_generic_support(agent_id, count=random.randint(3, 5))
    generic_support = [
        {
            "text": q["text"], 
            "elaboration": q.get("citation", "Evidence-based reference"),
            "grade": q.get("grade", "A")
        } 
        for q in generic_support_raw
    ]
    
    # Generate intent-based dynamic prompt
    intent_prompts = {
        "CA_SCREENING_CONCERN": "To help me narrow down the best advice for you, would you like to ask about screening methods or early symptoms?",
        "CA_TREATMENT_QUESTION": "Regarding cancer treatments, would you like to ask about side effects or how to prepare for your next appointment?",
        "DM_MEDICATION_QUERY": "Do you have specific questions about your diabetes medication, like side effects or how to manage your doses?",
        "DM_GLUCOSE_MONITORING": "Would you like to ask about tracking your sugar levels or what to do when your readings are high?",
        "CV_SYMPTOM_ASSESSMENT": "Based on your heart symptoms, would you like to ask about what activities are safe or when to see a specialist?",
        "MH_DEPRESSION_CONCERN": "Regarding your emotional well-being, would you like to ask about coping strategies or finding local support?",
        "MH_ANXIETY_CONCERN": "To help manage your anxiety, would you like to ask about grounding techniques or how to handle panic attacks?",
        "RS_ASTHMA_SYMPTOMS": "Would you like to ask about identifying your asthma triggers or using your inhaler correctly?",
        "GENERAL_WELLBEING": "To help you feel your best, would you like to ask about nutrition, exercise, or improving your sleep habits?",
    }
    follow_up_prompt = intent_prompts.get(intent, "Based on our conversation, would you like to ask one of the following to explore further?")
    
    return {
        "enriched_system_prompt": enriched_system_prompt,
        "format_used":            format_used,
        "follow_up_questions":    follow_up_questions,
        "generic_support":        generic_support,
        "follow_up_prompt":       follow_up_prompt,
        "repetition_detected":    repetition_detected,
        "repetition_reminder":    repetition_reminder,
        "memory":                 memory.to_dict(),
    }


def compute_conversation_quality(
    conversation_history: List[Dict],
    slots_filled: Dict,
    intent: str,
    format_used: str,
    memory_dict: Dict,
) -> Dict:
    """
    Computes the Projected Conversation Quality Score.
    """
    from backend.core.quality.conversation_quality import QualityScorer, get_quality_recommendation
    
    memory = ConversationMemory.from_dict(memory_dict)
    
    ragas_scores = []
    frustration_scores = []
    for msg in conversation_history:
        if isinstance(msg, dict):
            if msg.get("ragas_scores"): ragas_scores.append(msg["ragas_scores"])
            if msg.get("frustration"): frustration_scores.append(msg["frustration"])
        
    score = QualityScorer.compute_score(
        history=conversation_history,
        ragas_scores=ragas_scores,
        frustration_scores=frustration_scores,
        slots_filled=slots_filled,
        intent=intent,
        format_used=format_used,
        response_count=memory.response_count,
    )
    
    return {
        "projected_score": score,
        "recommendation": get_quality_recommendation(score)
    }
