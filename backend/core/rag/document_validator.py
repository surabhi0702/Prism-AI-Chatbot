# ═══════════════════════════════════════════════════════════════════════════════
# FILE: backend/core/rag/document_validator.py
# PRISM Medical Document Validator — F1 Scoring & Disease Classification
# ═══════════════════════════════════════════════════════════════════════════════

import re
from typing import Dict, List, Optional, Tuple
from backend.core.agents.base_agent import call_llm_sync
from backend.config.agent_registry import ALL_AGENTS

# ─── Comprehensive Medical Vocabulary for F1 Scoring ───────────────────────────
MEDICAL_VOCAB = {
    # Symptoms & Conditions
    "pain", "fever", "nausea", "vomiting", "dizziness", "fatigue", "inflammation",
    "infection", "lesion", "tumor", "carcinoma", "metastasis", "benign", "malignant",
    "chronic", "acute", "syndrome", "disorder", "dysfunction", "insufficiency",
    # Body Systems & Organs
    "cardiovascular", "respiratory", "neurological", "gastrointestinal", "renal",
    "hepatic", "pulmonary", "cardiac", "dermatological", "endocrine", "lymphatic",
    "heart", "lung", "brain", "liver", "kidney", "pancreas", "spleen", "bladder",
    # Treatments & Meds
    "medication", "treatment", "therapy", "prescription", "dosage", "tablet", "capsule",
    "injection", "infusion", "surgery", "operation", "rehabilitation", "antibiotic",
    "chemotherapy", "immunotherapy", "insulin", "metformin", "statin", "aspirin",
    # Diagnostics & Labs
    "diagnosis", "prognosis", "screening", "biopsy", "ultrasound", "mri", "ct", "xray",
    "ecg", "ekg", "blood", "glucose", "hba1c", "cholesterol", "creatinine", "hemoglobin",
    "pathology", "radiology", "oncology", "hematology", "clinical", "laboratory",
    # Disease Specific
    "diabetes", "cancer", "asthma", "copd", "hypertension", "depression", "anxiety",
    "ischemic", "myocardial", "infarction", "stroke", "seizure", "arthritis",
}

# ─── Domain Keywords for Classification ──────────────────────────────────────
DOMAIN_MAP = {
    "CA": {"cancer", "tumor", "tumour", "oncology", "chemotherapy", "radiation", "biopsy", "malignant", "metastasis", "carcinoma", "screening", "mammogram"},
    "DM": {"diabetes", "glucose", "insulin", "hba1c", "metformin", "glycemic", "hypoglycemia", "hyperglycemia", "diabetic", "pancreas"},
    "CV": {"heart", "cardiac", "cardiovascular", "blood pressure", "hypertension", "cholesterol", "ecg", "ekg", "arrhythmia", "statin", "stroke", "infarction"},
    "MH": {"depression", "anxiety", "mental", "stress", "panic", "ptsd", "therapy", "psychiatrist", "psychologist", "mood", "insomnia"},
    "RS": {"asthma", "copd", "breathing", "inhaler", "lung", "bronchitis", "respiratory", "pulmonary", "oxygen", "nebulizer", "apnea"},
}

DOMAIN_NAMES = {
    "CA": "Cancer Care",
    "DM": "Diabetes",
    "CV": "Cardiovascular",
    "MH": "Mental Health",
    "RS": "Respiratory",
}

def compute_medical_f1(text: str) -> Dict:
    """
    Calculate a medical F1 score based on vocabulary overlap.
    We use a high-density check for documents.
    """
    # Clean and tokenize text
    words = set(re.findall(r'\b\w+\b', text.lower()))
    if not words:
        return {"f1": 0.0, "is_medical": False, "terms_found": []}

    # Common English stop words to filter out for better precision calculation
    STOP_WORDS = {"the", "a", "an", "and", "or", "but", "if", "then", "else", "when", "at", "from", "by", "for", "with", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "to", "of", "in", "on", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "can", "could", "shall", "should", "will", "would", "may", "might", "must"}
    
    meaningful_words = words - STOP_WORDS
    if not meaningful_words:
        return {"f1": 0.0, "is_medical": False, "terms_found": []}

    med_hits = meaningful_words & MEDICAL_VOCAB
    
    # Precision: Medical words / Meaningful words
    precision = len(med_hits) / len(meaningful_words)
    
    # Recall: Medical words / Target set (scaled since our vocab is small compared to all medical terms)
    # We target at least 15-20 medical terms in a good document
    recall = min(len(med_hits) / 15, 1.0)
    
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # LLM Verification for edge cases if F1 is near threshold
    is_medical = f1 >= 0.7
    
    if 0.5 <= f1 < 0.7:
        # Ask LLM if this is actually a medical document
        llm_check = call_llm_sync(
            system_prompt="You are a medical document classifier. Determine if the following text is a clinical or medical document (guidelines, research, reports, etc.). Return only JSON: {\"is_medical\": true/false, \"confidence\": 0.0-1.0}",
            user_message=f"Text excerpt: {text[:2000]}",
            temperature=0.0
        )
        try:
            import json
            res = json.loads(llm_check["response"])
            if res.get("is_medical") and res.get("confidence", 0) > 0.8:
                f1 = 0.71 # Boost to pass threshold
                is_medical = True
        except: pass

    return {
        "f1": round(f1 * 100, 1),
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "is_medical": is_medical,
        "terms_found": list(med_hits)[:10]
    }

