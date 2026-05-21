// ═══════════════════════════════════════════════════════════════════════════════
// FILE: frontend/src/components/VoiceChat.jsx
// PRISM Voice Chat — Interactive Telemedicine Voice Interface
// ═══════════════════════════════════════════════════════════════════════════════

import { useState, useRef, useCallback, useEffect } from "react";
import { useAuthStore } from "../store/auth";

const API = "/api";

// ─── Recording states ─────────────────────────────────────────────────────────
const PHASE = {
  IDLE:         "idle",
  LISTENING:    "listening",
  PROCESSING:   "processing",
  TRANSCRIBED:  "transcribed",   // show transcript, allow edit before sending
  SENDING:      "sending",
  SPEAKING:     "speaking",      // AI is speaking the response
  DONE:         "done",
  ERROR:        "error",
  GUARDRAIL:    "guardrail",
};

// ─── Language → BCP-47 for Web Speech API ─────────────────────────────────────
const LANG_CODES = {
  en: "en-US", es: "es-MX", pt: "pt-BR",
  hi: "hi-IN", te: "te-IN", pa: "pa-IN",
};

// ─── TTS voice selection (Web Speech API) ─────────────────────────────────────
function getBestVoice(lang = "en") {
  if (!window.speechSynthesis) return null;
  const voices = window.speechSynthesis.getVoices();
  const bcp    = LANG_CODES[lang] || "en-US";
  const exact  = voices.find(v => v.lang === bcp && !v.localService);
  const partial = voices.find(v => v.lang.startsWith(bcp.split("-")[0]) && !v.localService);
  const local  = voices.find(v => v.lang === bcp);
  return exact || partial || local || voices[0] || null;
}

