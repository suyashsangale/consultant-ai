import { useState, useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { teamApi, saveToken } from "../api";
import "../styles.css";

export default function InviteAcceptPage() {
  const { token }    = useParams();
  const navigate     = useNavigate();
  const [invite, setInvite]     = useState(null);
  const [error, setError]       = useState("");
  const [loading, setLoading]   = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm]         = useState({ password:"", full_name:"" });

  useEffect(() => {
    teamApi.getInvite(token)
      .then(setInvite)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [token]);

  async function handleAccept(e) {
    e.preventDefault();
    if (form.password.length < 8) { setError("Password must be at least 8 characters"); return; }
    setSubmitting(true); setError("");
    try {
      const { access_token } = await teamApi.acceptInvite(token, form);
      saveToken(access_token);
      navigate("/dashboard");
    } catch(err) { setError(err.message); }
    setSubmitting(false);
  }

  if (loading) return (
    <div className="auth-wrap">
      <div style={{ color:"#888", fontSize:14 }}>Checking invite…</div>
    </div>
  );

  if (error && !invite) return (
    <div className="auth-wrap">
      <div className="auth-card" style={{ textAlign:"center" }}>
        <div style={{ fontSize:32, marginBottom:12 }}>⚠️</div>
        <div style={{ fontSize:15, fontWeight:600, color:"#1a2744", marginBottom:8 }}>Invite unavailable</div>
        <div style={{ fontSize:13, color:"#888" }}>{error}</div>
      </div>
    </div>
  );

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <div className="auth-logo">
          <div className="auth-logo-mark">B</div>
          <span className="auth-logo-text">Business Buddy</span>
        </div>

        <div style={{ marginBottom:"1.5rem" }}>
          <h1 className="auth-title">You're invited</h1>
          <p className="auth-sub" style={{ marginBottom:0 }}>
            Join <strong>{invite?.business_name}</strong> as a{" "}
            <strong>{invite?.role}</strong>
          </p>
        </div>

        {error && <div className="error-banner">{error}</div>}

        <form onSubmit={handleAccept}>
          <div style={{ padding:"10px 12px", background:"#f0ede8", borderRadius:7,
            marginBottom:"1rem", fontSize:12, color:"#6b6458" }}>
            Signing in as <strong>{invite?.email}</strong>
          </div>

          <div className="field">
            <label>Full name (optional)</label>
            <input value={form.full_name}
              onChange={e => setForm(f => ({...f, full_name: e.target.value}))}
              placeholder="Your name" />
          </div>
          <div className="field">
            <label>Set a password *</label>
            <input type="password" value={form.password}
              onChange={e => setForm(f => ({...f, password: e.target.value}))}
              placeholder="8+ characters" required />
          </div>

          <button className="btn-primary" disabled={submitting || !form.password}>
            {submitting ? "Joining…" : `Join ${invite?.business_name} →`}
          </button>
        </form>

        <div className="auth-footer">
          Already have an account?{" "}
          <span style={{ color:"#b8832a", cursor:"pointer", fontWeight:500 }}
            onClick={() => navigate("/login")}>
            Sign in instead
          </span>
        </div>
      </div>
    </div>
  );
}