def classify_disease_domain(text: str) -> Dict:
    """
    Classify the document into one of the 5 domains.
    Returns {code, name, confidence}.
    """
    text_lower = text.lower()
    scores = {}
    
    for code, kws in DOMAIN_MAP.items():
        # Count occurrences of keywords
        count = sum(1 for kw in kws if kw in text_lower)
        scores[code] = count

    # Get the best match
    best_code = max(scores, key=scores.get) if any(scores.values()) else None
    
    if not best_code or scores[best_code] < 2:
        # Fallback to LLM for precise classification
        llm_check = call_llm_sync(
            system_prompt="Classify this medical text into exactly one of these domains: CA (Cancer), DM (Diabetes), CV (Cardiovascular), MH (Mental Health), RS (Respiratory). If none fit well, return null. Return only JSON: {\"domain\": \"CA/DM/CV/MH/RS/null\", \"reason\": \"...\"}",
            user_message=f"Text excerpt: {text[:2000]}",
            temperature=0.0
        )
        try:
            import json
            res = json.loads(llm_check["response"])
            best_code = res.get("domain")
            if best_code == "null": best_code = None
        except: pass

    if best_code and best_code in DOMAIN_NAMES:
        return {
            "code": best_code,
            "name": DOMAIN_NAMES[best_code],
            "confidence": 1.0 if scores.get(best_code, 0) > 5 else 0.8
        }
    
    return {"code": None, "name": "Unknown", "confidence": 0.0}

def classify_specific_agent(text: str, domain_code: str) -> Dict:
    """
    Classify the document into a specific agent (e.g., CA1, CA2) within a domain.
    """
    if not domain_code:
        return {"agent_id": None, "agent_name": "None", "description": ""}

    # Get all agents for this domain
    domain_agents = {k: v for k, v in ALL_AGENTS.items() if v.disease_code == domain_code and v.role == 'primary'}
    
    if not domain_agents:
        return {"agent_id": None, "agent_name": "None", "description": ""}

    # Use LLM to pick the best agent based on role and description
    agent_options = "\n".join([f"- {a.agent_id}: {a.agent_name}. Role: {a.description}" for a in domain_agents.values()])
    
    llm_res = call_llm_sync(
        system_prompt=(
            "You are a medical document router. Match the provided text to the MOST relevant specialist agent.\n"
            "Return only JSON: {\"agent_id\": \"ID\", \"confidence\": 0.0-1.0}\n\n"
            f"AVAILABLE AGENTS:\n{agent_options}"
        ),
        user_message=f"Text excerpt: {text[:3000]}",
        temperature=0.0
    )
    
    try:
        import json
        res = json.loads(llm_res["response"])
        best_id = res.get("agent_id")
        if best_id in domain_agents:
            agent = domain_agents[best_id]
            return {
                "agent_id": agent.agent_id,
                "agent_name": agent.agent_name,
                "description": agent.description,
                "confidence": res.get("confidence", 0.9)
            }
    except: pass
    
    # Fallback to first agent in domain
    first_id = list(domain_agents.keys())[0]
    return {
        "agent_id": first_id,
        "agent_name": domain_agents[first_id].agent_name,
        "description": domain_agents[first_id].description,
        "confidence": 0.5
    }

def compute_agent_f1(text: str, agent_id: str) -> Dict:
    """
    Calculate F1 score specifically for an agent's role and keywords.
    """
    if not agent_id or agent_id not in ALL_AGENTS:
        return {"f1": 0.0, "passed": False}

    agent = ALL_AGENTS[agent_id]
    # Use agent's keywords and description for scoring
    target_vocab = set([kw.lower() for kw in agent.crawl_keywords])
    # Also add words from description
    desc_words = set(re.findall(r'\b\w+\b', agent.description.lower()))
    target_vocab.update(desc_words)
    
    # Filter target_vocab to remove common words
    STOP_WORDS = {"the", "a", "an", "and", "or", "but", "if", "then", "else", "when", "at", "from", "by", "for", "with", "about", "against", "between", "into", "through", "during", "before", "after", "above", "below", "to", "of", "in", "on", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had", "do", "does", "did", "can", "could", "shall", "should", "will", "would", "may", "might", "must", "guides", "patients", "clinicians", "through", "based", "protocols", "for", "evidence", "interprets", "explains", "advises", "on", "references"}
    target_vocab = target_vocab - STOP_WORDS
    
    words = set(re.findall(r'\b\w+\b', text.lower()))
    hits = words & target_vocab
    
    if not words or not target_vocab:
        return {"f1": 0.0, "passed": False}
        
    precision = len(hits) / len(words) if words else 0
    recall = len(hits) / len(target_vocab) if target_vocab else 0
    
    # Scale recall because target_vocab is small
    recall = min(len(hits) / 5, 1.0) 
    
    f1 = (2 * precision * recall) / (precision + recall) if (precision + recall) > 0 else 0.0
    
    # LLM verification for agent match
    passed = f1 >= 0.7
    if 0.4 <= f1 < 0.7:
        llm_check = call_llm_sync(
            system_prompt=(
                f"Determine if the text is highly relevant to this specific clinical role: {agent.agent_name} - {agent.description}\n"
                "Return only JSON: {\"relevant\": true/false, \"confidence\": 0.0-1.0}"
            ),
            user_message=f"Text excerpt: {text[:2000]}",
            temperature=0.0
        )
        try:
            import json
            res = json.loads(llm_check["response"])
            if res.get("relevant") and res.get("confidence", 0) > 0.8:
                f1 = 0.72
                passed = True
        except: pass
        
    return {
        "f1": round(f1 * 100, 1),
        "passed": passed
    }
