// ═══════════════════════════════════════════════════════════════════════════════
// FILE: frontend/src/pages/PatientApp.jsx  (FULL REPLACEMENT)
// PRISM Patient Chat — with Smart Routing + Escalation Monitor panel
// ═══════════════════════════════════════════════════════════════════════════════

import { useState, useEffect, useRef, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuthStore } from "../store/auth";
import api from "../services/api";
import { LogOut, User as UserIcon, Send, ChevronRight, Lock, MessageSquare, ExternalLink, Settings, Brain, Activity, RefreshCw, Plus, FileText, Download, Trash2 } from "lucide-react";
import ImageUpload, { ImageAnalysisMessage } from "../Components/ImageUpload";
import VoiceChat, { VoiceMessage } from "../Components/VoiceChat";
import LanguageSelector from "../Components/LanguageSelector";
import { useLanguage } from "../Context/LanguageContext";
import ChatHistory from "../Components/ChatHistory";
import { ConversationalMessage, ConversationProgress, TypingIndicator } from "../Components/ConversationalChat";

// ─── Disease / Agent metadata (mirrors backend DISEASE_GROUPS) ─────────────────
const DISEASES = [
  { code:"CA", icon:"🎗", name:"Cancer Care",      color:"#7C3AED", bg:"#F5F3FF",
    agents:[
      { id:"CA1", name:"Screening",    fullName: "Cancer Screening & Early Detection Specialist", description: "Guides patients and clinicians through evidence-based cancer screening protocols for breast, cervical, colorectal, lung, and prostate cancers.", icon:"🔬", qs:["When should I start mammograms?","My PSA is 5.2 — is that concerning?","HPV test vs Pap smear?","At 52, do I need a colonoscopy?","Should I get BRCA testing?"] },
      { id:"CA2", name:"Treatment",    fullName: "Cancer Treatment Navigation Specialist", description: "Navigates patients through cancer treatment options including chemotherapy, immunotherapy, targeted therapy, radiation, and surgery.", icon:"💊", qs:["What is HER2-positive breast cancer?","Neoadjuvant vs adjuvant chemo?","FOLFOX side effects?","What is PD-L1 test?","Supplements during chemo?"] },
      { id:"CA3", name:"Supportive",   fullName: "Cancer Supportive Care & Symptom Management Specialist", description: "Manages cancer-related symptoms, treatment side effects, pain, nutritional support, and palliative care needs.", icon:"🌿", qs:["How to manage chemo nausea?","What to eat with no appetite?","Cancer fatigue tips?","What is palliative care?","Managing mouth sores?"] },
      { id:"CA4", name:"Survivorship", fullName: "Cancer Survivorship & Long-Term Follow-Up Specialist", description: "Supports cancer survivors with post-treatment surveillance, late effects management, return-to-work planning, and psychological recovery.", icon:"🌟", qs:["How often do I need follow-up scans?","Late effects of chemo to watch for?","Managing lymphedema after breast surgery?","What is chemo brain?","When can I return to work?"] },
      { id:"CA5", name:"Genetics",     fullName: "Hereditary Cancer Genetics & Risk Assessment Specialist", description: "Provides pre- and post-genetic test counselling for hereditary cancer syndromes including BRCA1/2, Lynch syndrome, and risk-reduction strategies.", icon:"🧬", qs:["Should I get BRCA testing?","My mother had ovarian cancer — am I at risk?","What is Lynch syndrome?","Options if I test BRCA1 positive?","Should my children be tested?"] },
      { id:"CA6", name:"General",      fullName: "Cancer Care Holistic Navigator & General Assistance", description: "Provides broad assistance for cancer-related logistics, general health literacy, caregiver support, and patient rights.", icon:"🎗", qs:["How can I get general support for my cancer journey?","Where can I find caregiver resources?","How do I navigate the different cancer specialists here?","What are some general wellness tips during treatment?","How do I find local cancer support groups?"] },
    ]},
  { code:"DM", icon:"🩺", name:"Diabetes",         color:"#2563EB", bg:"#EFF6FF",
    agents:[
      { id:"DM1", name:"Monitoring",   fullName: "Glucose Monitoring & Diabetes Diagnostics Specialist", description: "Guides patients on blood glucose interpretation, CGM usage, HbA1c targets, and hypoglycaemia management.", icon:"📊", qs:["Fasting glucose 210 mg/dL — dangerous?","What HbA1c target should I aim for?","What is the 15-15 rule?","What is Time in Range?","Dawn phenomenon vs Somogyi?"] },
      { id:"DM2", name:"Medication",   fullName: "Diabetes Medication & Insulin Management Specialist", description: "Explains diabetes pharmacotherapy including metformin, GLP-1 agonists, SGLT-2 inhibitors, and insulin regimens.", icon:"💉", qs:["Metformin causing diarrhoea — what can I do?","Semaglutide vs liraglutide?","Do SGLT-2s protect heart and kidneys?","What is basal-bolus insulin?","Metformin + SGLT-2 together — safe?"] },
      { id:"DM3", name:"Nutrition",    fullName: "Diabetes Nutrition, Lifestyle & Weight Management Specialist", description: "Evidence-based medical nutrition therapy, meal planning, carbohydrate counting, and exercise prescriptions for diabetes management.", icon:"🥗", qs:["Foods to avoid with type 2 diabetes?","Can I eat rice and tortillas?","How much exercise to lower blood sugar?","What is glycaemic index?","How to count carbohydrates?"] },
      { id:"DM4", name:"Complications",fullName: "Diabetes Complications Prevention & Management Specialist", description: "Manages diabetic complications: nephropathy, retinopathy, neuropathy, and cardiovascular risk reduction.", icon:"⚠️", qs:["Numbness in feet — diabetic neuropathy?","eGFR is declining — related to diabetes?","How to prevent diabetic foot ulcers?","Protein in urine — what does it mean?","How often for eye checks?"] },
      { id:"DM5", name:"Gestational",  fullName: "Gestational Diabetes & Special Populations Specialist", description: "Specialised diabetes care for gestational diabetes (GDM), paediatric type 1, and elderly patients with frailty.", icon:"🤱", qs:["GDM — what does it mean for my baby?","Blood sugar targets during pregnancy?","Child diagnosed type 1 — how to manage?","Diabetes at age 75 — different targets?","Can GDM come back?"] },
      { id:"DM6", name:"General",      fullName: "Diabetes 360° Lifestyle & General Assistance Agent", description: "Provides general assistance for living with diabetes, health literacy, and domain navigation.", icon:"🔄", qs:["How do I start living a healthy life with diabetes?","What are some tips for traveling with diabetes?","Where can I find general diabetes education?","How do I find a local diabetes support group?","What insurance resources are available for diabetes supplies?"] },
    ]},
  { code:"CV", icon:"❤️", name:"Cardiovascular",   color:"#DB2777", bg:"#FDF2F8",
    agents:[
      { id:"CV1", name:"Clinical",     fullName: "Cardiovascular Clinical Assessment Specialist", description: "Guides patients on hypertension management, dyslipidaemia, heart failure assessment, and atrial fibrillation anticoagulation.", icon:"❤️", qs:["BP 148/92 — do I have hypertension?","LDL 168 after heart attack — need statin?","Why SGLT-2 for non-diabetic HF?","HFrEF vs HFpEF difference?","AF — do I need a blood thinner?"] },
      { id:"CV2", name:"Emergency",    fullName: "Cardiac Emergency & Critical Care Response Specialist", description: "Provides immediate life-safety guidance for STEMI, stroke (FAST), cardiac arrest (CPR), and hypertensive emergency.", icon:"🚨", qs:["Severe chest pain radiating to arm — what to do?","FAST stroke signs and treatment window?","Someone collapsed — I do not know CPR?","Hypertensive emergency vs urgency?","D-dimer elevated after long flight?"] },
      { id:"CV3", name:"Medications",  fullName: "Cardiovascular Medications & Pharmacotherapy Specialist", description: "Expert guidance on cardiovascular medications: ACE inhibitors, ARBs, beta-blockers, statins, and anticoagulants.", icon:"💊", qs:["Lisinopril causing dry cough?","Why beta-blocker if heart is weak?","What is sacubitril/valsartan?","Ibuprofen safe with heart failure meds?","Foods that affect warfarin?"] },
      { id:"CV4", name:"Rehab",        fullName: "Cardiac Rehabilitation & Exercise Therapy Specialist", description: "Evidence-based cardiac rehabilitation guidance, exercise progression, and safety for cardiac recovery.", icon:"🏃", qs:["What does cardiac rehab involve?","Target heart rate with heart failure?","Resistance training safe after bypass?","No rehab centre nearby — alternatives?","How does exercise help a weak heart?"] },
      { id:"CV5", name:"Nutrition",    fullName: "Cardiovascular Nutrition, Prevention & Lifestyle Specialist", description: "Evidence-based dietary interventions for cardiovascular prevention: DASH diet, Mediterranean diet, and triglyceride management.", icon:"🥗", qs:["What is the DASH diet?","Triglycerides 480 mg/dL — what to cut first?","Do omega-3 supplements help the heart?","Mediterranean diet realistic in Brazil?","LATAM heart-healthy foods?"] },
      { id:"CV6", name:"General",      fullName: "Heart Health Wellness & General Cardiovascular Assistance", description: "Broad assistance for heart-healthy living, general cardiovascular literacy, and navigating the CV domain.", icon:"❤️", qs:["How can I start a heart-healthy exercise routine safely?","What resources are available to help me stop smoking?","How do I read a basic heart health report?","What are the general goals for long-term heart health?","How do I find a cardiologist in my area?"] },
    ]},
  { code:"MH", icon:"🧠", name:"Mental Health",    color:"#059669", bg:"#F0FDF4",
    agents:[
      { id:"MH1", name:"Depression",   fullName: "Depression Assessment & Evidence-Based Support Specialist", description: "Evidence-based depression assessment using PHQ-9, explanation of SSRIs/SNRIs, and lifestyle support.", icon:"🧠", qs:["Depression vs sadness — how do I know?","SSRIs vs SNRIs difference?","How long do antidepressants take?","Depression without medication — possible?","PHQ-9 score of 15 — what does it mean?"] },
      { id:"MH2", name:"Anxiety",      fullName: "Anxiety Disorders & Evidence-Based Management Specialist", description: "Anxiety disorder assessment using GAD-7, with evidence-based interventions: CBT, exposure therapy, and mindfulness.", icon:"💚", qs:["How do I know if I have an anxiety disorder?","Panic attack vs heart attack?","Can breathing exercises help anxiety?","What medications treat anxiety?","How does CBT work?"] },
      { id:"MH3", name:"Sleep",        fullName: "Sleep, Wellness & Burnout Recovery Specialist", description: "Evidence-based insomnia management using CBT-I, sleep hygiene, and burnout recovery support.", icon:"🌙", qs:["Fix insomnia without sleeping pills?","What is CBT-I for sleep?","Does melatonin actually work?","How does poor sleep affect mental health?","Best sleep hygiene routine?"] },
      { id:"MH4", name:"Trauma",       fullName: "Trauma, PTSD & Trauma-Informed Care Specialist", description: "Trauma-informed assessment of PTSD, ACEs, and evidence-based treatment options like EMDR and PE.", icon:"🛡️", qs:["What are the symptoms of PTSD?","How is PTSD treated — what is EMDR?","Domestic violence — how to get help?","What are ACEs and how do they affect health?","Dealing with trauma flashbacks?"] },
      { id:"MH5", name:"Crisis",       fullName: "Mental Health Crisis & Suicide Prevention Specialist", description: "Immediate, compassionate crisis support for suicidal ideation, self-harm, and acute psychiatric emergencies.", icon:"🆘", qs:["Thoughts of harming myself — what do I do?","How to help a friend wanting to die?","Warning signs someone may be suicidal?","I feel like I cannot go on — who to call?","What is a safety plan?"] },
      { id:"MH6", name:"General",      fullName: "Mental Well-being & General Psychological Assistance Agent", description: "General mental well-being support, stress reduction, and mental health domain navigation.", icon:"🍃", qs:["What are some simple ways to improve my daily mental well-being?","How can I start practicing mindfulness?","Where can I find mental health resources for my community?","How do I find the right type of therapist?","What are the signs that I might need professional mental health support?"] },
    ]},
  { code:"RS", icon:"🫁", name:"Respiratory",      color:"#D97706", bg:"#FFFBEB",
    agents:[
      { id:"RS1", name:"Asthma",       fullName: "Asthma Management & Inhaler Therapy Specialist", description: "GINA 2024-based asthma management: inhaler technique, step therapy, and trigger avoidance.", icon:"𫫁", qs:["How to use my rescue inhaler correctly?","Rescue vs preventer inhaler?","Asthma worse at night — why?","What triggers should I avoid?","When to go to ER for asthma attack?"] },
      { id:"RS2", name:"COPD",         fullName: "COPD Management & Spirometry Interpretation Specialist", description: "GOLD 2024 COPD management: spirometry interpretation, staging, and exacerbation prevention.", icon:"🌬️", qs:["COPD staging — what does FEV1 mean?","Best inhaler for COPD?","When do I need home oxygen?","How to prevent COPD exacerbations?","Quit smoking to help COPD?"] },
      { id:"RS3", name:"Rehab",        fullName: "Pulmonary Rehabilitation & Breathing Therapy Specialist", description: "Evidence-based pulmonary rehabilitation: exercise tolerance, breathing techniques, and airway clearance.", icon:"💨", qs:["Breathing exercises that help COPD?","What is pulmonary rehabilitation?","How to improve breathing capacity?","What is pursed-lip breathing?","Can exercise help my lungs?"] },
      { id:"RS4", name:"Medications",  fullName: "Respiratory Medications & Inhaler Device Specialist", description: "Expert guidance on respiratory medications: inhaler device selection, spacer use, and side effect management.", icon:"💊", qs:["How to use a spacer with inhaler?","Side effects of inhaled steroids?","Nebuliser or inhaler — which is better?","What is montelukast for?","Azithromycin long-term for COPD?"] },
      { id:"RS5", name:"Sleep Apnea",  fullName: "Sleep-Disordered Breathing & OSA Management Specialist", description: "Obstructive sleep apnoea (OSA) assessment and management: PSG interpretation, AHI staging, and CPAP therapy.", icon:"🌙", qs:["How do I know if I have sleep apnea?","What is CPAP and how does it work?","Partner says I stop breathing at night?","Does sleep apnea affect my heart?","Alternatives to CPAP?"] },
      { id:"RS6", name:"General",      fullName: "Lung Health & General Respiratory Assistance Specialist", description: "Broad assistance for lung health, air quality awareness, and respiratory domain navigation.", icon:"🌬️", qs:["How can I improve the air quality in my home?","What are some simple breathing exercises for general lung health?","How do I read a basic lung function report?","What environmental factors affect my breathing the most?","How do I find a respiratory specialist in my area?"] },
    ]},
];



