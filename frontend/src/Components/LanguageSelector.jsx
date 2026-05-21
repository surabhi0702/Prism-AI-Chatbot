// ═══════════════════════════════════════════════════════════════════════════════
// FILE: frontend/src/Components/LanguageSelector.jsx
// PRISM Language Selector — Dark-theme dropdown for the Patient Portal header
// ═══════════════════════════════════════════════════════════════════════════════

import { useState, useEffect, useRef } from "react";

// ─── Language config (mirrors backend) ────────────────────────────────────────
export const LANGUAGES = [
  {
    code: "en", name: "English", nativeName: "English",
    flag: "🇬🇧", script: "latin",
    hint: "Type in English",
  },
  {
    code: "hi", name: "Hindi", nativeName: "हिंदी",
    flag: "🇮🇳", script: "devanagari",
    hint: "हिंदी में लिखें या Roman में टाइप करें",
    romanHint: "e.g. mujhe chest mein dard hai",
  },
  {
    code: "te", name: "Telugu", nativeName: "తెలుగు",
    flag: "🇮🇳", script: "telugu",
    hint: "తెలుగులో రాయండి లేదా Roman లో టైప్ చేయండి",
    romanHint: "e.g. naku chest lo noppi undi",
  },
  {
    code: "es", name: "Spanish", nativeName: "Español",
    flag: "🇲🇽", script: "latin",
    hint: "Escribe tu pregunta médica aquí",
    romanHint: "e.g. tengo dolor en el pecho",
  },
  {
    code: "pa", name: "Punjabi", nativeName: "ਪੰਜਾਬੀ",
    flag: "🇮🇳", script: "gurmukhi",
    hint: "ਪੰਜਾਬੀ ਵਿੱਚ ਲਿਖੋ ਜਾਂ Roman ਵਿੱਚ ਟਾਈਪ ਕਰੋ",
    romanHint: "e.g. mera sugar level bahut zyada hai",
  },
];

export function getLanguage(code) {
  return LANGUAGES.find(l => l.code === code) || LANGUAGES[0];
}

// ─── UI STRINGS per language ───────────────────────────────────────────────────
export const UI_STRINGS = {
  en: {
    placeholder:          "Type your medical question…",
    send:                 "Send",
    speak:                "Speak",
    scan:                 "Scan Image",
    thinking:             "PRISM is thinking…",
    disclaimer:           "Not a substitute for professional medical advice.",
    rateResponse:         "Rate this response",
    requestPrescription:  "Request prescription",
    skip:                 "Skip → Just answer",
    questionOf:           (n, max) => `Question ${n} of ${max}`,
    feedbackThanks:       "Thank you for your feedback!",
    translitNote:         null,
  },
  hi: {
    placeholder:          "अपना स्वास्थ्य संबंधी प्रश्न टाइप करें…",
    send:                 "भेजें",
    speak:                "बोलें",
    scan:                 "छवि स्कैन करें",
    thinking:             "PRISM सोच रहा है…",
    disclaimer:           "यह पेशेवर चिकित्सा सलाह का विकल्प नहीं है।",
    rateResponse:         "इस उत्तर को रेटिंग दें",
    requestPrescription:  "प्रिस्क्रिप्शन का अनुरोध करें",
    skip:                 "छोड़ें → सीधे उत्तर दें",
    questionOf:           (n, max) => `प्रश्न ${n} / ${max}`,
    feedbackThanks:       "आपकी प्रतिक्रिया के लिए धन्यवाद!",
    translitNote:         "हिंदी या Roman लिपि दोनों स्वीकार हैं",
  },
  te: {
    placeholder:          "మీ వైద్య ప్రశ్నను టైప్ చేయండి…",
    send:                 "పంపండి",
    speak:                "మాట్లాడండి",
    scan:                 "చిత్రం స్కాన్ చేయండి",
    thinking:             "PRISM ఆలోచిస్తోంది…",
    disclaimer:           "ఇది వృత్తిపరమైన వైద్య సలహాకు ప్రత్యామ్నాయం కాదు.",
    rateResponse:         "ఈ సమాధానాన్ని రేట్ చేయండి",
    requestPrescription:  "ప్రిస్క్రిప్షన్ అభ్యర్థించండి",
    skip:                 "దాటవేయి → సమాధానం చెప్పు",
    questionOf:           (n, max) => `ప్రశ్న ${n} / ${max}`,
    feedbackThanks:       "మీ అభిప్రాయానికి ధన్యవాదాలు!",
    translitNote:         "తెలుగు లేదా Roman రెండూ అంగీకరించబడతాయి",
  },
  es: {
    placeholder:          "Escribe tu pregunta médica aquí…",
    send:                 "Enviar",
    speak:                "Hablar",
    scan:                 "Escanear imagen",
    thinking:             "PRISM está pensando…",
    disclaimer:           "No sustituye el consejo médico profesional.",
    rateResponse:         "Califica esta respuesta",
    requestPrescription:  "Solicitar receta",
    skip:                 "Saltar → Responder ahora",
    questionOf:           (n, max) => `Pregunta ${n} de ${max}`,
    feedbackThanks:       "¡Gracias por tu opinión!",
    translitNote:         null,
  },
  pa: {
    placeholder:          "ਆਪਣਾ ਡਾਕਟਰੀ ਸਵਾਲ ਟਾਈਪ ਕਰੋ…",
    send:                 "ਭੇਜੋ",
    speak:                "ਬੋਲੋ",
    scan:                 "ਤਸਵੀਰ ਸਕੈਨ ਕਰੋ",
    thinking:             "PRISM ਸੋਚ ਰਿਹਾ ਹੈ…",
    disclaimer:           "ਇਹ ਪੇਸ਼ੇਵਰ ਡਾਕਟਰੀ ਸਲਾਹ ਦਾ ਬਦਲ ਨਹੀਂ ਹੈ।",
    rateResponse:         "ਇਸ ਜਵਾਬ ਨੂੰ ਰੇਟ ਕਰੋ",
    requestPrescription:  "ਨੁਸਖਾ ਮੰਗੋ",
    skip:                 "ਛੱਡੋ → ਸਿੱਧਾ ਜਵਾਬ ਦਿਓ",
    questionOf:           (n, max) => `ਸਵਾਲ ${n} / ${max}`,
    feedbackThanks:       "ਤੁਹਾਡੀ ਰਾਏ ਲਈ ਧੰਨਵਾਦ!",
    translitNote:         "ਪੰਜਾਬੀ ਜਾਂ Roman ਦੋਵੇਂ ਮਨਜ਼ੂਰ ਹਨ",
  },
};

