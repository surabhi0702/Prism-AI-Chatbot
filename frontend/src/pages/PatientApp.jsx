// ═══════════════════════════════════════════════════════════════════════════════
// FILE A: Changes to frontend/src/pages/PatientApp.jsx
// FILE B: SQL migration for conversation title column
// ═══════════════════════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════════════════════
// FILE A — PatientApp.jsx changes (5 steps)
// ═══════════════════════════════════════════════════════════════════════════════

// ─── STEP 1: Add import ────────────────────────────────────────────────────────
// import ChatHistory from "../components/ChatHistory";

// ─── STEP 2: Add state variables ──────────────────────────────────────────────
// const [showHistory, setShowHistory] = useState(false);

// ─── STEP 3: Add history restore handler ──────────────────────────────────────
/*
const handleRestoreConversation = useCallback((data) => {
  const { conversation, messages } = data;
  if (!conversation) return;

  // Find the matching disease and agent in the sidebar
  const diseaseCode = conversation.disease_code;
  const agentId     = conversation.agent_id;
  const disease     = DISEASES.find(d => d.code === diseaseCode);
  const agent       = disease?.agents.find(a => a.id === agentId);

  if (disease && agent) {
    setSelDisease(disease);
    setSelAgent(agent);
  }

  // Restore the conversation ID so new messages append to it
  setConvId(conversation.id);

  // Restore messages into the chat
  setMessages(messages.map(m => ({
    role:        m.role,
    content:     m.content,
    id:          m.id,
    isVoice:     m.is_voice,
    isImageAnalysis: m.is_image,
    confidence:  m.confidence,
    citations:   m.citations || [],
    // Mark as restored so StarRating doesn't double-show
    isRestored:  true,
  })));

  // Reset conversational state (fresh session on top of restored)
  setIsAskingQuestions(false);
  setCurrentQuestionNum(0);
  setCurrentIntent(null);
  setCurrentSlots({});

  // Reset escalation state
  setEscalationData(null);
  setRouteDecision("primary");
  setConfidence(null);
  setShowHumanCard(false);
}, []);
*/

// ─── STEP 4: Add History button to the NavBar / AgentHeaderBar ───────────────
/*
// In the NavBar (when no agent selected) or AgentHeaderBar,
// add the history button alongside the language selector:

<button
  onClick={() => setShowHistory(true)}
  title="View chat history (last 15 days)"
  style={{
    display:      "flex",
    alignItems:   "center",
    gap:          5,
    padding:      "6px 10px",
    background:   "transparent",
    border:       "1px solid #E2E8F0",
    borderRadius: 8,
    fontSize:     12,
    color:        "#475569",
    cursor:       "pointer",
    fontFamily:   "inherit",
    fontWeight:   500,
  }}
>
  🕐 History
</button>
*/

// ─── STEP 5: Add ChatHistory component to PatientApp JSX ─────────────────────
/*
// Add near the bottom of PatientApp's JSX, before the closing </div>:

<ChatHistory
  isOpen={showHistory}
  onClose={() => setShowHistory(false)}
  onRestoreConversation={handleRestoreConversation}
  currentConvId={convId}
/>
*/

// ─── STEP 6: Auto-update conversation title in DB when first message sent ─────
// In sendMessage(), after convId is set, update the title:
/*
// After: if (!convId) setConvId(data.conversation_id);
// Add:
if (!convId && data.conversation_id) {
  setConvId(data.conversation_id);
  // Title is auto-generated from first message on the backend
}
*/


// ═══════════════════════════════════════════════════════════════════════════════
// FILE B — SQL Migration (add title + created_at to conversations if missing)
// ═══════════════════════════════════════════════════════════════════════════════

const MIGRATION_SQL = `
-- Ensure conversations table has all required columns for history
ALTER TABLE conversations
  ADD COLUMN IF NOT EXISTS title        VARCHAR(200),
  ADD COLUMN IF NOT EXISTS created_at   TIMESTAMP DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS updated_at   TIMESTAMP DEFAULT NOW(),
  ADD COLUMN IF NOT EXISTS escalated    BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS language     VARCHAR(10) DEFAULT 'en',
  ADD COLUMN IF NOT EXISTS meta_json    JSONB DEFAULT '{}';

-- Performance indexes for history queries (filtering by user + date)
CREATE INDEX IF NOT EXISTS idx_conversations_user_updated
  ON conversations (user_id, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_user_disease
  ON conversations (user_id, disease_code, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_user_agent
  ON conversations (user_id, agent_id, updated_at DESC);

-- Full text search index on messages
CREATE INDEX IF NOT EXISTS idx_messages_content_fts
  ON messages USING gin(to_tsvector('english', content));

-- Partial index for user messages only
CREATE INDEX IF NOT EXISTS idx_messages_user_role
  ON messages (conversation_id, role, created_at);

-- Auto-update updated_at trigger
CREATE OR REPLACE FUNCTION update_conversation_timestamp()
RETURNS TRIGGER AS $$
BEGIN
  UPDATE conversations
  SET updated_at = NOW()
  WHERE id = NEW.conversation_id;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trigger_update_conv_timestamp ON messages;
CREATE TRIGGER trigger_update_conv_timestamp
AFTER INSERT ON messages
FOR EACH ROW EXECUTE FUNCTION update_conversation_timestamp();
`;

// Run this SQL:
// psql -U prism_user -d prism -c "$(cat migration.sql)"
// OR via pgAdmin / DBeaver


// ═══════════════════════════════════════════════════════════════════════════════
// COMPLETE FEATURE SUMMARY
// ═══════════════════════════════════════════════════════════════════════════════

/*
WHAT THIS FEATURE DOES:
  ✓ Stores ALL patient conversations for 15 days (existing DB — no new tables)
  ✓ Auto-deletes conversations older than 15 days (background scheduler, 2AM UTC)
  ✓ History panel (🕐 History button) opens as a left drawer
  ✓ Three views: Timeline (ChatGPT-style), By Disease, By Agent
  ✓ Full-text search across all messages in history
  ✓ Filter by disease domain and agent
  ✓ Click any conversation card → restores full chat (messages + agent context)
  ✓ Per-conversation delete + Clear all
  ✓ Expiry warning badge (shows when <2 days until auto-delete)
  ✓ Stats: total convs, messages, most used agent
  ✓ Escalated conversations flagged
  ✓ Auto-generated titles from first user message

HOW HISTORY IS PERSISTED:
  No new tables needed. The existing conversations + messages tables are used.
  The 15-day window is enforced purely at query time (WHERE updated_at >= cutoff)
  and at cleanup time (DELETE WHERE updated_at < cutoff).

CONVERSATION CARD SHOWS:
  • Auto-generated title (first 8 words of first message)
  • Last AI response snippet (120 chars)
  • Disease icon + code badge (colour-coded)
  • Agent name badge
  • Turn count (Q&A exchanges)
  • Time ago label (Today / Yesterday / 3 days ago)
  • ⚡ Escalated badge if conversation triggered escalation
  • ⚠ Expires in Nd badge for conversations expiring soon
  • 🗑 Delete button (hover to reveal)

VIEWS:
  Timeline:  Grouped by Today / Yesterday / This week / Last week
  Disease:   Expandable disease tree → agent → conversations
  Agent:     Flat agent list sorted by conversation count → conversations
  Search:    Real-time full-text search with 400ms debounce + highlighted snippet
*/