"""
PRISM — Base Agent Class
All 25 disease agents inherit from PRISMBaseAgent.
Each agent wraps its AgentDefinition and provides:
  - build_messages()   : assemble LangChain messages
  - invoke()           : call LLM with context
  - extract_citations(): pull references from chunks
"""
import time
import re
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from backend.config.agent_registry import AgentDefinition, ALL_AGENTS
from backend.config.settings import get_settings

settings = get_settings()


def get_llm(temperature: float = 0.2, max_tokens: int = 2048):
    """Factory: returns LLM based on .env LLM_PROVIDER."""
    if settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.llm_model,
            temperature=temperature,
            anthropic_api_key=settings.anthropic_api_key,
            max_tokens=max_tokens,
        )
    elif settings.llm_provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=settings.llm_model or "gemini-1.5-flash",
            temperature=temperature,
            google_api_key=settings.google_api_key,
            max_tokens=max_tokens,
        )
    else:
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=settings.llm_model or "gpt-4o",
            temperature=temperature,
            openai_api_key=settings.openai_api_key,
            max_tokens=max_tokens,
        )


class PRISMBaseAgent(ABC):
    """
    Abstract base class for all PRISM agents.
    Concrete agents (CA1Agent, DM1Agent, etc.) inherit from this.
    """

    def __init__(self, agent_id: str):
        self.config: AgentDefinition = ALL_AGENTS[agent_id]
        self.llm = get_llm(self.config.temperature, self.config.max_tokens)

    @property
    def agent_id(self) -> str:
        return self.config.agent_id

    @property
    def collection_name(self) -> str:
        return self.config.collection_name

    def build_system_prompt(self, context: str) -> str:
        """Assemble full system prompt with context and guardrails."""
        guardrail_block = "\n".join(f"  • {g}" for g in self.config.guardrails)
        return (
            f"{self.config.system_prompt}\n\n"
            f"GUARDRAILS (MUST FOLLOW):\n{guardrail_block}\n\n"
            f"KNOWLEDGE BASE CONTEXT:\n"
            f"{context if context.strip() else 'No context retrieved. Use your clinical knowledge with appropriate caveats.'}\n\n"
            f"RESPONSE FORMAT:\n"
            f"1. Direct answer in patient-friendly language\n"
            f"2. Evidence Grade (A/B/C) for every clinical recommendation\n"
            f"3. Numbered citations from the context\n"
            f"4. LATAM-relevant resources if applicable\n"
            f"5. Professional follow-up recommendation"
        )

    def build_messages(
        self,
        user_query:   str,
        context:      str,
        history:      List[Dict] = None,
    ) -> List:
        """Build the full message list for the LLM."""
        messages = [SystemMessage(content=self.build_system_prompt(context))]

        # Inject conversation history (last N turns)
        for h in (history or [])[-settings.max_chat_history:]:
            if h["role"] == "user":
                messages.append(HumanMessage(content=h["content"]))
            elif h["role"] == "assistant":
                messages.append(AIMessage(content=h["content"]))

        messages.append(HumanMessage(content=user_query))
        return messages

    def invoke(
        self,
        user_query: str,
        context:    str,
        history:    List[Dict] = None,
    ) -> Dict:
        """Call the LLM and return structured response."""
        t0 = time.time()
        messages = self.build_messages(user_query, context, history)
        try:
            result   = self.llm.invoke(messages)
            response = result.content if hasattr(result, "content") else str(result)
            tokens   = getattr(result, "usage_metadata", {})
            return {
                "response":     response,
                "agent_id":     self.agent_id,
                "latency_ms":   int((time.time() - t0) * 1000),
                "prompt_tokens":   tokens.get("input_tokens", 0),
                "completion_tokens": tokens.get("output_tokens", 0),
                "success":      True,
                "error":        None,
            }
        except Exception as e:
            return {
                "response":    f"I encountered an error processing your request. Please try again.",
                "agent_id":    self.agent_id,
                "latency_ms":  int((time.time() - t0) * 1000),
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "success":     False,
                "error":       str(e),
            }

    def extract_citations(self, chunks: List[Dict]) -> List[Dict]:
        """Extract unique citations from retrieved chunks."""
        citations, seen = [], set()
        for c in chunks:
            meta = c.get("metadata", {})
            src  = meta.get("source", "PRISM Knowledge Base")
            if src not in seen:
                seen.add(src)
                citations.append({
                    "source":         src,
                    "year":           meta.get("year"),
                    "evidence_grade": meta.get("evidence_grade"),
                    "url":            meta.get("source_url"),
                    "doc_type":       meta.get("doc_type"),
                })
        return citations[:5]

    def check_guardrails(self, query: str) -> Optional[str]:
        """
        Pre-response guardrail check.
        Returns override message if a hard guardrail is triggered, else None.
        """
        # Override in concrete agents for domain-specific guardrail pre-checks
        return None


