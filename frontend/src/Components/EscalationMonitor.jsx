// ═══════════════════════════════════════════════════════════════════════════════
// FILE: frontend/src/components/EscalationMonitor.jsx
// PRISM Escalation Monitor — left panel displayed in PatientApp during chat
// Matches the UI design from the reference screenshot exactly.
// ═══════════════════════════════════════════════════════════════════════════════

import { useState, useEffect, useRef } from "react";

// ─── Trigger code → human readable label ──────────────────────────────────────
const TRIGGER_LABELS = {
  KEYWORD:       "Frustration keywords detected",
  HUMAN_REQUEST: "Explicit request for real doctor",
  REPEATED:      "Repeated concern — same issue stated twice",
  UNCERTAIN:     "Agent uncertain — needs more info",
  EMERGENCY:     "Emergency symptom detected",
};

// ─── Route decision → display label ───────────────────────────────────────────
const ROUTE_LABELS = {
  primary:    { label: "Primary Agent",         color: "#1A7A4A", bg: "#E6F5EE" },
  specialist: { label: "Specialist Agent Active", color: "#B45309", bg: "#FEF3C7" },
  human:      { label: "Escalation Active",       color: "#B91C1C", bg: "#FEF2F2" },
};

// ─── Frustration score → colour band ──────────────────────────────────────────
function getFrustrationColor(score) {
  if (score >= 75) return "#B91C1C";   // Red — human escalation
  if (score >= 50) return "#D97706";   // Amber — specialist
  if (score >= 25) return "#F59E0B";   // Yellow — watch
  return "#1A7A4A";                    // Green — healthy
}

