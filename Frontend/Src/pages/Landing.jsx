import React from "react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  IconBrain, IconZap, IconMic, IconUsers, IconShield, IconMap,
  IconSparkle, IconArrowRight, IconActivity, IconLeaf
} from "../Components/Icons.jsx";

const FEATURES = [
  { icon: IconBrain, title: "Context-Aware AI", desc: "Bedrock-powered reasoning understands pooja timings, fasting days and festivals — not just on/off schedules." },
  { icon: IconMap,   title: "Live Digital Twin", desc: "A breathing 2D floor plan shows presence, running appliances and AI actions across every room in real time." },
  { icon: IconZap,   title: "Load-Shedding Ready", desc: "Predicts power cuts and pre-charges your inverter automatically, so the lights never blink during dinner." },
  { icon: IconMic,   title: "Voice in Your Language", desc: "Whisper-based voice control that listens in Hindi and English, tuned for Indian households." },
  { icon: IconUsers, title: "Community Micro-Grid", desc: "See how your colony shares solar and balances peak load together for lower bills for everyone." },
  { icon: IconShield,title: "Caregiver Peace of Mind", desc: "Gentle monitoring keeps an eye on elders and kids, nudging the family over WhatsApp when it matters." },
];

const fade = (d = 0) => ({
  initial: { opacity: 0, y: 22 },
  whileInView: { opacity: 1, y: 0 },
  viewport: { once: true, margin: "-60px" },
  transition: { duration: 0.55, delay: d, ease: [0.22, 1, 0.36, 1] },
});