# ─── Concrete Agent Classes (one per agent ID) ───────────────────────────

class CA1Agent(PRISMBaseAgent):
    """Cancer Screening & Early Detection"""
    def __init__(self): super().__init__("CA1")

    def check_guardrails(self, query: str) -> Optional[str]:
        q = query.lower()
        if any(t in q for t in ["i have cancer", "diagnosed with cancer", "my biopsy showed"]):
            return (
                "I can see you've received a cancer diagnosis. I specialize in screening, "
                "but I want to make sure you're connected with the right support. "
                "My colleague **CA2 (Treatment Navigation)** can best guide you through "
                "what comes next. Please also ensure you have an oncologist's contact. "
                "Would you like me to share what CA2 covers?"
            )
        return None


class CA2Agent(PRISMBaseAgent):
    """Cancer Treatment Navigation"""
    def __init__(self): super().__init__("CA2")

    def check_guardrails(self, query: str) -> Optional[str]:
        q = query.lower()
        if any(t in q for t in ["fever", "temperature", "chills"]) and "chemo" in q:
            return (
                "⚠️ **URGENT**: If you have a fever (≥ 38°C / 100.4°F) during chemotherapy, "
                "this may indicate **febrile neutropenia** — a medical emergency. "
                "Please contact your oncology team or go to the emergency room **immediately**. "
                "Do not wait for a scheduled appointment. This is time-sensitive."
            )
        return None


class CA3Agent(PRISMBaseAgent):
    """Cancer Supportive Care"""
    def __init__(self): super().__init__("CA3")


class CA4Agent(PRISMBaseAgent):
    """Cancer Survivorship"""
    def __init__(self): super().__init__("CA4")


class CA5Agent(PRISMBaseAgent):
    """Hereditary Cancer Genetics"""
    def __init__(self): super().__init__("CA5")


class DM1Agent(PRISMBaseAgent):
    """Diabetes Glucose Monitoring"""
    def __init__(self): super().__init__("DM1")

    def check_guardrails(self, query: str) -> Optional[str]:
        q = query.lower()
        # DKA emergency detection
        if any(t in q for t in ["fruity breath", "vomiting", "dka", "ketones", "ketoacidosis"]):
            glucose_high = any(g in q for g in ["high sugar", "high glucose", "300", "400", "500", "hyperglycemia"])
            if glucose_high or "dka" in q:
                return (
                    "🚨 **URGENT MEDICAL EMERGENCY**: The symptoms you're describing "
                    "(high blood sugar + vomiting / fruity breath / ketones) may indicate "
                    "**Diabetic Ketoacidosis (DKA)**. This is life-threatening. "
                    "**Please go to the Emergency Room or call 911/SAMU immediately.** "
                    "Do not wait. DKA requires IV fluids and insulin in hospital."
                )
        # Severe hypoglycaemia
        if any(t in q for t in ["unconscious", "passed out", "seizure"]) and any(t in q for t in ["low blood sugar", "hypoglycemia", "sugar dropped"]):
            return (
                "🚨 **EMERGENCY**: Seizure or unconsciousness from low blood sugar "
                "requires **glucagon injection or 911 immediately**. "
                "Do NOT give food/liquid to an unconscious person."
            )
        return None


class DM2Agent(PRISMBaseAgent):
    """Diabetes Medication & Insulin"""
    def __init__(self): super().__init__("DM2")


class DM3Agent(PRISMBaseAgent):
    """Diabetes Nutrition & Lifestyle"""
    def __init__(self): super().__init__("DM3")


class DM4Agent(PRISMBaseAgent):
    """Diabetes Complications"""
    def __init__(self): super().__init__("DM4")

    def check_guardrails(self, query: str) -> Optional[str]:
        q = query.lower()
        if any(t in q for t in ["foot wound", "foot ulcer", "my foot is", "wound on foot", "black toe"]):
            return (
                "⚠️ **URGENT**: A wound, ulcer, or colour change on your foot with diabetes "
                "requires **urgent podiatry or emergency evaluation within 24 hours**. "
                "Diabetic foot infections can progress to limb-threatening infection rapidly. "
                "Please do not delay. Keep the foot clean and elevated and seek care now."
            )
        return None


class DM5Agent(PRISMBaseAgent):
    """Gestational & Special Population Diabetes"""
    def __init__(self): super().__init__("DM5")


class CV1Agent(PRISMBaseAgent):
    """Cardiovascular Clinical"""
    def __init__(self): super().__init__("CV1")


