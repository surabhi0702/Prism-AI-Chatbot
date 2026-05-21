// ═══════════════════════════════════════════════════════════════════════════════
// FILE A: frontend/src/context/LanguageContext.jsx  (CREATE NEW FILE)
// Global language state — wraps the entire app
// ═══════════════════════════════════════════════════════════════════════════════

import { createContext, useContext, useState, useCallback, useEffect } from "react";
import { UI_STRINGS, getLanguage } from "../Components/LanguageSelector";

const LanguageContext = createContext(null);

export function LanguageProvider({ children }) {
  const [lang, setLang] = useState(() => {
    // Persist language preference in localStorage
    return localStorage.getItem("prism_language") || "en";
  });

  const changeLang = useCallback((code) => {
    setLang(code);
    localStorage.setItem("prism_language", code);
    // Update document dir for RTL support (future)
    document.documentElement.lang = code;
  }, []);

  const t = UI_STRINGS[lang] || UI_STRINGS.en;
  const langConfig = getLanguage(lang);

  return (
    <LanguageContext.Provider value={{ lang, changeLang, t, langConfig }}>
      {children}
    </LanguageContext.Provider>
  );
}

export function useLanguage() {
  const ctx = useContext(LanguageContext);
  if (!ctx) throw new Error("useLanguage must be used inside LanguageProvider");
  return ctx;
}

export default LanguageContext;


// ═══════════════════════════════════════════════════════════════════════════════
// FILE B: Update frontend/src/main.jsx or App.jsx
// Wrap the app with LanguageProvider
// ═══════════════════════════════════════════════════════════════════════════════

/*
// In main.jsx or App.jsx — wrap everything with LanguageProvider:

import { LanguageProvider } from "./context/LanguageContext";

root.render(
  <LanguageProvider>
    <App />
  </LanguageProvider>
);
*/


// ═══════════════════════════════════════════════════════════════════════════════
// FILE C: CHANGES TO frontend/src/pages/PatientApp.jsx
// ═══════════════════════════════════════════════════════════════════════════════

// ─── STEP 1: Add imports ───────────────────────────────────────────────────────

/*
import LanguageSelector, { LANGUAGES } from "../Components/LanguageSelector";
import { useLanguage } from "../context/LanguageContext";
*/

// ─── STEP 2: Use language context in PatientApp ────────────────────────────────
/*
export default function PatientApp({ user, onLogout, onSubscribe }) {
  const { lang, changeLang, t, langConfig } = useLanguage();

  // Pass lang to sendMessage, apiFetch, etc.
  // ...
*/

// ─── STEP 3: Update apiFetch / sendMessage to include language ─────────────────
/*
const sendMessage = async (txt) => {
  const msg = txt || input.trim();
  // ...
  const data = await apiFetch("/chat", {
    method: "POST",
    body: JSON.stringify({
      agent_id:        selAgent.id,
      message:         msg,
      language:        lang,           // ← send current language
      conversation_id: convId || undefined,
    }),
  });
  // ...
};
*/

// ─── STEP 4: Add LanguageSelector to the AgentHeaderBar ───────────────────────
/*
// In AgentHeaderBar or PatientApp NavBar, add:
<LanguageSelector
  value={lang}
  onChange={changeLang}
  compact={false}
/>
*/

// ─── STEP 5: Update InputBar placeholder to use localised strings ──────────────
/*
<input
  placeholder={t.placeholder}   // ← localised placeholder
  ...
/>
<button>{t.send}</button>         // ← localised Send button
*/

