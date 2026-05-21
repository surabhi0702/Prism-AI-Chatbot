import { useState, useEffect, useCallback, useRef } from "react";
import api from "../services/api";

// ─── Time group labels ─────────────────────────────────────────────────────────
function getTimeGroup(ageDays) {
  if (ageDays === 0) return "Today";
  if (ageDays === 1) return "Yesterday";
  if (ageDays <= 7)  return "This week";
  if (ageDays <= 14) return "Last week";
  return "Older";
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN HISTORY PANEL
// ═══════════════════════════════════════════════════════════════════════════════
export default function ChatHistory({
  isOpen,
  onClose,
  onRestoreConversation,    // (conversationData) → restores into PatientApp
  currentConvId,            // Highlight the active conversation
}) {
  const [view, setView]             = useState("topic");     // "timeline" | "disease" | "agent" | "topic" | "search"
  const [history, setHistory]       = useState(null);
  const [stats, setStats]           = useState(null);
  const [loading, setLoading]       = useState(true);
  const [searchQuery, setSearchQuery]   = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching]   = useState(false);
  const [filterDisease, setFilterDisease] = useState("");
  const [filterAgent, setFilterAgent]     = useState("");
  const [expandedDisease, setExpandedDisease] = useState(null);
  const [expandedAgent, setExpandedAgent]     = useState(null);
  const [expandedTopic, setExpandedTopic]     = useState(null);
  const [deleting, setDeleting]     = useState(null);
  const [confirmClearAll, setConfirmClearAll] = useState(false);
  const searchRef                   = useRef(null);
  const searchTimer                 = useRef(null);

  // ── Load history ─────────────────────────────────────────────────────────────
  const loadHistory = useCallback(async () => {
    setLoading(true);
    try {
      const [hRes, sRes] = await Promise.all([
        api.get("/history"),
        api.get("/history/stats"),
      ]);
      setHistory(hRes.data);
      setStats(sRes.data);
    } catch (e) {
      console.error("History load error:", e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (isOpen) loadHistory(); }, [isOpen, loadHistory]);

  // ── Search with debounce ──────────────────────────────────────────────────────
  const handleSearch = useCallback((q) => {
    setSearchQuery(q);
    clearTimeout(searchTimer.current);
    if (!q.trim() || q.trim().length < 2) { setSearchResults(null); return; }
    setSearching(true);
    searchTimer.current = setTimeout(async () => {
      try {
        const res = await api.get(
          `/history/search?q=${encodeURIComponent(q)}${filterDisease ? `&disease=${filterDisease}` : ""}${filterAgent ? `&agent=${filterAgent}` : ""}`
        );
        setSearchResults(res.data.results);
      } catch { setSearchResults([]); }
      finally { setSearching(false); }
    }, 400);
  }, [filterDisease, filterAgent]);

  // ── Delete conversation ────────────────────────────────────────────────────
  const handleDelete = useCallback(async (convId, e) => {
    e.stopPropagation();
    setDeleting(convId);
    try {
      await api.delete(`/history/${convId}`);
      await loadHistory();
      if (searchResults) handleSearch(searchQuery);
    } catch { } finally { setDeleting(null); }
  }, [loadHistory, searchResults, searchQuery, handleSearch]);

  // ── Clear all history ─────────────────────────────────────────────────────
  const handleClearAll = useCallback(async () => {
    try {
      await api.delete("/history");
      setConfirmClearAll(false);
      await loadHistory();
    } catch { setConfirmClearAll(false); }
  }, [loadHistory]);

  // ── Restore conversation ──────────────────────────────────────────────────
  const handleRestore = useCallback(async (card) => {
    try {
      const res = await api.get(`/history/${card.conversation_id}`);
      if (res.data.found && onRestoreConversation) {
        onRestoreConversation(res.data);
        onClose();
      }
    } catch (e) {
      console.error("Restore error:", e);
    }
  }, [onRestoreConversation, onClose]);

  if (!isOpen) return null;

  const timeline   = history?.timeline || [];
  const byDisease  = history?.by_disease || {};
  const byAgent    = history?.by_agent || {};
  const byTopic    = history?.by_topic || [];

  // ─── Filtered timeline ────────────────────────────────────────────────────
  const filteredTimeline = timeline.filter(c => {
    if (filterDisease && c.disease_code !== filterDisease) return false;
    if (filterAgent   && c.agent_id    !== filterAgent)    return false;
    return true;
  });

  // ─── Group timeline by time ────────────────────────────────────────────────
  const timelineGroups = filteredTimeline.reduce((acc, card) => {
    const group = getTimeGroup(card.age_days);
    if (!acc[group]) acc[group] = [];
    acc[group].push(card);
    return acc;
  }, {});
  const TIME_ORDER = ["Today", "Yesterday", "This week", "Last week", "Older"];

  return (
    <div style={{
      position:    "fixed",
      inset:       0,
      zIndex:      900,
      display:     "flex",
      pointerEvents: "none",
    }}>
      {/* ── Backdrop ─────────────────────────────────────────────────────── */}
      <div
        onClick={onClose}
        style={{
          position:       "absolute",
          inset:          0,
          background:     "rgba(0,0,0,.25)",
          pointerEvents:  "all",
          animation:      "fadeIn .2s ease",
        }}
      />

      {/* ── Drawer ───────────────────────────────────────────────────────── */}
      <div style={{
        position:       "relative",
        width:          340,
        height:         "100%",
        background:     "#FFFFFF",
        boxShadow:      "4px 0 24px rgba(0,0,0,.15)",
        display:        "flex",
        flexDirection:  "column",
        pointerEvents:  "all",
        animation:      "slideRight .22s ease",
        overflowY:      "hidden",
        fontFamily:     "system-ui, -apple-system, sans-serif",
      }}>

        {/* ── Header ────────────────────────────────────────────────────── */}
        <div style={{
          padding:       "14px 16px 10px",
          borderBottom:  "1px solid #F1F5F9",
          background:    "#0D2240",
          flexShrink:    0,
        }}>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span style={{ fontSize: 18 }}>🕐</span>
              <div>
                <div style={{ color: "#FFFFFF", fontWeight: 700, fontSize: 14 }}>
                  Chat History
                </div>
                {stats && (
                  <div style={{ color: "#6B8CAE", fontSize: 10 }}>
                    {stats.conversations} conversations · {stats.messages} messages · last {stats.retention_days} days
                  </div>
                )}
              </div>
            </div>
            <button onClick={onClose} style={{ background: "none", border: "none",
              color: "#6B8CAE", fontSize: 20, cursor: "pointer" }}>×</button>
          </div>

          {/* Search bar */}
          <div style={{ position: "relative" }}>
            <input
              ref={searchRef}
              value={searchQuery}
              onChange={e => handleSearch(e.target.value)}
              placeholder="Search messages…"
              style={{
                width:        "100%",
                padding:      "7px 32px 7px 10px",
                border:       "1px solid #1E3254",
                borderRadius: 8,
                background:   "#0A1628",
                color:        "#FFFFFF",
                fontSize:     12,
                fontFamily:   "inherit",
                outline:      "none",
                boxSizing:    "border-box",
              }}
            />
            <span style={{ position: "absolute", right: 8, top: 8, fontSize: 12, color: "#4B7CBE" }}>
              {searching ? "⟳" : "🔍"}
            </span>
          </div>
        </div>

        {/* ── View tabs ─────────────────────────────────────────────────── */}
        {!searchQuery && (
          <div style={{
            display:       "flex",
            borderBottom:  "1px solid #F1F5F9",
            flexShrink:    0,
          }}>
            {[
              { id: "topic",    icon: "🏷️", label: "Topic" },
              { id: "timeline", icon: "📅", label: "Timeline" },
              { id: "disease",  icon: "🏥", label: "Disease" },
              { id: "agent",    icon: "🤖", label: "Agent" },
            ].map(tab => (
              <button
                key={tab.id}
                onClick={() => setView(tab.id)}
                style={{
                  flex:         1,
                  padding:      "9px 4px",
                  background:   view === tab.id ? "#EFF6FF" : "transparent",
                  border:       "none",
                  borderBottom: view === tab.id ? "2px solid #2563EB" : "2px solid transparent",
                  cursor:       "pointer",
                  fontSize:     11,
                  fontWeight:   view === tab.id ? 600 : 400,
                  color:        view === tab.id ? "#2563EB" : "#64748B",
                  fontFamily:   "inherit",
                  display:      "flex",
                  alignItems:   "center",
                  justifyContent: "center",
                  gap:          4,
                }}
              >
                {tab.icon} {tab.label}
              </button>
            ))}
          </div>
        )}

        {/* ── Filter bar (Disease + Agent) ──────────────────────────────── */}
        {!searchQuery && (filterDisease || filterAgent || timeline.length > 5) && (
          <div style={{
            padding:       "8px 12px",
            borderBottom:  "1px solid #F8FAFC",
            display:       "flex",
            gap:           6,
            flexShrink:    0,
            flexWrap:      "wrap",
          }}>
            <select
              value={filterDisease}
              onChange={e => { setFilterDisease(e.target.value); setFilterAgent(""); }}
              style={{ flex: 1, padding: "4px 6px", border: "1px solid #E2E8F0",
                       borderRadius: 6, fontSize: 11, fontFamily: "inherit",
                       background: "#FFF", cursor: "pointer" }}
            >
              <option value="">All Diseases</option>
              {Object.keys(byDisease).map(dc => (
                <option key={dc} value={dc}>
                  {byDisease[dc].disease_icon} {byDisease[dc].disease_name}
                </option>
              ))}
            </select>
            {filterDisease && (
              <select
                value={filterAgent}
                onChange={e => setFilterAgent(e.target.value)}
                style={{ flex: 1, padding: "4px 6px", border: "1px solid #E2E8F0",
                         borderRadius: 6, fontSize: 11, fontFamily: "inherit",
                         background: "#FFF", cursor: "pointer" }}
              >
                <option value="">All Agents</option>
                {Object.keys(byDisease[filterDisease]?.agents || {}).map(aid => (
                  <option key={aid} value={aid}>
                    {byDisease[filterDisease].agents[aid].agent_icon} {byDisease[filterDisease].agents[aid].agent_name}
                  </option>
                ))}
              </select>
            )}
            {(filterDisease || filterAgent) && (
              <button onClick={() => { setFilterDisease(""); setFilterAgent(""); }}
                style={{ padding: "4px 8px", border: "1px solid #E2E8F0",
                         borderRadius: 6, fontSize: 11, cursor: "pointer",
                         background: "transparent", color: "#64748B", fontFamily: "inherit" }}>
                ✕
              </button>
            )}
          </div>
        )}

        {/* ── Main content ──────────────────────────────────────────────── */}
        <div style={{ flex: 1, overflowY: "auto" }}>
          {loading ? (
            <LoadingState />
          ) : searchQuery ? (
            <SearchResults
              results={searchResults}
              query={searchQuery}
              searching={searching}
              onRestore={handleRestore}
              onDelete={handleDelete}
              deleting={deleting}
              currentConvId={currentConvId}
            />
          ) : view === "timeline" ? (
            <TimelineView
              groups={timelineGroups}
              timeOrder={TIME_ORDER}
              onRestore={handleRestore}
              onDelete={handleDelete}
              deleting={deleting}
              currentConvId={currentConvId}
              empty={filteredTimeline.length === 0}
            />
          ) : view === "topic" ? (
            <TopicView
              byTopic={byTopic}
              expandedTopic={expandedTopic}
              expandedDisease={expandedDisease}
              expandedAgent={expandedAgent}
              onToggleTopic={label => { setExpandedTopic(expandedTopic === label ? null : label); setExpandedDisease(null); setExpandedAgent(null); }}
              onToggleDisease={dc => { setExpandedDisease(expandedDisease === dc ? null : dc); setExpandedAgent(null); }}
              onToggleAgent={aid => setExpandedAgent(expandedAgent === aid ? null : aid)}
              onRestore={handleRestore}
              onDelete={handleDelete}
              deleting={deleting}
              currentConvId={currentConvId}
            />
          ) : view === "disease" ? (
            <DiseaseView
              byDisease={byDisease}
              expandedDisease={expandedDisease}
              expandedAgent={expandedAgent}
              onToggleDisease={dc => { setExpandedDisease(expandedDisease === dc ? null : dc); setExpandedAgent(null); }}
              onToggleAgent={aid => setExpandedAgent(expandedAgent === aid ? null : aid)}
              onRestore={handleRestore}
              onDelete={handleDelete}
              deleting={deleting}
              currentConvId={currentConvId}
            />
          ) : (
            <AgentView
              byAgent={byAgent}
              expandedAgent={expandedAgent}
              onToggleAgent={aid => setExpandedAgent(expandedAgent === aid ? null : aid)}
              onRestore={handleRestore}
              onDelete={handleDelete}
              deleting={deleting}
              currentConvId={currentConvId}
            />
          )}
        </div>

        {/* ── Footer: retention notice + clear all ─────────────────────── */}
        <div style={{
          padding:       "10px 14px",
          borderTop:     "1px solid #F1F5F9",
          background:    "#F8FAFC",
          flexShrink:    0,
        }}>
          <div style={{ fontSize: 10, color: "#94A3B8", marginBottom: 8, textAlign: "center" }}>
            💾 Conversations kept for 15 days · Auto-deleted after expiry
          </div>
          {!confirmClearAll ? (
            <button
              onClick={() => setConfirmClearAll(true)}
              style={{
                width:        "100%",
                padding:      "6px",
                background:   "transparent",
                border:       "1px solid #FCA5A5",
                borderRadius: 6,
                color:        "#EF4444",
                fontSize:     11,
                cursor:       "pointer",
                fontFamily:   "inherit",
              }}
            >
              🗑 Clear all history
            </button>
          ) : (
            <div style={{ display: "flex", gap: 6 }}>
              <button onClick={() => setConfirmClearAll(false)}
                style={{ flex: 1, padding: "6px", background: "transparent",
                         border: "1px solid #E2E8F0", borderRadius: 6,
                         fontSize: 11, cursor: "pointer", fontFamily: "inherit" }}>
                Cancel
              </button>
              <button onClick={handleClearAll}
                style={{ flex: 1, padding: "6px", background: "#EF4444",
                         border: "none", borderRadius: 6, color: "#fff",
                         fontSize: 11, fontWeight: 600, cursor: "pointer", fontFamily: "inherit" }}>
                Yes, clear all
              </button>
            </div>
          )}
        </div>
      </div>
      <style>{`
        @keyframes fadeIn { from{opacity:0} to{opacity:1} }
        @keyframes slideRight { from{transform:translateX(-100%);opacity:0} to{transform:translateX(0);opacity:1} }
      `}</style>
    </div>
  );
}

// ─── Conversation Card ─────────────────────────────────────────────────────────
function ConvCard({ card, onRestore, onDelete, deleting, currentConvId }) {
  const isActive  = card.conversation_id === currentConvId;
  const isDeleting = deleting === card.conversation_id;
  const expiryWarning = card.expires_in_days <= 2;

  return (
    <div
      onClick={() => !isDeleting && onRestore(card)}
      style={{
        padding:      "10px 14px",
        borderBottom: "1px solid #F8FAFC",
        cursor:       "pointer",
        background:   isActive ? "#EFF6FF" : "transparent",
        borderLeft:   isActive ? `3px solid ${card.disease_color || "#2563EB"}` : "3px solid transparent",
        transition:   "all .1s",
        opacity:      isDeleting ? 0.4 : 1,
        display:      "flex",
        gap:          10,
        alignItems:   "flex-start",
        position:     "relative",
      }}
      onMouseEnter={e => { if (!isActive) e.currentTarget.style.background = "#F8FAFC"; }}
      onMouseLeave={e => { if (!isActive) e.currentTarget.style.background = "transparent"; }}
    >
      {/* Icon */}
      <span style={{ fontSize: 18, flexShrink: 0, marginTop: 2 }}>{card.agent_icon}</span>

      {/* Content */}
      <div style={{ flex: 1, minWidth: 0 }}>
        {/* Title + time */}
        <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 6, marginBottom: 2 }}>
          <div style={{
            fontSize:     12,
            fontWeight:   600,
            color:        "#0F172A",
            lineHeight:   1.3,
            overflow:     "hidden",
            textOverflow: "ellipsis",
            whiteSpace:   "nowrap",
            flex:         1,
          }}>
            {card.title}
          </div>
          <div style={{ fontSize: 9, color: "#94A3B8", flexShrink: 0, marginTop: 1 }}>
            {card.age_label}
          </div>
        </div>

        {/* Snippet */}
        {card.snippet && (
          <div style={{
            fontSize:     11,
            color:        "#64748B",
            lineHeight:   1.4,
            overflow:     "hidden",
            display:      "-webkit-box",
            WebkitLineClamp: 2,
            WebkitBoxOrient: "vertical",
            marginBottom: 4,
          }}>
            {card.snippet}
          </div>
        )}

        {/* Meta badges */}
        <div style={{ display: "flex", gap: 4, flexWrap: "wrap", alignItems: "center" }}>
          <span style={{
            fontSize: 9, fontWeight: 600,
            color: card.disease_color || "#6B7280",
            background: (card.disease_color || "#6B7280") + "15",
            padding: "1px 5px", borderRadius: 3,
          }}>
            {card.disease_icon} {card.disease_code}
          </span>
          <span style={{
            fontSize: 9, color: "#64748B",
            background: "#F1F5F9",
            padding: "1px 5px", borderRadius: 3,
          }}>
            {card.agent_name}
          </span>
          <span style={{ fontSize: 9, color: "#94A3B8" }}>
            {card.user_turns} Q&A
          </span>
          {card.escalated && (
            <span style={{ fontSize: 9, color: "#B91C1C", background: "#FEF2F2",
                           padding: "1px 5px", borderRadius: 3 }}>⚡ Escalated</span>
          )}
          {expiryWarning && (
            <span style={{ fontSize: 9, color: "#92400E", background: "#FEF3C7",
                           padding: "1px 5px", borderRadius: 3 }}>
              ⚠ Expires in {card.expires_in_days}d
            </span>
          )}
        </div>
      </div>

      {/* Delete button */}
      <button
        onClick={e => onDelete(card.conversation_id, e)}
        title="Delete conversation"
        style={{
          background:   "none",
          border:       "none",
          color:        "#CBD5E1",
          fontSize:     13,
          cursor:       "pointer",
          padding:      "2px 4px",
          flexShrink:   0,
          marginTop:    1,
          opacity:      0,
          transition:   "opacity .15s",
        }}
        onMouseEnter={e => { e.currentTarget.style.opacity = "1"; e.currentTarget.style.color = "#EF4444"; }}
        onMouseLeave={e => { e.currentTarget.style.opacity = "0"; e.currentTarget.style.color = "#CBD5E1"; }}
      >
        🗑
      </button>
    </div>
  );
}

