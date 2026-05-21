// ═══════════════════════════════════════════════════════════════════════════════
// FILE: frontend/src/components/ImageUpload.jsx
// PRISM Medical Image Upload — Upload Button, Preview, Analysis Display
// ═══════════════════════════════════════════════════════════════════════════════

import { useState, useRef, useCallback } from "react";

import api from "../services/api";

const MAX_SIZE_MB = 10;

// ─── Accepted file types (Images + Documents) ──────────────────────────────────
const ACCEPT = "image/jpeg,image/jpg,image/png,image/webp,image/gif,image/tiff,application/pdf,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/vnd.ms-excel,application/vnd.openxmlformats-officedocument.wordprocessingml.document";


// ─── Image type icons ──────────────────────────────────────────────────────────
const TYPE_ICONS = {
  prescription: "📜", medicine_pack: "💊", tablet_capsule: "💊",
  syrup_bottle: "🧴", inhaler_device: "🫁", blood_report: "🩸",
  hba1c_report: "📊", lipid_panel: "🩺", ecg_strip: "❤️",
  xray: "🩻", mri_scan: "🩻", ct_scan: "🩻", glucose_meter: "📊",
  bp_monitor: "💓", pulse_oximeter: "🩺", spirometry: "🫁",
  phq_gad_score: "🧠", wound_image: "🩹", 
  operative_report: "🔪", discharge_summary: "🏥", 
  consultation_report: "👨‍⚕️", imaging_report: "📝", 
  lab_results: "🧪", default: "🏥",
};


// ─── Upload state machine ──────────────────────────────────────────────────────
const STATES = {
  IDLE:       "idle",
  SELECTED:   "selected",
  UPLOADING:  "uploading",
  VALIDATING: "validating",
  ANALYSING:  "analysing",
  DONE:       "done",
  ERROR:      "error",
  GUARDRAIL:  "guardrail",
  REDIRECT:   "redirect",
};

// ─── Progress step labels ──────────────────────────────────────────────────────
const PROGRESS_STEPS = [
  { key: "upload",   label: "Uploading document",      icon: "⬆️" },
  { key: "validate", label: "Medical validation",      icon: "🔍" },
  { key: "classify", label: "Content classification",  icon: "🏷️" },
  { key: "analyse",  label: "Agent analysis",          icon: "🤖" },
];



