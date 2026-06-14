import React, { useState, useRef } from "react";
import { BackendService } from "../Services/BackendService";

export default function VoiceWidget() {
  const [isRecording, setIsRecording] = useState(false);
  const [status, setStatus] = useState("idle"); // idle | recording | processing | done | error
  const [lastResult, setLastResult] = useState(null);
  const mediaRecorderRef = useRef(null);
  const chunksRef = useRef([]);

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });
      mediaRecorderRef.current = mediaRecorder;
      chunksRef.current = [];

      mediaRecorder.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mediaRecorder.onstop = async () => {
        stream.getTracks().forEach(t => t.stop());
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        await processAudio(blob);
      };

      mediaRecorder.start();
      setIsRecording(true);
      setStatus("recording");
      setLastResult(null);

      // Auto-stop after 5 seconds
      setTimeout(() => {
        if (mediaRecorder.state === "recording") stopRecording();
      }, 5000);
    } catch (err) {
      setStatus("error");
      setLastResult({ message: "Microphone access denied. Please allow microphone access." });
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && mediaRecorderRef.current.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    setIsRecording(false);
    setStatus("processing");
  };

  const processAudio = async (blob) => {
    try {
      const result = await BackendService.transcribeVoice(blob);
      setLastResult(result);
      setStatus(result.executed ? "done" : "no_match");
    } catch (err) {
      setStatus("error");
      setLastResult({ message: "Transcription failed." });
    }
  };

  const statusConfig = {
    idle:       { color: "var(--textMuted)",    icon: "🎙️", label: "Tap to speak" },
    recording:  { color: "#ec7063",             icon: "⏹️", label: "Recording... (tap to stop)" },
    processing: { color: "#ffc837",             icon: "⚙️", label: "Processing..." },
    done:       { color: "var(--colorSuccess)", icon: "✅", label: "Command executed!" },
    no_match:   { color: "#ffc837",             icon: "❓", label: "Not recognised" },
    error:      { color: "var(--colorDanger)",  icon: "❌", label: "Error" },
  };
  const cfg = statusConfig[status];

  return (
    <div className="glassCard" style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
      <div className="cardHeader" style={{ marginBottom: "4px" }}>
        <h2>🎙️ Voice Control (Hindi / Hinglish)</h2>
        <span className="statusBadge" style={{ background: "rgba(38,194,129,0.1)", color: "var(--colorSuccess)", border: "1px solid rgba(38,194,129,0.2)", fontSize: "10px" }}>
          Whisper ASR
        </span>
      </div>

      <p style={{ fontSize: "11px", color: "var(--textMuted)" }}>
        Speak in Hindi or Hinglish: "geyser on", "batti off", "pooja mode", "padhai mode"
      </p>

      {/* Big mic button */}
      <div style={{ display: "flex", justifyContent: "center" }}>
        <button
          onClick={isRecording ? stopRecording : startRecording}
          disabled={status === "processing"}
          style={{
            width: "72px",
            height: "72px",
            borderRadius: "50%",
            background: isRecording
              ? "rgba(236,112,99,0.2)"
              : "rgba(255,255,255,0.04)",
            border: `2px solid ${cfg.color}`,
            fontSize: "28px",
            cursor: status === "processing" ? "wait" : "pointer",
            transition: "all 0.2s ease",
            boxShadow: isRecording ? `0 0 20px rgba(236,112,99,0.4)` : "none",
            animation: isRecording ? "pulse 1s infinite ease-in-out" : "none",
          }}
        >
          {cfg.icon}
        </button>
      </div>

      {/* Status label */}
      <div style={{ textAlign: "center", fontSize: "12px", fontWeight: "600", color: cfg.color }}>
        {cfg.label}
      </div>

      {/* Result card */}
      {lastResult && (
        <div style={{
          background: lastResult.executed ? "rgba(38,194,129,0.06)" : "rgba(255,200,55,0.06)",
          border: `1px solid ${lastResult.executed ? "rgba(38,194,129,0.2)" : "rgba(255,200,55,0.2)"}`,
          borderRadius: "8px",
          padding: "10px 12px",
          fontSize: "12px",
          display: "flex",
          flexDirection: "column",
          gap: "4px"
        }}>
          {lastResult.transcript && (
            <div>
              <span style={{ color: "var(--textMuted)", fontSize: "10px", textTransform: "uppercase" }}>Heard: </span>
              <span style={{ color: "white" }}>"{lastResult.transcript}"</span>
            </div>
          )}
          {lastResult.action && (
            <div>
              <span style={{ color: "var(--textMuted)", fontSize: "10px", textTransform: "uppercase" }}>Action: </span>
              <span style={{ color: "var(--colorSuccess)" }}>{lastResult.action}</span>
            </div>
          )}
          {lastResult.message && !lastResult.executed && (
            <div style={{ color: "#ffc837" }}>{lastResult.message}</div>
          )}
        </div>
      )}

      {/* Quick phrases hint */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px" }}>
        {["geyser on", "batti off", "pooja mode", "motor band", "padhai mode", "so jao"].map(phrase => (
          <span key={phrase} style={{
            fontSize: "10px", padding: "2px 7px",
            background: "rgba(255,255,255,0.03)",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: "10px", color: "var(--textMuted)"
          }}>
            {phrase}
          </span>
        ))}
      </div>
    </div>
  );
}