// ─── Timeline view ─────────────────────────────────────────────────────────────
function TimelineView({ groups, timeOrder, onRestore, onDelete, deleting, currentConvId, empty }) {
  if (empty) return <EmptyState />;
  return (
    <div>
      {timeOrder.map(group => {
        const cards = groups[group];
        if (!cards?.length) return null;
        return (
          <div key={group}>
            <div style={{
              padding:      "8px 14px 4px",
              fontSize:     10,
              fontWeight:   700,
              color:        "#94A3B8",
              letterSpacing: ".08em",
              textTransform: "uppercase",
              background:   "#FAFAFA",
              borderBottom: "1px solid #F1F5F9",
            }}>
              {group} · {cards.length}
            </div>
            {cards.map(c => (
              <ConvCard key={c.conversation_id} card={c}
                onRestore={onRestore} onDelete={onDelete}
                deleting={deleting} currentConvId={currentConvId} />
            ))}
          </div>
        );
      })}
    </div>
  );
}

// ─── Disease view ──────────────────────────────────────────────────────────────
function DiseaseView({ byDisease, expandedDisease, expandedAgent,
                       onToggleDisease, onToggleAgent, onRestore, onDelete, deleting, currentConvId }) {
  if (!Object.keys(byDisease).length) return <EmptyState />;
  return (
    <div>
      {Object.values(byDisease)
        .sort((a, b) => (b.last_active || "").localeCompare(a.last_active || ""))
        .map(disease => (
          <div key={disease.disease_code}>
            {/* Disease header */}
            <button
              onClick={() => onToggleDisease(disease.disease_code)}
              style={{
                width:        "100%",
                padding:      "10px 14px",
                background:   expandedDisease === disease.disease_code
                              ? disease.disease_color + "10"
                              : "#F8FAFC",
                border:       "none",
                borderBottom: "1px solid #E2E8F0",
                borderLeft:   `4px solid ${disease.disease_color}`,
                cursor:       "pointer",
                display:      "flex",
                alignItems:   "center",
                gap:          8,
                fontFamily:   "inherit",
              }}
            >
              <span style={{ fontSize: 18 }}>{disease.disease_icon}</span>
              <span style={{ fontWeight: 600, fontSize: 13, color: "#0F172A", flex: 1, textAlign: "left" }}>
                {disease.disease_name}
              </span>
              <span style={{ fontSize: 10, color: "#94A3B8" }}>
                {disease.total_convs} conv
              </span>
              <span style={{ fontSize: 10, color: disease.disease_color }}>
                {expandedDisease === disease.disease_code ? "▼" : "▶"}
              </span>
            </button>

            {/* Agent list within disease */}
            {expandedDisease === disease.disease_code && (
              Object.values(disease.agents)
                .sort((a, b) => (b.last_active || "").localeCompare(a.last_active || ""))
                .map(agent => (
                  <div key={agent.agent_id} style={{ marginLeft: 4 }}>
                    <button
                      onClick={() => onToggleAgent(agent.agent_id)}
                      style={{
                        width:        "100%",
                        padding:      "8px 14px 8px 20px",
                        background:   expandedAgent === agent.agent_id ? "#EFF6FF" : "transparent",
                        border:       "none",
                        borderBottom: "1px solid #F8FAFC",
                        cursor:       "pointer",
                        display:      "flex",
                        alignItems:   "center",
                        gap:          6,
                        fontFamily:   "inherit",
                      }}
                    >
                      <span style={{ fontSize: 14 }}>{agent.agent_icon}</span>
                      <span style={{ fontSize: 12, color: "#374151", flex: 1, textAlign: "left" }}>
                        {agent.agent_name}
                      </span>
                      <span style={{ fontSize: 10, color: "#94A3B8" }}>{agent.total_convs}</span>
                      <span style={{ fontSize: 10, color: "#94A3B8" }}>
                        {expandedAgent === agent.agent_id ? "▼" : "▶"}
                      </span>
                    </button>
                    {expandedAgent === agent.agent_id && agent.conversations.map(c => (
                      <ConvCard key={c.conversation_id} card={c}
                        onRestore={onRestore} onDelete={onDelete}
                        deleting={deleting} currentConvId={currentConvId} />
                    ))}
                  </div>
                ))
            )}
          </div>
        ))}
    </div>
  );
}