function getFrustrationBg(score) {
  if (score >= 75) return "linear-gradient(90deg, #B91C1C, #DC2626)";
  if (score >= 50) return "linear-gradient(90deg, #D97706, #F59E0B)";
  return "linear-gradient(90deg, #1A7A4A, #22C55E)";
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export default function EscalationMonitor({
  agentId,
  agentName,
  diseaseCode,
  escalationData,       // Latest from API response
  routeDecision,        // "primary" | "specialist" | "human"
  specialistAgent,      // { name, activated }
  humanAgent,           // { name, role, contact, activated }
  confidence,           // 0.0 – 1.0
}) {
  const [triggerLog, setTriggerLog] = useState([]);
  const [score, setScore]           = useState(0);
  const [animScore, setAnimScore]   = useState(0);
  const prevScore = useRef(0);

  // ── Update trigger log when new escalation data arrives ──────────────────────
  useEffect(() => {
    if (!escalationData) return;

    const newScore = escalationData.frustration_score || 0;
    setScore(newScore);

    // Add new triggers to the log (deduplicated)
    if (escalationData.triggers?.length) {
      setTriggerLog(prev => {
        const existingLabels = new Set(prev.map(t => t.label));
        const newItems = escalationData.triggers
          .filter(t => !existingLabels.has(t))
          .map(t => ({
            id:        Date.now() + Math.random(),
            label:     t,
            timestamp: new Date().toLocaleTimeString(),
            severity:  escalationData.active ? "high" : "medium",
          }));
        return [...prev, ...newItems].slice(-8); // Keep last 8 entries
      });
    }

    // If emergency is detected, add it
    if (escalationData.trigger_codes?.includes("EMERGENCY")) {
      setTriggerLog(prev => {
        const hasEmergency = prev.some(t => t.label.includes("Emergency"));
        if (hasEmergency) return prev;
        return [...prev, {
          id:        Date.now(),
          label:     "Emergency symptom detected",
          timestamp: new Date().toLocaleTimeString(),
          severity:  "emergency",
        }].slice(-8);
      });
    }
  }, [escalationData]);

  // ── Animate score bar ─────────────────────────────────────────────────────────
  useEffect(() => {
    const start   = prevScore.current;
    const end     = score;
    const steps   = 20;
    const step    = (end - start) / steps;
    let   current = start;
    let   count   = 0;
    const interval = setInterval(() => {
      current += step;
      count++;
      setAnimScore(Math.round(current));
      if (count >= steps) {
        clearInterval(interval);
        setAnimScore(end);
        prevScore.current = end;
      }
    }, 20);
    return () => clearInterval(interval);
  }, [score]);

  const isActive  = routeDecision === "specialist" || routeDecision === "human";
  const routeInfo = ROUTE_LABELS[routeDecision] || ROUTE_LABELS.primary;
  const frustColor = getFrustrationColor(score);

  return (
    <div style={{
      width: 220,
      background: "#0D1B2E",
      borderRight: "1px solid #1E3254",
      display: "flex",
      flexDirection: "column",
      flexShrink: 0,
      fontFamily: "system-ui, -apple-system, sans-serif",
      overflow: "hidden",
    }}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <div style={{
        background: "#0A1628",
        borderBottom: "1px solid #1E3254",
        padding: "10px 12px",
      }}>
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          marginBottom: 4,
        }}>
          {/* Pulse dot — animates when escalation is active */}
          <div style={{
            width: 8,
            height: 8,
            borderRadius: "50%",
            background: isActive ? "#EF4444" : "#22C55E",
            boxShadow: isActive ? "0 0 6px #EF4444" : "0 0 4px #22C55E",
            animation: isActive ? "pulse 1.2s ease infinite" : "none",
          }} />
          <span style={{
            color: "#FFFFFF",
            fontWeight: 700,
            fontSize: 11,
            letterSpacing: "0.05em",
          }}>
            ESCALATION MONITOR
          </span>
        </div>
        <div style={{ color: "#6B8CAE", fontSize: 10, lineHeight: 1.3 }}>
          {agentName || agentId}
        </div>
        {diseaseCode && (
          <div style={{ color: "#4B7CBE", fontSize: 9, marginTop: 2 }}>
            {diseaseCode} (COFEPRIS)
          </div>
        )}
      </div>

      {/* ── Route Status Badge ────────────────────────────────────────────── */}
      {isActive && (
        <div style={{
          margin: "8px 10px 0",
          padding: "5px 8px",
          background: routeInfo.bg,
          borderRadius: 6,
          display: "flex",
          alignItems: "center",
          gap: 6,
        }}>
          <span style={{ fontSize: 12 }}>
            {routeDecision === "human" ? "🆘" : "⚡"}
          </span>
          <span style={{
            color: routeInfo.color,
            fontSize: 10,
            fontWeight: 700,
          }}>
            {routeInfo.label}
          </span>
        </div>
      )}

      {/* ── Frustration Score ─────────────────────────────────────────────── */}
      <div style={{ padding: "12px 12px 8px" }}>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 6,
        }}>
          <span style={{
            color: "#9BAFC7",
            fontSize: 10,
            fontWeight: 600,
            letterSpacing: "0.04em",
          }}>
            Frustration score
          </span>
          <span style={{
            color: frustColor,
            fontSize: 12,
            fontWeight: 700,
          }}>
            {animScore} / 100
          </span>
        </div>

        {/* Score bar */}
        <div style={{
          height: 6,
          background: "#1E3254",
          borderRadius: 3,
          overflow: "hidden",
        }}>
          <div style={{
            height: "100%",
            width: `${animScore}%`,
            background: getFrustrationBg(animScore),
            borderRadius: 3,
            transition: "width 0.3s ease",
          }} />
        </div>

        {/* Threshold markers */}
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          marginTop: 3,
        }}>
          <span style={{ fontSize: 8, color: "#3D5C82" }}>0</span>
          <span style={{ fontSize: 8, color: "#D97706" }}>75 → Human</span>
          <span style={{ fontSize: 8, color: "#3D5C82" }}>100</span>
        </div>
      </div>

      {/* ── Confidence Score ──────────────────────────────────────────────── */}
      <div style={{ padding: "0 12px 10px" }}>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 5,
        }}>
          <span style={{ color: "#9BAFC7", fontSize: 10, fontWeight: 600 }}>
            Confidence score
          </span>
          <span style={{
            color: confidence >= 0.7 ? "#22C55E" : confidence >= 0.5 ? "#F59E0B" : "#EF4444",
            fontSize: 12,
            fontWeight: 700,
          }}>
            {confidence ? `${Math.round(confidence * 100)}%` : "—"}
          </span>
        </div>
        <div style={{ height: 4, background: "#1E3254", borderRadius: 2, overflow: "hidden" }}>
          <div style={{
            height: "100%",
            width: confidence ? `${confidence * 100}%` : "0%",
            background: confidence >= 0.7
              ? "linear-gradient(90deg, #1A7A4A, #22C55E)"
              : confidence >= 0.5
                ? "linear-gradient(90deg, #D97706, #F59E0B)"
                : "linear-gradient(90deg, #B91C1C, #EF4444)",
            borderRadius: 2,
            transition: "width 0.3s ease",
          }} />
        </div>
        <div style={{ display: "flex", justifyContent: "flex-end", marginTop: 2 }}>
          <span style={{ fontSize: 8, color: "#B45309" }}>70% → Specialist</span>
        </div>
      </div>

      {/* ── Active Sub-Agent Status ───────────────────────────────────────── */}
      <div style={{ padding: "0 10px 8px" }}>
        {/* Specialist Agent */}
        <SubAgentRow
          label="Specialist Agent"
          name={specialistAgent?.name || `${agentId}-S`}
          activated={routeDecision === "specialist"}
          activeColor="#B45309"
          activeBg="#FEF3C7"
          icon="⚡"
          trigger="Conf < 70%"
        />
        {/* Human Escalation Agent */}
        <SubAgentRow
          label="Human Coordinator"
          name={humanAgent?.name || `${agentId}-H`}
          activated={routeDecision === "human"}
          activeColor="#B91C1C"
          activeBg="#FEF2F2"
          icon="🆘"
          trigger="Frust > 75"
        />
      </div>

      {/* Divider */}
      <div style={{ height: 1, background: "#1E3254", margin: "0 10px" }} />

      {/* ── Trigger Log ───────────────────────────────────────────────────── */}
      <div style={{ flex: 1, overflowY: "auto", padding: "10px 12px" }}>
        <div style={{
          color: "#4B7CBE",
          fontSize: 9,
          fontWeight: 700,
          letterSpacing: "0.08em",
          textTransform: "uppercase",
          marginBottom: 8,
        }}>
          TRIGGER LOG
        </div>

        {triggerLog.length === 0 ? (
          <div style={{
            color: "#3D5C82",
            fontSize: 10,
            fontStyle: "italic",
            textAlign: "center",
            marginTop: 20,
          }}>
            No triggers yet
          </div>
        ) : (
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {triggerLog.map(t => (
              <TriggerRow key={t.id} trigger={t} />
            ))}
          </div>
        )}
      </div>

      {/* ── Human Contact Card (only shown when human escalation active) ──── */}
      {routeDecision === "human" && humanAgent && (
        <HumanContactCard humanAgent={humanAgent} />
      )}

      {/* CSS animation keyframe */}
      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; transform: scale(1); }
          50%       { opacity: 0.6; transform: scale(0.85); }
        }
      `}</style>
    </div>
  );
}

// ─── Sub-Agent Status Row ──────────────────────────────────────────────────────
function SubAgentRow({ label, name, activated, activeColor, activeBg, icon, trigger }) {
  return (
    <div style={{
      padding: "6px 8px",
      borderRadius: 6,
      marginBottom: 4,
      background: activated ? activeBg : "#0F1E33",
      border: `1px solid ${activated ? activeColor + "40" : "#1E3254"}`,
      transition: "all 0.3s ease",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 2 }}>
        <span style={{ fontSize: 10 }}>{icon}</span>
        <span style={{
          fontSize: 9,
          fontWeight: 600,
          color: activated ? activeColor : "#4B7CBE",
          letterSpacing: "0.04em",
          textTransform: "uppercase",
        }}>
          {label}
        </span>
        {activated && (
          <span style={{
            marginLeft: "auto",
            fontSize: 8,
            fontWeight: 700,
            color: activeColor,
            background: activeColor + "22",
            padding: "1px 5px",
            borderRadius: 3,
          }}>
            ACTIVE
          </span>
        )}
      </div>
      <div style={{ color: activated ? activeColor : "#3D5C82", fontSize: 9, lineHeight: 1.3 }}>
        {name}
      </div>
      <div style={{ color: "#2D4A6A", fontSize: 8, marginTop: 1 }}>
        Trigger: {trigger}
      </div>
    </div>
  );
}

// ─── Single Trigger Row ────────────────────────────────────────────────────────
function TriggerRow({ trigger }) {
  const severityColors = {
    emergency: "#EF4444",
    high:      "#F97316",
    medium:    "#F59E0B",
    low:       "#6B7280",
  };
  const color = severityColors[trigger.severity] || severityColors.medium;
  const isGrey = trigger.severity === "low";

  return (
    <div style={{ display: "flex", gap: 7, alignItems: "flex-start" }}>
      {/* Dot */}
      <div style={{
        width: 7,
        height: 7,
        borderRadius: "50%",
        background: isGrey ? "#3D5C82" : color,
        flexShrink: 0,
        marginTop: 3,
      }} />
      <span style={{
        color: isGrey ? "#3D5C82" : "#C8D8E8",
        fontSize: 10,
        lineHeight: 1.4,
        flex: 1,
      }}>
        {trigger.label}
      </span>
    </div>
  );
}

// ─── Human Contact Card ────────────────────────────────────────────────────────
function HumanContactCard({ humanAgent }) {
  return (
    <div style={{
      margin: "0 10px 10px",
      background: "#0A1E35",
      border: "1px solid #B91C1C44",
      borderRadius: 8,
      padding: "10px",
    }}>
      <div style={{
        color: "#FFFFFF",
        fontSize: 10,
        fontWeight: 700,
        marginBottom: 4,
        display: "flex",
        alignItems: "center",
        gap: 5,
      }}>
        <span>🤝</span> Connect to Coordinator
      </div>
      <div style={{ color: "#9BAFC7", fontSize: 9, lineHeight: 1.4 }}>
        {humanAgent.name}
      </div>
      <div style={{
        marginTop: 6,
        color: "#6B8CAE",
        fontSize: 9,
        borderTop: "1px solid #1E3254",
        paddingTop: 6,
        lineHeight: 1.5,
      }}>
        {humanAgent.contact}
      </div>
    </div>
  );
}