// ─── STEP 6: Show transliteration banner when non-Latin language is active ────
function TransliterationBanner({ lang, langConfig }) {
  const NON_LATIN = ["hi", "te", "pa"];
  if (!NON_LATIN.includes(lang)) return null;

  const EXAMPLES = {
    hi: { roman: "mujhe seene mein dard hai", native: "मुझे सीने में दर्द है" },
    te: { roman: "naku chest lo noppi undi", native: "నాకు చెస్ట్ లో నొప్పి ఉంది" },
    pa: { roman: "mera seena dard kar raha hai", native: "ਮੇਰਾ ਸੀਨਾ ਦਰਦ ਕਰ ਰਿਹਾ ਹੈ" },
  };
  const ex = EXAMPLES[lang];

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

// ─── STEP 7: Add language badge to AI message bubbles ────────────────────────
function LangBadge({ lang, isTranslated }) {
  if (!isTranslated || lang === "en") return null;
  const cfg = LANGUAGES.find(l => l.code === lang);
  if (!cfg) return null;
  return (
    <span style={{
      fontSize:     9,
      color:        "#2563EB",
      background:   "#DBEAFE",
      padding:      "1px 5px",
      borderRadius: 4,
      marginLeft:   4,
      fontWeight:   500,
    }}>
      {cfg.flag} {cfg.nativeName}
    </span>
  );
}

// ─── STEP 8: Show native script version of user message if romanised ──────────
function UserMessageBubble({ message, lang }) {
  const hasNative = message.nativeInput && message.nativeInput !== message.content;
  return (
    <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 12, gap: 8 }}>
      <div style={{
        maxWidth:     "68%",
        background:   "#F1F5F9",
        border:       "1px solid #E2E8F0",
        borderRadius: "12px 12px 2px 12px",
        padding:      "9px 13px",
        fontSize:     13,
        lineHeight:   1.6,
      }}>
        {/* Show native script if input was romanised */}
        {hasNative ? (
          <>
            <div style={{ fontSize: 13, color: "#0F172A", marginBottom: 3 }}>
              {message.nativeInput}
            </div>
            <div style={{
              fontSize:   10,
              color:      "#94A3B8",
              fontStyle:  "italic",
              borderTop:  "1px solid #E2E8F0",
              paddingTop: 3,
              marginTop:  2,
            }}>
              Typed: "{message.content}"
            </div>
          </>
        ) : (
          message.content
        )}
      </div>
      <div style={{
        width: 26, height: 26, borderRadius: "50%", background: "#E2E8F0",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 10, color: "#64748B", fontWeight: 600, flexShrink: 0, marginTop: 2,
      }}>
        You
      </div>
    </div>
  );
}

// ─── STEP 9: Update ConversationalMessage to show language badge ───────────────
// Add to the AI message bubble, after the tier badge:
/*
<LangBadge lang={message.responseLanguage || lang} isTranslated={message.responseLanguage !== "en"} />
*/

// ─── STEP 10: Updated sendMessage return handling ─────────────────────────────
/*
// In sendMessage(), handle the new multilingual fields:
setMessages(m => [...m, {
  role:             "user",
  content:          msg,
  nativeInput:      data.native_input,    // ← native script version
  id:               Date.now(),
}]);

setMessages(m => [...m, {
  role:             "assistant",
  content:          data.response,         // ← already translated by backend
  responseLanguage: data.selected_language,
  id:               Date.now() + 1,
  // ... other existing fields
}]);
*/


// ═══════════════════════════════════════════════════════════════════════════════
// COMPLETE INTEGRATION SUMMARY
// ═══════════════════════════════════════════════════════════════════════════════

/*
FINAL LAYOUT of PatientApp (all capabilities integrated):

┌─────────────────────────────────────────────────────────────────┐
│  Disease Sidebar                                                │
│  ├── Cancer Care                                                │
│  │   ├── CA1 Screening                                         │
│  │   └── CA2 Treatment                                         │
│  └── Diabetes...                                                │
├─────────────────────────────────────────────────────────────────┤
│  Escalation Monitor  │  CHAT AREA                              │
│  [Frustration bar]   │                                         │
│  [Confidence bar]    │  Agent Header: DM2 | 🇮🇳 हिंदी ▼ | Conf │
│  [Trigger log]       │  ─────────────────────────────────────  │
│  [Sub-agent status]  │  Transliteration banner (Hindi active)  │
│                      │  ─────────────────────────────────────  │
│                      │  [User: "mujhe sugar ki dawai batao"]   │
│                      │  → shown as: [मुझे शुगर की दवाई बताओ]  │
│                      │                                         │
│                      │  [AI: Question 1 of 5 - native]        │
│                      │                                         │
│                      │  [AI: Full Hindi response with ⭐ stars]│
│                      │  [🇮🇳 हिंदी badge on response]          │
│                      │                                         │
│                      │  ConversationProgress bar (Hindi)      │
│                      │  ─────────────────────────────────────  │
│                      │  [🔬] [🎙️] [____input____] [भेजें]     │
│                      │                                         │
│                      │  ⚕ पेशेवर सलाह का विकल्प नहीं है।      │
└─────────────────────────────────────────────────────────────────┘
*/