// ─── Topic view (Semantic grouping) ───────────────────────────────────────────
function TopicView({ byTopic, expandedTopic, expandedDisease, expandedAgent,
                     onToggleTopic, onToggleDisease, onToggleAgent, onRestore, onDelete, deleting, currentConvId }) {
  if (!byTopic.length) return <EmptyState />;
  return (
    <div>
      {byTopic.map(topic => (
        <div key={topic.label}>
          {/* Topic header */}
          <button
            onClick={() => onToggleTopic(topic.label)}
            style={{
              width:        "100%",
              padding:      "12px 14px",
              background:   expandedTopic === topic.label ? "#F1F5F9" : "#FFFFFF",
              border:       "none",
              borderBottom: "1px solid #E2E8F0",
              cursor:       "pointer",
              display:      "flex",
              alignItems:   "center",
              gap:          10,
              fontFamily:   "inherit",
              textAlign:    "left"
            }}
          >
            <span style={{ fontSize: 18 }}>🏷️</span>
            <div style={{ flex: 1 }}>
              <div style={{ fontWeight: 700, fontSize: 13, color: "#0F172A" }}>{topic.label}</div>
              <div style={{ fontSize: 10, color: "#64748B" }}>
                {topic.total_convs} related interaction{topic.total_convs !== 1 ? "s" : ""}
              </div>
            </div>
            <span style={{ fontSize: 10, color: "#94A3B8" }}>
              {expandedTopic === topic.label ? "▼" : "▶"}
            </span>
          </button>

          {/* Nested Disease/Agent list for this topic */}
          {expandedTopic === topic.label && (
            <div style={{ background: "#F8FAFC", borderBottom: "1px solid #E2E8F0" }}>
              <DiseaseView
                byDisease={topic.diseases}
                expandedDisease={expandedDisease}
                expandedAgent={expandedAgent}
                onToggleDisease={onToggleDisease}
                onToggleAgent={onToggleAgent}
                onRestore={onRestore}
                onDelete={onDelete}
                deleting={deleting}
                currentConvId={currentConvId}
              />
            </div>
          )}
        </div>
      ))}
    </div>
  );
}