class CV2Agent(PRISMBaseAgent):
    """Cardiac Emergency"""
    def __init__(self): super().__init__("CV2")

    def check_guardrails(self, query: str) -> Optional[str]:
        q = query.lower()
        emergency_terms = [
            "chest pain", "chest tightness", "heart attack", "can't breathe",
            "arm pain", "jaw pain", "crushing", "stroke", "face drooping",
            "arm weakness", "speech slurred", "cardiac arrest", "not breathing",
            "collapsed", "passed out", "fainted", "severe headache sudden",
        ]
        if any(t in q for t in emergency_terms):
            return (
                "🚨 **CALL 911 / SAMU / 112 IMMEDIATELY** 🚨\n\n"
                "The symptoms you are describing may indicate a **cardiac or neurological emergency**.\n\n"
                "**While waiting for emergency services:**\n"
                "• HEART ATTACK: Chew 325mg aspirin (if not allergic and not on anticoagulant)\n"
                "• CARDIAC ARREST: Begin hands-only CPR — push hard and fast in centre of chest\n"
                "• STROKE: Do not give food or water. Note the time symptoms started.\n"
                "• Stay with the person. Unlock the door for paramedics.\n\n"
                "**Emergency numbers:** 911 (USA/Mexico) | 192 SAMU (Brazil) | 112 (Europe)"
            )
        return None


class CV3Agent(PRISMBaseAgent):
    """CV Medications"""
    def __init__(self): super().__init__("CV3")


class CV4Agent(PRISMBaseAgent):
    """Cardiac Rehabilitation"""
    def __init__(self): super().__init__("CV4")


class CV5Agent(PRISMBaseAgent):
    """Cardiac Nutrition"""
    def __init__(self): super().__init__("CV5")


class MH1Agent(PRISMBaseAgent):
    """Depression Assessment"""
    def __init__(self): super().__init__("MH1")

    def check_guardrails(self, query: str) -> Optional[str]:
        q = query.lower()
        crisis_terms = [
            "want to die", "end my life", "suicide", "kill myself", "no point living",
            "better off dead", "self harm", "hurting myself", "cutting myself",
        ]
        if any(t in q for t in crisis_terms):
            return None  # Return None — let MH5 handle via orchestrator routing


class MH2Agent(PRISMBaseAgent):
    """Anxiety Management"""
    def __init__(self): super().__init__("MH2")


class MH3Agent(PRISMBaseAgent):
    """Sleep & Wellness"""
    def __init__(self): super().__init__("MH3")


class MH4Agent(PRISMBaseAgent):
    """Trauma & PTSD"""
    def __init__(self): super().__init__("MH4")

    def check_guardrails(self, query: str) -> Optional[str]:
        q = query.lower()
        dv_terms = ["domestic violence", "abusive partner", "hitting me", "he hits me",
                    "she hits me", "my partner hurts", "abuse at home", "scared of my partner"]
        if any(t in q for t in dv_terms):
            return (
                "I hear you, and I want you to know you are not alone. Your safety is the priority.\n\n"
                "**Crisis resources:**\n"
                "• 🇺🇸 National DV Hotline: 1-800-799-7233 | Text: START to 88788\n"
                "• 🇲🇽 INMUJERES: 800-290-0024\n"
                "• 🇧🇷 Ligue 180 (Central de Atendimento à Mulher)\n"
                "• 🇦🇷 144 (Argentina DV Helpline)\n\n"
                "Please reach out to one of these lines. I can also help you with information "
                "about safety planning. Would that be helpful?"
            )
        return None


class MH5Agent(PRISMBaseAgent):
    """Crisis & Suicide Prevention — HIGHEST PRIORITY"""
    def __init__(self): super().__init__("MH5")

    def check_guardrails(self, query: str) -> Optional[str]:
        # Always provide crisis line at start of any response
        return (
            "You've reached PRISM's Crisis Support. I'm here with you right now.\n\n"
            "**If you are in immediate danger, please call:**\n"
            "• 🇺🇸 **988** (USA Suicide & Crisis Lifeline)\n"
            "• 🇲🇽 **800-290-0024** (CVIVD Mexico)\n"
            "• 🇧🇷 **CVV 188** (Brazil)\n"
            "• 🇦🇷 **(011) 5275-1135** (Argentina ASIST)\n"
            "• **112** (Europe emergency)\n\n"
            "I'm not going anywhere. Tell me what's happening."
        )