export default function Landing() {
  const navigate = useNavigate();

  return (
    <div>
      {/* Nav */}
      <nav className="landingNav">
        <div style={{ display: "flex", alignItems: "center", gap: "12px" }}>
          <div className="brandMark" style={{ width: "38px", height: "38px" }}>🪔</div>
          <span className="gradientText" style={{ fontSize: "19px", fontWeight: 800, letterSpacing: "-0.4px" }}>GharBuddy</span>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: "10px" }}>
          <button
            className="btn"
            onClick={() => navigate("/login")}
            style={{ padding: "9px 16px", fontSize: "13.5px" }}
          >
            Sign In
          </button>
          <button
            className="btn btnPrimary"
            onClick={() => navigate("/login?mode=signup")}
            style={{ padding: "9px 18px", fontSize: "13.5px" }}
          >
            Get Started <IconArrowRight width="14" height="14" />
          </button>
        </div>
      </nav>

      {/* Hero */}
      <section className="landingHero">
        <motion.div initial={{ opacity: 0, y: 26 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}>
          <span className="heroEyebrow"><IconSparkle width="13" height="13" /> AI Smart Home for Indian Households</span>
          <h1 className="heroTitle">
            The home that <span className="gradientText">understands</span> how India lives.
          </h1>
          <p className="heroSub">
            GharBuddy blends AWS Bedrock reasoning with real Indian context — pooja, power cuts,
            cooker whistles and joint-family routines — into one calm, beautiful control center.
          </p>
          <div className="heroCtas">
            <button className="btn btnPrimary" style={{ padding: "12px 22px", fontSize: "14px" }} onClick={() => navigate("/login?mode=signup")}>
              Get Started <IconArrowRight width="15" height="15" />
            </button>
            <button className="btn" style={{ padding: "12px 22px", fontSize: "14px" }} onClick={() => navigate("/login")}>
              Sign In
            </button>
            <a className="btn btnGhost" style={{ padding: "12px 18px", fontSize: "13px" }} href="#features">
              Explore features
            </a>
          </div>
          <div className="heroStats">
            <div className="heroStat"><div className="num gradientText">6</div><div className="lbl">Rooms mapped live</div></div>
            <div className="heroStat"><div className="num" style={{ color: "var(--colorSuccess)" }}>32%</div><div className="lbl">Avg. energy saved</div></div>
            <div className="heroStat"><div className="num" style={{ color: "var(--secondary)" }}>24/7</div><div className="lbl">Context-aware</div></div>
          </div>
        </motion.div>

        {/* Visual */}
        <div className="heroVisual">
          <div className="heroOrb" style={{ width: "260px", height: "260px", background: "var(--accentGlow)", top: "10%", right: "8%" }} />
          <div className="heroOrb" style={{ width: "200px", height: "200px", background: "color-mix(in srgb, var(--secondary) 40%, transparent)", bottom: "6%", left: "0%", animationDelay: "1.5s" }} />

          <motion.div className="heroPanel" initial={{ opacity: 0, scale: 0.94 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.7, delay: 0.15 }}>
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "18px" }}>
              <div style={{ display: "flex", alignItems: "center", gap: "9px" }}>
                <span className="glowingDot" /> <span style={{ fontSize: "13px", fontWeight: 600 }}>Home is calm</span>
              </div>
              <span className="statusBadge" style={{ background: "var(--accentSoft)", color: "var(--accentText)", borderColor: "var(--accentLine)" }}>
                <IconActivity width="11" height="11" /> 06:30
              </span>
            </div>

            {[
              { room: "Pooja Room", state: "Diya lit · dimmed", c: "var(--accent)" },
              { room: "Kitchen", state: "Cooker · 2 whistles", c: "var(--colorWarning)" },
              { room: "Living Room", state: "Idle · lights off", c: "var(--textMuted)" },
            ].map((r) => (
              <div key={r.room} style={{ display: "flex", justifyContent: "space-between", alignItems: "center", padding: "12px 0", borderBottom: "1px solid var(--borderSubtle)" }}>
                <span style={{ fontSize: "13px", color: "var(--textSecondary)" }}>{r.room}</span>
                <span style={{ fontSize: "12px", fontWeight: 600, color: r.c }}>{r.state}</span>
              </div>
            ))}

            <div style={{ marginTop: "18px", padding: "12px 14px", borderRadius: "12px", background: "var(--secondarySoft)", border: "1px solid color-mix(in srgb, var(--secondary) 25%, transparent)", display: "flex", gap: "10px", alignItems: "center" }}>
              <IconLeaf width="18" height="18" style={{ color: "var(--secondary)", flexShrink: 0 }} />
              <span style={{ fontSize: "12.5px", color: "var(--textSecondary)" }}>Pre-charged inverter before the 6 PM cut.</span>
            </div>
          </motion.div>

          <div className="heroFloatChip" style={{ top: "4%", left: "2%" }}>
            <IconBrain width="15" height="15" style={{ color: "var(--accent)" }} /> AI reasoning
          </div>
          <div className="heroFloatChip" style={{ bottom: "2%", right: "4%", animationDelay: "1.2s" }}>
            <IconZap width="15" height="15" style={{ color: "var(--colorSuccess)" }} /> ₹34 saved today
          </div>
        </div>
      </section>

      {/* Features */}
      <section className="landingSection" id="features">
        <motion.div className="sectionHead" {...fade()}>
          <h2>Built for the way <span className="gradientText">we</span> live</h2>
          <p>Every feature is shaped around real Indian household rhythms — not a generic smart-home template.</p>
        </motion.div>
        <div className="featureGrid">
          {FEATURES.map((f, i) => (
            <motion.div key={f.title} className="featureCard" {...fade(i * 0.06)}>
              <div className="fIcon"><f.icon width="22" height="22" /></div>
              <h3>{f.title}</h3>
              <p>{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="landingSection" style={{ paddingTop: "20px" }}>
        <motion.div {...fade()} className="glassCard" style={{ textAlign: "center", padding: "clamp(36px, 6vw, 64px)", background: "linear-gradient(135deg, var(--accentSoft), color-mix(in srgb, var(--secondary) 10%, transparent))" }}>
          <h2 style={{ fontFamily: "var(--fontDisplay)", fontSize: "clamp(24px, 4vw, 36px)", fontWeight: 800, letterSpacing: "-1px", marginBottom: "12px" }}>
            Step inside your smarter ghar
          </h2>
          <p style={{ color: "var(--textSecondary)", maxWidth: "480px", margin: "0 auto 28px", fontSize: "15px" }}>
            Create an account and watch GharBuddy reason about your home in real time.
          </p>
          <div style={{ display: "flex", gap: "12px", justifyContent: "center", flexWrap: "wrap" }}>
            <button className="btn btnPrimary" style={{ padding: "13px 26px", fontSize: "15px" }} onClick={() => navigate("/login?mode=signup")}>
              Create your account <IconArrowRight width="16" height="16" />
            </button>
            <button className="btn" style={{ padding: "13px 22px", fontSize: "14px" }} onClick={() => navigate("/login")}>
              Sign in
            </button>
          </div>
        </motion.div>
      </section>

      <footer className="landingFooter">
        🪔 GharBuddy Smart Systems · HackOn with Amazon Season 6.0 · Powered by AWS Bedrock Claude &amp; IoT Core
      </footer>
    </div>
  );
}
