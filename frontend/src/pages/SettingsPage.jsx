import { useState, useEffect } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { billingApi, teamApi, integrationApi } from "../api";
import "../styles.css";

const PLANS = [
  { id:"free",     label:"Free",     price:"$0",  period:"",    color:"#888",
    features:["1 user","5 documents","Chat + knowledge base","No integrations"] },
  { id:"pro",      label:"Pro",      price:"$49", period:"/mo", color:"#1a2744",
    features:["5 users","100 documents","Email integration","Slack integration","Priority support"] },
  { id:"business", label:"Business", price:"$149",period:"/mo", color:"#0f6e56",
    features:["Unlimited users","Unlimited documents","All integrations","Dedicated support","SLA"] },
];

// ── Shared UI atoms ───────────────────────────────────────────────────────────
function Card({ children, style }) {
  return (
    <div style={{ background:"white", border:"1px solid rgba(90,70,40,0.12)",
      borderRadius:12, padding:"1.25rem 1.5rem", ...style }}>
      {children}
    </div>
  );
}

function Btn({ children, onClick, disabled, variant="primary", style }) {
  const base = { fontFamily:"inherit", fontSize:13, fontWeight:600, borderRadius:7,
    padding:"8px 18px", cursor: disabled ? "not-allowed" : "pointer",
    border:"none", transition:"all 0.15s", opacity: disabled ? 0.5 : 1, ...style };
  const variants = {
    primary: { background:"#1a2744", color:"white" },
    danger:  { background:"transparent", color:"#c0392b", border:"1px solid rgba(192,57,43,0.3)" },
    outline: { background:"transparent", color:"#1a2744", border:"1px solid rgba(26,39,68,0.3)" },
    teal:    { background:"#0f6e56", color:"white" },
  };
  return <button style={{ ...base, ...variants[variant] }} onClick={onClick} disabled={disabled}>{children}</button>;
}

function Badge({ label, color="#0f6e56", bg="#e8f9f3" }) {
  return <span style={{ fontSize:11, fontWeight:600, padding:"2px 9px",
    borderRadius:20, background:bg, color }}>{label}</span>;
}

