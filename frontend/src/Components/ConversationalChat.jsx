// ═══════════════════════════════════════════════════════════════════════════════
// FILE: frontend/src/components/ConversationalChat.jsx   (FULL REPLACEMENT)
// Fixes: chip dark-mode colour, citation tab, dynamic chip count
// ═══════════════════════════════════════════════════════════════════════════════

import { useState } from "react";
import { Brain, ExternalLink } from "lucide-react";
import StarRating from "./StarRating";

// ─── Format badge config ───────────────────────────────────────────────────────
const FORMAT_BADGE = {
  progressive: { icon: "▸",  label: "In depth",    color: "#2563EB", bg: "#DBEAFE" },
  narrative:   { icon: "✦",  label: "Story",        color: "#7C3AED", bg: "#EDE9FE" },
  quick_tips:  { icon: "✓",  label: "Quick tips",   color: "#059669", bg: "#D1FAE5" },
  real_talk:   { icon: "◉",  label: "Direct",       color: "#DC2626", bg: "#FEE2E2" },
  comparison:  { icon: "⇄",  label: "Compare",      color: "#D97706", bg: "#FEF3C7" },
  staged:      { icon: "↓",  label: "Step by step", color: "#0891B2", bg: "#CFFAFE" },
  myth_bust:   { icon: "✗→✓","label": "Myth busted", color: "#9333EA", bg: "#F3E8FF" },
  bridge:      { icon: "⤷",  label: "Building on",  color: "#475569", bg: "#F1F5F9" },
};

// ─── Evidence grade colours ───────────────────────────────────────────────────
const GRADE_COLORS = {
  A: { bg: "#D1FAE5", color: "#065F46", label: "Grade A — Strong evidence" },
  B: { bg: "#FEF3C7", color: "#92400E", label: "Grade B — Moderate evidence" },
  C: { bg: "#FEE2E2", color: "#991B1B", label: "Grade C — Limited evidence" },
};

// ─── Citation parser — extracts inline citations and evidence grades ──────────
function parseCitations(text, citationsArray) {
  const found = [];

  // Extract evidence grade references from text
  const gradeMatches = [...text.matchAll(/Evidence Grade[:\s]+([ABC])/gi)];
  gradeMatches.forEach(m => {
    const grade = m[1].toUpperCase();
    if (!found.some(f => f.grade === grade && !f.source)) {
      found.push({ grade, source: null, text: `Evidence Grade ${grade}` });
    }
  });

  // Add provided citations
  if (Array.isArray(citationsArray)) {
    citationsArray.forEach((c, i) => {
      found.push({
        index:  i + 1,
        source: c.source || c.title || `Source ${i + 1}`,
        year:   c.year || "",
        grade:  c.evidence_grade || null,
        type:   c.type || "Clinical guideline",
        text:   c.source || c.title || "",
      });
    });
  }

  // Try to parse numbered references from response text
  const refMatches = [...text.matchAll(/\[(\d+)\]/g)];
  const refNumbers = [...new Set(refMatches.map(m => parseInt(m[1])))];
  refNumbers.forEach(n => {
    if (!found.some(f => f.index === n)) {
      found.push({ index: n, source: `Reference ${n}`, grade: null });
    }
  });

  return found;
}