class RS1Agent(PRISMBaseAgent):
    """Asthma Management"""
    def __init__(self): super().__init__("RS1")

    def check_guardrails(self, query: str) -> Optional[str]:
        q = query.lower()
        if any(t in q for t in ["can't breathe", "cannot breathe", "inhaler not working",
                                  "blue lips", "gasping", "severe attack"]):
            return (
                "🚨 **ACUTE SEVERE ASTHMA — ACT NOW:**\n"
                "1. Sit upright — do NOT lie down\n"
                "2. Use your rescue inhaler (salbutamol): 4 puffs every 20 minutes (up to 3 doses)\n"
                "3. **Call 911/112/SAMU if no improvement after 10 minutes**\n"
                "4. If lips turn blue or you cannot complete a sentence — call emergency NOW\n\n"
                "Do not wait. Severe asthma attacks can be fatal."
            )
        return None


class RS2Agent(PRISMBaseAgent):
    """COPD Management"""
    def __init__(self): super().__init__("RS2")


class RS3Agent(PRISMBaseAgent):
    """Pulmonary Rehabilitation"""
    def __init__(self): super().__init__("RS3")


class RS4Agent(PRISMBaseAgent):
    """Respiratory Medications"""
    def __init__(self): super().__init__("RS4")


class RS5Agent(PRISMBaseAgent):
    """Sleep-Disordered Breathing & OSA"""
    def __init__(self): super().__init__("RS5")


# ─── Agent factory ────────────────────────────────────────────────────────

_AGENT_CLASSES = {
    "CA1": CA1Agent, "CA2": CA2Agent, "CA3": CA3Agent, "CA4": CA4Agent, "CA5": CA5Agent,
    "DM1": DM1Agent, "DM2": DM2Agent, "DM3": DM3Agent, "DM4": DM4Agent, "DM5": DM5Agent,
    "CV1": CV1Agent, "CV2": CV2Agent, "CV3": CV3Agent, "CV4": CV4Agent, "CV5": CV5Agent,
    "MH1": MH1Agent, "MH2": MH2Agent, "MH3": MH3Agent, "MH4": MH4Agent, "MH5": MH5Agent,
    "RS1": RS1Agent, "RS2": RS2Agent, "RS3": RS3Agent, "RS4": RS4Agent, "RS5": RS5Agent,
}

_agent_instances: Dict[str, PRISMBaseAgent] = {}


def get_agent(agent_id: str) -> PRISMBaseAgent:
    """Return (or create) singleton agent instance by agent_id."""
    agent_id = agent_id.upper()
    if agent_id not in _agent_instances:
        cls = _AGENT_CLASSES.get(agent_id)
        if not cls:
            raise ValueError(f"Unknown agent ID: {agent_id}")
        _agent_instances[agent_id] = cls()
    return _agent_instances[agent_id]


# ═══════════════════════════════════════════════════════════════════════════════
def call_llm_sync(
    system_prompt: str,
    user_message:  str,
    history:       List[Dict] = None,
    temperature:   float = 0.2,
    max_tokens:    int = 1000,
) -> Dict:
    """
    Synchronous utility to call the configured LLM for one-off tasks 
    like classification, enrichment, or analysis.
    """
    import time
    t0 = time.time()
    try:
        # Use the factory to get the correctly configured LLM (Anthropic or OpenAI)
        llm = get_llm(temperature=temperature, max_tokens=max_tokens)
        
        messages = [SystemMessage(content=system_prompt)]
        
        # Inject conversation history
        for h in (history or []):
            role = h.get("role")
            content = h.get("content", "")
            if role == "user": 
                messages.append(HumanMessage(content=content))
            elif role == "assistant": 
                messages.append(AIMessage(content=content))
            
        messages.append(HumanMessage(content=user_message))
        
        # Invoke LLM
        res = llm.invoke(messages)
        
        # Extract usage if available
        p_tokens = getattr(res, "usage_metadata", {}).get("input_tokens", 0) if hasattr(res, "usage_metadata") else 0
        c_tokens = getattr(res, "usage_metadata", {}).get("output_tokens", 0) if hasattr(res, "usage_metadata") else 0
        
        # Handle different response types from LangChain
        response_text = res.content if hasattr(res, "content") else str(res)
        
        return {
            "response":          response_text,
            "prompt_tokens":     p_tokens,
            "completion_tokens": c_tokens,
            "latency_ms":        int((time.time() - t0) * 1000),
            "success":           True,
            "error":             None,
        }
    except Exception as e:
        print(f"[LLM_ERROR] {str(e)}")
        return {
            "response":          f"I encountered an error processing the request. {str(e)[:100]}",
            "prompt_tokens":     0,
            "completion_tokens": 0,
            "latency_ms":        int((time.time() - t0) * 1000),
            "success":           False,
            "error":             str(e),
        }