// ── Billing tab ───────────────────────────────────────────────────────────────
function BillingTab() {
  const [billing, setBilling] = useState(null);
  const [loading, setLoading] = useState(false);
  const [params]  = useSearchParams();

  useEffect(() => { billingApi.status().then(setBilling).catch(()=>{}); }, []);

  const currentPlan = billing?.plan || "free";
  const success     = params.get("billing") === "success";

  async function handleUpgrade(plan) {
    setLoading(true);
    try {
      const { checkout_url } = await billingApi.checkout(plan);
      window.location.href = checkout_url;
    } catch(e) { alert(e.message); }
    setLoading(false);
  }

  async function handlePortal() {
    setLoading(true);
    try {
      const { portal_url } = await billingApi.portal();
      window.location.href = portal_url;
    } catch(e) { alert(e.message); }
    setLoading(false);
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
      {success && (
        <div style={{ padding:"12px 16px", background:"#e8f9f3", border:"1px solid #9fe1cb",
          borderRadius:8, fontSize:13, color:"#085041", fontWeight:500 }}>
          Subscription activated successfully. Your plan has been upgraded.
        </div>
      )}

      {/* Current plan */}
      {billing && (
        <Card>
          <div style={{ fontSize:12, color:"#888", marginBottom:6 }}>Current plan</div>
          <div style={{ display:"flex", alignItems:"center", gap:12 }}>
            <span style={{ fontSize:22, fontWeight:700, color:"#1a2744", textTransform:"capitalize" }}>
              {currentPlan}
            </span>
            <Badge label={billing.status === "active" ? "Active" : billing.status}
              color={billing.status === "active" ? "#085041" : "#854f0b"}
              bg={billing.status === "active" ? "#e8f9f3" : "#fdf3e0"} />
            {billing.cancel_at_period_end && (
              <Badge label="Cancels at period end" color="#c0392b" bg="#fdf0ee" />
            )}
          </div>
          {billing.current_period_end && (
            <div style={{ fontSize:12, color:"#888", marginTop:6 }}>
              {billing.cancel_at_period_end ? "Access until" : "Renews"}{" "}
              {new Date(billing.current_period_end).toLocaleDateString()}
            </div>
          )}
          {currentPlan !== "free" && billing.stripe_enabled && (
            <div style={{ marginTop:12 }}>
              <Btn variant="outline" onClick={handlePortal} disabled={loading}>
                Manage subscription →
              </Btn>
            </div>
          )}
        </Card>
      )}

      {/* Plan cards */}
      <div style={{ display:"grid", gridTemplateColumns:"repeat(auto-fit, minmax(200px, 1fr))", gap:12 }}>
        {PLANS.map(plan => {
          const isCurrent = plan.id === currentPlan;
          return (
            <Card key={plan.id} style={{ border: isCurrent ? "2px solid #1a2744" : undefined }}>
              {isCurrent && (
                <div style={{ fontSize:10, fontWeight:700, color:"#1a2744",
                  textTransform:"uppercase", letterSpacing:"0.1em", marginBottom:8 }}>
                  Current plan
                </div>
              )}
              <div style={{ fontSize:18, fontWeight:700, color:plan.color }}>{plan.label}</div>
              <div style={{ fontSize:22, fontWeight:700, color:"#1a1612", margin:"6px 0" }}>
                {plan.price}<span style={{ fontSize:13, color:"#888", fontWeight:400 }}>{plan.period}</span>
              </div>
              <ul style={{ listStyle:"none", margin:"12px 0", padding:0, display:"flex",
                flexDirection:"column", gap:5 }}>
                {plan.features.map(f => (
                  <li key={f} style={{ fontSize:12, color:"#444", display:"flex", gap:7, alignItems:"flex-start" }}>
                    <span style={{ color:"#0f6e56", fontWeight:700, flexShrink:0 }}>✓</span>{f}
                  </li>
                ))}
              </ul>
              {!isCurrent && plan.id !== "free" && billing?.stripe_enabled && (
                <Btn onClick={() => handleUpgrade(plan.id)} disabled={loading}
                  variant={plan.id === "business" ? "teal" : "primary"}
                  style={{ width:"100%", marginTop:8 }}>
                  Upgrade to {plan.label}
                </Btn>
              )}
              {!billing?.stripe_enabled && plan.id !== "free" && (
                <div style={{ fontSize:11, color:"#aaa", marginTop:8 }}>
                  Configure Stripe to enable upgrades
                </div>
              )}
            </Card>
          );
        })}
      </div>
    </div>
  );
}