// ═══════════════════════════════════════════════════════════════════════════════
// MAIN COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export default function ImageUpload({
  agentId,
  conversationId,
  diseaseColor = "#2563EB",
  diseaseName  = "Medical",
  language     = "en",
  onAnalysisComplete,   // callback(analysisResult) → inserts message into chat
  onGuardrail,          // callback(guardrailResult) → handles redirect
}) {
  const [phase, setPhase]           = useState(STATES.IDLE);
  const [file, setFile]             = useState(null);
  const [preview, setPreview]       = useState(null);
  const [query, setQuery]           = useState("");
  const [result, setResult]         = useState(null);
  const [error, setError]           = useState("");
  const [progressStep, setProgressStep] = useState(0);
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef                = useRef(null);

  // ── File selection ────────────────────────────────────────────────────────
  const handleFile = useCallback((selectedFile) => {
    if (!selectedFile) return;

    // Size check
    if (selectedFile.size > MAX_SIZE_MB * 1024 * 1024) {
      setError(`File too large. Max ${MAX_SIZE_MB}MB. Your file: ${(selectedFile.size / 1024 / 1024).toFixed(1)}MB`);
      setPhase(STATES.ERROR);
      return;
    }

    // Type check
    const isImage = selectedFile.type.startsWith("image/");
    const isDoc = ["application/pdf", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "application/vnd.ms-excel", "application/vnd.openxmlformats-officedocument.wordprocessingml.document"].includes(selectedFile.type);
    
    if (!isImage && !isDoc) {
      setError("Supported files: Images (JPG/PNG), PDF, Excel, and Word documents.");
      setPhase(STATES.ERROR);
      return;
    }


    setFile(selectedFile);
    setError("");
    setResult(null);

    // Generate preview
    if (isImage) {
      const reader = new FileReader();
      reader.onload = (e) => {
        setPreview(e.target.result);
        setPhase(STATES.SELECTED);
      };
      reader.readAsDataURL(selectedFile);
    } else {
      // For docs, show a generic icon/label
      setPreview(null);
      setPhase(STATES.SELECTED);
    }

  }, []);

  const handleInputChange = (e) => handleFile(e.target.files?.[0]);

  // ── Drag-and-drop ─────────────────────────────────────────────────────────
  const handleDrop = (e) => {
    e.preventDefault();
    setIsDragging(false);
    handleFile(e.dataTransfer.files?.[0]);
  };

  // ── Upload and analyse ────────────────────────────────────────────────────
  const handleUpload = useCallback(async () => {
    if (!file) return;

    setPhase(STATES.UPLOADING);
    setProgressStep(0);
    setError("");

    const formData = new FormData();
    formData.append("file",            file);
    formData.append("agent_id",        agentId);
    formData.append("query",           query || "Please analyse this medical document.");

    formData.append("language",        language);
    if (conversationId) formData.append("conversation_id", conversationId);
    if (window._prism_force_analysis) {
        formData.append("force_analysis", "true");
        window._prism_force_analysis = false;
    }

    try {
      // Animate progress steps
      const stepInterval = setInterval(() => {
        setProgressStep(s => Math.min(s + 1, PROGRESS_STEPS.length - 1));
      }, 1200);
      setPhase(STATES.VALIDATING);

      const res = await api.post("/chat/image", formData, {
        headers: { "Content-Type": "multipart/form-data" }
      });

      clearInterval(stepInterval);
      setProgressStep(PROGRESS_STEPS.length - 1);

      const data = res.data;

      // Agent mismatch (guardrail redirect)
      if (data.response_type === "guardrail") {
        setResult(data);
        setPhase(STATES.REDIRECT);
        return;
      }

      setResult(data);
      setPhase(STATES.DONE);
      if (onAnalysisComplete) onAnalysisComplete(data);

    } catch (e) {
      // @ts-ignore
      if (typeof stepInterval !== 'undefined') clearInterval(stepInterval);
      if (e.response?.status === 422) {
        setResult(e.response.data);
        setPhase(STATES.GUARDRAIL);
      } else {
        setError(e.response?.data?.detail || e.message || "Upload failed. Please try again.");
        setPhase(STATES.ERROR);
      }
    }
  }, [file, query, agentId, conversationId, language, onAnalysisComplete, onGuardrail]);

  const reset = () => {
    setPhase(STATES.IDLE);
    setFile(null);
    setPreview(null);
    setQuery("");
    setResult(null);
    setError("");
    setProgressStep(0);
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  // ════════════════════════════════════════════════════════════════════════════
  // RENDER
  // ════════════════════════════════════════════════════════════════════════════

  return (
    <div style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}>

      {/* ── IDLE — Upload trigger button (inline in input bar) ─────────────── */}
      {phase === STATES.IDLE && (
        <>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPT}
            onChange={handleInputChange}
            style={{ display: "none" }}
          />
          <button
            onClick={() => fileInputRef.current?.click()}
            title="Upload medical documents (PDF, Excel, Images) for specialist analysis"
            style={{
              display:        "flex",
              alignItems:     "center",
              gap:            6,
              padding:        "7px 12px",
              background:     "transparent",
              border:         `1px solid ${diseaseColor}44`,
              borderRadius:   10,
              color:          diseaseColor,
              cursor:         "pointer",
              fontSize:       12,
              fontWeight:     700,
              fontFamily:     "inherit",
              transition:     "all .15s",
              whiteSpace:     "nowrap",
              flexShrink:     0,
            }}
            onMouseEnter={e => {
              e.currentTarget.style.background = diseaseColor + "11";
              e.currentTarget.style.borderColor = diseaseColor;
              e.currentTarget.style.transform = "translateY(-1px)";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.borderColor = diseaseColor + "44";
              e.currentTarget.style.transform = "translateY(0)";
            }}
          >
            <span style={{ fontSize: 16 }}>📂</span> Upload Medical Document
          </button>
          
          {/* Helper Tips */}
          <div style={{
            fontSize: 10,
            color: "#64748B",
            marginLeft: 8,
            display: "none", // Shown on mobile or in subtext
            opacity: 0.7
          }}>
            PDF, Excel, Images accepted
          </div>

        </>
      )}

      {/* ── SELECTED — Preview + query input modal ────────────────────────── */}
      {phase === STATES.SELECTED && (
        <ImagePreviewModal
          file={file}
          preview={preview}
          query={query}
          setQuery={setQuery}
          onUpload={handleUpload}
          onCancel={reset}
          diseaseColor={diseaseColor}
          diseaseName={diseaseName}
          isDragging={isDragging}
          setIsDragging={setIsDragging}
          handleDrop={handleDrop}
        />
      )}

      {/* ── UPLOADING / VALIDATING / ANALYSING — Progress ────────────────── */}
      {[STATES.UPLOADING, STATES.VALIDATING, STATES.ANALYSING].includes(phase) && (
        <AnalysisProgress
          progressStep={progressStep}
          preview={preview}
          diseaseColor={diseaseColor}
        />
      )}

      {/* ── GUARDRAIL — Non-medical rejection ────────────────────────────── */}
      {phase === STATES.GUARDRAIL && result && (
        <GuardrailMessage
          message={result.guardrail_message}
          f1Score={result.f1_score}
          onRetry={reset}
          diseaseColor={diseaseColor}
        />
      )}

      {/* ── REDIRECT — Agent mismatch ─────────────────────────────────────── */}
      {phase === STATES.REDIRECT && result && (
        <RedirectMessage
          message={result.guardrail_message}
          imageLabel={result.image_label}
          redirectTo={result.redirect_to}
          onRetry={reset}
          onProceed={() => {
            window._prism_force_analysis = true;
            handleUpload();
          }}
          diseaseColor={diseaseColor}
        />
      )}

      {/* ── ERROR ────────────────────────────────────────────────────────── */}
      {phase === STATES.ERROR && (
        <ErrorMessage error={error} onRetry={reset} diseaseColor={diseaseColor} />
      )}

      {/* ── DONE — Show a compact "new image" button ──────────────────────── */}
      {phase === STATES.DONE && (
        <button
          onClick={reset}
          style={{
            display:      "flex",
            alignItems:   "center",
            gap:          4,
            padding:      "5px 10px",
            background:   "#F0FDF4",
            border:       "1px solid #86EFAC",
            borderRadius: 8,
            color:        "#1A7A4A",
            cursor:       "pointer",
            fontSize:     11,
            fontFamily:   "inherit",
            flexShrink:   0,
          }}
        >
          ✓ Done · Upload another
        </button>
      )}
    </div>
  );
}