// ─── Transliteration Banner ────────────────────────────────────────────────────
function TransliterationBanner({ lang, langConfig }) {
  const NON_LATIN = ["hi", "te", "pa"];
  if (!NON_LATIN.includes(lang)) return null;

  const EXAMPLES = {
    hi: { roman: "mujhe seene mein dard hai", native: "मुझे सीने में दर्द है" },
    te: { roman: "naku chest lo noppi undi", native: "నాకు చెస్ట్ లో నొప్పి ఉంది" },
    pa: { roman: "mera seena dard kar raha hai", native: "ਮੇਰਾ ਸੀਨਾ ਦਰਦ ਕਰ ਰਿਹਾ ਹੈ" },
  };
  const ex = EXAMPLES[lang] || { roman: "", native: "" };

  return (
    <div style={{
      padding:      "7px 16px",
      background:   "#FFFBEB",
      borderBottom: "1px solid #FDE68A",
      fontSize:     11,
      color:        "#92400E",
      display:      "flex",
      alignItems:   "center",
      gap:          8,
      flexWrap:     "wrap",
    }}>
      <span style={{ fontSize: 14 }}>{langConfig.flag}</span>
      <strong>{langConfig.nativeName} mode active</strong>
      <span style={{ color: "#B45309" }}>·</span>
      <span>Type in {langConfig.nativeName} script or English keyboard:</span>
      <span style={{ fontStyle: "italic" }}>"{ex.roman}"</span>
      <span style={{ color: "#B45309" }}>→</span>
      <span style={{ fontWeight: 600, fontFamily: "serif" }}>{ex.native}</span>
    </div>
  );
}