// ── Team tab ──────────────────────────────────────────────────────────────────
function TeamTab({ currentUser }) {
  const [members, setMembers]   = useState([]);
  const [invites, setInvites]   = useState([]);
  const [inviteEmail, setEmail] = useState("");
  const [inviteRole, setRole]   = useState("member");
  const [inviteResult, setInviteResult] = useState(null);
  const [loading, setLoading]   = useState(false);
  const [error, setError]       = useState("");

  const isOwnerOrAdmin = ["owner","admin"].includes(currentUser?.role);

  useEffect(() => {
    teamApi.listMembers().then(setMembers).catch(()=>{});
    if (isOwnerOrAdmin) teamApi.listInvites().then(setInvites).catch(()=>{});
  }, []);

  async function handleInvite(e) {
    e.preventDefault();
    setError(""); setLoading(true); setInviteResult(null);
    try {
      const res = await teamApi.invite(inviteEmail, inviteRole);
      setInviteResult(res);
      setEmail("");
      teamApi.listInvites().then(setInvites).catch(()=>{});
    } catch(err) { setError(err.message); }
    setLoading(false);
  }

  async function handleRemove(id) {
    if (!confirm("Remove this member?")) return;
    try {
      await teamApi.removeMember(id);
      setMembers(m => m.filter(x => x.id !== id));
    } catch(err) { alert(err.message); }
  }

  function copyInviteLink(url) {
    navigator.clipboard.writeText(url).catch(()=>{});
    alert("Invite link copied to clipboard!");
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
      {/* Member list */}
      <Card>
        <div style={{ fontSize:13, fontWeight:600, color:"#1a2744", marginBottom:12 }}>
          Team members ({members.length})
        </div>
        <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
          {members.map(m => (
            <div key={m.id} style={{ display:"flex", alignItems:"center", gap:10,
              padding:"8px 10px", borderRadius:8,
              background: m.is_self ? "#f0f4ff" : "#faf9f6",
              border: "1px solid rgba(90,70,40,0.08)" }}>
              <div style={{ width:34, height:34, borderRadius:"50%", background:"#1a2744",
                display:"flex", alignItems:"center", justifyContent:"center",
                color:"white", fontSize:13, fontWeight:700, flexShrink:0 }}>
                {(m.full_name || m.email)[0].toUpperCase()}
              </div>
              <div style={{ flex:1, minWidth:0 }}>
                <div style={{ fontSize:13, fontWeight:600, color:"#1a1612" }}>
                  {m.full_name || m.email}
                  {m.is_self && <span style={{ fontSize:10, color:"#888", marginLeft:6 }}>(you)</span>}
                </div>
                <div style={{ fontSize:11, color:"#888" }}>{m.email}</div>
              </div>
              <Badge label={m.role}
                color={m.role === "owner" ? "#1a2744" : m.role === "admin" ? "#0f6e56" : "#6b6458"}
                bg={m.role === "owner" ? "#e8ecf8" : m.role === "admin" ? "#e8f9f3" : "#f0ede8"} />
              {isOwnerOrAdmin && !m.is_self && m.role !== "owner" && (
                <Btn variant="danger" style={{ padding:"4px 10px", fontSize:11 }}
                  onClick={() => handleRemove(m.id)}>Remove</Btn>
              )}
            </div>
          ))}
        </div>
      </Card>

      {/* Invite form */}
      {isOwnerOrAdmin && (
        <Card>
          <div style={{ fontSize:13, fontWeight:600, color:"#1a2744", marginBottom:12 }}>
            Invite a team member
          </div>
          {error && <div className="error-banner">{error}</div>}
          {inviteResult && (
            <div style={{ padding:"10px 12px", background:"#e8f9f3", borderRadius:8,
              border:"1px solid #9fe1cb", marginBottom:12 }}>
              <div style={{ fontSize:12, fontWeight:600, color:"#085041", marginBottom:4 }}>
                Invite created for {inviteResult.email}
              </div>
              <div style={{ fontSize:11, color:"#0f6e56", wordBreak:"break-all" }}>
                {inviteResult.invite_url}
              </div>
              <Btn style={{ marginTop:8, padding:"5px 12px", fontSize:11 }}
                onClick={() => copyInviteLink(inviteResult.invite_url)}>
                Copy link
              </Btn>
            </div>
          )}
          <form onSubmit={handleInvite}>
            <div style={{ display:"grid", gridTemplateColumns:"1fr auto", gap:8, alignItems:"end" }}>
              <div className="field">
                <label>Email address</label>
                <input type="email" value={inviteEmail}
                  onChange={e => setEmail(e.target.value)}
                  placeholder="colleague@company.com" required />
              </div>
              <div className="field">
                <label>Role</label>
                <select value={inviteRole} onChange={e => setRole(e.target.value)}>
                  <option value="member">Member</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
            </div>
            <Btn disabled={loading || !inviteEmail}>
              {loading ? "Sending…" : "Send invite"}
            </Btn>
          </form>
        </Card>
      )}

      {/* Pending invites */}
      {isOwnerOrAdmin && invites.length > 0 && (
        <Card>
          <div style={{ fontSize:13, fontWeight:600, color:"#1a2744", marginBottom:10 }}>
            Pending invites
          </div>
          {invites.map(inv => (
            <div key={inv.id} style={{ display:"flex", alignItems:"center", gap:8,
              padding:"7px 0", borderBottom:"1px solid rgba(90,70,40,0.08)" }}>
              <span style={{ flex:1, fontSize:12, color:"#1a1612" }}>{inv.email}</span>
              <Badge label={inv.role} color="#6b6458" bg="#f0ede8" />
              <button onClick={() => copyInviteLink(inv.invite_url)}
                style={{ fontSize:11, color:"#b8832a", background:"none", border:"none",
                  cursor:"pointer", fontFamily:"inherit" }}>Copy link</button>
            </div>
          ))}
        </Card>
      )}
    </div>
  );
}