// ─── Image Preview Modal ───────────────────────────────────────────────────────
function ImagePreviewModal({
  file, preview, query, setQuery, onUpload, onCancel,
  diseaseColor, diseaseName, isDragging, setIsDragging, handleDrop,
}) {
  return (
    <div style={{
      position:        "fixed",
      inset:           0,
      background:      "rgba(13,34,64,.7)",
      display:         "flex",
      alignItems:      "center",
      justifyContent:  "center",
      zIndex:          1000,
      padding:         16,
      backdropFilter:  "blur(3px)",
      animation:       "fadeIn .2s ease",
    }}>
      <div style={{
        background:   "#FFFFFF",
        borderRadius: 16,
        width:        "100%",
        maxWidth:     520,
        boxShadow:    "0 20px 60px rgba(0,0,0,.3)",
        overflow:     "hidden",
        fontFamily:   "system-ui, -apple-system, sans-serif",
      }}>
        {/* Header */}
        <div style={{
          background:  "#0D2240",
          padding:     "14px 18px",
          display:     "flex",
          alignItems:  "center",
          gap:         10,
        }}>
          <span style={{ fontSize: 22 }}>🔬</span>
          <div>
            <div style={{ color: "#FFFFFF", fontWeight: 700, fontSize: 14 }}>
              Medical Document Analysis
            </div>
            <div style={{ color: "#6B8CAE", fontSize: 11 }}>
              {diseaseName} Agent — Comprehensive clinical review (PDF/Excel/Images)
            </div>

          </div>
          <button
            onClick={onCancel}
            style={{ marginLeft: "auto", background: "none", border: "none",
                     color: "#6B8CAE", fontSize: 20, cursor: "pointer" }}
          >×</button>
        </div>

        <div style={{ padding: "18px 20px" }}>
          {/* Image preview */}
          <div style={{
            borderRadius: 10,
            overflow:     "hidden",
            border:       "1px solid #E2E8F0",
            marginBottom: 14,
            maxHeight:    240,
            display:      "flex",
            alignItems:   "center",
            justifyContent: "center",
            background:   "#F8FAFC",
            position:     "relative",
          }}>
            {preview ? (
              <img
                src={preview}
                alt="Medical image preview"
                style={{
                  maxHeight: 240,
                  maxWidth:  "100%",
                  objectFit: "contain",
                  display:   "block",
                }}
              />
            ) : (
              <div style={{ padding: 40, textAlign: "center" }}>
                <div style={{ fontSize: 48, marginBottom: 10 }}>
                  {file.type.includes("pdf") ? "📕" : file.type.includes("sheet") ? "📊" : "📄"}
                </div>
                <div style={{ fontSize: 14, fontWeight: 600, color: "#1E293B" }}>
                  {file.name}
                </div>
                <div style={{ fontSize: 11, color: "#64748B" }}>
                  Ready for secure text extraction and analysis
                </div>
              </div>
            )}

            {/* File info badge */}
            <div style={{
              position:     "absolute",
              bottom:       6,
              right:        6,
              background:   "rgba(0,0,0,.6)",
              color:        "#FFFFFF",
              fontSize:     10,
              padding:      "2px 7px",
              borderRadius: 6,
            }}>
              {file.name} · {(file.size / 1024).toFixed(0)} KB
            </div>
          </div>

          {/* Query input */}
          <div style={{ marginBottom: 16 }}>
            <label style={{
              fontSize:    11,
              fontWeight:  600,
              color:       "#374151",
              display:     "block",
              marginBottom: 5,
            }}>
              What would you like the AI to analyse? (optional)
            </label>
            <textarea
              autoFocus
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder="e.g. What do these glucose readings mean? Is this HbA1c level normal for my age?"
              rows={2}
              style={{
                width:        "100%",
                padding:      "8px 10px",
                border:       "1px solid #D1D5DB",
                borderRadius: 8,
                fontSize:     12,
                fontFamily:   "inherit",
                resize:       "none",
                outline:      "none",
                background:   "#FAFAFA",
                boxSizing:    "border-box",
                color:        "#0F172A", // Ensure text is visible
              }}
            />
          </div>

          {/* Disclaimer */}
          <div style={{
            background:   "#F0F9FF",
            border:       "1px solid #BAE6FD",
            borderRadius: 8,
            padding:      "10px 14px",
            fontSize:     11,
            color:        "#0369A1",
            marginBottom: 16,
            lineHeight:   1.5,
          }}>
            ℹ️ PRISM will extract all clinical data from this {file.type.startsWith("image/") ? "image" : "document"} for your specialist to review. 
            <strong> Support:</strong> Prescription, Lab Result, Discharge Summary, Operative Report, etc.
          </div>


          {/* Actions */}
          <div style={{ display: "flex", gap: 10 }}>
            <button
              onClick={onCancel}
              style={{
                padding:      "9px 16px",
                background:   "transparent",
                border:       "1px solid #E2E8F0",
                borderRadius: 8,
                fontSize:     13,
                cursor:       "pointer",
                fontFamily:   "inherit",
                color:        "#64748B",
                flex:         "0 0 auto",
              }}
            >
              Cancel
            </button>
            <button
              onClick={onUpload}
              style={{
                padding:        "9px 0",
                background:     diseaseColor,
                border:         "none",
                borderRadius:   8,
                fontSize:       13,
                fontWeight:     600,
                cursor:         "pointer",
                fontFamily:     "inherit",
                color:          "#FFFFFF",
                flex:           1,
                display:        "flex",
                alignItems:     "center",
                justifyContent: "center",
                gap:            6,
              }}
            >
              🔬 Analyse Medical {file.type.startsWith("image/") ? "Image" : "Document"}

            </button>
          </div>
        </div>
      </div>
      <style>{`@keyframes fadeIn{from{opacity:0}to{opacity:1}}`}</style>
    </div>
  );
}