// ─── Draw animated waveform on canvas ────────────────────────────────────────
function drawWaveform(canvas, analyser, color, animRef) {
  if (!canvas || !analyser) return;
  const ctx    = canvas.getContext("2d");
  const buf    = new Uint8Array(analyser.frequencyBinCount);
  const W      = canvas.width;
  const H      = canvas.height;

  function draw() {
    animRef.current = requestAnimationFrame(draw);
    analyser.getByteTimeDomainData(buf);
    ctx.clearRect(0, 0, W, H);
    ctx.lineWidth   = 2.5;
    ctx.strokeStyle = color;
    ctx.shadowColor = color;
    ctx.shadowBlur  = 8;
    ctx.beginPath();
    const slice = W / buf.length;
    let x = 0;
    for (let i = 0; i < buf.length; i++) {
      const v  = buf[i] / 128.0;
      const y  = (v * H) / 2;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
      x += slice;
    }
    ctx.lineTo(W, H / 2);
    ctx.stroke();
  }
  draw();
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN VOICE CHAT COMPONENT
// ═══════════════════════════════════════════════════════════════════════════════

export default function VoiceChat({
  agentId,
  conversationId,
  diseaseColor  = "#2563EB",
  diseaseName   = "Medical",
  language      = "en",
  onMessageAdded,   // callback({role, content, isVoice, voiceData}) → adds to chat
}) {
  const storeToken = useAuthStore(state => state.token);
  const [phase, setPhase]           = useState(PHASE.IDLE);
  const [transcript, setTranscript] = useState("");
  const [editedText, setEditedText] = useState("");
  const [response, setResponse]     = useState("");
  const [ttsText, setTtsText]       = useState("");
  const [error, setError]           = useState("");
  const [guardrail, setGuardrail]   = useState("");
  const [voiceData, setVoiceData]   = useState(null);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const [recordDuration, setRecordDuration] = useState(0);

  // Refs
  const mediaRecorder   = useRef(null);
  const audioChunks     = useRef([]);
  const audioContext    = useRef(null);
  const analyser        = useRef(null);
  const canvasRef       = useRef(null);
  const waveformAnim    = useRef(null);
  const timerRef        = useRef(null);
  const streamRef       = useRef(null);
  const utteranceRef    = useRef(null);
  const audioRef        = useRef(null);

  // ── Load voices ─────────────────────────────────────────────────────────────
  useEffect(() => {
    if (window.speechSynthesis) {
      window.speechSynthesis.onvoiceschanged = () => {};
      window.speechSynthesis.getVoices();
    }
    return () => {
      if (mediaRecorder.current && mediaRecorder.current.state !== "inactive") {
        mediaRecorder.current.stop();
      }
      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, []);

  // ── Process recorded audio ──────────────────────────────────────────────────
  const processAudio = useCallback(async () => {
    if (audioChunks.current.length === 0) {
      setError("No audio data captured. Please check your microphone.");
      setPhase(PHASE.ERROR);
      return;
    }

    setPhase(PHASE.PROCESSING);
    const blob     = new Blob(audioChunks.current, { type: "audio/webm" });
    console.log(`[VOICE] Captured ${blob.size} bytes`);
    
    const formData = new FormData();
    formData.append("file",      blob,      "voice.webm");
    formData.append("agent_id",  agentId);
    formData.append("language",  language);

    const token = storeToken || localStorage.getItem("prism_token");
    try {
      const res  = await fetch(`${API}/voice/transcribe`, {
        method:  "POST",
        headers: { Authorization: `Bearer ${token}` },
        body:    formData,
      });
      const data = await res.json();
      console.log("[VOICE_RESPONSE]", data);

      if (!data.success && data.stage === "medical_validation") {
        setGuardrail(data.guardrail_message || "This doesn't seem to be a medical query. Please ask about your health.");
        setPhase(PHASE.GUARDRAIL);
        speakText(data.guardrail_message || "This doesn't seem to be a medical query. Please ask about your health.");
        return;
      }

      if (!data.success || !data.transcript) {
        setError(data.guardrail_message || data.error || data.detail || "The AI could not interpret the audio. Please speak clearly and try again.");
        setPhase(PHASE.ERROR);
        return;
      }

      if (!data.is_medical) {
        setGuardrail(data.guardrail_message);
        setPhase(PHASE.GUARDRAIL);
        speakText(data.guardrail_message);
        return;
      }

      setTranscript(data.transcript);
      setEditedText(data.enriched_query || data.transcript);
      setVoiceData(data);
      setPhase(PHASE.TRANSCRIBED);

    } catch (e) {
      console.error("[VOICE_FETCH_ERROR]", e);
      setError("Network error during transcription. Please try again.");
      setPhase(PHASE.ERROR);
    }
  }, [agentId, language]);

  // ── Start recording ─────────────────────────────────────────────────────────
  const startRecording = useCallback(async () => {
    setPhase(PHASE.LISTENING);
    setError("");
    setTranscript("");
    setEditedText("");
    setResponse("");
    setGuardrail("");
    audioChunks.current = [];
    setRecordDuration(0);

    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      streamRef.current = stream;

      // Web Audio analyser for waveform
      audioContext.current = new (window.AudioContext || window.webkitAudioContext)();
      const source = audioContext.current.createMediaStreamSource(stream);
      analyser.current = audioContext.current.createAnalyser();
      analyser.current.fftSize = 256;
      source.connect(analyser.current);
      drawWaveform(canvasRef.current, analyser.current, diseaseColor, waveformAnim);

      // MediaRecorder
      const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
        ? "audio/webm;codecs=opus"
        : "audio/webm";

      mediaRecorder.current = new MediaRecorder(stream, { mimeType });
      mediaRecorder.current.ondataavailable = e => {
        if (e.data.size > 0) audioChunks.current.push(e.data);
      };
      mediaRecorder.current.onstop = processAudio;
      
      // Start recording — using a larger slice or no slice for stability
      mediaRecorder.current.start(); 

      // Duration counter
      timerRef.current = setInterval(() => {
        setRecordDuration(d => d + 1);
      }, 1000);

    } catch (e) {
      console.error("[VOICE_START_ERROR]", e);
      setError("Microphone access denied. Please check your system permissions.");
      setPhase(PHASE.ERROR);
    }
  }, [diseaseColor, processAudio]);

  // ── Stop recording ──────────────────────────────────────────────────────────
  const stopRecording = useCallback(() => {
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    if (waveformAnim.current) { cancelAnimationFrame(waveformAnim.current); waveformAnim.current = null; }
    if (mediaRecorder.current && mediaRecorder.current.state !== "inactive") {
      mediaRecorder.current.stop();
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach(t => t.stop());
      streamRef.current = null;
    }
    if (audioContext.current) {
      audioContext.current.close().catch(() => {});
      audioContext.current = null;
    }
  }, []);


  // ── Send transcript to agent ────────────────────────────────────────────────
  const sendToAgent = useCallback(async () => {
    if (!editedText.trim()) return;
    setPhase(PHASE.SENDING);

    const blob     = new Blob(audioChunks.current, { type: "audio/webm" });
    const formData = new FormData();
    formData.append("file",            blob, "voice.webm");
    formData.append("agent_id",        agentId);
    formData.append("language",        language);
    formData.append("tts_enabled",     "true");
    if (conversationId) formData.append("conversation_id", conversationId);

    const token = storeToken || localStorage.getItem("prism_token");
    try {
      const res  = await fetch(`${API}/voice/chat`, {
        method:  "POST",
        headers: { Authorization: `Bearer ${token}` },
        body:    formData,
      });
      const data = await res.json();

      if (!data.success) {
        const fallbackMsg = data.guardrail_message || data.error || data.detail || "Something went wrong. Please try again.";
        setGuardrail(fallbackMsg);
        setPhase(PHASE.GUARDRAIL);
        speakText(fallbackMsg);
        return;
      }

      setResponse(data.response);
      setTtsText(data.tts_text || data.response);

      // Add to chat
      if (onMessageAdded) {
        onMessageAdded({
          role: "user", content: editedText, isVoice: true,
          voiceData: { transcript, f1Score: voiceData?.f1_score },
        });
        onMessageAdded({
          role: "assistant", content: data.response, isVoice: true,
          voiceData: data, id: data.message_id,
          routeDecision: data.route_decision, confidence: data.confidence,
          respondedBy: data.responded_by,
        });
      }

      setPhase(PHASE.SPEAKING);
      if (data.tts_audio_b64) {
        playAudioB64(data.tts_audio_b64, () => setPhase(PHASE.DONE));
      } else {
        speakText(data.tts_text || data.response, () => setPhase(PHASE.DONE));
      }

    } catch (e) {
      setError("Network error. Please try again.");
      setPhase(PHASE.ERROR);
    }
  }, [editedText, agentId, language, conversationId, transcript, voiceData, onMessageAdded]);

  // ── Browser TTS ─────────────────────────────────────────────────────────────
  const speakText = useCallback((text, onEnd) => {
    if (!window.speechSynthesis || !text) { onEnd?.(); return; }
    window.speechSynthesis.cancel();
    const utt        = new SpeechSynthesisUtterance(text);
    utt.lang         = LANG_CODES[language] || "en-US";
    utt.rate         = 0.92;
    utt.pitch        = 1.0;
    utt.volume       = 1.0;
    const voice      = getBestVoice(language);
    if (voice) utt.voice = voice;
    utt.onstart      = () => setIsSpeaking(true);
    utt.onend        = () => { setIsSpeaking(false); onEnd?.(); };
    utt.onerror      = () => { setIsSpeaking(false); onEnd?.(); };
    utteranceRef.current = utt;
    window.speechSynthesis.speak(utt);
  }, [language]);

  // ── Server-side base64 TTS ──────────────────────────────────────────────────
  const playAudioB64 = useCallback((b64Data, onEnd) => {
    try {
      if (audioRef.current) {
        audioRef.current.pause();
        audioRef.current = null;
      }
      setIsSpeaking(true);
      const audioUrl = `data:audio/mp3;base64,${b64Data}`;
      const snd = new Audio(audioUrl);
      audioRef.current = snd;
      snd.onended = () => {
        setIsSpeaking(false);
        onEnd?.();
      };
      snd.onerror = () => {
        setIsSpeaking(false);
        onEnd?.();
      };
      snd.play().catch(err => {
        console.error("Audio playback failed, falling back to synthesis:", err);
        setIsSpeaking(false);
        onEnd?.();
      });
    } catch (e) {
      console.error("Failed to play base64 audio", e);
      setIsSpeaking(false);
      onEnd?.();
    }
  }, []);

  const stopSpeaking = useCallback(() => {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current = null;
    }
    setIsSpeaking(false);
    setPhase(PHASE.DONE);
  }, []);

  const reset = useCallback(() => {
    stopSpeaking();
    stopRecording();
    setPhase(PHASE.IDLE);
    setTranscript(""); setEditedText(""); setResponse("");
    setTtsText(""); setError(""); setGuardrail("");
    setVoiceData(null); setRecordDuration(0);
  }, [stopSpeaking, stopRecording]);

  // ─── RENDER ─────────────────────────────────────────────────────────────────
  return (
    <div style={{ fontFamily: "system-ui, -apple-system, sans-serif" }}>

      {/* ── IDLE: Mic button ─────────────────────────────────────────────────── */}
      {phase === PHASE.IDLE && (
        <button
          onClick={startRecording}
          title="Start voice session"
          style={{
            display:      "flex",
            alignItems:   "center",
            gap:          5,
            padding:      "6px 12px",
            background:   "transparent",
            border:       `1px solid ${diseaseColor}55`,
            borderRadius: 8,
            color:        diseaseColor,
            cursor:       "pointer",
            fontSize:     12,
            fontWeight:   500,
            fontFamily:   "inherit",
            flexShrink:   0,
            transition:   "all .15s",
          }}
          onMouseEnter={e => { e.currentTarget.style.background = diseaseColor + "15"; e.currentTarget.style.borderColor = diseaseColor; }}
          onMouseLeave={e => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.borderColor = diseaseColor + "55"; }}
        >
          <span style={{ fontSize: 16 }}>🎙️</span> Speak
        </button>
      )}

      {/* ── Full voice overlay (all non-idle states) ──────────────────────── */}
      {phase !== PHASE.IDLE && (
        <VoiceOverlay
          phase={phase}
          transcript={transcript}
          editedText={editedText}
          setEditedText={setEditedText}
          response={response}
          ttsText={ttsText}
          error={error}
          guardrail={guardrail}
          recordDuration={recordDuration}
          isSpeaking={isSpeaking}
          voiceData={voiceData}
          diseaseColor={diseaseColor}
          diseaseName={diseaseName}
          canvasRef={canvasRef}
          onStop={stopRecording}
          onSend={sendToAgent}
          onStopSpeaking={stopSpeaking}
          onReset={reset}
          onReRecord={() => { reset(); setTimeout(startRecording, 200); }}
        />
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// VOICE OVERLAY MODAL
// ═══════════════════════════════════════════════════════════════════════════════
function VoiceOverlay({
  phase, transcript, editedText, setEditedText, response, ttsText,
  error, guardrail, recordDuration, isSpeaking, voiceData,
  diseaseColor, diseaseName, canvasRef,
  onStop, onSend, onStopSpeaking, onReset, onReRecord,
}) {
  const fmtTime = s => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

  const STEP_LABELS = {
    [PHASE.LISTENING]:   { icon: "🔴", label: "Listening…",               sub: "Speak your medical question clearly" },
    [PHASE.PROCESSING]:  { icon: "⚙️", label: "Transcribing…",             sub: "Converting your voice to text" },
    [PHASE.TRANSCRIBED]: { icon: "✏️", label: "Review & edit transcript",  sub: "Edit if needed, then send" },
    [PHASE.SENDING]:     { icon: "🤖", label: "Agent is thinking…",        sub: "Generating personalised response" },
    [PHASE.SPEAKING]:    { icon: "🔊", label: "PRISM is speaking",          sub: "Listen to the response" },
    [PHASE.DONE]:        { icon: "✅", label: "Complete",                   sub: "Voice session finished" },
    [PHASE.ERROR]:       { icon: "⚠️", label: "Something went wrong",       sub: error },
    [PHASE.GUARDRAIL]:   { icon: "🚫", label: "Not a medical query",        sub: guardrail },
  };

  const current = STEP_LABELS[phase] || { icon: "🎙️", label: "Voice Chat", sub: "" };

  return (
    <div style={{
      position:       "fixed",
      inset:          0,
      background:     "rgba(8,20,44,.85)",
      display:        "flex",
      alignItems:     "center",
      justifyContent: "center",
      zIndex:         1200,
      backdropFilter: "blur(6px)",
      animation:      "fadeIn .2s ease",
    }}>
      <div style={{
        background:   "#0D1E35",
        borderRadius: 20,
        width:        "100%",
        maxWidth:     520,
        overflow:     "hidden",
        boxShadow:    `0 30px 80px rgba(0,0,0,.6), 0 0 0 1px ${diseaseColor}33`,
        fontFamily:   "system-ui, -apple-system, sans-serif",
      }}>

        {/* ── Header ────────────────────────────────────────────────────────── */}
        <div style={{
          background:    "#06111F",
          padding:       "14px 18px",
          display:       "flex",
          alignItems:    "center",
          gap:           12,
          borderBottom:  `1px solid ${diseaseColor}22`,
        }}>
          <div style={{
            width:          36,
            height:         36,
            borderRadius:   "50%",
            background:     diseaseColor + "22",
            border:         `2px solid ${diseaseColor}`,
            display:        "flex",
            alignItems:     "center",
            justifyContent: "center",
            fontSize:       18,
            flexShrink:     0,
            animation:      phase === PHASE.LISTENING ? "pulse 1.5s ease infinite" : "none",
          }}>
            {current.icon}
          </div>
          <div style={{ flex: 1 }}>
            <div style={{ color: "#FFFFFF", fontWeight: 700, fontSize: 14 }}>{current.label}</div>
            <div style={{ color: "#4B7CBE", fontSize: 11, marginTop: 1 }}>{diseaseName} · Voice Session</div>
          </div>
          {phase === PHASE.LISTENING && (
            <div style={{ color: "#EF4444", fontSize: 11, fontWeight: 600,
                          display: "flex", alignItems: "center", gap: 4 }}>
              <div style={{ width: 7, height: 7, borderRadius: "50%",
                            background: "#EF4444", animation: "blink 1s ease infinite" }} />
              {fmtTime(recordDuration)}
            </div>
          )}
          <button onClick={onReset}
            style={{ background: "none", border: "none", color: "#4B7CBE",
                     fontSize: 20, cursor: "pointer", padding: "2px 6px" }}>×</button>
        </div>

        {/* ── Body ──────────────────────────────────────────────────────────── */}
        <div style={{ padding: "20px 22px" }}>

          {/* Waveform canvas (visible while recording) */}
          {phase === PHASE.LISTENING && (
            <div style={{ marginBottom: 20 }}>
              <canvas
                ref={canvasRef}
                width={472}
                height={72}
                style={{
                  width:        "100%",
                  height:       72,
                  borderRadius: 10,
                  background:   "#06111F",
                  border:       `1px solid ${diseaseColor}33`,
                  display:      "block",
                }}
              />
              <div style={{ textAlign: "center", color: "#4B7CBE", fontSize: 11, marginTop: 8 }}>
                {current.sub}
              </div>
            </div>
          )}

          {/* Processing spinner */}
          {(phase === PHASE.PROCESSING || phase === PHASE.SENDING) && (
            <div style={{ textAlign: "center", padding: "20px 0" }}>
              <div style={{
                width: 52, height: 52, borderRadius: "50%",
                border: `3px solid ${diseaseColor}33`,
                borderTop: `3px solid ${diseaseColor}`,
                margin: "0 auto 14px",
                animation: "spin 1s linear infinite",
              }} />
              <div style={{ color: "#9BAFC7", fontSize: 12 }}>{current.sub}</div>
            </div>
          )}

          {/* Transcript editor */}
          {phase === PHASE.TRANSCRIBED && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: "#4B7CBE", fontSize: 10, fontWeight: 600,
                            letterSpacing: ".06em", marginBottom: 5 }}>
                TRANSCRIBED TEXT — edit if needed
              </div>
              <div style={{
                background:   "#06111F",
                border:       `1px solid ${diseaseColor}44`,
                borderRadius: 8,
                padding:      "8px 10px",
                fontSize:     11,
                color:        "#6B8CAE",
                marginBottom: 8,
                lineHeight:   1.4,
              }}>
                Raw: "{transcript}"
              </div>
              <div style={{ color: "#4B7CBE", fontSize: 10, marginBottom: 4 }}>
                Enriched query (edit before sending):
              </div>
              <textarea
                value={editedText}
                onChange={e => setEditedText(e.target.value)}
                rows={3}
                style={{
                  width:        "100%",
                  background:   "#0F1E33",
                  border:       `1px solid ${diseaseColor}66`,
                  borderRadius: 8,
                  color:        "#FFFFFF",
                  fontSize:     13,
                  padding:      "10px 12px",
                  resize:       "none",
                  outline:      "none",
                  fontFamily:   "inherit",
                  boxSizing:    "border-box",
                }}
              />
              {voiceData?.medical_terms?.length > 0 && (
                <div style={{ display: "flex", gap: 4, flexWrap: "wrap", marginTop: 6 }}>
                  <span style={{ fontSize: 9, color: "#4B7CBE" }}>Medical terms detected:</span>
                  {voiceData.medical_terms.map(t => (
                    <span key={t} style={{
                      fontSize: 9, color: diseaseColor,
                      background: diseaseColor + "20",
                      padding: "1px 5px", borderRadius: 4,
                    }}>{t}</span>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* AI response (speaking phase) */}
          {(phase === PHASE.SPEAKING || phase === PHASE.DONE) && response && (
            <div style={{ marginBottom: 16 }}>
              <div style={{ color: "#4B7CBE", fontSize: 10, fontWeight: 600,
                            letterSpacing: ".06em", marginBottom: 8 }}>
                {phase === PHASE.SPEAKING ? "🔊 PRISM IS SPEAKING" : "📋 RESPONSE"}
              </div>
              <div style={{
                background:   "#06111F",
                border:       `1px solid ${diseaseColor}33`,
                borderRadius: 10,
                padding:      "12px 14px",
                fontSize:     12,
                color:        "#C8D8E8",
                lineHeight:   1.7,
                maxHeight:    200,
                overflowY:    "auto",
              }}>
                {response.split("\n").map((line, i) => {
                  const clean = line.replace(/\*\*/g, "");
                  if (line.trim() === "") return <div key={i} style={{ height: 5 }} />;
                  if (line.startsWith("**") || line.startsWith("##"))
                    return <div key={i} style={{ fontWeight: 600, color: "#FFFFFF", marginTop: 8 }}>{clean}</div>;
                  if (line.startsWith("- ") || line.startsWith("• "))
                    return <div key={i} style={{ display: "flex", gap: 6, paddingLeft: 6 }}>
                      <span style={{ color: diseaseColor }}>•</span><span>{line.slice(2)}</span></div>;
                  return <div key={i}>{line}</div>;
                })}
              </div>
            </div>
          )}

          {/* Guardrail */}
          {(phase === PHASE.GUARDRAIL || phase === PHASE.ERROR) && (
            <div style={{
              background:   "#1A0505",
              border:       "1px solid #EF444422",
              borderRadius: 10,
              padding:      "14px 16px",
              marginBottom: 16,
              fontSize:     12,
              color:        "#FCA5A5",
              lineHeight:   1.6,
            }}>
              {(guardrail || error)}
            </div>
          )}

          {/* Speaking pulse bars */}
          {phase === PHASE.SPEAKING && isSpeaking && (
            <div style={{ display: "flex", alignItems: "flex-end", gap: 3,
                          justifyContent: "center", height: 32, marginBottom: 12 }}>
              {[1,1.5,2,2.5,2,1.5,1].map((h, i) => (
                <div key={i} style={{
                  width:        4,
                  height:       h * 10,
                  borderRadius: 2,
                  background:   diseaseColor,
                  animation:    `soundBar .6s ease ${i * .08}s infinite alternate`,
                }} />
              ))}
            </div>
          )}
        </div>

        {/* ── Actions ───────────────────────────────────────────────────────── */}
        <div style={{
          padding:       "0 22px 20px",
          display:       "flex",
          gap:           10,
          flexWrap:      "wrap",
        }}>
          {phase === PHASE.LISTENING && (
            <>
              <VoiceBtn color="#EF4444" onClick={onStop} style={{ flex: 1 }}>
                ⏹ Stop Recording
              </VoiceBtn>
            </>
          )}

          {phase === PHASE.TRANSCRIBED && (
            <>
              <VoiceBtn color="#4B7CBE" onClick={onReRecord} style={{ flex: "0 0 auto" }}>
                🔄 Re-record
              </VoiceBtn>
              <VoiceBtn color={diseaseColor} onClick={onSend}
                disabled={!editedText.trim()} style={{ flex: 1 }}>
                🤖 Send to Agent
              </VoiceBtn>
            </>
          )}

          {phase === PHASE.SPEAKING && (
            <>
              <VoiceBtn color="#6B7280" onClick={onStopSpeaking} style={{ flex: "0 0 auto" }}>
                ⏸ Stop Speaking
              </VoiceBtn>
              <VoiceBtn color={diseaseColor} onClick={onReset} style={{ flex: 1 }}>
                🎙️ New Question
              </VoiceBtn>
            </>
          )}

          {(phase === PHASE.DONE || phase === PHASE.GUARDRAIL || phase === PHASE.ERROR) && (
            <>
              <VoiceBtn color="#4B7CBE" onClick={onReset} style={{ flex: "0 0 auto" }}>
                Close
              </VoiceBtn>
              <VoiceBtn color={diseaseColor} onClick={onReRecord} style={{ flex: 1 }}>
                🎙️ Ask Another Question
              </VoiceBtn>
            </>
          )}
        </div>
      </div>

      <style>{`
        @keyframes fadeIn{from{opacity:0}to{opacity:1}}
        @keyframes spin{to{transform:rotate(360deg)}}
        @keyframes pulse{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.95)}}
        @keyframes blink{0%,100%{opacity:1}50%{opacity:.2}}
        @keyframes soundBar{from{transform:scaleY(.4)}to{transform:scaleY(1)}}
      `}</style>
    </div>
  );
}

function VoiceBtn({ children, onClick, disabled, color, style = {} }) {
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      style={{
        padding:      "10px 16px",
        background:   disabled ? "#1A2D45" : color,
        border:       "none",
        borderRadius: 8,
        color:        disabled ? "#3D5C82" : "#FFFFFF",
        fontSize:     12,
        fontWeight:   600,
        cursor:       disabled ? "not-allowed" : "pointer",
        fontFamily:   "inherit",
        transition:   "all .15s",
        ...style,
      }}
    >
      {children}
    </button>
  );
}


// ═══════════════════════════════════════════════════════════════════════════════
// VOICE MESSAGE BUBBLE
// Rendered in the chat alongside text messages
// ═══════════════════════════════════════════════════════════════════════════════
export function VoiceMessage({ message, disease }) {
  const [playing, setPlaying] = useState(false);
  const audioRef = useRef(null);
  const color = disease?.color || "#2563EB";

  // Clean up audio on unmount
  useEffect(() => {
    return () => {
      if (audioRef.current) {
        audioRef.current.pause();
      }
    };
  }, []);

  const speakThis = () => {
    // Premium server-side base64 playback
    if (message.voiceData?.tts_audio_b64) {
      if (playing) {
        if (audioRef.current) audioRef.current.pause();
        setPlaying(false);
        return;
      }
      try {
        const audioUrl = `data:audio/mp3;base64,${message.voiceData.tts_audio_b64}`;
        const snd = new Audio(audioUrl);
        audioRef.current = snd;
        snd.onended = () => setPlaying(false);
        snd.onerror = () => setPlaying(false);
        setPlaying(true);
        snd.play().catch(() => setPlaying(false));
      } catch (e) {
        setPlaying(false);
      }
      return;
    }

    // Fallback to browser synthesis
    if (!window.speechSynthesis) return;
    if (playing) { window.speechSynthesis.cancel(); setPlaying(false); return; }
    const utt  = new SpeechSynthesisUtterance(message.ttsText || message.content);
    utt.lang   = "en-US";
    utt.rate   = 0.92;
    utt.onstart = () => setPlaying(true);
    utt.onend   = () => setPlaying(false);
    utt.onerror = () => setPlaying(false);
    window.speechSynthesis.speak(utt);
  };

  if (message.role === "user") {
    return (
      <div style={{ display: "flex", justifyContent: "flex-end", marginBottom: 10, gap: 8 }}>
        <div style={{
          maxWidth:     "68%",
          background:   "#F1F5F9",
          border:       "1px solid #E2E8F0",
          borderRadius: "12px 12px 2px 12px",
          padding:      "9px 13px",
          fontSize:     13,
          lineHeight:   1.6,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: 5, marginBottom: 4 }}>
            <span style={{ fontSize: 11, color, fontWeight: 500 }}>🎙️ Voice</span>
            {message.voiceData?.f1Score && (
              <span style={{ fontSize: 9, color: "#94A3B8" }}>
                Medical: {(message.voiceData.f1Score * 100).toFixed(0)}%
              </span>
            )}
          </div>
          {message.content}
        </div>
        <div style={{
          width: 26, height: 26, borderRadius: "50%",
          background: "#E2E8F0", display: "flex", alignItems: "center",
          justifyContent: "center", fontSize: 10, color: "#64748B",
          fontWeight: 600, flexShrink: 0, marginTop: 2,
        }}>You</div>
      </div>
    );
  }

  return (
    <div style={{ display: "flex", gap: 10, marginBottom: 8 }}>
      <div style={{
        width: 28, height: 28, borderRadius: 8, background: color,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 10, color: "#FFFFFF", fontWeight: 700, flexShrink: 0, marginTop: 2,
      }}>AI</div>
      <div style={{ flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginBottom: 4 }}>
          <span style={{ fontSize: 10, color: color, fontWeight: 500,
                          background: color + "15", padding: "1px 7px", borderRadius: 10 }}>
            🎙️ Voice Response
          </span>
          <button
            onClick={speakThis}
            style={{
              background:   playing ? color + "22" : "transparent",
              border:       `1px solid ${color}44`,
              borderRadius: 6,
              padding:      "1px 8px",
              fontSize:     10,
              color:        color,
              cursor:       "pointer",
              fontFamily:   "inherit",
            }}
          >
            {playing ? "⏸ Stop" : "▶ Play"}
          </button>
        </div>
        <div style={{
          background: "#FFFFFF", border: "1px solid #E2E8F0",
          borderRadius: "2px 12px 12px 12px",
          padding: "10px 14px", fontSize: 13, lineHeight: 1.65,
          boxShadow: "0 1px 3px rgba(0,0,0,.06)",
        }}>
          {message.content}
        </div>
      </div>
    </div>
  );
}