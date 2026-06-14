import React, { useState } from "react";
import { BackendService } from "../Services/BackendService";

export default function LoginModal({ onLogin, onClose }) {
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const result = await BackendService.login(username, password);
      localStorage.setItem("gharbuddy_token", result.access_token || result.token);
      localStorage.setItem("gharbuddy_user", JSON.stringify({ username: result.username, role: result.role }));
      onLogin(result);
    } catch (err) {
      setError("Invalid credentials. Try admin/gharbuddy123");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      position: "fixed", inset: 0, background: "rgba(0,0,0,0.7)",
      display: "flex", alignItems: "center", justifyContent: "center",
      zIndex: 1000, backdropFilter: "blur(4px)"
    }}>
      <div className="glassCard" style={{ width: "340px", padding: "32px" }}>
        <div style={{ textAlign: "center", marginBottom: "24px" }}>
          <span style={{ fontSize: "40px" }}>&#x1F54C;</span>
          <h2 className="gradientText" style={{ marginTop: "8px" }}>GharBuddy Login</h2>
          <p style={{ fontSize: "12px", color: "var(--textMuted)", marginTop: "4px" }}>
            Sign in to control your smart home
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: "14px" }}>
          <input
            type="text"
            placeholder="Username"
            value={username}
            onChange={e => setUsername(e.target.value)}
            required
            aria-label="Username"
            style={{
              padding: "10px 14px", background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px",
              color: "white", fontSize: "14px", fontFamily: "var(--fontFamily)"
            }}
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            required
            aria-label="Password"
            style={{
              padding: "10px 14px", background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px",
              color: "white", fontSize: "14px", fontFamily: "var(--fontFamily)"
            }}
          />
          {error && (
            <p role="alert" style={{ color: "var(--colorDanger)", fontSize: "12px", margin: 0 }}>
              {error}
            </p>
          )}
          <button
            type="submit"
            className="btn btnPrimary"
            disabled={loading}
            style={{ padding: "12px" }}
          >
            {loading ? "Signing in..." : "\uD83D\uDD11 Sign In"}
          </button>
        </form>

        <div style={{ marginTop: "16px", fontSize: "11px", color: "var(--textMuted)", textAlign: "center" }}>
          Demo: <strong>admin</strong> / <strong>gharbuddy123</strong>
        </div>

        <button
          onClick={onClose}
          style={{
            marginTop: "12px", width: "100%", padding: "8px",
            background: "none", border: "none", color: "var(--textMuted)",
            fontSize: "12px", cursor: "pointer"
          }}
        >
          Continue without login (limited access)
        </button>
      </div>
    </div>
  );
}