// ── Integrations tab ──────────────────────────────────────────────────────────
function IntegrationsTab() {
  const [integrations, setIntegrations] = useState([]);
  const [showEmailForm, setShowEmailForm] = useState(false);
  const [showSlackForm, setShowSlackForm] = useState(false);
  const [saving, setSaving]   = useState(false);
  const [syncing, setSyncing] = useState({});
  const [error, setError]     = useState("");
  const [billing, setBilling] = useState(null);

  const [emailForm, setEmailForm] = useState({
    imap_host:"imap.gmail.com", imap_port:993, email:"", password:"",
    folder:"INBOX", max_emails:50, name:"",
  });
  const [slackForm, setSlackForm] = useState({
    bot_token:"", channel_ids:"", max_messages:200, name:"Slack workspace",
  });

  useEffect(() => {
    integrationApi.list().then(setIntegrations).catch(()=>{});
    billingApi.status().then(setBilling).catch(()=>{});
  }, []);

  const planAllows = billing?.limits?.integrations;

  async function connectEmail(e) {
    e.preventDefault(); setError(""); setSaving(true);
    try {
      const res = await integrationApi.connectEmail({ ...emailForm, imap_port: Number(emailForm.imap_port) });
      setIntegrations(prev => [...prev, res]);
      setShowEmailForm(false);
    } catch(err) { setError(err.message); }
    setSaving(false);
  }

  async function connectSlack(e) {
    e.preventDefault(); setError(""); setSaving(true);
    try {
      const channel_ids = slackForm.channel_ids.split(",").map(s => s.trim()).filter(Boolean);
      const res = await integrationApi.connectSlack({ ...slackForm, channel_ids });
      setIntegrations(prev => [...prev, res]);
      setShowSlackForm(false);
    } catch(err) { setError(err.message); }
    setSaving(false);
  }

  async function handleSync(id) {
    setSyncing(s => ({ ...s, [id]: true }));
    try {
      await integrationApi.sync(id);
      setTimeout(() => integrationApi.list().then(setIntegrations).catch(()=>{}), 3000);
    } catch(err) { alert(err.message); }
    setSyncing(s => ({ ...s, [id]: false }));
  }

  async function handleRemove(id) {
    if (!confirm("Disconnect this integration?")) return;
    await integrationApi.remove(id).catch(()=>{});
    setIntegrations(prev => prev.filter(x => x.id !== id));
  }

  if (!planAllows) {
    return (
      <Card style={{ textAlign:"center", padding:"2.5rem" }}>
        <div style={{ fontSize:32, marginBottom:12 }}>🔌</div>
        <div style={{ fontSize:15, fontWeight:600, color:"#1a2744", marginBottom:8 }}>
          Integrations require Pro or Business
        </div>
        <div style={{ fontSize:13, color:"#888", marginBottom:16 }}>
          Connect your email and Slack to let your buddy learn from your real communications.
        </div>
        <Btn onClick={() => window.location.href="/settings?tab=billing"}>
          Upgrade plan →
        </Btn>
      </Card>
    );
  }

  const emailCfg  = { imap_host:"", imap_port:"", email:"", folder:"", max_emails:"" };

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:16 }}>
      {error && <div className="error-banner">{error}</div>}

      {/* Connected integrations */}
      {integrations.map(int => (
        <Card key={int.id} style={{ display:"flex", alignItems:"flex-start", gap:12 }}>
          <div style={{ width:40, height:40, borderRadius:8, background:"#f0ede8",
            display:"flex", alignItems:"center", justifyContent:"center",
            fontSize:18, flexShrink:0 }}>
            {int.type === "email" ? "✉" : "💬"}
          </div>
          <div style={{ flex:1, minWidth:0 }}>
            <div style={{ fontSize:13, fontWeight:600, color:"#1a1612" }}>{int.name}</div>
            <div style={{ fontSize:11, color:"#888", marginTop:2, textTransform:"capitalize" }}>
              {int.type} · {int.status}
              {int.last_synced_at && ` · Last synced ${new Date(int.last_synced_at).toLocaleString()}`}
            </div>
            {int.last_error && (
              <div style={{ fontSize:11, color:"#c0392b", marginTop:4 }}>{int.last_error}</div>
            )}
            {Object.entries(int.config_preview || {}).map(([k,v]) => (
              <div key={k} style={{ fontSize:10, color:"#aaa", marginTop:1 }}>
                {k}: {Array.isArray(v) ? v.join(", ") : String(v)}
              </div>
            ))}
          </div>
          <div style={{ display:"flex", gap:6, flexShrink:0 }}>
            <Btn variant="outline" style={{ padding:"5px 10px", fontSize:11 }}
              onClick={() => handleSync(int.id)} disabled={syncing[int.id]}>
              {syncing[int.id] ? "Syncing…" : "↻ Sync"}
            </Btn>
            <Btn variant="danger" style={{ padding:"5px 10px", fontSize:11 }}
              onClick={() => handleRemove(int.id)}>Remove</Btn>
          </div>
        </Card>
      ))}

      {/* Add buttons */}
      {!showEmailForm && !showSlackForm && (
        <div style={{ display:"flex", gap:10 }}>
          <Btn variant="outline" onClick={() => setShowEmailForm(true)}>+ Connect email (IMAP)</Btn>
          <Btn variant="outline" onClick={() => setShowSlackForm(true)}>+ Connect Slack</Btn>
        </div>
      )}

      {/* Email form */}
      {showEmailForm && (
        <Card>
          <div style={{ fontSize:13, fontWeight:600, color:"#1a2744", marginBottom:14 }}>
            Connect email via IMAP
          </div>
          <form onSubmit={connectEmail}>
            <div className="field-row">
              <div className="field"><label>IMAP host</label>
                <input value={emailForm.imap_host} onChange={e => setEmailForm(f=>({...f,imap_host:e.target.value}))} placeholder="imap.gmail.com" required /></div>
              <div className="field"><label>Port</label>
                <input type="number" value={emailForm.imap_port} onChange={e => setEmailForm(f=>({...f,imap_port:e.target.value}))} required /></div>
            </div>
            <div className="field"><label>Email address</label>
              <input type="email" value={emailForm.email} onChange={e => setEmailForm(f=>({...f,email:e.target.value}))} required /></div>
            <div className="field"><label>Password / App Password</label>
              <input type="password" value={emailForm.password} onChange={e => setEmailForm(f=>({...f,password:e.target.value}))} required />
              <span style={{ fontSize:10, color:"#888", marginTop:3 }}>For Gmail: use an App Password (not your main password)</span>
            </div>
            <div className="field-row">
              <div className="field"><label>Folder</label>
                <input value={emailForm.folder} onChange={e => setEmailForm(f=>({...f,folder:e.target.value}))} /></div>
              <div className="field"><label>Max emails per sync</label>
                <input type="number" value={emailForm.max_emails} onChange={e => setEmailForm(f=>({...f,max_emails:e.target.value}))} /></div>
            </div>
            <div style={{ display:"flex", gap:8, marginTop:4 }}>
              <Btn disabled={saving}>{saving ? "Connecting…" : "Connect"}</Btn>
              <Btn variant="outline" onClick={() => setShowEmailForm(false)} type="button">Cancel</Btn>
            </div>
          </form>
        </Card>
      )}

      {/* Slack form */}
      {showSlackForm && (
        <Card>
          <div style={{ fontSize:13, fontWeight:600, color:"#1a2744", marginBottom:14 }}>
            Connect Slack
          </div>
          <div style={{ fontSize:12, color:"#888", marginBottom:14, lineHeight:1.6 }}>
            Create a Slack app → add scopes: <code>channels:history channels:read groups:history</code> → install to workspace → copy the Bot User OAuth Token.
          </div>
          <form onSubmit={connectSlack}>
            <div className="field"><label>Bot token</label>
              <input type="password" value={slackForm.bot_token} onChange={e => setSlackForm(f=>({...f,bot_token:e.target.value}))} placeholder="xoxb-..." required /></div>
            <div className="field"><label>Channel IDs (comma-separated)</label>
              <input value={slackForm.channel_ids} onChange={e => setSlackForm(f=>({...f,channel_ids:e.target.value}))} placeholder="C123ABC, C456DEF" required /></div>
            <div className="field"><label>Display name</label>
              <input value={slackForm.name} onChange={e => setSlackForm(f=>({...f,name:e.target.value}))} /></div>
            <div style={{ display:"flex", gap:8, marginTop:4 }}>
              <Btn disabled={saving}>{saving ? "Connecting…" : "Connect"}</Btn>
              <Btn variant="outline" onClick={() => setShowSlackForm(false)} type="button">Cancel</Btn>
            </div>
          </form>
        </Card>
      )}
    </div>
  );
}