// ─── Agent view ────────────────────────────────────────────────────────────────
function AgentView({ byAgent, expandedAgent, onToggleAgent, onRestore, onDelete, deleting, currentConvId }) {
  if (!Object.keys(byAgent).length) return <EmptyState />;
  return (
    <div>
      {Object.values(byAgent)
        .sort((a, b) => b.total_convs - a.total_convs)
        .map(agent => (
          <div key={agent.agent_id}>
            <button
              onClick={() => onToggleAgent(agent.agent_id)}
              style={{
                width:        "100%",
                padding:      "10px 14px",
                background:   expandedAgent === agent.agent_id ? "#EFF6FF" : "#F8FAFC",
                border:       "none",
                borderBottom: "1px solid #E2E8F0",
                borderLeft:   `4px solid ${agent.disease_color || "#6B7280"}`,
                cursor:       "pointer",
                display:      "flex",
                alignItems:   "center",
                gap:          8,
                fontFamily:   "inherit",
              }}
            >
              <span style={{ fontSize: 16 }}>{agent.agent_icon}</span>
              <div style={{ flex: 1, textAlign: "left" }}>
                <div style={{ fontSize: 12, fontWeight: 600, color: "#0F172A" }}>
                  {agent.agent_name}
                </div>
                <div style={{ fontSize: 10, color: "#94A3B8" }}>
                  {agent.disease_name} · {agent.agent_id}
                </div>
              </div>
              <span style={{ fontSize: 10, color: "#94A3B8" }}>{agent.total_convs}</span>
              <span style={{ fontSize: 10, color: "#2563EB" }}>
                {expandedAgent === agent.agent_id ? "▼" : "▶"}
              </span>
            </button>
            {expandedAgent === agent.agent_id && agent.conversations.map(c => (
              <ConvCard key={c.conversation_id} card={c}
                onRestore={onRestore} onDelete={onDelete}
                deleting={deleting} currentConvId={currentConvId} />
            ))}
          </div>
        ))}
    </div>
  );
}

