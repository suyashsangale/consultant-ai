import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import { api } from "../api";
import { knowledge } from "../knowledge";
import Sidebar        from "../components/Sidebar";
import ChatWindow     from "../components/ChatWindow";
import KnowledgePanel from "../components/KnowledgePanel";
import DocumentPanel  from "../components/DocumentPanel";

export default function DashboardPage() {
  const { user, logout }    = useAuth();
  const navigate            = useNavigate();
  const [kb, setKb]         = useState(null);
  const [convos, setConvos] = useState([]);
  const [convLoaded, setConvLoaded]         = useState(false);
  const [activeConvId, setActiveConvId]     = useState(null);
  const [rightPanel, setRightPanel]         = useState("kb");

  // ── Fetch conversation list ──────────────────────────────────────────────
  const loadConvos = useCallback(() => {
    api.listConversations()
      .then(list => setConvos(list))
      .catch(() => {});
  }, []);

  // ── On mount: load KB + conversations, auto-select the latest ───────────
  useEffect(() => {
    api.getKnowledge().then(setKb).catch(() => {});
    api.listConversations()
      .then(list => {
        setConvos(list);
        if (list.length > 0) setActiveConvId(list[0].id);
        setConvLoaded(true);
      })
      .catch(() => setConvLoaded(true));
  }, []);

  // ── KB update handler ────────────────────────────────────────────────────
  const handleKbUpdate = useCallback((updates) => {
    setKb(prev => {
      if (!prev) return prev;
      return { ...prev, data: knowledge.deepMerge(prev.data, updates) };
    });
    setTimeout(() => api.getKnowledge().then(setKb).catch(() => {}), 800);
  }, []);

  // ── New conversation created by ChatWindow ───────────────────────────────
  function handleConversationCreated(id) {
    setActiveConvId(id);
    // Re-fetch so the new tab appears with correct title
    setTimeout(loadConvos, 300);
  }

  // ── First message sent → title has been set, refresh sidebar ────────────
  function handleFirstMessage() {
    setTimeout(loadConvos, 300);
  }

  const biz   = user?.business;
  const phase = kb?.phase || "discovery";

  return (
    <div style={{ display:"flex", flexDirection:"column", height:"100vh", overflow:"hidden" }}>

      {/* ── Top nav ─────────────────────────────────────────────────── */}
      <header style={{
        height:50, borderBottom:"1px solid rgba(90,70,40,0.12)",
        background:"white", display:"flex", alignItems:"center",
        padding:"0 16px", gap:12, flexShrink:0,
      }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, flex:1 }}>
          <div style={{
            width:28, height:28, borderRadius:"50%", background:"#1a2744",
            display:"flex", alignItems:"center", justifyContent:"center",
            color:"white", fontSize:12, fontWeight:700,
          }}>B</div>
          <span style={{ fontSize:15, fontWeight:700, color:"#1a2744" }}>Business Buddy</span>
          {biz && (
            <span style={{
              fontSize:12, color:"#888",
              borderLeft:"1px solid rgba(90,70,40,0.2)",
              paddingLeft:10, marginLeft:2,
            }}>
              {biz.name}
            </span>
          )}
        </div>

        <div style={{ display:"flex", gap:4, background:"#f0ede8", borderRadius:8, padding:3 }}>
          {[{ id:"kb", label:"Knowledge" }, { id:"docs", label:"Documents" }].map(tab => (
            <button key={tab.id} onClick={() => setRightPanel(tab.id)}
              style={{
                fontSize:11, fontWeight:600, padding:"4px 12px",
                border:"none", borderRadius:6, cursor:"pointer",
                fontFamily:"inherit", transition:"all 0.15s",
                background: rightPanel === tab.id ? "white"   : "transparent",
                color:      rightPanel === tab.id ? "#1a2744" : "#888",
                boxShadow:  rightPanel === tab.id ? "0 1px 2px rgba(0,0,0,0.08)" : "none",
              }}>
              {tab.label}
            </button>
          ))}
        </div>

        <div style={{ display:"flex", alignItems:"center", gap:8 }}>
          <span style={{ fontSize:12, color:"#888" }}>{user?.full_name || user?.email}</span>
          <button onClick={() => navigate("/settings")} title="Settings"
            style={{
              display:"flex", alignItems:"center", justifyContent:"center",
              width:30, height:30, border:"1px solid rgba(90,70,40,0.2)",
              borderRadius:7, background:"transparent", cursor:"pointer",
              fontSize:14, color:"#6b6458",
            }}>⚙</button>
          <button onClick={logout}
            style={{
              fontSize:12, padding:"4px 10px",
              border:"1px solid rgba(90,70,40,0.2)", borderRadius:6,
              background:"transparent", cursor:"pointer",
              fontFamily:"inherit", color:"#666",
            }}>Sign out</button>
        </div>
      </header>

      {/* ── Three-panel body ─────────────────────────────────────────── */}
      <div style={{ display:"flex", flex:1, minHeight:0 }}>

        {/* Left: Conversation tabs */}
        <Sidebar
          convos={convos}
          activeId={activeConvId}
          onSelect={setActiveConvId}
          onNew={() => setActiveConvId(null)}
        />

        {/* Centre: Chat */}
        <div style={{ flex:1, display:"flex", flexDirection:"column", minWidth:0 }}>
          {convLoaded && (
            <ChatWindow
              key={activeConvId ?? "new"}
              conversationId={activeConvId}
              onConversationCreated={handleConversationCreated}
              onFirstMessage={handleFirstMessage}
              businessName={biz?.name}
              onKbUpdate={handleKbUpdate}
              initialPhase={kb?.phase}
            />
          )}
        </div>

        {/* Right: Knowledge or Documents */}
        {rightPanel === "kb"
          ? <KnowledgePanel kb={kb} businessName={biz?.name} phase={phase} />
          : <DocumentPanel  onKbUpdate={handleKbUpdate} />
        }
      </div>
    </div>
  );
}