// ─── Analysis Progress Overlay ─────────────────────────────────────────────────
function AnalysisProgress({ progressStep, preview, diseaseColor }) {
  return (
    <div style={{
      position:        "fixed",
      inset:           0,
      background:      "rgba(13,34,64,.8)",
      display:         "flex",
      alignItems:      "center",
      justifyContent:  "center",
      zIndex:          1001,
      backdropFilter:  "blur(4px)",
    }}>
      <div style={{
        background:   "#FFFFFF",
        borderRadius: 16,
        padding:      "28px 32px",
        maxWidth:     380,
        width:        "90%",
        textAlign:    "center",
        boxShadow:    "0 20px 60px rgba(0,0,0,.3)",
      }}>
        {/* Preview thumbnail */}
        {preview && (
          <img
            src={preview}
            style={{
              width:        64,
              height:       64,
              objectFit:    "cover",
              borderRadius: 10,
              border:       `2px solid ${diseaseColor}`,
              marginBottom: 16,
            }}
          />
        )}

        <div style={{ fontWeight: 700, fontSize: 15, marginBottom: 18, color: "#0F172A" }}>
          Analysing your medical image…
        </div>

        {/* Step indicators */}
        <div style={{ display: "flex", flexDirection: "column", gap: 10, textAlign: "left" }}>
          {PROGRESS_STEPS.map((step, i) => {
            const done    = i < progressStep;
            const active  = i === progressStep;
            return (
              <div key={step.key} style={{
                display:     "flex",
                alignItems:  "center",
                gap:         10,
                opacity:     i > progressStep ? 0.35 : 1,
                transition:  "opacity .3s",
              }}>
                <div style={{
                  width:          28,
                  height:         28,
                  borderRadius:   "50%",
                  background:     done ? "#1A7A4A" : active ? diseaseColor : "#E2E8F0",
                  display:        "flex",
                  alignItems:     "center",
                  justifyContent: "center",
                  fontSize:       12,
                  color:          done || active ? "#FFFFFF" : "#94A3B8",
                  fontWeight:     700,
                  flexShrink:     0,
                  transition:     "all .3s",
                }}>
                  {done ? "✓" : active ? (
                    <span style={{ animation: "spin 1s linear infinite", display: "block" }}>⟳</span>
                  ) : i + 1}
                </div>
                <div>
                  <div style={{ fontSize: 12, fontWeight: active ? 600 : 400, color: active ? "#0F172A" : "#64748B" }}>
                    {step.icon} {step.label}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      <style>{`@keyframes spin{to{transform:rotate(360deg)}}`}</style>
    </div>
  );
}

// ─── Guardrail Message — non-medical image ─────────────────────────────────────
function GuardrailMessage({ message, f1Score, onRetry, diseaseColor }) {
  return (
    <div style={{
      position:        "fixed",
      inset:           0,
      background:      "rgba(13,34,64,.7)",
      display:         "flex",
      alignItems:      "center",
      justifyContent:  "center",
      zIndex:          1001,
      padding:         16,
    }}>
      <div style={{
        background:   "#FFFFFF",
        borderRadius: 16,
        maxWidth:     480,
        width:        "90%",
        overflow:     "hidden",
        boxShadow:    "0 20px 60px rgba(0,0,0,.25)",
      }}>
        <div style={{ background: "#B91C1C", padding: "12px 16px", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 20 }}>🚫</span>
          <span style={{ color: "#FFFFFF", fontWeight: 700, fontSize: 14 }}>Non-Medical Image Rejected</span>
        </div>
        <div style={{ padding: "18px 20px" }}>
          <div style={{ fontSize: 12, color: "#374151", lineHeight: 1.7, marginBottom: 16 }}>
            {/* Render the guardrail message as simple text */}
            {message.split("\n").map((line, i) => (
              <div key={i} style={{ marginBottom: line === "" ? 6 : 2 }}>
                {line.replace(/\*\*/g, "")}
              </div>
            ))}
          </div>
          {f1Score !== undefined && (
            <div style={{
              background:   "#FEF2F2",
              border:       "1px solid #FECACA",
              borderRadius: 8,
              padding:      "8px 12px",
              fontSize:     11,
              color:        "#991B1B",
              marginBottom: 16,
            }}>
              Medical relevance score: <strong>{(f1Score * 100).toFixed(0)}%</strong>
              {" "}(minimum required: 55%)
            </div>
          )}
          <button
            onClick={onRetry}
            style={{
              width:        "100%",
              padding:      "10px",
              background:   diseaseColor,
              border:       "none",
              borderRadius: 8,
              color:        "#FFFFFF",
              fontWeight:   600,
              fontSize:     13,
              cursor:       "pointer",
              fontFamily:   "inherit",
            }}
          >
            Upload a different image
          </button>
        </div>
      </div>
    </div>
  );
}

// ─── Redirect Message — wrong agent ───────────────────────────────────────────
function RedirectMessage({ message, imageLabel, redirectTo, onRetry, onProceed, diseaseColor }) {
  return (
    <div style={{
      position:       "fixed",
      inset:          0,
      background:     "rgba(13,34,64,.7)",
      display:        "flex",
      alignItems:     "center",
      justifyContent: "center",
      zIndex:         1001,
      padding:        16,
    }}>
      <div style={{
        background:   "#FFFFFF",
        borderRadius: 16,
        maxWidth:     480,
        width:        "90%",
        overflow:     "hidden",
        boxShadow:    "0 20px 60px rgba(0,0,0,.25)",
        animation:    "fadeIn .2s ease",
      }}>
        <div style={{ background: "#B45309", padding: "12px 16px", display: "flex", alignItems: "center", gap: 8 }}>
          <span style={{ fontSize: 20 }}>⚠️</span>
          <span style={{ color: "#FFFFFF", fontWeight: 700, fontSize: 14 }}>{imageLabel || "Image"} Mismatch — Specialized Agent Only</span>
        </div>
        <div style={{ padding: "18px 20px" }}>
          <div style={{ fontSize: 12, color: "#374151", lineHeight: 1.7, marginBottom: 14 }}>
            {message.split("\n").map((line, i) => {
               if (line.startsWith("**") && line.endsWith("**")) 
                 return <div key={i} style={{fontWeight:700, marginTop:10}}>{line.replace(/\*\*/g, "")}</div>;
               return <div key={i} style={{ marginBottom: 2 }}>{line.replace(/\*\*/g, "")}</div>;
            })}
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <button
              onClick={onRetry}
              style={{
                width:        "100%",
                padding:      "10px",
                background:   diseaseColor,
                border:       "none",
                borderRadius: 8,
                color:        "#FFFFFF",
                fontWeight:   600,
                fontSize:     13,
                cursor:       "pointer",
                fontFamily:   "inherit",
              }}
            >
              Switch agent or try again
            </button>
            <button
              onClick={onProceed}
              style={{
                width:        "100%",
                padding:      "8px",
                background:   "transparent",
                border:       "1px solid #E2E8F0",
                borderRadius: 8,
                color:        "#64748B",
                fontWeight:   500,
                fontSize:     12,
                cursor:       "pointer",
                fontFamily:   "inherit",
              }}
            >
              Proceed with current agent anyway
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Error Message ─────────────────────────────────────────────────────────────
function ErrorMessage({ error, onRetry, diseaseColor }) {
  return (
    <div style={{
      position:       "fixed",
      inset:          0,
      background:     "rgba(13,34,64,.7)",
      display:        "flex",
      alignItems:     "center",
      justifyContent: "center",
      zIndex:         1001,
      padding:        16,
    }}>
      <div style={{
        background:   "#FFFFFF",
        borderRadius: 16,
        maxWidth:     400,
        width:        "90%",
        padding:      20,
        textAlign:    "center",
        boxShadow:    "0 20px 60px rgba(0,0,0,.25)",
      }}>
        <div style={{ fontSize: 36, marginBottom: 12 }}>⚠️</div>
        <div style={{ fontWeight: 600, marginBottom: 8, color: "#0F172A" }}>Upload Failed</div>
        <div style={{ fontSize: 12, color: "#64748B", marginBottom: 16 }}>{error}</div>
        <button
          onClick={onRetry}
          style={{
            padding:      "9px 24px",
            background:   diseaseColor,
            border:       "none",
            borderRadius: 8,
            color:        "#FFFFFF",
            fontWeight:   600,
            fontSize:     13,
            cursor:       "pointer",
            fontFamily:   "inherit",
          }}
        >
          Try again
        </button>
      </div>
    </div>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// IMAGE ANALYSIS MESSAGE BUBBLE
// Used in PatientApp to display the AI's image analysis in the chat
// ═══════════════════════════════════════════════════════════════════════════════

export function ImageAnalysisMessage({
  message,        // { content, imageLabel, imageType, keyValues, clinicalObs,
                  //   hasCriticalValues, criticalFlags, f1Score, visionConfidence }
  disease,
  agentId,
  conversationId,
  preview,        // base64 preview URL shown inline
  onFollowUpSelect, // NEW: callback to start chatting
}) {
  const [showDetails, setShowDetails] = useState(false);
  const diseaseColor = disease?.color || "#2563EB";
  const typeIcon     = TYPE_ICONS[message.imageType] || TYPE_ICONS.default;

  return (
    <div style={{ display: "flex", gap: 10, marginBottom: 6, animation: "slideIn .2s ease" }}>
      {/* Avatar */}
      <div style={{
        width:          28,
        height:         28,
        borderRadius:   8,
        background:     diseaseColor,
        display:        "flex",
        alignItems:     "center",
        justifyContent: "center",
        fontSize:       10,
        color:          "#FFFFFF",
        fontWeight:     700,
        flexShrink:     0,
        marginTop:      2,
      }}>
        🔬
      </div>

      <div style={{ flex: 1 }}>
        {/* Image type badge */}
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 5 }}>
          <span style={{
            fontSize:     10,
            fontWeight:   600,
            color:        diseaseColor,
            background:   diseaseColor + "15",
            padding:      "2px 8px",
            borderRadius: 10,
            border:       `1px solid ${diseaseColor}33`,
          }}>
            {typeIcon} {message.imageLabel || "Medical Image Analysis"}
          </span>
          {message.hasCriticalValues && (
            <span style={{
              fontSize:     10,
              fontWeight:   700,
              color:        "#B91C1C",
              background:   "#FEF2F2",
              padding:      "2px 8px",
              borderRadius: 10,
              border:       "1px solid #FECACA",
              animation:    "pulse 1.5s ease infinite",
            }}>
              ⚠️ CRITICAL VALUES
            </span>
          )}
        </div>

        {/* Image thumbnail + analysis card */}
        <div style={{
          background:   "#FFFFFF",
          border:       "1px solid #E2E8F0",
          borderRadius: "2px 12px 12px 12px",
          overflow:     "hidden",
          boxShadow:    "0 1px 4px rgba(0,0,0,.06)",
        }}>
          {/* Image thumbnail */}
          {preview && (
            <div style={{
              background:    "#F8FAFC",
              borderBottom:  "1px solid #E2E8F0",
              padding:       8,
              display:       "flex",
              alignItems:    "center",
              gap:           8,
            }}>
              <img
                src={preview}
                alt="Uploaded medical image"
                style={{
                  height:       48,
                  width:        64,
                  objectFit:    "cover",
                  borderRadius: 6,
                  border:       "1px solid #E2E8F0",
                }}
              />
              <div style={{ fontSize: 11, color: "#64748B", lineHeight: 1.4 }}>
                <div style={{ fontWeight: 500, color: "#374151" }}>{message.imageLabel}</div>
                <div>F1 Score: {(message.f1Score * 100).toFixed(0)}% medical relevance</div>
                <div>Vision confidence: {(message.visionConfidence * 100).toFixed(0)}%</div>
              </div>
            </div>
          )}

          {/* Analysis text */}
          <div style={{ padding: "12px 14px", fontSize: 13, lineHeight: 1.65, color: "#334155" }}>
            {message.content.split("\n").map((line, i) => {
              const isHeader = line.startsWith("**") && line.endsWith("**");
              const clean    = line.replace(/\*\*/g, "");
              if (isHeader) return (
                <div key={i} style={{ fontWeight: 600, color: "#0F172A", marginTop: 10, marginBottom: 4 }}>
                  {clean}
                </div>
              );
              if (line.startsWith("- ") || line.startsWith("• "))
                return (
                  <div key={i} style={{ display: "flex", gap: 6, paddingLeft: 8, marginBottom: 3 }}>
                    <span style={{ color: diseaseColor, flexShrink: 0 }}>•</span>
                    <span>{line.slice(2)}</span>
                  </div>
                );
              if (line.trim() === "") return <div key={i} style={{ height: 5 }} />;
              return <div key={i} style={{ marginBottom: 2 }}>{line}</div>;
            })}
          </div>

          {/* Key values expandable */}
          {message.keyValues && Object.keys(message.keyValues).length > 0 && (
            <div style={{ borderTop: "1px solid #F1F5F9" }}>
              <button
                onClick={() => setShowDetails(!showDetails)}
                style={{
                  width:        "100%",
                  padding:      "7px 14px",
                  background:   "transparent",
                  border:       "none",
                  cursor:       "pointer",
                  fontSize:     11,
                  color:        diseaseColor,
                  fontFamily:   "inherit",
                  display:      "flex",
                  alignItems:   "center",
                  gap:          4,
                }}
              >
                {showDetails ? "▾" : "▸"} Extracted values ({Object.keys(message.keyValues).length})
              </button>
              {showDetails && (
                <div style={{
                  padding:    "0 14px 10px",
                  display:    "flex",
                  flexWrap:   "wrap",
                  gap:        6,
                }}>
                  {Object.entries(message.keyValues).map(([k, v]) => (
                    <div key={k} style={{
                      background:   diseaseColor + "10",
                      border:       `1px solid ${diseaseColor}30`,
                      borderRadius: 6,
                      padding:      "3px 8px",
                      fontSize:     10,
                    }}>
                      <span style={{ color: "#64748B" }}>{k.replace(/_/g, " ")}: </span>
                      <span style={{ fontWeight: 600, color: diseaseColor }}>{v}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* 🆕 Suggested Follow-ups */}
          <div style={{
            padding:      "10px 14px",
            background:   "#F8FAFC",
            borderTop:    "1px solid #E2E8F0",
          }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: "#64748B", marginBottom: 8, textTransform: "uppercase", letterSpacing: "0.05em" }}>
              Suggested follow-up queries
            </div>
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {(message.followUpQuestions && message.followUpQuestions.length > 0 ? message.followUpQuestions : [
                "Explain the key findings again",
                "What questions should I ask my doctor?",
                "Are these values within normal ranges?",
                "Suggest lifestyle changes based on this"
              ]).map(q => (
                <button
                  key={q}
                  onClick={() => onFollowUpSelect && onFollowUpSelect(q)}
                  style={{
                    padding:      "5px 10px",
                    background:   "#FFFFFF",
                    border:       "1px solid #E2E8F0",
                    borderRadius: 12,
                    fontSize:     11,
                    color:        diseaseColor,
                    cursor:       "pointer",
                    fontFamily:   "inherit",
                    transition:   "all .15s",
                  }}
                  onMouseEnter={e => {
                    e.currentTarget.style.background = diseaseColor + "08";
                    e.currentTarget.style.borderColor = diseaseColor;
                  }}
                  onMouseLeave={e => {
                    e.currentTarget.style.background = "#FFFFFF";
                    e.currentTarget.style.borderColor = "#E2E8F0";
                  }}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
      <style>{`@keyframes slideIn{from{opacity:0;transform:translateY(6px)}to{opacity:1;transform:translateY(0)}} @keyframes pulse{0%,100%{opacity:1}50%{opacity:.6}}`}</style>
    </div>
  );
}