// MAIN PATIENT CHAT COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export default function PatientApp() {
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const { lang, changeLang, t, langConfig } = useLanguage();

  const onLogout = () => {
    console.log("Logout triggered");
    logout();
    navigate("/login");
  };

  const [selDisease, setSelDisease]       = useState(null);
  const [selAgent, setSelAgent]           = useState(null);
  const [isResuming, setIsResuming]       = useState(false);
  const [messages, setMessages]           = useState([]);
  const [loading, setLoading]             = useState(false);
  const [input, setInput]                 = useState("");
  const [convId, setConvId]               = useState(null);

  // Prescription State
  const [isPrescriptionModalOpen, setPrescriptionModalOpen] = useState(false);
  const [isGeneratingPrescription, setIsGeneratingPrescription] = useState(false);

  // History State
  const [isHistoryModalOpen, setHistoryModalOpen] = useState(false);
  const [isDownloadingHistory, setIsDownloadingHistory] = useState(false);
  const [historyAck, setHistoryAck] = useState(true);
  const [showChatHistory, setShowChatHistory] = useState(false);
  const [isHistoryHidden, setIsHistoryHidden] = useState(false);

  // Escalation state
  const [escalationData, setEscalationData]   = useState(null);
  const [routeDecision, setRouteDecision]     = useState("primary");
  const [specialistAgent, setSpecialistAgent] = useState(null);
  const [humanAgent, setHumanAgent]           = useState(null);
  const [confidence, setConfidence]           = useState(null);
  const [showHumanCard, setShowHumanCard]     = useState(false);

  // Conversational Engine state
  const [isAskingQuestions, setIsAskingQuestions] = useState(false);
  const [currentQuestionNum, setCurrentQuestionNum] = useState(0);
  const [maxQuestions, setMaxQuestions]           = useState(5);
  const [currentIntent, setCurrentIntent]         = useState(null);
  const [slotsFilledCount, setSlotsFilledCount]   = useState(0);
  const [qualityScore, setQualityScore]           = useState(null);
  const [qualityRecommendation, setQualityRec]    = useState("");
  const [dynamicQuestions, setDynamicQuestions]   = useState([]);

  const endRef = useRef(null);
  const effectiveSubs = ['CA', 'DM', 'CV', 'MH', 'RS'];

  // Auto-select first agent if none selected
  // (Disabled to prioritize History view on entry as per user request)
  /*
  useEffect(() => {
    if (!selAgent && effectiveSubs.length > 0) {
      const firstCode = effectiveSubs[0];
      const disease = DISEASES.find(d => d.code === firstCode) || DISEASES[0];
      if (disease && disease.agents[0]) {
        setSelDisease(disease);
        setSelAgent(disease.agents[0]);
      }
    }
  }, [effectiveSubs, selAgent]);
  */

  console.log("PatientApp user:", user);
  console.log("PatientApp subs:", effectiveSubs);

  useEffect(() => {
    if (loading) {
      endRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [loading]);

  useEffect(() => {
    if (messages.length > 0) {
      const lastMsg = messages[messages.length - 1];
      // If it's a new assistant message, scroll to TOP of it
      if (lastMsg.role === "assistant" && !lastMsg.isRestored) {
        setTimeout(() => {
          const el = document.getElementById("last-message");
          if (el) {
            el.scrollIntoView({ behavior: "smooth", block: "start" });
          } else {
            endRef.current?.scrollIntoView({ behavior: "smooth" });
          }
        }, 100);
      } else {
        // User message or restored session, scroll to bottom
        endRef.current?.scrollIntoView({ behavior: "smooth" });
      }
    }
  }, [messages]);

  const handleRestoreConversation = useCallback((data) => {
    const { conversation, messages: histMessages } = data;
    if (!conversation) return;

    const disease = DISEASES.find(d => d.code === conversation.disease_code);
    const agent   = disease?.agents.find(a => a.id === conversation.agent_id);

    if (disease && agent) {
      setSelDisease(disease);
      setSelAgent(agent);
    }

    setConvId(conversation.id);
    setMessages(histMessages.map(m => ({
      role:             m.role,
      content:          m.content,
      id:               m.id,
      isVoice:          m.is_voice,
      response_type:    m.is_image ? "image_analysis" : "answer",
      confidence:       m.confidence,
      citations:        m.citations || [],
      isRestored:       true,
      followUpQuestions: m.follow_up_questions || [],
      genericSupport:    m.generic_support || [],
      responseFormat:    m.response_format,
      intent:            m.intent,
    })));

    setIsHistoryHidden(conversation.is_hidden || false);

    setEscalationData(null);
    setRouteDecision("primary");
    setSpecialistAgent(null);
    setHumanAgent(null);
    setConfidence(null);
    setShowHumanCard(false);
  }, []);

  // Reset escalation state when agent changes + Resume Session Logic
  const selectAgent = useCallback(async (disease, agent) => {
    setSelDisease(disease);
    setSelAgent(agent);
    
    setLoading(true);
    setIsResuming(true);
    setMessages([]); // Clear immediately to show fresh state
    setConvId(null);
    setEscalationData(null);
    setRouteDecision("primary");
    setSpecialistAgent(null);
    setHumanAgent(null);
    setConfidence(null);
    setShowHumanCard(false);
    setDynamicQuestions([]); 

    try {
      const { data } = await api.get(`/conversations/resume/${agent.id}`);
      if (data && data.conversation) {
        handleRestoreConversation(data);
        setIsResuming(false);
        setLoading(false);
        return;
      }
    } catch (e) {
      console.log("No previous session found for agent:", agent.id);
    }

    setIsResuming(false);
    setLoading(false);
  }, [handleRestoreConversation]);

  // Global Resume on Mount
  useEffect(() => {
    setIsResuming(true);
    api.get("/conversations/last_active")
      .then(res => {
        if (res.data && res.data.conversation) {
          handleRestoreConversation(res.data);
        }
      })
      .catch(err => console.log("No global last active session found"))
      .finally(() => setIsResuming(false));
  }, [handleRestoreConversation]);

  // Fetch dynamic initial questions
  useEffect(() => {
    if (selAgent && messages.length === 0 && !isResuming && !loading) {
      api.get(`/agents/${selAgent.id}/questions`)
        .then(res => setDynamicQuestions(res.data.questions || []))
        .catch(err => {
          console.error("Failed to fetch dynamic questions:", err);
          setDynamicQuestions(selAgent.qs || []);
        });
    }
  }, [selAgent, messages.length, isResuming, loading]);

  const handleGeneratePrescription = async () => {
    if (!selAgent || !convId) return;
    setIsGeneratingPrescription(true);
    try {
      const response = await api.post("/chat/prescription", {
        conversation_id: convId,
        agent_id: selAgent.id
      }, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `prescription_${convId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      setPrescriptionModalOpen(false);
    } catch (e) {
      console.error("Failed to generate prescription:", e);
      if (e.response?.data instanceof Blob && e.response.data.type === 'application/json') {
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const errorData = JSON.parse(reader.result);
            alert(`Failed to generate prescription: ${errorData.detail || "Unknown error"}`);
          } catch (err) {
            alert("Failed to generate prescription. Please try again.");
          }
        };
        reader.readAsText(e.response.data);
      } else {
        alert("Failed to generate prescription. Please try again.");
      }
    } finally {
      setIsGeneratingPrescription(false);
    }
  };


  const handleDownloadHistory = async () => {
    if (!convId) return;
    setIsDownloadingHistory(true);
    try {
      const response = await api.post("/chat/history/download", {
        conversation_id: convId
      }, {
        responseType: 'blob'
      });
      
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `history_${convId}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.parentNode.removeChild(link);
      setHistoryModalOpen(false);
      setHistoryAck(false);
    } catch (e) {
      console.error("Failed to download history:", e);
      if (e.response?.data instanceof Blob && e.response.data.type === 'application/json') {
        const reader = new FileReader();
        reader.onload = () => {
          try {
            const errorData = JSON.parse(reader.result);
            alert(`Failed to download history: ${errorData.detail || "Unknown error"}`);
          } catch (err) {
            alert("Failed to download history. Please try again.");
          }
        };
        reader.readAsText(e.response.data);
      } else {
        alert("Failed to download history. Please try again.");
      }
    } finally {
      setIsDownloadingHistory(false);
    }
  };

  const sendMessage = async (txt) => {
    const msg = txt || input.trim();
    if (!msg || !selAgent) return;
    setInput("");

    const userMsg = { role: "user", content: msg, id: Date.now() };
    setMessages(m => [...m, userMsg]);
    setLoading(true);

    try {
      const { data } = await api.post("/chat", {
        agent_id:        selAgent.id,
        message:         msg,
        language:        lang,
        conversation_id: convId || undefined,
      });

      if (!convId) setConvId(data.conversation_id);

      setConfidence(data.confidence);
      setRouteDecision(data.route_decision || "primary");
      setEscalationData(data.escalation_monitor);
      setSpecialistAgent(data.specialist_agent);
      setHumanAgent(data.human_agent);

      // Update conversational engine state
      if (data.response_type === "question") {
        setIsAskingQuestions(true);
        setCurrentQuestionNum(data.question_number);
        setMaxQuestions(data.max_questions || 5);
      } else {
        setIsAskingQuestions(false);
      }
      setCurrentIntent(data.intent);
      setSlotsFilledCount(data.slots_filled ? Object.keys(data.slots_filled).length : 0);
      
      // Update Quality State
      if (data.quality_score) {
        setQualityScore(data.quality_score);
        setQualityRec(data.quality_recommendation);
      }

      if (data.route_decision === "human") {
        setShowHumanCard(true);
      }

      setMessages(m => {
        const newM = m.map(msg => msg.id === userMsg.id ? { ...msg, nativeInput: data.native_input } : msg);
        return [...newM, {
          role:             "assistant",
          content:          data.response,
          responseLanguage: lang,
          id:               Date.now() + 1,
          message_id:       data.message_id,
          conversation_id:  data.conversation_id,
          routeDecision:    data.route_decision,
          confidence:       data.confidence,
          frustration:      data.frustration_score,
          escalationActive: data.escalation_active,
          respondedBy:      data.responded_by,
          specialistAgent:  data.specialist_agent,
          humanAgent:       data.human_agent,
          citations:        data.citations,
          followUpQuestions: data.follow_up_questions,
          genericSupport:   data.generic_support,
          responseFormat:   data.response_format,
          intent:           data.intent,
          isQuestion:       data.response_type === "question",
          questionNumber:   data.question_number,
          maxQuestions:     data.max_questions,
          slotsCount:       data.slots_filled ? Object.keys(data.slots_filled).length : 0,
          contextCollected: data.context_collected,
        }];
      });
      setIsHistoryHidden(false); // Auto-restore on new message
    } catch (e) {
      setMessages(m => [...m, {
        role:    "assistant",
        content: `⚠️ Error: ${e.message}`,
        id:      Date.now() + 1,
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleImageAnalysis = (data) => {
    if (!convId) setConvId(data.conversation_id);
    setMessages(m => [...m, {
      role: "user",
      content: `[Image: ${data.image_label}]`,
      id: Date.now()
    }, {
      role: "assistant",
      content: data.response,
      id: Date.now() + 1,
      message_id: data.message_id,
      conversation_id: data.conversation_id,
      response_type: "image_analysis",
      imageLabel: data.image_label,
      imageType: data.image_type,
      keyValues: data.key_values,
      clinicalObs: data.clinical_obs,
      hasCriticalValues: data.has_critical_values,
      criticalFlags: data.critical_flags,
      f1Score: data.f1_score,
      visionConfidence: data.vision_confidence,
      preview: data.preview,
      citations: data.citations || [],
      followUpQuestions: data.follow_up_questions || []
    }]);
  };

  const handleVoiceMessage = (msgObj) => {
    // msgObj: {role, content, isVoice, voiceData, id, respondedBy, etc}
    if (!convId && msgObj.conversation_id) setConvId(msgObj.conversation_id);
    setMessages(m => [...m, { ...msgObj, id: msgObj.id || Date.now() }]);
    setIsHistoryHidden(false); // Auto-restore on voice message
  };

  const handleToggleVisibility = async () => {
    if (!convId) return;
    try {
      const { data } = await api.post(`/conversations/${convId}/toggle-visibility`);
      setIsHistoryHidden(data.is_hidden);
    } catch (e) {
      console.error("Failed to toggle visibility:", e);
    }
  };

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden", background: "var(--bg-main)", color: "var(--text-main)", fontFamily: "Inter, system-ui, -apple-system, sans-serif" }}>

      {/* ── Disease Sidebar ─────────────────────────────────────────────────── */}
      <DiseaseSidebar
        diseases={DISEASES}
        subs={effectiveSubs}
        selDisease={selDisease}
        selAgent={selAgent}
        onSelectAgent={selectAgent}
        onToggleHistory={() => setShowChatHistory(true)}
      />


      {/* ── Main Chat Area ──────────────────────────────────────────────────── */}
      <main style={{ flex: 1, display: "flex", flexDirection: "column", overflow: "hidden", minWidth: 0 }}>

        {/* Agent header bar */}
        {selAgent && (
          <>
            <AgentHeaderBar
              agent={selAgent}
              disease={selDisease}
              routeDecision={routeDecision}
              confidence={confidence}
              user={user}
              onLogout={onLogout}
              onOpenPrescription={() => setPrescriptionModalOpen(true)}
              onOpenHistory={() => { setHistoryModalOpen(true); setHistoryAck(true); }}
              onToggleHistory={() => setShowChatHistory(true)}
              canRequestPrescription={!!convId}
              lang={lang}
              changeLang={changeLang}
            />
            <TransliterationBanner lang={lang} langConfig={langConfig} />
          </>
        )}

        {/* NavBar when no agent selected */}
        {!selAgent && (
          <div style={{ padding: "0 20px", height: 52, display: "flex", alignItems: "center", justifyContent: "space-between", background: "var(--bg-card)", borderBottom: "1px solid var(--border)" }}>
            <div style={{ fontWeight: 800, fontSize: 16, color: "var(--text-main)", tracking: "tight" }}>PRISM</div>
            <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
              <button
                onClick={() => setShowChatHistory(true)}
                title="View chat history (last 15 days)"
                style={{
                  display:      "flex",
                  alignItems:   "center",
                  gap:          5,
                  padding:      "6px 10px",
                  background:   "transparent",
                  border:       "1px solid rgba(255,255,255,0.15)",
                  borderRadius: 8,
                  fontSize:     12,
                  color:        "#94A3B8",
                  cursor:       "pointer",
                  fontFamily:   "inherit",
                  fontWeight:   500,
                }}
              >
                🕐 History
              </button>
              <button 
                onClick={() => navigate('/admin')}
                style={{ background: "rgba(59, 130, 246, 0.1)", border: "1px solid rgba(59, 130, 246, 0.2)", padding: "6px 14px", borderRadius: 8, cursor: "pointer", color: "var(--accent)", fontSize: 12, fontWeight: 700, display: "flex", alignItems: "center", gap: 8 }}
              >
                <Settings size={14} /> Admin Console
              </button>
              <button 
                onClick={onLogout} 
                title="Sign out"
                style={{ background: "transparent", border: "none", padding: 8, cursor: "pointer", color: "#64748B", display: "flex", alignItems: "center" }}
              >
                <LogOut size={18} />
              </button>
            </div>
          </div>
        )}

        {/* Chat messages */}
        {/* ── Projected Quality Score Banner ── */}
        {qualityScore && (
          <div style={{
            margin: "12px 16px 0 16px",
            padding: "10px 14px",
            background: qualityScore >= 80 ? "#ECFDF5" : "#FFFBEB",
            border: `1px solid ${qualityScore >= 80 ? "#10B981" : "#FBBF24"}44`,
            borderRadius: 12,
            display: "flex",
            alignItems: "center",
            gap: 12,
            animation: "slideIn .3s ease",
          }}>
            <div style={{
              width: 36, height: 36, borderRadius: "50%",
              background: qualityScore >= 80 ? "#10B981" : "#FBBF24",
              display: "flex", alignItems: "center", justifyContent: "center",
              fontSize: 11, color: "#fff", fontWeight: 700, flexShrink: 0
            }}>
              {Math.round(qualityScore)}%
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ fontSize: 11, fontWeight: 700, color: qualityScore >= 80 ? "#065F46" : "#92400E" }}>
                Projected Conversation Quality
              </div>
              <div style={{ fontSize: 10, color: qualityScore >= 80 ? "#047857" : "#B45309", marginTop: 1 }}>
                {qualityRecommendation}
              </div>
            </div>
            {qualityScore >= 85 && <span style={{ fontSize: 16 }}>🏆</span>}
          </div>
        )}

        <div style={{ flex: 1, overflowY: "auto", padding: "16px 0", position: "relative" }} className="chat-scroll">
          {!selAgent && (
            <EmptyState onSubscribe={() => {}} />
          )}

          {selAgent && messages.length === 0 && !isResuming && !loading && (
            <div style={{ padding: "0 20px 20px" }}>
              <AgentIntro agent={selAgent} />
              <SuggestedQuestions 
                questions={dynamicQuestions} 
                onSelect={(q) => { setInput(q); }} 
              />
            </div>
          )}

          {isResuming && (
            <div style={{ padding: "40px 20px", textAlign: "center", color: "#94A3B8" }}>
              <RefreshCw size={32} className="animate-spin" style={{ margin: "0 auto 12px", opacity: 0.5 }} />
              <div style={{ fontSize: 14, fontWeight: 500 }}>Restoring your previous session...</div>
            </div>
          )}

          {isHistoryHidden && (
            <div style={{ padding: "60px 20px", textAlign: "center", color: "#64748B" }}>
              <div style={{ fontSize: 40, marginBottom: 12, opacity: 0.5 }}>🙈</div>
              <div style={{ fontSize: 14, fontWeight: 500 }}>Chat history is hidden to reduce clutter.</div>
              <div style={{ fontSize: 12, marginTop: 4 }}>Click "Restore" below to bring it back.</div>
            </div>
          )}

          {!isHistoryHidden && messages.map((m, idx) => (
            <div 
              key={m.id} 
              id={idx === messages.length - 1 ? "last-message" : undefined}
              style={{ scrollMarginTop: "20px" }}
            >
              {m.response_type === "image_analysis" ? (
                <ImageAnalysisMessage 
                  message={m}
                  disease={selDisease}
                  agentId={selAgent?.id}
                  conversationId={convId}
                  preview={m.preview}
                  onFollowUpSelect={(q) => { setInput(q); inputRef.current?.focus(); }}
                />
              ) : (
                <ConversationalMessage 
                  message={m} 
                  disease={selDisease} 
                  agentId={selAgent?.id}
                  conversationId={convId}
                  onFollowUpSelect={(q) => { setInput(q); inputRef.current?.focus(); }}
                  followUpDisabled={loading}
                />
              )}
            </div>
          ))}

          {/* Human Coordinator Card — appears after human escalation */}
          {showHumanCard && humanAgent && routeDecision === "human" && (
            <HumanCoordinatorCard
              humanAgent={humanAgent}
              disease={selDisease}
              onDismiss={() => setShowHumanCard(false)}
            />
          )}

          {/* Loading indicator */}
          {loading && (
            <TypingIndicator 
              isQuestion={isAskingQuestions} 
              diseaseColor={selDisease?.color} 
            />
          )}
          <div ref={endRef} />
        </div>

          {isAskingQuestions && (
            <ConversationProgress
              questionNumber={currentQuestionNum}
              maxQuestions={maxQuestions}
              intent={currentIntent}
              slotsFilledCount={slotsFilledCount}
              onSkip={() => sendMessage("skip")}
              diseaseColor={selDisease?.color}
            />
          )}

        {/* Restore / Delete Button */}
        {selAgent && convId && (
          <div style={{ display: "flex", justifyContent: "center", paddingBottom: 8 }}>
            <button 
              onClick={handleToggleVisibility}
              style={{
                background: "rgba(255,255,255,0.03)",
                border: "1px solid rgba(255,255,255,0.08)",
                padding: "6px 14px",
                borderRadius: 20,
                cursor: "pointer",
                color: isHistoryHidden ? "#F37029" : "#94A3B8",
                fontSize: 11,
                fontWeight: 700,
                display: "flex",
                alignItems: "center",
                gap: 6,
                transition: "all 0.2s ease",
                boxShadow: "0 2px 5px rgba(0,0,0,0.2)"
              }}
              onMouseEnter={e => e.currentTarget.style.background = "rgba(255,255,255,0.08)"}
              onMouseLeave={e => e.currentTarget.style.background = "rgba(255,255,255,0.03)"}
            >
              {isHistoryHidden ? <RefreshCw size={12} /> : <Trash2 size={12} />}
              {isHistoryHidden ? "Restore History" : "Delete / Restore"}
            </button>
          </div>
        )}

        {/* Input bar */}
        {selAgent && (
          <InputBar
            input={input}
            setInput={setInput}
            loading={loading}
            onSend={sendMessage}
            agentName={selAgent.name}
            agentId={selAgent.id}
            convId={convId}
            language={lang}
            onImageAnalysis={handleImageAnalysis}
            onVoiceMessage={handleVoiceMessage}
            diseaseColor={selDisease?.color}
            diseaseName={selDisease?.name}
            t={t}
          />
        )}

        <ChatHistory
          isOpen={showChatHistory}
          onClose={() => setShowChatHistory(false)}
          onRestoreConversation={handleRestoreConversation}
          currentConvId={convId}
        />
      </main>

      {/* Prescription Disclaimer Modal */}
      {isPrescriptionModalOpen && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", animation: "fadeIn .2s ease" }}>
          <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 16, width: 400, maxWidth: "90%", padding: 24, color: "var(--text-main)", boxShadow: "0 10px 25px rgba(0,0,0,0.5)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, color: "#F59E0B" }}>
              <div style={{ width: 40, height: 40, borderRadius: "50%", background: "rgba(245, 158, 11, 0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <FileText size={20} />
              </div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>Prescription Request</div>
            </div>
            <div style={{ fontSize: 14, lineHeight: 1.6, color: "#CBD5E1", marginBottom: 24, padding: "12px 16px", background: "rgba(239, 68, 68, 0.1)", borderLeft: "4px solid #EF4444", borderRadius: "0 8px 8px 0" }}>
              <strong style={{ color: "#EF4444" }}>DISCLAIMER:</strong> This prescription will be generated for reference purposes only and NOT for recommendation as per local compliance or regulatory instructions. Please consult a registered medical practitioner before taking any medication.
            </div>
            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button 
                onClick={() => setPrescriptionModalOpen(false)}
                disabled={isGeneratingPrescription}
                style={{ padding: "8px 16px", background: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "#F1F5F9", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}
              >
                Cancel
              </button>
              <button 
                onClick={handleGeneratePrescription}
                disabled={isGeneratingPrescription}
                style={{ padding: "8px 16px", background: "#10B981", border: "none", color: "#fff", borderRadius: 8, cursor: isGeneratingPrescription ? "not-allowed" : "pointer", fontWeight: 600, display: "flex", alignItems: "center", gap: 8 }}
              >
                {isGeneratingPrescription ? "Generating..." : "Agree & Download"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Download History Modal */}
      {isHistoryModalOpen && (
        <div style={{ position: "fixed", top: 0, left: 0, right: 0, bottom: 0, background: "rgba(0,0,0,0.6)", zIndex: 1000, display: "flex", alignItems: "center", justifyContent: "center", animation: "fadeIn .2s ease" }}>
          <div style={{ background: "var(--bg-card)", border: "1px solid var(--border)", borderRadius: 16, width: 440, maxWidth: "90%", padding: 24, color: "var(--text-main)", boxShadow: "0 10px 25px rgba(0,0,0,0.5)" }}>
            <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 16, color: "#3B82F6" }}>
              <div style={{ width: 40, height: 40, borderRadius: "50%", background: "rgba(59, 130, 246, 0.1)", display: "flex", alignItems: "center", justifyContent: "center" }}>
                <Download size={20} />
              </div>
              <div style={{ fontSize: 18, fontWeight: 700 }}>Download Chat History</div>
            </div>
            
            <label style={{ display: "flex", gap: 12, alignItems: "flex-start", marginBottom: 24, padding: "12px 16px", background: "rgba(255,255,255,0.05)", borderRadius: 8, cursor: "pointer" }}>
              <input 
                type="checkbox" 
                checked={historyAck} 
                onChange={(e) => setHistoryAck(e.target.checked)} 
                style={{ marginTop: 4 }}
              />
              <div style={{ fontSize: 14, lineHeight: 1.6, color: "#CBD5E1" }}>
                <strong>Yes</strong>, I acknowledge that this conversation history is downloaded for future reference purposes only and NOT for medical recommendation.
              </div>
            </label>

            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button 
                onClick={() => setHistoryModalOpen(false)}
                disabled={isDownloadingHistory}
                style={{ padding: "8px 16px", background: "transparent", border: "1px solid rgba(255,255,255,0.2)", color: "#F1F5F9", borderRadius: 8, cursor: "pointer", fontWeight: 600 }}
              >
                Cancel
              </button>
              <button 
                onClick={handleDownloadHistory}
                disabled={isDownloadingHistory}
                style={{ padding: "8px 16px", background: "#3B82F6", border: "none", color: "#fff", borderRadius: 8, cursor: isDownloadingHistory ? "not-allowed" : "pointer", fontWeight: 600, display: "flex", alignItems: "center", gap: 8, opacity: 1 }}
              >
                {isDownloadingHistory ? "Downloading..." : "Download PDF"}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes pulse { 0%, 100% { opacity: .4 } 50% { opacity: 1 } }
        @keyframes slideIn { from { opacity: 0; transform: translateY(10px) } to { opacity: 1; transform: translateY(0) } }
      `}</style>
    </div>
  );
}

// ─── Disease Sidebar ───────────────────────────────────────────────────────────
function DiseaseSidebar({ diseases, subs, selDisease, selAgent, onSelectAgent, onToggleHistory }) {
  const finalVisible = diseases;

  return (
    <aside style={{ width: 220, background: "var(--bg-main)", borderRight: "1px solid var(--border)", overflowY: "hidden", flexShrink: 0, display: "flex", flexDirection: "column" }}>
      <div style={{ padding: "16px 12px", borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
        <button
          onClick={onToggleHistory}
          style={{
            width: "100%",
            padding: "12px",
            background: "var(--grad-primary)",
            border: "none",
            borderRadius: 12,
            color: "#fff",
            fontSize: 14,
            fontWeight: 800,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: 10,
            cursor: "pointer",
            boxShadow: "0 4px 12px var(--accent-glow)",
            transition: "all 0.2s ease",
            fontFamily: "inherit"
          }}
          onMouseOver={e => e.currentTarget.style.transform = "translateY(-2px)"}
          onMouseOut={e => e.currentTarget.style.transform = "translateY(0)"}
        >
          <RefreshCw size={18} /> Chat History
        </button>
      </div>

      <div style={{ padding: "10px 8px", flex: 1, overflowY: "auto" }}>
        <div style={{ fontSize: 10, fontWeight: 600, color: "#94A3B8", textTransform: "uppercase", letterSpacing: ".08em", marginBottom: 8, padding: "0 6px" }}>Disease Domains</div>
        {finalVisible.map(d => {
          const has    = true; // Since we filtered, they all have it
          const active = selDisease?.code === d.code;
          return (
            <div key={d.code} style={{ marginBottom: 4 }}>
              <button
                onClick={() => { if (d.agents[0]) onSelectAgent(d, d.agents[0]); }}
                style={{ width: "100%", textAlign: "left", padding: "10px 12px", borderRadius: 12, border: "none", background: active ? "var(--accent-glow)" : "transparent", color: active ? "var(--accent)" : "var(--text-dim)", fontWeight: active ? 700 : 500, fontSize: 13, display: "flex", alignItems: "center", gap: 10, cursor: "pointer", transition: "all .2s ease", fontFamily: "inherit" }}
              >
                <span style={{ fontSize: 16 }}>{d.icon}</span>{d.name}
              </button>
              {active && (
                <div style={{ paddingLeft: 12, marginTop: 4, marginBottom: 8, borderLeft: "2px solid var(--accent-glow)", marginLeft: 20 }}>
                  {d.agents.map(a => (
                    <button
                      key={a.id}
                      onClick={() => onSelectAgent(d, a)}
                      title={a.fullName}
                      style={{ width: "100%", textAlign: "left", padding: "6px 12px", borderRadius: 8, border: "none", background: selAgent?.id === a.id ? "var(--accent-glow)" : "transparent", color: selAgent?.id === a.id ? "var(--accent)" : "var(--text-dim)", fontSize: 12, fontWeight: selAgent?.id === a.id ? 600 : 400, display: "flex", alignItems: "center", gap: 8, cursor: "pointer", marginBottom: 2, transition: "all .2s ease", fontFamily: "inherit" }}
                    >
                      <span style={{ fontSize: 12 }}>{a.icon}</span>{a.name}
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}

// ─── Agent Header Bar ──────────────────────────────────────────────────────────
function AgentHeaderBar({ agent, disease, routeDecision, confidence, user, onLogout, onOpenPrescription, onOpenHistory, onToggleHistory, canRequestPrescription, lang, changeLang }) {
  const routeBadge = {
    primary:    { label: "Primary",    color: "#34D399", bg: "rgba(52, 211, 153, 0.1)" },
    specialist: { label: "Specialist", color: "#F5C842", bg: "rgba(245, 200, 66, 0.1)" },
    human:      { label: "Human Coord.", color: "#F05252", bg: "rgba(240, 82, 82, 0.1)" },
  }[routeDecision] || { label: "Primary", color: "#34D399", bg: "rgba(52, 211, 153, 0.1)" };

  return (
    <div style={{ padding: "12px 20px", background: "var(--bg-card)", borderBottom: "1px solid var(--border)", display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ width: 40, height: 40, rounded: "12px", background: "var(--accent-glow)", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 20, flexShrink: 0 }}>{agent.icon}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontWeight: 800, fontSize: 18, color: "var(--text-main)", letterSpacing: "-0.01em" }}>{disease?.name}</div>
        <div style={{ fontSize: 12, color: "var(--text-dim)", fontWeight: 500 }}>{agent.fullName || agent.name} · <span style={{ color: "var(--accent)", fontWeight: 700 }}>{agent.id}</span></div>
      </div>

      {canRequestPrescription && (
        <>
          <button 
            onClick={onToggleHistory}
            title="View chat history (last 15 days)"
            style={{ display: "flex", alignItems: "center", gap: 6, background: "rgba(255,255,255,0.05)", border: "1px solid rgba(255,255,255,0.1)", padding: "8px 12px", borderRadius: 10, cursor: "pointer", color: "#94A3B8", fontSize: 12, fontWeight: 600, transition: "all 0.2s" }}
          >
            <RefreshCw size={14} /> History
          </button>

          <button 
            onClick={onOpenHistory}
            style={{ background: "rgba(59, 130, 246, 0.1)", border: "1px solid rgba(59, 130, 246, 0.2)", padding: "6px 12px", borderRadius: 8, cursor: "pointer", color: "var(--accent)", fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", gap: 6, marginRight: 8 }}
          >
            <Download size={14} /> Download History
          </button>

          <button 
            onClick={onOpenPrescription}
            style={{ background: "rgba(16, 185, 129, 0.1)", border: "1px solid rgba(16, 185, 129, 0.2)", padding: "6px 12px", borderRadius: 8, cursor: "pointer", color: "#10B981", fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", gap: 6, marginRight: 8 }}
          >
            <FileText size={14} /> Request Prescription
          </button>
        </>
      )}

      <LanguageSelector value={lang} onChange={changeLang} compact={false} />

      <button 
        onClick={() => navigate('/admin')}
        style={{ background: "rgba(59, 130, 246, 0.1)", border: "1px solid rgba(59, 130, 246, 0.2)", padding: "6px 12px", borderRadius: 8, cursor: "pointer", color: "var(--accent)", fontSize: 11, fontWeight: 700, display: "flex", alignItems: "center", gap: 6, marginRight: 8 }}
      >
        <Settings size={14} /> Admin Console
      </button>

      <button 
        onClick={onLogout} 
        title="Sign out"
        style={{ background: "transparent", border: "none", padding: 8, cursor: "pointer", color: "#64748B" }}
      >
        <LogOut size={18} />
      </button>
    </div>
  );
}



// ─── Human Coordinator Card ────────────────────────────────────────────────────
function HumanCoordinatorCard({ humanAgent, disease, onDismiss }) {
  return (
    <div style={{ margin: "8px 0 16px", border: "1px solid #FECACA", borderRadius: 12, overflow: "hidden", boxShadow: "0 4px 12px rgba(185,28,28,.1)", animation: "slideIn .3s ease" }}>
      {/* Header */}
      <div style={{ background: "#0D1B2E", padding: "12px 16px", display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{ width: 36, height: 36, borderRadius: "50%", background: "#F37029", display: "flex", alignItems: "center", justifyContent: "center", color: "#fff", fontWeight: 700, fontSize: 16 }}>P</div>
        <div>
          <div style={{ color: "#FFFFFF", fontWeight: 700, fontSize: 13 }}>Connect to a PRISM care coordinator</div>
          <div style={{ color: "#6B8CAE", fontSize: 11 }}>Available Mon–Fri 8am–8pm · Saturday 9am–2pm</div>
        </div>
      </div>

      {/* Contact options */}
      <div style={{ background: "#FFFFFF", padding: "8px 0" }}>
        <ContactRow icon="📞" title="Toll-free call" subtitle={humanAgent.contact?.split("·")[0]?.trim() || "800-PRISM-HEALTH"} />
        <ContactRow icon="💬" title="WhatsApp coordinator" subtitle={(humanAgent.contact?.split("·")[1]?.trim() || "+52 55 1234-5678") + " · reply in 15 min"} />
        <ContactRow icon="📅" title="Book doctor appointment" subtitle="Next available: Dr. Ramírez · Tomorrow 10:00" />
      </div>

      {/* Footer note */}
      <div style={{ background: "#F8FAFC", borderTop: "1px solid #E2E8F0", padding: "8px 16px", fontSize: 10, color: "#94A3B8", lineHeight: 1.5 }}>
        Your conversation summary has been shared with the care coordinator so you do not need to repeat yourself.
        IMSS/ISSSTE patients: bring your number. Private: we accept all major plans.
      </div>
    </div>
  );
}

function ContactRow({ icon, title, subtitle }) {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12, padding: "10px 16px", borderBottom: "1px solid #F1F5F9" }}>
      <div style={{ width: 32, height: 32, borderRadius: 8, background: "#EFF6FF", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 16, flexShrink: 0 }}>{icon}</div>
      <div>
        <div style={{ fontSize: 13, fontWeight: 500, color: "#0F172A" }}>{title}</div>
        <div style={{ fontSize: 11, color: "#64748B" }}>{subtitle}</div>
      </div>
    </div>
  );
}

// ─── Agent Introduction ───────────────────────────────────────────────────────
function AgentIntro({ agent }) {
  return (
    <div style={{
      marginBottom: 12,
      padding: "12px 16px",
      background: "var(--bg-card)",
      border: "1px solid var(--border)",
      borderRadius: 12,
      textAlign: "left",
      borderLeft: "4px solid var(--accent)",
      boxShadow: "0 2px 8px rgba(0,0,0,0.05)"
    }}>
      <h2 style={{ fontSize: 14, fontWeight: 800, color: "var(--text-main)", marginBottom: 2 }}>{agent.fullName}</h2>
      <p style={{ fontSize: 11, color: "var(--text-dim)", lineHeight: 1.4, margin: 0 }}>
        {agent.description}
      </p>
    </div>
  );
}

// ─── Suggested Questions ───────────────────────────────────────────────────────
function SuggestedQuestions({ questions, onSelect }) {
  const [hoverIdx, setHoverIdx] = useState(null);

  return (
    <div style={{ marginBottom: 16 }}>
      <div style={{ fontSize: 13, color: "var(--color-text-secondary)", marginBottom: 10, fontWeight: 500 }}>To help me understand your needs, would you like to start by asking about...?</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {(questions || []).map((q, i) => (
          <button 
            key={i} 
            onClick={() => onSelect(q)}
            onMouseEnter={() => setHoverIdx(i)}
            onMouseLeave={() => setHoverIdx(null)}
            style={{ 
              textAlign: "left", 
              padding: "12px 16px", 
              background: hoverIdx === i ? "var(--accent-glow)" : "var(--bg-card)", 
              border: hoverIdx === i ? "1px solid var(--accent)" : "1px solid var(--border)", 
              borderRadius: 12, 
              fontSize: 12, 
              color: hoverIdx === i ? "var(--text-main)" : "var(--text-dim)", 
              display: "flex", 
              alignItems: "flex-start", 
              gap: 10, 
              fontFamily: "inherit",
              cursor: "pointer",
              transition: "all 0.2s ease",
              width: "100%"
            }}
          >
            <span style={{ fontSize: 10, fontWeight: 700, color: "var(--accent)", fontFamily: "monospace", paddingTop: 2, flexShrink: 0 }}>{String(i + 1).padStart(2, "0")}</span>
            <span>{q}</span>
          </button>
        ))}
      </div>
    </div>
  );
}

// ─── Empty State ───────────────────────────────────────────────────────────────
function EmptyState({ onOpenHistory }) {
  return (
    <div style={{ height: "100%", display: "flex", alignItems: "center", justifyContent: "center", flexDirection: "column", gap: 20, color: "#94A3B8", padding: 40 }}>
      <div style={{ fontSize: 64, animation: "bounce 2s infinite" }}>👋</div>
      <div style={{ textAlign: "center", maxWidth: 400 }}>
        <h2 style={{ color: "#F1F5F9", marginBottom: 12 }}>Welcome back to PRISM</h2>
        <p style={{ fontSize: 15, lineHeight: 1.6, marginBottom: 24 }}>
          You can check your previous conversations in the <strong>Chat History</strong> or select a disease domain from the sidebar to start a new consultation.
        </p>
      </div>
    </div>
  );
}

// ─── Input Bar ─────────────────────────────────────────────────────────────────
function InputBar({ input, setInput, loading, onSend, agentName, agentId, convId, language, onImageAnalysis, onVoiceMessage, diseaseColor, diseaseName, t }) {
  return (
    <div style={{ padding: "16px 20px", background: "var(--bg-card)", borderTop: "1px solid var(--border)" }}>
      <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
        <ImageUpload
          agentId={agentId}
          conversationId={convId}
          language={language}
          onAnalysisComplete={onImageAnalysis}
          diseaseColor={diseaseColor}
          diseaseName={diseaseName}
        />
        <VoiceChat
          agentId={agentId}
          conversationId={convId}
          language={language}
          onMessageAdded={onVoiceMessage}
          diseaseColor={diseaseColor}
          diseaseName={diseaseName}
        />
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); onSend(); } }}
          placeholder={t ? t.placeholder : `Ask ${agentName} specialist…`}
          style={{ flex: 1, padding: "12px 16px", border: "1px solid var(--border)", background: "var(--bg-main)", borderRadius: 12, fontSize: 13, color: "var(--text-main)", fontFamily: "inherit", outline: "none" }}
        />
        <button
          disabled={loading || !input.trim()}
          onClick={() => onSend()}
          style={{ flexShrink: 0, padding: "12px 24px", background: loading || !input.trim() ? "var(--border)" : "var(--accent)", color: "#fff", border: "none", borderRadius: 12, fontSize: 13, fontWeight: 700, cursor: loading || !input.trim() ? "not-allowed" : "pointer", fontFamily: "inherit", transition: "all .2s ease" }}
        >
          {t ? t.send : "Send"}
        </button>
      </div>
      <div style={{ fontSize: 10, color: "#CBD5E1", marginTop: 6, textAlign: "center" }}>
        ⚕ {t ? t.disclaimer : "Not a substitute for professional medical advice. Always consult your doctor."}
      </div>
    </div>
  );
}