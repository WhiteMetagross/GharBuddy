import React, { useState, useEffect } from "react";
import { BackendService } from "../Services/BackendService";

export default function CommunityEnergyDashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchData = async () => {
    try {
      const res = await fetch("/api/community/energy");
      const json = await res.json();
      setData(json);
      setLoading(false);
    } catch (e) {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const id = setInterval(fetchData, 5000);
    return () => clearInterval(id);
  }, []);

  if (loading || !data) {
    return (
      <div className="glassCard" style={{ display: "flex", alignItems: "center", justifyContent: "center", minHeight: "200px" }}>
        <span style={{ color: "var(--textMuted)", fontSize: "13px" }}>Loading community energy data...</span>
      </div>
    );
  }

  const { homes, totals, transformerLoad, tradingRecommendations, cooperativeSheddingSchedule } = data;

  const transformerColor = transformerLoad.status === "CRITICAL" ? "var(--colorDanger)"
    : transformerLoad.status === "HIGH" ? "var(--colorWarning)" : "var(--colorSuccess)";

  const priorityColor = (p) => p === "HIGH" ? "var(--colorDanger)" : p === "MEDIUM" ? "var(--colorWarning)" : "var(--colorSuccess)";

  return (
    <div className="glassCard" style={{ display: "flex", flexDirection: "column", gap: "18px" }}>
      {/* Header */}
      <div className="cardHeader" style={{ marginBottom: "4px" }}>
        <h2>🏘️ Community Energy Dashboard</h2>
        <span className="statusBadge" style={{ background: "rgba(38,194,129,0.1)", color: "var(--colorSuccess)", border: "1px solid rgba(38,194,129,0.2)", fontSize: "10px" }}>
          <span className="glowingDot" style={{ width: "5px", height: "5px" }}></span> Live · 5s
        </span>
      </div>

      {/* Transformer Load */}
      <div style={{
        display: "flex", alignItems: "center", gap: "14px",
        background: `rgba(${transformerLoad.status === "CRITICAL" ? "236,112,99" : transformerLoad.status === "HIGH" ? "245,176,65" : "38,194,129"},0.08)`,
        border: `1px solid rgba(${transformerLoad.status === "CRITICAL" ? "236,112,99" : transformerLoad.status === "HIGH" ? "245,176,65" : "38,194,129"},0.2)`,
        borderRadius: "12px", padding: "12px 16px"
      }}>
        <span style={{ fontSize: "24px" }}>🔌</span>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: "13px", fontWeight: "700", color: transformerColor }}>
            Transformer: {transformerLoad.status} — {transformerLoad.percentageUsed}% Capacity
          </div>
          <div style={{ fontSize: "11px", color: "var(--textSecondary)", marginTop: "2px" }}>
            Community demand: {(totals.totalDemandW / 1000).toFixed(1)} kW total · Solar offset: {(totals.totalSolarW / 1000).toFixed(1)} kW
          </div>
        </div>
        {/* Transformer bar */}
        <div style={{ width: "80px" }}>
          <div style={{ height: "8px", background: "rgba(255,255,255,0.05)", borderRadius: "4px", overflow: "hidden" }}>
            <div style={{
              height: "100%", width: `${transformerLoad.percentageUsed}%`,
              background: transformerColor, borderRadius: "4px", transition: "width 0.6s ease"
            }} />
          </div>
          <div style={{ fontSize: "10px", color: "var(--textMuted)", textAlign: "right", marginTop: "2px" }}>{transformerLoad.percentageUsed}%</div>
        </div>
      </div>

      {/* Community Totals */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: "10px" }}>
        {[
          { label: "Total Demand", value: `${(totals.totalDemandW / 1000).toFixed(1)} kW`, color: "var(--colorOrange)", icon: "⚡" },
          { label: "Solar Generated", value: `${(totals.totalSolarW / 1000).toFixed(1)} kW`, color: "#fbbf24", icon: "☀️" },
          { label: "Excess Solar", value: `${(totals.totalExcessSolarW / 1000).toFixed(1)} kW`, color: "var(--colorSuccess)", icon: "🔋" },
        ].map(m => (
          <div key={m.label} style={{ background: "rgba(255,255,255,0.02)", borderRadius: "10px", padding: "12px", border: "1px solid rgba(255,255,255,0.04)", textAlign: "center" }}>
            <div style={{ fontSize: "18px", marginBottom: "4px" }}>{m.icon}</div>
            <div style={{ fontSize: "16px", fontWeight: "700", color: m.color }}>{m.value}</div>
            <div style={{ fontSize: "10px", color: "var(--textMuted)", marginTop: "2px" }}>{m.label}</div>
          </div>
        ))}
      </div>

      {/* Per-Home Load Table */}
      <div>
        <div style={{ fontSize: "11px", color: "var(--textMuted)", textTransform: "uppercase", fontWeight: "700", letterSpacing: "0.5px", marginBottom: "8px" }}>
          Neighbourhood Load Breakdown
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "6px" }}>
          {homes.map(home => (
            <div key={home.id} style={{
              display: "flex", alignItems: "center", gap: "10px",
              background: "rgba(0,0,0,0.15)", borderRadius: "8px", padding: "8px 12px",
              borderLeft: `3px solid ${priorityColor(home.sheddingPriority)}`
            }}>
              <span style={{ fontSize: "14px" }}>{home.solarCapacityKw > 0 ? "☀️" : "🏠"}</span>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{ fontSize: "12px", fontWeight: "600", color: "white", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                  {home.name}
                </div>
                <div style={{ fontSize: "10px", color: "var(--textSecondary)" }}>
                  Load: {home.currentLoadW}W
                  {home.solarGenerationW > 0 && ` · Solar: ${home.solarGenerationW}W`}
                  {home.excessSolarW > 0 && <span style={{ color: "#fbbf24" }}> · +{home.excessSolarW}W surplus</span>}
                </div>
              </div>
              <span style={{ fontSize: "9px", fontWeight: "800", color: priorityColor(home.sheddingPriority), background: `rgba(${home.sheddingPriority === "HIGH" ? "236,112,99" : home.sheddingPriority === "MEDIUM" ? "245,176,65" : "38,194,129"},0.12)`, padding: "2px 6px", borderRadius: "6px", whiteSpace: "nowrap" }}>
                {home.sheddingPriority}
              </span>
            </div>
          ))}
        </div>
      </div>

      {/* P2P Solar Trading Recommendations */}
      {tradingRecommendations.length > 0 && (
        <div>
          <div style={{ fontSize: "11px", color: "var(--textMuted)", textTransform: "uppercase", fontWeight: "700", letterSpacing: "0.5px", marginBottom: "8px" }}>
            ☀️ Peer-to-Peer Solar Sharing
          </div>
          {tradingRecommendations.map((rec, i) => (
            <div key={i} style={{
              background: "rgba(251,191,36,0.06)", border: "1px solid rgba(251,191,36,0.2)",
              borderRadius: "8px", padding: "10px 12px", marginBottom: "6px",
              display: "flex", alignItems: "center", gap: "10px"
            }}>
              <span style={{ fontSize: "16px" }}>⚡</span>
              <div style={{ flex: 1, fontSize: "12px", color: "var(--textSecondary)" }}>
                {rec.message}
              </div>
              <span style={{ fontSize: "11px", fontWeight: "700", color: "var(--colorSuccess)", whiteSpace: "nowrap" }}>
                Save ₹{rec.savingsRupees}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Cooperative Load Shedding Schedule */}
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "14px" }}>
        <div style={{ fontSize: "11px", color: "var(--textMuted)", textTransform: "uppercase", fontWeight: "700", letterSpacing: "0.5px", marginBottom: "8px" }}>
          🔁 Cooperative Load Shedding Order
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: "4px" }}>
          {cooperativeSheddingSchedule.map((s, i) => (
            <div key={i} style={{
              display: "flex", alignItems: "center", gap: "8px",
              fontSize: "11px", color: s.recommendShed ? "var(--colorDanger)" : "var(--textSecondary)",
              opacity: s.recommendShed ? 1 : 0.6,
            }}>
              <span style={{ width: "16px", textAlign: "center", fontWeight: "700", color: "var(--textMuted)" }}>{i + 1}.</span>
              <span style={{ flex: 1 }}>{s.home}</span>
              <span style={{ color: priorityColor(s.priority), fontWeight: "700", fontSize: "10px" }}>{s.priority}</span>
              {s.recommendShed && <span style={{ color: "var(--colorDanger)", fontSize: "10px" }}>→ Shed first</span>}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
