import { useState } from "react";
import { Link } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import "../styles.css";

const INDUSTRIES = [
  "E-commerce","SaaS","Restaurant","Retail","Agency",
  "Healthcare","Fintech","Manufacturing","Real Estate","EdTech",
  "Logistics","Consulting","Other",
];

const SIZES = [
  "Solo / Freelancer","2–10 employees","11–50 employees",
  "51–200 employees","200+ employees",
];

const STAGES = [
  "Idea / Pre-revenue","Early stage (< 1 year)",
  "Growth stage (1–3 years)","Established (3+ years)","Scaling / Series A+",
];

export default function SignupPage() {
  const { signup } = useAuth();
  const [form, setForm] = useState({
    business_name: "", full_name: "", email: "", password: "",
    industry: "", size: "", stage: "",
  });
  const [error, setError]     = useState("");
  const [loading, setLoading] = useState(false);

  function set(field) {
    return (e) => setForm(f => ({ ...f, [field]: e.target.value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError("");
    if (form.password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }
    setLoading(true);
    try {
      await signup(form);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-mark">B</div>
          <span className="auth-logo-text">Business Buddy</span>
        </div>

        <h1 className="auth-title">Set up your buddy</h1>
        <p className="auth-sub">Your AI business partner — built around your specific business</p>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleSubmit}>
          <div className="section-label">Your business</div>

          <div className="field">
            <label>Business name *</label>
            <input value={form.business_name} onChange={set("business_name")}
              placeholder="Acme Ventures" required />
          </div>

          <div className="field-row">
            <div className="field">
              <label>Industry</label>
              <select value={form.industry} onChange={set("industry")}>
                <option value="">Select…</option>
                {INDUSTRIES.map(i => <option key={i}>{i}</option>)}
              </select>
            </div>
            <div className="field">
              <label>Team size</label>
              <select value={form.size} onChange={set("size")}>
                <option value="">Select…</option>
                {SIZES.map(s => <option key={s}>{s}</option>)}
              </select>
            </div>
          </div>

          <div className="field">
            <label>Business stage</label>
            <select value={form.stage} onChange={set("stage")}>
              <option value="">Select…</option>
              {STAGES.map(s => <option key={s}>{s}</option>)}
            </select>
          </div>

          <div className="section-label">Your account</div>

          <div className="field">
            <label>Full name</label>
            <input value={form.full_name} onChange={set("full_name")} placeholder="Jane Smith" />
          </div>

          <div className="field">
            <label>Email *</label>
            <input type="email" value={form.email} onChange={set("email")}
              placeholder="you@company.com" required />
          </div>

          <div className="field">
            <label>Password *</label>
            <input type="password" value={form.password} onChange={set("password")}
              placeholder="8+ characters" required />
          </div>

          <button className="btn-primary" disabled={loading || !form.business_name || !form.email || !form.password}>
            {loading ? "Creating your buddy…" : "Create my buddy →"}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account? <Link to="/login">Sign in</Link>
        </div>
      </div>
    </div>
  );
}
