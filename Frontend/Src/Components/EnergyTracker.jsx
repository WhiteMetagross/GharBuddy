import React, { useState, useEffect } from "react";
import { BackendService } from "../Services/BackendService";

export default function EnergyTracker({ energyStats }) {
  const { totalSavedWh, rupeesSaved, peakPowerAvoidedW, inverterBatteryCharge } = energyStats;
  const kwhSaved = (totalSavedWh / 1000).toFixed(2);

  const [loadRisk, setLoadRisk] = useState(null);

  useEffect(() => {
    const fetchRisk = async () => {
      try {
        const data = await BackendService.getLoadSheddingRisk();
        setLoadRisk(data);
      } catch (err) {
        // Silently ignore — backend may not be running in all environments
      }
    };

    fetchRisk();
    const intervalId = setInterval(fetchRisk, 5000);
    return () => clearInterval(intervalId);
  }, []);

  const getBatteryColor = (charge) => {
    if (charge > 80) return "var(--colorSuccess)";
    if (charge > 30) return "var(--colorWarning)";
    return "var(--colorDanger)";
  };

  const getRiskBadge = (risk) => {
    if (!risk) return null;
    const score = risk.riskScore;

    if (score >= 0.75) {
      return {
        emoji: "🔴",
        label: "Pre-charge Now",
        subLabel: `${Math.round(score * 100)}% cut risk`,
        bg: "rgba(231,76,60,0.15)",
        color: "var(--colorDanger)",
        border: "1px solid rgba(231,76,60,0.3)"
      };
    }
    if (score >= 0.5) {
      return {
        emoji: "🟡",
        label: "Monitor",
        subLabel: `${Math.round(score * 100)}% cut risk`,
        bg: "rgba(241,196,15,0.12)",
        color: "var(--colorYellow)",
        border: "1px solid rgba(241,196,15,0.25)"
      };
    }
    return {
      emoji: "🟢",
      label: "Low Risk",
      subLabel: `${Math.round(score * 100)}% cut risk`,
      bg: "rgba(38,194,129,0.10)",
      color: "var(--colorSuccess)",
      border: "1px solid rgba(38,194,129,0.2)"
    };
  };

  const badge = getRiskBadge(loadRisk);

  return (
    <div className="glassCard" style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
      <div className="cardHeader">
        <h2>📊 Indian Household Energy & Cost Tracker</h2>
        <span className="statusBadge" style={{ background: "rgba(38,194,129,0.12)", color: "var(--colorSuccess)", border: "1px solid rgba(38,194,129,0.2)" }}>
          Live DISCOM Estimate
        </span>
      </div>

      {/* Load Shedding Risk Badge */}
      {badge && (
        <div style={{
          display: "flex",
          alignItems: "center",
          gap: "12px",
          background: badge.bg,
          border: badge.border,
          borderRadius: "12px",
          padding: "12px 16px"
        }}>
          <span style={{ fontSize: "22px" }}>{badge.emoji}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: "13px", fontWeight: "700", color: badge.color }}>
              Load Shedding: {badge.label}
            </div>
            <div style={{ fontSize: "11px", color: "var(--textSecondary)", marginTop: "2px" }}>
              {badge.subLabel}
              {loadRisk?.nextCutStart != null && (
                <span> · Next cut at {loadRisk.nextCutStart}:00</span>
              )}
              {loadRisk?.recommendation === "precharge_inverter" && (
                <span> · Pre-charging inverter</span>
              )}
            </div>
          </div>
          <span style={{ fontSize: "10px", color: "var(--textMuted)", whiteSpace: "nowrap" }}>
            Live · 5s
          </span>
        </div>
      )}

      {/* Grid of Key Metrics */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
        {/* Metric 1 */}
        <div style={{ background: "rgba(255,255,255,0.02)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.04)" }}>
          <span style={{ fontSize: "11px", color: "var(--textSecondary)", textTransform: "uppercase", fontWeight: "600" }}>
            Total Energy Saved
          </span>
          <div style={{ display: "flex", alignItems: "baseline", gap: "4px", marginTop: "6px" }}>
            <span style={{ fontSize: "28px", fontWeight: "700", color: "var(--colorSuccess)" }}>{kwhSaved}</span>
            <span style={{ fontSize: "14px", color: "var(--textSecondary)", fontWeight: "600" }}>kWh</span>
          </div>
        </div>

        {/* Metric 2 */}
        <div style={{ background: "rgba(255,255,255,0.02)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.04)" }}>
          <span style={{ fontSize: "11px", color: "var(--textSecondary)", textTransform: "uppercase", fontWeight: "600" }}>
            Financial Savings
          </span>
          <div style={{ display: "flex", alignItems: "baseline", gap: "4px", marginTop: "6px" }}>
            <span style={{ fontSize: "28px", fontWeight: "700", color: "var(--colorYellow)" }}>₹ {rupeesSaved}</span>
            <span style={{ fontSize: "12px", color: "var(--textSecondary)", fontWeight: "600" }}>INR Saved</span>
          </div>
        </div>
      </div>

      {/* Inverter Battery Charge Level Indicator */}
      <div style={{ display: "flex", gap: "16px", alignItems: "center", background: "rgba(255,255,255,0.02)", padding: "16px", borderRadius: "12px", border: "1px solid rgba(255,255,255,0.04)" }}>
        {/* SVG Battery Block */}
        <div style={{ position: "relative", width: "42px", height: "74px", border: "3px solid #63697a", borderRadius: "6px", padding: "2px" }}>
          {/* Battery Cap */}
          <div style={{ position: "absolute", top: "-8px", left: "11px", width: "14px", height: "6px", background: "#63697a", borderRadius: "2px 2px 0 0" }}></div>
          {/* Inner Fill level */}
          <div
            style={{
              height: `${inverterBatteryCharge}%`,
              background: getBatteryColor(inverterBatteryCharge),
              borderRadius: "2px",
              marginTop: "auto",
              position: "absolute",
              bottom: "2px",
              left: "2px",
              right: "2px",
              width: "calc(100% - 4px)",
              transition: "height 0.5s ease"
            }}
          ></div>
        </div>

        <div style={{ flex: 1 }}>
          <span style={{ fontSize: "11px", color: "var(--textSecondary)", textTransform: "uppercase", fontWeight: "600", display: "block" }}>
            Inverter Backup Status
          </span>
          <div style={{ fontSize: "20px", fontWeight: "700", color: "white", marginTop: "4px" }}>
            {inverterBatteryCharge}% Charged
          </div>
          <p style={{ fontSize: "12px", color: "var(--textMuted)", marginTop: "2px" }}>
            {inverterBatteryCharge === 100 ? "Full capacity - peak load ready" : "Pre-charging backup storage"}
          </p>
        </div>
      </div>

      {/* Savings Breakdown Chart Visualizer */}
      <div style={{ borderTop: "1px solid rgba(255,255,255,0.05)", paddingTop: "16px" }}>
        <span style={{ fontSize: "12px", color: "var(--textSecondary)", fontWeight: "600", display: "block", marginBottom: "12px" }}>
          Cumulative Optimization Savings:
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
          {/* Row 1 */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "4px" }}>
              <span style={{ color: "var(--textSecondary)" }}>🛁 Geyser Idle Shutoff</span>
              <span style={{ color: "var(--colorSuccess)", fontWeight: "700" }}>300 Wh</span>
            </div>
            <div style={{ height: "6px", background: "rgba(255,255,255,0.05)", borderRadius: "4px" }}>
              <div style={{ height: "100%", width: "45%", background: "var(--colorSuccess)", borderRadius: "4px" }}></div>
            </div>
          </div>
          {/* Row 2 */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "4px" }}>
              <span style={{ color: "var(--textSecondary)" }}>⛲ Motor Overflow Prevent</span>
              <span style={{ color: "var(--colorSuccess)", fontWeight: "700" }}>500 Wh</span>
            </div>
            <div style={{ height: "6px", background: "rgba(255,255,255,0.05)", borderRadius: "4px" }}>
              <div style={{ height: "100%", width: "75%", background: "var(--colorSuccess)", borderRadius: "4px" }}></div>
            </div>
          </div>
          {/* Row 3 */}
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "11px", marginBottom: "4px" }}>
              <span style={{ color: "var(--textSecondary)" }}>🔋 Power-Cut Pre-charge Shedding</span>
              <span style={{ color: "var(--colorSuccess)", fontWeight: "700" }}>600 Wh</span>
            </div>
            <div style={{ height: "6px", background: "rgba(255,255,255,0.05)", borderRadius: "4px" }}>
              <div style={{ height: "100%", width: "90%", background: "var(--colorSuccess)", borderRadius: "4px" }}></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
