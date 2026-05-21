import { useState } from "react";
import { Star, X, MessageSquare, AlertTriangle } from "lucide-react";
import api from "../services/api";
import toast from "react-hot-toast";

const FEEDBACK_TAGS = [
  "Incorrect or incomplete",
  "Not what I asked for",
  "Slow or buggy",
  "Style or tone",
  "Safety or legal concern",
  "Medical Assistance Grievance",
  "Other"
];

export default function StarRating({ messageId, agentId, conversationId, diseaseCode, diseaseColor }) {
  const [rating, setRating] = useState(0);
  const [hover, setHover] = useState(0);
  const [submitted, setSubmitted] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [selectedTags, setSelectedTags] = useState([]);
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleRatingClick = (r) => {
    setRating(r);
    if (r === 5) {
      submitFeedback(r, [], "");
    } else {
      setShowModal(true);
    }
  };

  const toggleTag = (tag) => {
    setSelectedTags(prev => 
      prev.includes(tag) ? prev.filter(t => t !== tag) : [...prev, tag]
    );
  };

  const submitFeedback = async (r, tags, msg) => {
    setIsSubmitting(true);
    const loadingToast = r !== 5 ? toast.loading("Submitting feedback...") : null;
    try {
      await api.post("/feedback", {
        message_id: String(messageId || ""),
        conversation_id: String(conversationId || ""),
        agent_id: agentId,
        disease_code: diseaseCode,
        rating: r,
        helpful: r >= 4,
        accurate: r >= 4,
        comment: msg || "",
        tags: tags || []
      });
      setSubmitted(true);
      setShowModal(false);
      toast.success("Feedback submitted! Thank you.", { id: loadingToast });
    } catch (err) {
      console.error("Feedback failed:", err);
      toast.error("Failed to submit feedback. Please try again.", { id: loadingToast });
    } finally {
      setIsSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div style={{ fontSize: 10, color: "#94A3B8", fontStyle: "italic", animation: "fadeIn .3s", marginTop: 4 }}>
        Thanks for your feedback!
      </div>
    );
  }

  return (
    <div style={{ position: "relative" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 3 }}>
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            onClick={() => handleRatingClick(star)}
            onMouseEnter={() => setHover(star)}
            onMouseLeave={() => setHover(0)}
            style={{
              background: "transparent",
              border: "none",
              padding: 0,
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              transition: "transform .1s"
            }}
          >
            <Star
              size={12}
              fill={(hover || rating) >= star ? (diseaseColor || "#EAB308") : "transparent"}
              color={(hover || rating) >= star ? (diseaseColor || "#EAB308") : "#CBD5E1"}
              strokeWidth={2}
            />
          </button>
        ))}
        <span style={{ fontSize: 9, color: "#94A3B8", marginLeft: 4 }}>Rate this response</span>
      </div>

      {showModal && (
        <div style={{
          position: "fixed",
          top: 0, left: 0, right: 0, bottom: 0,
          background: "rgba(0,0,0,0.5)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          zIndex: 1000,
          backdropFilter: "blur(4px)",
          padding: 20
        }}>
          <div style={{
            background: "#FFFFFF",
            borderRadius: 16,
            width: "100%",
            maxWidth: 450,
            padding: 24,
            boxShadow: "0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)",
            position: "relative",
            animation: "modalIn .3s cubic-bezier(0.16, 1, 0.3, 1)"
          }}>
            <button 
              onClick={() => setShowModal(false)}
              style={{ position: "absolute", top: 16, right: 16, background: "transparent", border: "none", cursor: "pointer", color: "#64748B" }}
            >
              <X size={20} />
            </button>

            <h3 style={{ fontSize: 18, fontWeight: 600, color: "#0F172A", marginBottom: 16, display: "flex", alignItems: "center", gap: 10 }}>
              <MessageSquare size={20} style={{ color: diseaseColor || "#F37029" }} />
              Share feedback
            </h3>

            <div style={{ display: "flex", flexWrap: "wrap", gap: 8, marginBottom: 20 }}>
              {FEEDBACK_TAGS.map(tag => (
                <button
                  key={tag}
                  onClick={() => toggleTag(tag)}
                  style={{
                    padding: "6px 12px",
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: 500,
                    border: "1px solid",
                    borderColor: selectedTags.includes(tag) ? (diseaseColor || "#F37029") : "#E2E8F0",
                    background: selectedTags.includes(tag) ? `${diseaseColor || "#F37029"}11` : "transparent",
                    color: selectedTags.includes(tag) ? (diseaseColor || "#F37029") : "#64748B",
                    cursor: "pointer",
                    transition: "all .2s"
                  }}
                >
                  {tag}
                </button>
              ))}
            </div>

            <div style={{ marginBottom: 8, display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <label style={{ fontSize: 12, fontWeight: 500, color: "#64748B" }}>Details</label>
              <span style={{ fontSize: 11, color: "#94A3B8" }}>(Optional)</span>
            </div>
            <textarea
              placeholder="Share more details about your experience..."
              value={comment}
              onChange={(e) => setComment(e.target.value)}
              style={{
                width: "100%",
                height: 100,
                borderRadius: 12,
                border: `1px solid ${diseaseColor || "#F37029"}33`,
                padding: 12,
                fontSize: 14,
                fontFamily: "inherit",
                resize: "none",
                marginBottom: 20,
                outline: "none",
                color: "#1E293B", // Dark color for visibility
                background: "#F8FAFC"
              }}
              onFocus={(e) => e.target.style.borderColor = (diseaseColor || "#F37029")}
              onBlur={(e) => e.target.style.borderColor = `${diseaseColor || "#F37029"}33`}
            />

            <div style={{ 
              background: "#F8FAFC", 
              borderRadius: 8, 
              padding: "10px 12px", 
              fontSize: 11, 
              color: "#64748B", 
              marginBottom: 24,
              display: "flex",
              gap: 8,
              alignItems: "flex-start"
            }}>
              <AlertTriangle size={14} style={{ flexShrink: 0, marginTop: 2, color: "#94A3B8" }} />
              <span>Your conversation will be included with your feedback to help improve PRISM AI.</span>
            </div>

            <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
              <button 
                onClick={() => setShowModal(false)}
                style={{ 
                  padding: "10px 20px", 
                  borderRadius: 10, 
                  fontSize: 14, 
                  fontWeight: 600, 
                  color: "#64748B", 
                  background: "transparent", 
                  border: "none",
                  cursor: "pointer"
                }}
              >
                Cancel
              </button>
              <button 
                disabled={isSubmitting}
                onClick={() => submitFeedback(rating, selectedTags, comment)}
                style={{ 
                  padding: "10px 24px", 
                  borderRadius: 10, 
                  fontSize: 14, 
                  fontWeight: 600, 
                  color: "#FFFFFF", 
                  background: (diseaseColor || "#F37029"), 
                  border: "none",
                  cursor: isSubmitting ? "not-allowed" : "pointer",
                  opacity: isSubmitting ? 0.7 : 1,
                  boxShadow: `0 4px 6px ${diseaseColor || "#F37029"}33`
                }}
              >
                {isSubmitting ? "Submitting..." : "Submit"}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`
        @keyframes fadeIn { from { opacity: 0; } to { opacity: 1; } }
        @keyframes modalIn { from { opacity: 0; transform: scale(0.95) translateY(10px); } to { opacity: 1; transform: scale(1) translateY(0); } }
      `}</style>
    </div>
  );
}
