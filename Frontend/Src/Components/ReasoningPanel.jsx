import React, { useState, useEffect } from "react";
import { BackendService } from "../Services/BackendService";

export default function ReasoningPanel({ lastTriggerResult }) {
  const [showRawContext, setShowRawContext] = useState(false);
  const [showRawOutput, setShowRawOutput] = useState(false);
  const [showRulesList, setShowRulesList] = useState(false);
  
  // Rule form states
  const [newRuleText, setNewRuleText] = useState("");
  const [newRuleCategory, setNewRuleCategory] = useState("routine");
  const [existingRules, setExistingRules] = useState([]);
  const [ruleStatus, setRuleStatus] = useState("");

  const fetchExistingRules = async () => {
    try {
      const rules = await BackendService.getVectorRules();
      setExistingRules(rules);
    } catch (e) {
      console.error("Error loading rules list:", e);
    }
  };

  useEffect(() => {
    fetchExistingRules();
  }, []);

  const handleAddRule = async (e) => {
    e.preventDefault();
    if (!newRuleText.trim()) return;
    try {
      setRuleStatus("⚙️ Generating Titan embeddings...");
      await BackendService.addVectorRule(newRuleText, newRuleCategory);
      setRuleStatus("✅ Rule embedded & saved to PostgreSQL!");
      setNewRuleText("");
      fetchExistingRules();
      setTimeout(() => setRuleStatus(""), 4000);
    } catch (err) {
      setRuleStatus("❌ Failed: " + err.message);
      setTimeout(() => setRuleStatus(""), 4000);
    }
  };

  if (!lastTriggerResult || !lastTriggerResult.decision) {
    return (
      <div className="glassCard" style={{ display: "flex", flexDirection: "column", gap: "16px", minHeight: "220px" }}>
        <div style={{ display: "flex", flexDirection: "column", gap: "12px", justifyContent: "center", alignItems: "center", flex: 1, color: "var(--textMuted)", textAlign: "center" }}>
          <span>🪔 Trigger a sensor event in the simulator to see AWS Bedrock reason in real time.</span>
        </div>
        
        {/* Render Vector Override Rule Editor even when no event triggered */}
        <div style={{ borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "12px" }}>
          {renderRuleForm()}
        </div>
      </div>
    );
  }

  const { prediction, decision, ragContext } = lastTriggerResult;
  const confidencePercent = Math.round((decision.confidence || prediction.confidence || 0.85) * 100);

  const getConfidenceColor = (score) => {
    if (score >= 85) return "var(--colorSuccess)";
    if (score >= 70) return "var(--colorWarning)";
    return "var(--colorDanger)";
  };

  function renderRuleForm() {
    return (
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        <h3 style={{ fontSize: "14px", fontWeight: "600", color: "white" }}>🧠 Add Custom Grounding / Override Rule</h3>
        <form onSubmit={handleAddRule} style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
          <textarea
            value={newRuleText}
            onChange={(e) => setNewRuleText(e.target.value)}
            placeholder="e.g. Never turn on Geyser when water level is critical."
            style={{
              width: "100%",
              height: "50px",
              padding: "8px",
              background: "#0c0d12",
              border: "1px solid rgba(255,255,255,0.08)",
              borderRadius: "6px",
              color: "white",
              fontSize: "12px",
              resize: "none",
              fontFamily: "var(--fontFamily)"
            }}
          />
          <div style={{ display: "flex", gap: "8px", alignItems: "center" }}>
            <select
              value={newRuleCategory}
              onChange={(e) => setNewRuleCategory(e.target.value)}
              style={{
                padding: "6px",
                background: "#0c0d12",
                border: "1px solid rgba(255,255,255,0.08)",
                borderRadius: "6px",
                color: "white",
                fontSize: "12px"
              }}
            >
              <option value="routine">Routine Heuristics</option>
              <option value="cultural">Cultural Protocol</option>
              <option value="safety">Safety Constraint</option>
            </select>
            <button type="submit" className="btn btnPrimary" style={{ fontSize: "12px", padding: "6px 12px" }}>
              💾 Embed & Store
            </button>
            {ruleStatus && (
              <span style={{ fontSize: "11px", color: "var(--textSecondary)", fontStyle: "italic" }}>
                {ruleStatus}
              </span>
            )}
          </div>
        </form>

        {/* Browser of stored vector rules */}
        <div>
          <button
            onClick={() => setShowRulesList(!showRulesList)}
            style={{ background: "none", border: "none", color: "var(--textSecondary)", fontSize: "11px", cursor: "pointer", display: "flex", alignItems: "center", gap: "4px", padding: "4px 0" }}
          >
            <span>{showRulesList ? "▼" : "▶"} Browse Stored Rules in Vector DB ({existingRules.length})</span>
          </button>
          {showRulesList && (
            <div style={{ 
              maxHeight: "120px", 
              overflowY: "auto", 
              background: "#050608", 
              borderRadius: "6px", 
              padding: "6px", 
              marginTop: "4px",
              display: "flex",
              flexDirection: "column",
              gap: "4px",
              border: "1px solid rgba(255,255,255,0.03)"
            }}>
              {existingRules.map((r, idx) => (
                <div key={idx} style={{ fontSize: "11px", color: "var(--textSecondary)", padding: "4px", borderBottom: "1px solid rgba(255,255,255,0.02)" }}>
                  <strong style={{ textTransform: "uppercase", color: r.category === 'cultural' ? '#c084fc' : r.category === 'safety' ? 'var(--colorDanger)' : 'var(--colorOrange)' }}>
                    [{r.category}]
                  </strong> {r.content}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="glassCard" style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      <div className="cardHeader">
        <h2>🧠 Bedrock Explainable AI Core</h2>
        <span className="statusBadge" style={{ background: "rgba(142,45,226,0.15)", color: "#c084fc", border: "1px solid rgba(142,45,226,0.2)" }}>
          Claude 3.5 Sonnet
        </span>
      </div>

      {/* Confidence Dial Display */}
      <div style={{ display: "flex", gap: "20px", alignItems: "center", background: "rgba(255,255,255,0.02)", padding: "12px", borderRadius: "12px" }}>
        <div style={{ position: "relative", width: "70px", height: "70px", display: "flex", alignItems: "center", justifyItems: "center", justifyContent: "center" }}>
          <svg style={{ transform: "rotate(-90deg)", width: "70px", height: "70px" }}>
            <circle cx="35" cy="35" r="28" fill="transparent" stroke="rgba(255,255,255,0.05)" strokeWidth="6" />
            <circle
              cx="35"
              cy="35"
              r="28"
              fill="transparent"
              stroke={getConfidenceColor(confidencePercent)}
              strokeWidth="6"
              strokeDasharray={175.9}
              strokeDashoffset={175.9 - (175.9 * confidencePercent) / 100}
              strokeLinecap="round"
              style={{ transition: "stroke-dashoffset 0.5s ease" }}
            />
          </svg>
          <span style={{ position: "absolute", fontSize: "16px", fontWeight: "700", color: getConfidenceColor(confidencePercent) }}>
            {confidencePercent}%
          </span>
        </div>

        <div style={{ flex: 1 }}>
          <h3 style={{ fontSize: "15px", fontWeight: "600", color: "white" }}>
            Confidence Level: {confidencePercent >= 85 ? "High (Auto-Execute)" : "Medium (User Confirm)"}
          </h3>
          <p style={{ fontSize: "12px", color: "var(--textSecondary)", marginTop: "2px" }}>
            Predictive Model matched sequence. Bedrock processed action approval rules.
          </p>
        </div>
      </div>

      {/* Reasoning details */}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
        {(decision.conflictDetected ?? false) && (
          <div style={{
            background: "rgba(245, 158, 11, 0.12)",
            border: "1px solid rgba(245, 158, 11, 0.35)",
            borderLeft: "4px solid #f59e0b",
            borderRadius: "8px",
            padding: "10px 14px",
            marginBottom: "4px"
          }}>
            <span style={{ fontSize: "13px", fontWeight: "700", color: "#fbbf24" }}>
              ⚠️ Conflict Resolved
            </span>
            {decision.conflictDescription && (
              <p style={{ fontSize: "12px", color: "#fde68a", marginTop: "4px", lineHeight: "1.4" }}>
                {decision.conflictDescription}
              </p>
            )}
          </div>
        )}
        <div>
          <span style={{ fontSize: "11px", textTransform: "uppercase", color: "var(--textMuted)", fontWeight: "700" }}>
            Action Classification
          </span>
          <div style={{ fontSize: "14px", fontWeight: "600", color: "var(--colorOrange)", marginTop: "2px" }}>
            {decision.actionId || prediction.predictedAction}
          </div>
        </div>

        <div>
          <span style={{ fontSize: "11px", textTransform: "uppercase", color: "var(--textMuted)", fontWeight: "700" }}>
            Explainable AI (Hindi Alert)
          </span>
          <div style={{ fontSize: "15px", color: "white", padding: "10px", background: "rgba(255, 126, 64, 0.05)", borderRadius: "8px", borderLeft: "4px solid var(--colorOrange)", marginTop: "4px", lineHeight: "1.4" }}>
            {decision.explanationHindi || "जानकारी उपलब्ध नहीं है।"}
          </div>
        </div>

        <div>
          <span style={{ fontSize: "11px", textTransform: "uppercase", color: "var(--textMuted)", fontWeight: "700" }}>
            Reasoning Context (English)
          </span>
          <p style={{ fontSize: "13px", color: "var(--textSecondary)", lineHeight: "1.4", marginTop: "4px" }}>
            {decision.explanationEnglish || prediction.reason}
          </p>
        </div>
      </div>

      {/* RAG Grounding Rules Panel */}
      <div style={{ background: "rgba(255,255,255,0.02)", padding: "12px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.04)" }}>
        <span style={{ fontSize: "11px", textTransform: "uppercase", color: "var(--textMuted)", fontWeight: "700", display: "block", marginBottom: "6px" }}>
          📡 Retrieved Grounding RAG Context (from Vector DB)
        </span>
        {ragContext && ragContext.length > 0 ? (
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {ragContext.map((rule, idx) => (
              <div key={idx} style={{ 
                background: "rgba(0,0,0,0.15)", 
                padding: "8px", 
                borderRadius: "6px", 
                fontSize: "12px", 
                borderLeft: `3px solid ${rule.category === 'cultural' ? '#a855f7' : rule.category === 'safety' ? 'var(--colorDanger)' : 'var(--colorOrange)'}` 
              }}>
                <div style={{ display: "flex", justifyContent: "space-between", color: "var(--textSecondary)", fontSize: "10px", marginBottom: "2px" }}>
                  <span style={{ textTransform: "uppercase", fontWeight: "700" }}>[{rule.category}]</span>
                  <span>Similarity: {Math.round(rule.similarity * 100)}%</span>
                </div>
                <div style={{ color: "white" }}>{rule.content}</div>
              </div>
            ))}
          </div>
        ) : (
          <p style={{ fontSize: "11px", color: "var(--textMuted)" }}>No matching rules retrieved for this context.</p>
        )}
      </div>

      {/* Interactive Overrides form */}
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "12px" }}>
        {renderRuleForm()}
      </div>

      {/* Collapsible raw data sections */}
      <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "10px", borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "12px" }}>
        <div>
          <button
            onClick={() => setShowRawContext(!showRawContext)}
            style={{ display: "flex", justifyContent: "space-between", width: "100%", background: "none", border: "none", color: "var(--textSecondary)", fontSize: "12px", cursor: "pointer", padding: "4px 0" }}
          >
            <span>{showRawContext ? "▼" : "▶"} Show Bedrock Ingestion Context Packet</span>
            <span>JSON</span>
          </button>
          {showRawContext && (
            <pre style={{ background: "#0a0c10", padding: "10px", borderRadius: "8px", fontSize: "11px", color: "#818cf8", overflowX: "auto", marginTop: "8px", maxHeight: "200px" }}>
              {JSON.stringify(lastTriggerResult.event, null, 2)}
            </pre>
          )}
        </div>

        <div>
          <button
            onClick={() => setShowRawOutput(!showRawOutput)}
            style={{ display: "flex", justifyContent: "space-between", width: "100%", background: "none", border: "none", color: "var(--textSecondary)", fontSize: "12px", cursor: "pointer", padding: "4px 0" }}
          >
            <span>{showRawOutput ? "▼" : "▶"} Show Bedrock Claude Response Payload</span>
            <span>JSON</span>
          </button>
          {showRawOutput && (
            <pre style={{ background: "#0a0c10", padding: "10px", borderRadius: "8px", fontSize: "11px", color: "#34d399", overflowX: "auto", marginTop: "8px" }}>
              {JSON.stringify(decision, null, 2)}
            </pre>
          )}
        </div>
      </div>
    </div>
  );
}