// ── Main Settings page ────────────────────────────────────────────────────────
export default function SettingsPage() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const [tab, setTab] = useState(params.get("tab") || "billing");

  const tabs = [
    { id:"billing",      label:"Billing" },
    { id:"team",         label:"Team" },
    { id:"integrations", label:"Integrations" },
  ];

  return (
    <div style={{ minHeight:"100vh", background:"#f8f7f4" }}>
      {/* Nav */}
      <header style={{ height:50, background:"white", borderBottom:"1px solid rgba(90,70,40,0.12)",
        display:"flex", alignItems:"center", padding:"0 24px", gap:12 }}>
        <button onClick={() => navigate("/dashboard")}
          style={{ background:"none", border:"none", cursor:"pointer", fontSize:13,
            color:"#888", fontFamily:"inherit" }}>← Back</button>
        <div style={{ width:1, height:20, background:"rgba(90,70,40,0.15)" }} />
        <span style={{ fontSize:15, fontWeight:700, color:"#1a2744" }}>Settings</span>
        <div style={{ flex:1 }} />
        <span style={{ fontSize:12, color:"#888" }}>{user?.email}</span>
      </header>

      <div style={{ maxWidth:780, margin:"0 auto", padding:"24px 16px" }}>
        {/* Tabs */}
        <div style={{ display:"flex", gap:4, background:"white",
          border:"1px solid rgba(90,70,40,0.12)", borderRadius:10,
          padding:4, marginBottom:20, width:"fit-content" }}>
          {tabs.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              style={{ padding:"7px 20px", borderRadius:7, border:"none",
                background: tab === t.id ? "#1a2744" : "transparent",
                color: tab === t.id ? "white" : "#888",
                fontFamily:"inherit", fontSize:13, fontWeight:600,
                cursor:"pointer", transition:"all 0.15s" }}>
              {t.label}
            </button>
          ))}
        </div>

        {tab === "billing"      && <BillingTab />}
        {tab === "team"         && <TeamTab currentUser={user} />}
        {tab === "integrations" && <IntegrationsTab />}
      </div>
    </div>
  );
}