// ─── Markdown renderer ────────────────────────────────────────────────────────
function MD({ text }) {
  const lines = (text || "").split("\n");
  return (
    <div style={{ lineHeight: 1.7, fontSize: 13, color: "inherit" }}>
      {lines.map((line, i) => {
        const b = line
          .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
          .replace(/\*(.+?)\*/g, "<em>$1</em>");
        if (line.startsWith("### "))
          return <div key={i} style={{ fontWeight: 600, fontSize: 13, marginTop: 10, marginBottom: 3 }}>{line.slice(4)}</div>;
        if (line.startsWith("**") && line.endsWith("**") && line.length > 4)
          return <div key={i} style={{ fontWeight: 600, marginTop: 6, marginBottom: 2 }}>{line.slice(2, -2)}</div>;
        if (line.startsWith("✓ "))
          return (
            <div key={i} style={{ display: "flex", gap: 8, marginBottom: 5, alignItems: "flex-start" }}>
              <span style={{ color: "#059669", fontWeight: 700, flexShrink: 0, marginTop: 2 }}>✓</span>
              <span dangerouslySetInnerHTML={{ __html: b.replace(/^✓\s*/, "") }} />
            </div>
          );
        if (line.startsWith("- ") || line.startsWith("• "))
          return (
            <div key={i} style={{ display: "flex", gap: 7, paddingLeft: 8, marginBottom: 3, alignItems: "flex-start" }}>
              <span style={{ color: "var(--color-text-tertiary)", flexShrink: 0, marginTop: 4, fontSize: 7 }}>●</span>
              <span dangerouslySetInnerHTML={{ __html: b.slice(2) }} />
            </div>
          );
        if (line.trim() === "") return <div key={i} style={{ height: 5 }} />;
        return <div key={i} dangerouslySetInnerHTML={{ __html: b }} style={{ marginBottom: 2 }} />;
      })}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// CITATION TAB — collapsible, shown on every AI message
// ═══════════════════════════════════════════════════════════════════════════════
function CitationTab({ responseText, citations, diseaseColor }) {
  const [open, setOpen] = useState(false);
  const items           = parseCitations(responseText, citations);

  if (items.length === 0) return null;

  // Group grades mentioned
  const grades = [...new Set(items.map(i => i.grade).filter(Boolean))];

  return (
    <div style={{
      borderTop:    "0.5px solid var(--color-border-tertiary)",
      marginTop:    8,
      paddingTop:   6,
    }}>
      <button
        onClick={() => setOpen(!open)}
        aria-expanded={open}
        style={{
          display:      "flex",
          alignItems:   "center",
          gap:          8,
          background:   "var(--color-background-secondary)",
          border:       `1px solid ${diseaseColor || "var(--color-border-tertiary)"}44`,
          padding:      "8px 16px",
          borderRadius: 10,
          cursor:       "pointer",
          fontSize:     13,
          color:        "var(--color-text-primary)",
          fontFamily:   "inherit",
          width:        "fit-content",
          textAlign:    "left",
          marginTop:    8,
          transition:   "all .2s cubic-bezier(0.4, 0, 0.2, 1)",
          boxShadow:    "0 2px 4px rgba(0,0,0,0.08)",
        }}
        onMouseEnter={e => {
          e.currentTarget.style.borderColor = diseaseColor || "var(--color-text-secondary)";
          e.currentTarget.style.transform = "translateY(-1px)";
          e.currentTarget.style.boxShadow = "0 4px 8px rgba(0,0,0,0.12)";
        }}
        onMouseLeave={e => {
          e.currentTarget.style.borderColor = `${diseaseColor || "var(--color-border-tertiary)"}44`;
          e.currentTarget.style.transform = "translateY(0)";
          e.currentTarget.style.boxShadow = "0 2px 4px rgba(0,0,0,0.08)";
        }}
      >
        <span style={{ fontSize: 14 }}>📚</span>
        <span style={{ fontWeight: 600 }}>Sources &amp; Evidence</span>

        {/* Grade pills (always visible) */}
        <div style={{ display: "flex", gap: 4 }}>
          {grades.map(g => {
            const gc = GRADE_COLORS[g] || GRADE_COLORS.B;
            return (
              <span key={g} style={{
                fontSize:     10,
                fontWeight:   700,
                color:        gc.color,
                background:   gc.bg,
                padding:      "1px 7px",
                borderRadius: 4,
                boxShadow:    "0 1px 2px rgba(0,0,0,0.05)",
              }}>
                {g}
              </span>
            );
          })}
        </div>

        <span style={{ marginLeft: 8, fontSize: 11, color: "var(--color-text-tertiary)", fontWeight: 500 }}>
          {items.length} {open ? "▲" : "▼"}
        </span>
      </button>

      {open && (
        <div style={{
          marginTop:  6,
          display:    "flex",
          flexDirection: "column",
          gap:        6,
          animation:  "slideDown .15s ease",
        }}>
          {/* Evidence Grade explanation */}
          {grades.length > 0 && (
            <div style={{
              display:      "flex",
              gap:          6,
              flexWrap:     "wrap",
              marginBottom: 4,
            }}>
              {grades.map(g => {
                const gc = GRADE_COLORS[g];
                if (!gc) return null;
                return (
                  <div key={g} style={{
                    padding:      "4px 10px",
                    background:   gc.bg,
                    borderRadius: 6,
                    fontSize:     11,
                    color:        gc.color,
                    fontWeight:   500,
                  }}>
                    Grade {g} — {gc.label}
                  </div>
                );
              })}
            </div>
          )}

          {/* Citation list */}
          {items.filter(i => i.source).map((item, idx) => (
            <div key={idx} style={{
              display:      "flex",
              gap:          8,
              alignItems:   "flex-start",
              padding:      "6px 8px",
              background:   "var(--color-background-secondary)",
              borderRadius: 6,
              fontSize:     11,
              lineHeight:   1.5,
            }}>
              {item.index && (
                <span style={{
                  color:        "var(--color-text-info)",
                  fontWeight:   600,
                  flexShrink:   0,
                  minWidth:     16,
                }}>
                  [{item.index}]
                </span>
              )}
              <div style={{ flex: 1 }}>
                <span style={{ color: "var(--color-text-primary)" }}>{item.source}</span>
                {item.year && (
                  <span style={{ color: "var(--color-text-tertiary)", marginLeft: 4 }}>({item.year})</span>
                )}
                {item.grade && (
                  <span style={{
                    marginLeft:   6,
                    fontSize:     9,
                    fontWeight:   600,
                    color:        (GRADE_COLORS[item.grade] || GRADE_COLORS.B).color,
                    background:   (GRADE_COLORS[item.grade] || GRADE_COLORS.B).bg,
                    padding:      "1px 5px",
                    borderRadius: 3,
                  }}>
                    Grade {item.grade}
                  </span>
                )}
              </div>
            </div>
          ))}

          <div style={{ fontSize: 10, color: "var(--color-text-tertiary)", marginTop: 2 }}>
            This AI analysis is for educational reference only. Consult your physician before making health decisions.
          </div>
        </div>
      )}

      <style>{`@keyframes slideDown { from { opacity:0;transform:translateY(-4px) } to { opacity:1;transform:translateY(0) } }`}</style>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// FOLLOW-UP CHIPS — fixed colours for light AND dark mode
// ═══════════════════════════════════════════════════════════════════════════════
export function SupportPanel({ questions, genericSupport, onSelect, diseaseColor, disabled, intent, followUpPrompt }) {
  if ((!questions || questions.length === 0) && (!genericSupport || genericSupport.length === 0)) return null;
  const color = diseaseColor || "#2563EB";

  // Normalize questions to dicts if they are strings
  const normalizedQs = questions ? questions.map(q => 
    typeof q === "string" ? { text: q, elaboration: "" } : q
  ) : [];

  const normalizedGs = genericSupport ? genericSupport.map(g => 
    typeof g === "string" ? { text: g, elaboration: "" } : g
  ) : [];

  const getIntentHeading = (it) => {
    if (!it) return "Would you like to explore these areas further?";
    const mapping = {
      CV_SYMPTOM_ASSESSMENT: "Based on your heart symptoms, would you like to ask about...",
      CV_RISK_ASSESSMENT: "To understand your cardiac risk better, would you like to explore...",
      MH_DEPRESSION_ASSESSMENT: "Regarding your mood and well-being, would you like to explore...",
      MH_ANXIETY_CONCERN: "To help manage your anxiety, would you like to ask about...",
      RS_ASTHMA_MANAGEMENT: "Would you like to know more about managing your asthma symptoms?",
      RS_BREATHING_DIFFICULTY: "Regarding your breathing concerns, would you like to ask about...",
      GENERAL_HEALTH_QUERY: "Is there anything else I can help you with regarding your health?",
    };
    return mapping[it] || "Based on our conversation, would you like to ask about...";
  };

  return (
    <div style={{
      paddingLeft: 38,
      paddingBottom: 16,
      paddingTop:    8,
      animation:     "slideIn .25s ease .1s both",
    }}>
      <div style={{
        fontWeight:  600,
        fontSize:    13,
        lineHeight:  1.5,
        color: "var(--color-text-secondary)",
        marginBottom: 12,
        display: "flex",
        alignItems: "center",
        gap: 8
      }}>
        <Brain size={14} style={{ color: color }} />
        {followUpPrompt || getIntentHeading(intent)}
      </div>

      <div style={{ display: "flex", gap: 20, flexWrap: "wrap" }}>
        
        {/* Left Column: Specific Questions (NON-CLICKABLE HINTS) */}
        <div style={{ flex: 1, minWidth: 280, display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: color, opacity: 0.8, letterSpacing: "0.05em", marginBottom: 4 }}>
            Specific Follow-ups (Hints)
          </div>
          {normalizedQs.map((q, i) => (
            <div
              key={i}
              style={{
                display:        "flex",
                alignItems:     "center",
                gap:            10,
                padding:        "12px 16px",
                background:     "var(--color-background-secondary)",
                border:         "1px solid var(--color-border-tertiary)",
                borderRadius:   "12px",
                fontSize:       12.5,
                color:          "var(--color-text-primary)",
                lineHeight:     1.4,
                textAlign:      "left",
                cursor:         "default",
                boxShadow:      "0 1px 2px rgba(0,0,0,0.03)",
                width:          "100%",
                opacity:        0.9
              }}
            >
              <span style={{ color: color, fontSize: 10, fontWeight: 700, opacity: 0.7 }}>💡</span>
              <span style={{ fontWeight: 450 }}>{q.text}</span>
            </div>
          ))}
        </div>

        {/* Right Column: Generic Support */}
        <div style={{ flex: 1, minWidth: 280, display: "flex", flexDirection: "column", gap: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 700, textTransform: "uppercase", color: "var(--accent)", opacity: 0.8, letterSpacing: "0.05em", marginBottom: 4 }}>
             Ask PRISM
          </div>
          {normalizedGs.map((g, i) => (
            <div 
              key={i} 
              onClick={() => !disabled && onSelect(g.text)}
              style={{
                display:        "flex",
                flexDirection:  "column",
                gap:            4,
                padding:        "12px 16px",
                background:     "var(--accent-glow)",
                border:         "1px dashed var(--accent)",
                borderRadius:   "12px",
                cursor:         disabled ? "not-allowed" : "pointer",
                transition:     "all 0.2s",
                width:          "100%"
              }}
              onMouseEnter={e => !disabled && (e.currentTarget.style.background = "var(--accent-glow)", e.currentTarget.style.borderStyle = "solid", e.currentTarget.style.transform = "translateY(-2px)")}
              onMouseLeave={e => !disabled && (e.currentTarget.style.background = "var(--accent-glow)", e.currentTarget.style.borderStyle = "dashed", e.currentTarget.style.transform = "translateY(0)")}
            >
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                <span style={{ 
                  fontSize: 12.5, 
                  fontWeight: 600, 
                  color: "var(--accent)", 
                  textDecoration: "underline",
                  textUnderlineOffset: "3px"
                }}>
                  {g.text}
                </span>
                <span style={{ 
                  fontSize: 9, 
                  fontWeight: 800, 
                  background: (GRADE_COLORS[g.grade] || GRADE_COLORS.A).bg, 
                  color: (GRADE_COLORS[g.grade] || GRADE_COLORS.A).color, 
                  padding: "1px 6px", 
                  borderRadius: 4,
                  flexShrink: 0
                }}>
                  Grade {g.grade || 'A'}
                </span>
              </div>
              <div style={{ fontSize: 10, color: "var(--color-text-tertiary)", fontStyle: "italic", display: "flex", alignItems: "center", gap: 4 }}>
                <ExternalLink size={10} /> {g.elaboration || "Evidence-based Reference"}
              </div>
            </div>
          ))}
        </div>

      </div>
    </div>
  );
}

// Keep FollowUpChips for backward compatibility or simple use cases
export function FollowUpChips(props) {
  return <SupportPanel {...props} />;
}

// ═══════════════════════════════════════════════════════════════════════════════
// CONVERSATION PROGRESS BAR
// ═══════════════════════════════════════════════════════════════════════════════
export function ConversationProgress({
  questionNumber, maxQuestions, intent,
  slotsFilledCount, onSkip, diseaseColor = "#2563EB",
}) {
  if (!questionNumber) return null;
  const pct         = Math.round((questionNumber / maxQuestions) * 100);
  const intentLabel = intent
    ? intent.replace(/_/g, " ").toLowerCase().replace(/^[a-z]{2,3} /, "")
    : "Gathering context";

  return (
    <div style={{
      background:   "var(--color-background-secondary)",
      borderTop:    "1px solid var(--color-border-tertiary)",
      padding:      "8px 16px",
      display:      "flex",
      alignItems:   "center",
      gap:          12,
    }}>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
          <span style={{ fontSize: 11, color: "var(--color-text-secondary)", fontWeight: 500 }}>
            🔍 Question {questionNumber}
            <span style={{ marginLeft: 6, color: "var(--color-text-tertiary)", fontStyle: "italic" }}>
              {intentLabel}
            </span>
          </span>
          <span style={{ fontSize: 10, color: "var(--color-text-tertiary)" }}>
            {slotsFilledCount} detail{slotsFilledCount !== 1 ? "s" : ""} collected
          </span>
        </div>
        <div style={{ height: 4, background: "var(--color-border-tertiary)", borderRadius: 2, overflow: "hidden" }}>
          <div style={{ height: "100%", width: `${pct}%`, background: diseaseColor, borderRadius: 2, transition: "width .4s ease" }} />
        </div>
      </div>
      <button
        onClick={onSkip}
        style={{
          padding:    "4px 10px",
          background: "transparent",
          border:     `1px solid ${diseaseColor}55`,
          borderRadius: 6,
          fontSize:   11,
          color:      diseaseColor,
          cursor:     "pointer",
          fontFamily: "inherit",
          fontWeight: 500,
          whiteSpace: "nowrap",
          flexShrink: 0,
        }}
      >
        Skip → Answer now
      </button>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// CONVERSATIONAL MESSAGE — with citation tab on every AI bubble
// ═══════════════════════════════════════════════════════════════════════════════
export function ConversationalMessage({
  message: m,
  disease,
  agentId,
  conversationId,
  onFollowUpSelect,
  followUpDisabled,
}) {
  const isUser      = m.role === "user";
  const isQuestion  = m.isQuestion || false;
  const diseaseColor = disease?.color || "#2563EB";
  const diseaseBg    = disease?.bg    || "#EFF6FF";

  // User message
  if (isUser) {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10, gap: 8, animation: "slideIn .18s ease" }}>
        {m.nativeInput && m.nativeInput !== m.content ? (
          <div style={{ maxWidth: "68%", display: "flex", flexDirection: "column", gap: 3, alignItems: "flex-end" }}>
            <div style={{
              background:   "var(--color-background-secondary)",
              border:       `1px solid ${diseaseColor}33`,
              borderRadius: "12px 12px 2px 12px",
              padding:      "9px 13px",
              fontSize:     13,
              lineHeight:   1.6,
              color:        "var(--color-text-primary)",
            }}>
              {m.nativeInput}
            </div>
            <div style={{ fontSize: 9, color: "var(--color-text-tertiary)", fontStyle: "italic" }}>
              Typed: "{m.content}"
            </div>
          </div>
        ) : (
          <div style={{
            maxWidth:     "68%",
            background:   "var(--color-background-secondary)",
            border:       "1px solid var(--color-border-tertiary)",
            borderRadius: "12px 12px 2px 12px",
            padding:      "9px 13px",
            fontSize:     13,
            lineHeight:   1.6,
            color:        "var(--color-text-primary)",
          }}>
            {m.content}
          </div>
        )}
        <div style={{
          width: 26, height: 26, borderRadius: "50%",
          background:   "var(--color-background-secondary)",
          border:       "1px solid var(--color-border-tertiary)",
          display:      "flex", alignItems: "center", justifyContent: "center",
          fontSize: 10, color: "var(--color-text-secondary)", fontWeight: 600,
          flexShrink: 0, marginTop: 2,
        }}>
          You
        </div>
      </div>
    );
  }

  // Clarifying question bubble
  if (isQuestion) {
    return (
      <div style={{ display: "flex", gap: 9, marginBottom: 10, animation: "slideIn .18s ease" }}>
        <div style={{
          width: 28, height: 28, borderRadius: 8,
          background:   diseaseBg,
          border:       `1.5px solid ${diseaseColor}44`,
          display:      "flex", alignItems: "center", justifyContent: "center",
          fontSize: 14, flexShrink: 0, marginTop: 2,
        }}>
          💬
        </div>
        <div style={{ maxWidth: "78%" }}>
          {m.questionNumber && (
            <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 4 }}>
              <span style={{
                fontSize: 9, fontWeight: 700, color: diseaseColor,
                background: diseaseBg, padding: "1px 7px", borderRadius: 10,
                border: `1px solid ${diseaseColor}33`,
              }}>
                Question {m.questionNumber} of {m.maxQuestions || 5}
              </span>
            </div>
          )}
          <div style={{
            background:   diseaseBg,
            border:       `1px solid ${diseaseColor}33`,
            borderRadius: "2px 12px 12px 12px",
            padding:      "10px 14px",
            fontSize:     13,
            lineHeight:   1.65,
            color:        "#1E293B", // Fixed dark slate color for visibility on light bg
          }}>
            <MD text={m.content} />
          </div>
          <div style={{ fontSize: 10, color: "var(--color-text-tertiary)", marginTop: 3, paddingLeft: 2 }}>
            Answer or type "skip" to get your response
          </div>
        </div>
      </div>
    );
  }

  // Full answer bubble
  const badge    = FORMAT_BADGE[m.responseFormat] || null;
  const tierBadge = m.routeDecision && m.routeDecision !== "primary" ? {
    specialist: { label: "⚡ Specialist", color: "#B45309", bg: "#FEF3C7" },
    human:      { label: "🤝 Coordinator", color: "#B91C1C", bg: "#FEF2F2" },
  }[m.routeDecision] : null;

  return (
    <div style={{ marginBottom: 4, animation: "slideIn .2s ease" }}>
      <div style={{ display: "flex", gap: 9 }}>
        {/* Avatar */}
        <div style={{
          width: 28, height: 28, borderRadius: 8,
          background:   diseaseColor,
          display:      "flex", alignItems: "center", justifyContent: "center",
          fontSize: 10, color: "#FFFFFF", fontWeight: 700, flexShrink: 0, marginTop: 2,
        }}>
          AI
        </div>

        <div style={{ flex: 1, minWidth: 0 }}>
          {/* Badges row */}
          {(badge || tierBadge || m.contextCollected) && (
            <div style={{ display: "flex", gap: 5, marginBottom: 5, flexWrap: "wrap", alignItems: "center" }}>
              {badge && (
                <span style={{
                  fontSize: 9, fontWeight: 600, color: badge.color,
                  background: badge.bg, padding: "1px 7px", borderRadius: 10,
                  border: `1px solid ${badge.color}33`,
                }}>
                  {badge.icon} {badge.label}
                </span>
              )}
              {tierBadge && (
                <span style={{
                  fontSize: 9, fontWeight: 600, color: tierBadge.color,
                  background: tierBadge.bg, padding: "1px 7px", borderRadius: 10,
                }}>
                  {tierBadge.label}
                </span>
              )}
              {m.contextCollected && m.slotsCount > 0 && (
                <span style={{
                  fontSize: 9, color: "#059669", background: "#D1FAE5",
                  padding: "1px 7px", borderRadius: 10, border: "1px solid #6EE7B7",
                }}>
                  ✓ Personalised ({m.slotsCount} details)
                </span>
              )}
            </div>
          )}

          {/* Answer bubble */}
          <div style={{
            background:   "var(--color-background-primary)",
            border:       "0.5px solid var(--color-border-tertiary)",
            borderRadius: "2px 12px 12px 12px",
            padding:      "11px 15px",
            boxShadow:    "0 1px 3px rgba(0,0,0,.04)",
            color:        "var(--color-text-primary)",
          }}>
            <MD text={m.content} />
            
            {/* ── Visual Payload (Image/Video) ── */}
            {(() => {
              const payload = m.visual_payload || {};
              const items = payload.items || (payload.url ? [payload] : []);
              if (items.length === 0) return null;

              return (
                <div style={{ display: "flex", flexDirection: "column", gap: 12, marginTop: 12, marginBottom: 8 }}>
                  {items.map((item, idx) => (
                    <div key={idx} style={{ borderRadius: 12, overflow: "hidden", border: "1px solid var(--color-border-tertiary)" }}>
                      {item.type === "video" ? (
                        <video 
                          src={item.url} 
                          controls 
                          style={{ width: "100%", display: "block" }} 
                          poster="/video-placeholder.png"
                        />
                      ) : (
                        <img 
                          src={item.url} 
                          alt={item.label || "Medical illustration"} 
                          style={{ width: "100%", display: "block" }} 
                        />
                      )}
                      <div style={{ padding: "6px 12px", background: "var(--color-background-secondary)", fontSize: 11, color: "var(--color-text-secondary)", display: "flex", justifyContent: "space-between" }}>
                        <span>{item.label || "Medical Visual"}</span>
                        {item.duration_s && <span>{item.duration_s}s</span>}
                      </div>
                    </div>
                  ))}
                </div>
              );
            })()}

            {/* ── Citation Tab (always present on AI answers) ── */}
            <CitationTab
              responseText={m.content}
              citations={m.citations || []}
              diseaseColor={diseaseColor}
            />
          </div>

          {/* Confidence meta */}

          {/* Star rating */}
          {m.id && conversationId && !m.isRestored && (
            <div style={{ marginTop: 3 }}>
              <StarRating
                messageId={m.id}
                agentId={agentId}
                conversationId={conversationId}
                diseaseCode={disease?.code}
                diseaseColor={diseaseColor}
              />
            </div>
          )}
        </div>
      </div>

      {/* Support panel with specific vs generic options */}
      {(m.followUpQuestions?.length > 0 || m.genericSupport?.length > 0) && (
        <SupportPanel
          questions={m.followUpQuestions}
          genericSupport={m.genericSupport}
          onSelect={onFollowUpSelect}
          diseaseColor={diseaseColor}
          disabled={followUpDisabled}
          intent={m.intent}
          followUpPrompt={m.follow_up_prompt}
        />
      )}
    </div>
  );
}

// ─── Typing indicator ──────────────────────────────────────────────────────────
export function TypingIndicator({ isQuestion, diseaseColor = "#2563EB" }) {
  return (
    <div style={{ display: "flex", gap: 9, marginBottom: 8, alignItems: "center" }}>
      <div style={{
        width: 28, height: 28, borderRadius: 8,
        background:   isQuestion ? "var(--color-background-secondary)" : diseaseColor,
        border:       isQuestion ? "1px solid var(--color-border-tertiary)" : "none",
        display:      "flex", alignItems: "center", justifyContent: "center",
        fontSize:     isQuestion ? 14 : 10,
        color:        "#FFFFFF",
        fontWeight:   700,
        flexShrink:   0,
      }}>
        {isQuestion ? "💬" : "AI"}
      </div>
      <div style={{
        background:   "var(--color-background-secondary)",
        border:       "0.5px solid var(--color-border-tertiary)",
        borderRadius: "2px 12px 12px 12px",
        padding:      "10px 14px",
        display:      "flex",
        gap:          5,
        alignItems:   "center",
      }}>
        {isQuestion && (
          <span style={{ fontSize: 11, color: "var(--color-text-secondary)", marginRight: 4 }}>
            Preparing follow-up…
          </span>
        )}
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 7, height: 7, borderRadius: "50%",
            background:   isQuestion ? "var(--color-text-tertiary)" : diseaseColor,
            animation:    `typingDot .9s ease ${i * 0.18}s infinite`,
          }} />
        ))}
      </div>
      <style>{`
        @keyframes typingDot { 0%,80%,100%{opacity:.25;transform:translateY(0)} 40%{opacity:1;transform:translateY(-4px)} }
        @keyframes slideIn { from{opacity:0;transform:translateY(6px)} to{opacity:1;transform:translateY(0)} }
      `}</style>
    </div>
  );
}