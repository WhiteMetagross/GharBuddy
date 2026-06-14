import React, { useState, useMemo } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { motion, AnimatePresence } from "framer-motion";
import {
  IconUser,
  IconLock,
  IconShield,
  IconArrowRight,
  IconSparkle,
} from "../Components/Icons.jsx";
import { validateAuthForm, ROLE_OPTIONS } from "../lib/authValidation.js";

// ---------- helpers ---------------------------------------------------------

// Brand placeholder for Google — non-functional badge so the path is honest.
function GoogleMark() {
  return (
    <svg width="16" height="16" viewBox="0 0 18 18" aria-hidden="true">
      <path fill="#4285F4" d="M17.64 9.2c0-.64-.06-1.25-.17-1.84H9v3.49h4.85a4.14 4.14 0 0 1-1.8 2.72v2.26h2.91c1.7-1.57 2.68-3.88 2.68-6.63z" />
      <path fill="#34A853" d="M9 18c2.43 0 4.47-.8 5.96-2.18l-2.91-2.26c-.81.54-1.84.86-3.05.86-2.34 0-4.32-1.58-5.03-3.7H.96v2.32A9 9 0 0 0 9 18z" />
      <path fill="#FBBC05" d="M3.97 10.71A5.41 5.41 0 0 1 3.68 9c0-.6.1-1.18.29-1.71V4.96H.96A9 9 0 0 0 0 9c0 1.45.35 2.82.96 4.04l3.01-2.33z" />
      <path fill="#EA4335" d="M9 3.58c1.32 0 2.51.45 3.44 1.34l2.58-2.58A9 9 0 0 0 9 0 9 9 0 0 0 .96 4.96l3.01 2.33C4.68 5.16 6.66 3.58 9 3.58z" />
    </svg>
  );
}

// Reusable floating-label-ish text input.
function Field({ icon: Icon, error, ...props }) {
  return (
    <div>
      <div style={{ position: "relative" }}>
        <span style={{
          position: "absolute", left: 12, top: "50%",
          transform: "translateY(-50%)", color: "var(--textMuted)",
          display: "flex", alignItems: "center",
        }}>
          <Icon width="14" height="14" />
        </span>
        <input
          {...props}
          style={{
            width: "100%",
            padding: "12px 12px 12px 38px",
            borderRadius: 10,
            fontSize: 14,
            background: "var(--bgInput)",
            border: `1px solid ${error ? "var(--colorDanger)" : "var(--borderCard)"}`,
            color: "var(--textPrimary)",
            outline: "none",
          }}
        />
      </div>
      {error && (
        <div style={{
          marginTop: 6, fontSize: 11.5,
          color: "var(--colorDanger)", letterSpacing: 0.2,
        }}>
          {error}
        </div>
      )}
    </div>
  );
}

// ---------- main -----------------------------------------------------------