// ─── Search Results ─────────────────────────────────────────────────────────────
function SearchResults({ results, query, searching, onRestore, onDelete, deleting, currentConvId }) {
  const [expandedTopic, setExpandedTopic] = useState(null);
  const [expandedDisease, setExpandedDisease] = useState(null);
  const [expandedAgent, setExpandedAgent] = useState(null);

  if (searching) return <LoadingState label="Searching…" />;
  if (!results)  return <div style={{ padding: "20px", textAlign: "center", fontSize: 12, color: "#94A3B8" }}>Type to search…</div>;
  
  const totalConvs = results.reduce((acc, t) => acc + t.total_convs, 0);

  if (!results.length) return (
    <div style={{ padding: "30px 20px", textAlign: "center" }}>
      <div style={{ fontSize: 32, marginBottom: 10 }}>🔍</div>
      <div style={{ fontSize: 13, color: "#64748B" }}>No results for "{query}"</div>
    </div>
  );

  return (
    <div>
      <div style={{ padding: "8px 14px", fontSize: 10, color: "#94A3B8", borderBottom: "1px solid #F1F5F9", background: "#FAFAFA" }}>
        {totalConvs} interaction{totalConvs !== 1 ? "s" : ""} across {results.length} topic{results.length !== 1 ? "s" : ""} for "{query}"
      </div>
      <TopicView 
        byTopic={results}
        expandedTopic={expandedTopic}
        expandedDisease={expandedDisease}
        expandedAgent={expandedAgent}
        onToggleTopic={label => { setExpandedTopic(expandedTopic === label ? null : label); setExpandedDisease(null); setExpandedAgent(null); }}
        onToggleDisease={dc => { setExpandedDisease(expandedDisease === dc ? null : dc); setExpandedAgent(null); }}
        onToggleAgent={aid => setExpandedAgent(expandedAgent === aid ? null : aid)}
        onRestore={onRestore}
        onDelete={onDelete}
        deleting={deleting}
        currentConvId={currentConvId}
      />
    </div>
  );
}

// ─── Shared small components ───────────────────────────────────────────────────
function EmptyState() {
  return (
    <div style={{ padding: "40px 20px", textAlign: "center" }}>
      <div style={{ fontSize: 40, marginBottom: 12 }}>💬</div>
      <div style={{ fontSize: 13, fontWeight: 500, color: "#64748B", marginBottom: 6 }}>No conversations yet</div>
      <div style={{ fontSize: 11, color: "#94A3B8" }}>Start chatting with any PRISM agent — your history will appear here.</div>
    </div>
  );
}

function LoadingState({ label = "Loading history…" }) {
  return (
    <div style={{ padding: "30px", textAlign: "center", color: "#94A3B8", fontSize: 12 }}>
      <div style={{ marginBottom: 10 }}>⟳</div>{label}
    </div>
  );
}