export function useUIStrings(lang) {
  return UI_STRINGS[lang] || UI_STRINGS.en;
}


// ═══════════════════════════════════════════════════════════════════════════════
// LANGUAGE SELECTOR COMPONENT  — Dark-theme ready
// ═══════════════════════════════════════════════════════════════════════════════

export default function LanguageSelector({ value, onChange, compact = false }) {
  const [open, setOpen]   = useState(false);
  const [hovered, setHovered] = useState(null);
  const dropdownRef       = useRef(null);
  const current           = getLanguage(value);

  // Close on outside click
  useEffect(() => {
    const handler = (e) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  return (
    <div ref={dropdownRef} style={{ position: "relative", flexShrink: 0 }}>

      {/* ── Trigger button — styled for dark header ─────────────────────────── */}
      <button
        id="language-selector-trigger"
        onClick={() => setOpen(!open)}
        title={`Language: ${current.name}`}
        style={{
          display:        "flex",
          alignItems:     "center",
          gap:            6,
          padding:        "6px 12px",
          background:     open
            ? "rgba(243,112,41,0.20)"
            : "rgba(243,112,41,0.10)",
          border:         `1px solid ${open ? "#F37029" : "rgba(243,112,41,0.45)"}`,
          borderRadius:   8,
          cursor:         "pointer",
          fontSize:       12,
          color:          "#F1F5F9",
          fontFamily:     "inherit",
          fontWeight:     600,
          transition:     "all .15s ease",
          whiteSpace:     "nowrap",
          outline:        "none",
          letterSpacing:  "0.02em",
        }}
        onMouseEnter={e => {
          e.currentTarget.style.background = "rgba(243,112,41,0.22)";
          e.currentTarget.style.borderColor = "#F37029";
        }}
        onMouseLeave={e => {
          if (!open) {
            e.currentTarget.style.background = "rgba(243,112,41,0.10)";
            e.currentTarget.style.borderColor = "rgba(243,112,41,0.45)";
          }
        }}
      >
        <span style={{ fontSize: 16, lineHeight: 1 }}>{current.flag}</span>
        <span style={{ color: "#F37029", fontSize: 10, fontWeight: 700 }}>🌐</span>
        <span>{current.nativeName}</span>
        <span style={{ fontSize: 8, color: "#94A3B8", marginLeft: 2 }}>
          {open ? "▲" : "▼"}
        </span>
      </button>

      {/* ── Dropdown panel — dark glass style ───────────────────────────────── */}
      {open && (
        <div style={{
          position:     "absolute",
          top:          "calc(100% + 8px)",
          right:        0,
          background:   "#0F172A",
          border:       "1px solid rgba(243,112,41,0.3)",
          borderRadius: 14,
          boxShadow:    "0 16px 48px rgba(0,0,0,0.6), 0 0 0 1px rgba(255,255,255,0.04)",
          zIndex: 9999,
          minWidth: 280,
          overflow: "hidden",
          animation: "langDropIn .18s cubic-bezier(.4,0,.2,1)",
        }}>

          {/* Header */}
          <div style={{
            padding: "10px 16px 8px",
            borderBottom: "1px solid rgba(255,255,255,0.07)",
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}>
            <span style={{ fontSize: 14 }}>🌐</span>
            <span style={{
              fontSize: 10,
              fontWeight: 700,
              color: "#64748B",
              letterSpacing: ".08em",
              textTransform: "uppercase",
            }}>
              Select Language
            </span>
          </div>

          {/* Language options */}
          {LANGUAGES.map(lang => {
            const isSelected = lang.code === value;
            const isHov = hovered === lang.code;
            return (
              <button
                key={lang.code}
                onClick={() => { onChange(lang.code); setOpen(false); }}
                onMouseEnter={() => setHovered(lang.code)}
                onMouseLeave={() => setHovered(null)}
                style={{
                  width: "100%",
                  padding: "10px 16px",
                  background: isSelected
                    ? "rgba(243,112,41,0.15)"
                    : isHov
                      ? "rgba(255,255,255,0.05)"
                      : "transparent",
                  border: "none",
                  borderLeft: isSelected ? "3px solid #F37029" : "3px solid transparent",
                  borderBottom: "1px solid rgba(255,255,255,0.04)",
                  cursor: "pointer",
                  textAlign: "left",
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  fontFamily: "inherit",
                  transition: "background .12s, border-color .12s",
                }}
              >
                {/* Flag */}
                <span style={{ fontSize: 22, lineHeight: 1, flexShrink: 0 }}>
                  {lang.flag}
                </span>

                <div style={{ flex: 1, minWidth: 0 }}>
                  {/* Name row */}
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{
                      fontWeight: 700,
                      fontSize: 13,
                      color: isSelected ? "#F37029" : "#F1F5F9",
                    }}>
                      {lang.nativeName}
                    </span>
                    <span style={{ fontSize: 11, color: "#64748B" }}>
                      {lang.name}
                    </span>
                    {isSelected && (
                      <span style={{
                        marginLeft: "auto",
                        fontSize: 9,
                        fontWeight: 700,
                        color: "#F37029",
                        background: "rgba(243,112,41,0.15)",
                        padding: "2px 7px",
                        borderRadius: 4,
                        border: "1px solid rgba(243,112,41,0.3)",
                        letterSpacing: "0.04em",
                        textTransform: "uppercase",
                      }}>
                        ✓ Active
                      </span>
                    )}
                  </div>

                  {/* Transliteration hint */}
                  {lang.romanHint && (
                    <div style={{
                      fontSize: 10,
                      color: "#475569",
                      marginTop: 2,
                      fontStyle: "italic",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      whiteSpace: "nowrap",
                    }}>
                      "{lang.romanHint}"
                    </div>
                  )}
                </div>
              </button>
            );
          })}

          {/* Footer tip */}
          <div style={{
            padding: "8px 16px",
            background: "rgba(243,112,41,0.06)",
            borderTop: "1px solid rgba(243,112,41,0.15)",
            fontSize: 10,
            color: "#F59E0B",
            lineHeight: 1.5,
            display: "flex",
            alignItems: "flex-start",
            gap: 6,
          }}>
            <span>💡</span>
            <span>For Hindi, Telugu &amp; Punjabi: type using English keyboard — PRISM converts automatically to native script.</span>
          </div>
        </div>
      )}

      <style>{`
        @keyframes langDropIn {
          from { opacity: 0; transform: translateY(-6px) scale(0.97); }
          to   { opacity: 1; transform: translateY(0)    scale(1); }
        }
      `}</style>
    </div>
  );
}