export default function Login({ onAuthenticated }) {
  const navigate = useNavigate();
  const location = useLocation();
  const initialMode = new URLSearchParams(location.search).get("mode") === "signup"
    ? "signup"
    : "signin";

  const [mode, setMode] = useState(initialMode);
  const [form, setForm] = useState({
    username: "",
    password: "",
    confirm: "",
    role: "family",
  });
  const [serverError, setServerError] = useState("");
  const [busy, setBusy] = useState(false);
  const [demoOpen, setDemoOpen] = useState(false);

  const errors = useMemo(() => validateAuthForm(form, mode), [form, mode]);
  const canSubmit = Object.keys(errors).length === 0 && !busy;

  const update = (k) => (e) => {
    const v = e.target.value;
    setForm((f) => ({ ...f, [k]: v }));
    setServerError("");
  };

  const callApi = async (endpoint, body) => {
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    let data = {};
    try { data = await res.json(); } catch (_e) { /* ignore */ }
    if (!res.ok) {
      const detail = data?.detail || data?.message || (res.status === 401
        ? "Invalid username or password"
        : `Request failed (${res.status})`);
      throw new Error(detail);
    }
    return data;
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!canSubmit) return;
    setBusy(true);
    setServerError("");
    try {
      const data = mode === "signup"
        ? await callApi("/api/auth/register", {
            username: form.username.trim(),
            password: form.password,
            role: form.role,
          })
        : await callApi("/api/auth/login", {
            username: form.username.trim(),
            password: form.password,
          });

      onAuthenticated(data.access_token || data.token, {
        username: data.username,
        role: data.role,
      });
      navigate("/app");
    } catch (err) {
      setServerError(err?.message || "Something went wrong");
      setBusy(false);
    }
  };

  // Quick demo path — pre-fills then submits the demo creds, but kept as an
  // explicit button instead of the default form state.
  const enterDemo = async () => {
    setBusy(true);
    setServerError("");
    try {
      const data = await callApi("/api/auth/login", {
        username: "admin",
        password: "gharbuddy123",
      });
      onAuthenticated(data.access_token || data.token, {
        username: data.username,
        role: data.role,
      });
      navigate("/app");
    } catch (err) {
      setServerError(err?.message || "Demo unavailable");
      setBusy(false);
    }
  };

  // ---------- render -------------------------------------------------------

  const tabBtn = (id, label) => (
    <button
      type="button"
      onClick={() => { setMode(id); setServerError(""); }}
      aria-pressed={mode === id}
      style={{
        flex: 1,
        padding: "9px 10px",
        borderRadius: 999,
        fontSize: 13,
        fontWeight: 600,
        border: "none",
        cursor: "pointer",
        background: mode === id
          ? "linear-gradient(135deg, var(--accent), var(--accent2))"
          : "transparent",
        color: mode === id ? "#1a1206" : "var(--textMuted)",
        transition: "all 0.18s ease",
      }}
    >
      {label}
    </button>
  );

  return (
    <div className="loginPage">
      <motion.div
        className="loginCard"
        initial={{ opacity: 0, y: 18, scale: 0.97 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        style={{ maxWidth: 440 }}
      >
        {/* Brand */}
        <div style={{ textAlign: "center", marginBottom: 22 }}>
          <div className="brandMark" style={{
            width: 56, height: 56, margin: "0 auto 14px",
            fontSize: 26, borderRadius: 16,
          }}>🪔</div>
          <h1 style={{ fontSize: 23, fontWeight: 800, marginBottom: 2 }}>
            <span className="gradientText">GharBuddy</span>
          </h1>
          <p style={{ color: "var(--textMuted)", fontSize: 12 }}>
            {mode === "signup" ? "Create your home account" : "Welcome back home"}
          </p>
        </div>

        {/* Tabs */}
        <div style={{
          display: "flex",
          padding: 4,
          marginBottom: 18,
          background: "color-mix(in srgb, var(--bgTertiary) 80%, transparent)",
          borderRadius: 999,
          border: "1px solid var(--borderSubtle)",
        }}>
          {tabBtn("signin", "Sign In")}
          {tabBtn("signup", "Sign Up")}
        </div>

        {/* OAuth — visual placeholder; real OAuth would need a server-side flow */}
        <button
          type="button"
          onClick={() => setServerError("Google sign-in is coming soon. Use a username for now.")}
          style={{
            width: "100%", padding: "11px 14px", marginBottom: 12,
            borderRadius: 10,
            background: "var(--bgInput)",
            border: "1px solid var(--borderCard)",
            color: "var(--textPrimary)",
            display: "flex", alignItems: "center", justifyContent: "center",
            gap: 10, fontSize: 13.5, fontWeight: 600, cursor: "pointer",
          }}
        >
          <GoogleMark /> Continue with Google
        </button>

        <div style={{
          display: "flex", alignItems: "center", gap: 10,
          margin: "12px 0 16px",
          fontSize: 11, color: "var(--textMuted)", letterSpacing: 0.4,
          textTransform: "uppercase", fontWeight: 600,
        }}>
          <span style={{ flex: 1, height: 1, background: "var(--borderSubtle)" }} />
          or with username
          <span style={{ flex: 1, height: 1, background: "var(--borderSubtle)" }} />
        </div>

        {/* Form */}
        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 12 }}>
          <Field
            icon={IconUser}
            value={form.username}
            onChange={update("username")}
            placeholder="Username"
            aria-label="Username"
            autoComplete="username"
            error={form.username && errors.username}
          />
          <Field
            icon={IconLock}
            type="password"
            value={form.password}
            onChange={update("password")}
            placeholder="Password"
            aria-label="Password"
            autoComplete={mode === "signup" ? "new-password" : "current-password"}
            error={form.password && errors.password}
          />

          <AnimatePresence initial={false}>
            {mode === "signup" && (
              <motion.div
                key="signup-extras"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.22 }}
                style={{ display: "flex", flexDirection: "column", gap: 12, overflow: "hidden" }}
              >
                <Field
                  icon={IconShield}
                  type="password"
                  value={form.confirm}
                  onChange={update("confirm")}
                  placeholder="Confirm password"
                  aria-label="Confirm password"
                  autoComplete="new-password"
                  error={form.confirm && errors.confirm}
                />
                <fieldset style={{ border: "none", padding: 0, margin: 0 }}>
                  <legend style={{
                    fontSize: 11, fontWeight: 600,
                    color: "var(--textSecondary)",
                    textTransform: "uppercase", letterSpacing: 0.5,
                    marginBottom: 8,
                  }}>
                    Role in the household
                  </legend>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: 8 }}>
                    {ROLE_OPTIONS.map((r) => {
                      const active = form.role === r.id;
                      return (
                        <button
                          key={r.id}
                          type="button"
                          onClick={() => setForm((f) => ({ ...f, role: r.id }))}
                          aria-pressed={active}
                          style={{
                            padding: "10px 8px",
                            borderRadius: 10,
                            cursor: "pointer",
                            textAlign: "center",
                            background: active ? "var(--accentSoft)" : "var(--bgInput)",
                            border: `1px solid ${active ? "var(--accentLine)" : "var(--borderCard)"}`,
                            color: active ? "var(--accentText)" : "var(--textSecondary)",
                            transition: "all 0.18s ease",
                          }}
                        >
                          <div style={{ fontSize: 13, fontWeight: 700 }}>{r.label}</div>
                          <div style={{ fontSize: 10.5, opacity: 0.75, marginTop: 2 }}>{r.hint}</div>
                        </button>
                      );
                    })}
                  </div>
                </fieldset>
              </motion.div>
            )}
          </AnimatePresence>

          {serverError && (
            <div style={{
              background: "color-mix(in srgb, var(--colorDanger) 10%, transparent)",
              border: "1px solid color-mix(in srgb, var(--colorDanger) 30%, transparent)",
              borderRadius: 10, padding: "10px 12px",
              fontSize: 12.5, color: "var(--colorDanger)",
              display: "flex", alignItems: "center", gap: 8,
            }}>
              <span aria-hidden>⚠</span> {serverError}
            </div>
          )}

          <button
            type="submit"
            className="btn btnPrimary"
            disabled={!canSubmit}
            style={{
              width: "100%", padding: 13,
              fontSize: 14, justifyContent: "center", marginTop: 4,
            }}
          >
            {busy
              ? (mode === "signup" ? "Creating account…" : "Signing in…")
              : (
                <>
                  {mode === "signup" ? "Create account" : "Sign in"}
                  <IconArrowRight width="15" height="15" />
                </>
              )}
          </button>
        </form>

        {/* Demo */}
        <div style={{ marginTop: 20 }}>
          <button
            type="button"
            onClick={() => setDemoOpen((v) => !v)}
            aria-expanded={demoOpen}
            style={{
              width: "100%", padding: "10px 14px",
              background: "transparent",
              border: "1px dashed var(--borderCard)",
              borderRadius: 10,
              color: "var(--textMuted)",
              fontSize: 12, cursor: "pointer",
              display: "flex", alignItems: "center", justifyContent: "space-between",
            }}
          >
            <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <IconSparkle width="13" height="13" />
              Just want to look around?
            </span>
            <span aria-hidden style={{ transform: demoOpen ? "rotate(180deg)" : "none", transition: "transform 0.2s" }}>⌄</span>
          </button>

          <AnimatePresence initial={false}>
            {demoOpen && (
              <motion.div
                key="demo"
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: "auto" }}
                exit={{ opacity: 0, height: 0 }}
                transition={{ duration: 0.22 }}
                style={{ overflow: "hidden", marginTop: 10 }}
              >
                <div style={{
                  padding: 12, borderRadius: 10,
                  background: "var(--secondarySoft)",
                  border: "1px solid color-mix(in srgb, var(--secondary) 22%, transparent)",
                }}>
                  <div style={{ fontSize: 12, color: "var(--textSecondary)", marginBottom: 8 }}>
                    Sign in with seeded demo credentials. No data leaves your machine.
                  </div>
                  <button
                    type="button"
                    onClick={enterDemo}
                    disabled={busy}
                    className="btn"
                    style={{
                      width: "100%", padding: "10px 12px",
                      fontSize: 12.5, justifyContent: "center",
                      background: "var(--bgInput)",
                      border: "1px solid color-mix(in srgb, var(--secondary) 30%, transparent)",
                      color: "var(--secondary)",
                      fontWeight: 600,
                    }}
                  >
                    Continue as demo · admin
                  </button>
                  <div style={{
                    marginTop: 8, fontSize: 10.5,
                    color: "var(--textMuted)", letterSpacing: 0.2,
                  }}>
                    Other seeded user: <code>child</code> / <code>child123</code>
                  </div>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        <div style={{ textAlign: "center", marginTop: 16 }}>
          <Link to="/" style={{ fontSize: 12, color: "var(--textMuted)", textDecoration: "none" }}>
            ← Back to home
          </Link>
        </div>
      </motion.div>
    </div>
  );
}
