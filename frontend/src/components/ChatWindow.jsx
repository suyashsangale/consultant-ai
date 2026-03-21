import { useState, useEffect, useRef } from "react";
import ReactMarkdown from "react-markdown";
import { api } from "../api";
import SourcesBadge from "./SourcesBadge";

// Web Speech API — supported in Chrome/Edge. Returns null in Firefox/Safari.
const SR = window.SpeechRecognition || window.webkitSpeechRecognition || null;

const HAT_LABELS = {
  cfo: "CFO mode", marketer: "Marketing mode",
  ops: "Ops mode", hr: "People mode", strategy: "Strategy mode", auto: "",
};

const HAT_COLORS = {
  cfo: "#1d4ed8", marketer: "#7c3aed", ops: "#b45309",
  hr: "#0f766e",  strategy: "#1a2744", auto: "#888",
};

export default function ChatWindow({ conversationId, onConversationCreated, onFirstMessage, businessName, onKbUpdate, initialPhase }) {
  const [messages, setMessages]   = useState([]);
  const [input, setInput]         = useState("");
  const [loading, setLoading]     = useState(false);
  const [error, setError]         = useState("");
  const [gaps, setGaps]           = useState([]);
  const [phase, setPhase]         = useState(initialPhase || "discovery");
  const [activeHat, setActiveHat] = useState("auto");
  const [initialized, setInitialized] = useState(false);
  const [listening, setListening] = useState(false);
  const endRef  = useRef(null);
  const taRef   = useRef(null);
  const srRef   = useRef(null);

  function toggleVoice() {
    if (!SR) { alert("Voice input is not supported in this browser. Please use Chrome or Edge."); return; }
    if (listening) {
      srRef.current?.stop();
      setListening(false);
      return;
    }
    const rec = new SR();
    rec.continuous = false;
    rec.interimResults = false;
    rec.lang = "en-US";
    rec.onresult = (e) => {
      const transcript = e.results[0][0].transcript;
      setInput(prev => (prev ? prev + " " + transcript : transcript));
      taRef.current?.focus();
    };
    rec.onerror = () => setListening(false);
    rec.onend   = () => setListening(false);
    srRef.current = rec;
    rec.start();
    setListening(true);
  }

  // Auto-scroll
  useEffect(() => { endRef.current?.scrollIntoView({ behavior:"smooth" }); }, [messages, loading]);

  // Load existing conversation or start fresh
  useEffect(() => {
    setMessages([]);
    setInitialized(false);

    if (conversationId) {
      api.getConversation(conversationId).then(conv => {
        setMessages(conv.messages.map(m => ({ role: m.role, content: m.content })));
        setInitialized(true);
      });
    } else {
      // New conversation — trigger greeting
      sendMessage(null, true);
    }
  }, [conversationId]);

  async function sendMessage(text, isGreeting = false) {
    const msg = text ?? input.trim();
    if (!isGreeting && (!msg || loading)) return;
    if (!isGreeting) setInput("");
    setError("");
    setLoading(true);

    if (!isGreeting && msg) {
      setMessages(prev => [...prev, { role:"user", content: msg }]);
    }

    try {
      const payload = { message: isGreeting ? "Start our session by asking me one focused question to understand my business — what we do, who we serve, or what challenge I'm trying to solve. Be concise and direct." : msg };
      if (conversationId) payload.conversation_id = conversationId;

      const res = await api.chat(payload);

      const isFirstUserMsg = !isGreeting && messages.filter(m => m.role === "user").length === 0;

      if (!conversationId && res.conversation_id) {
        onConversationCreated?.(res.conversation_id);
      } else if (isFirstUserMsg) {
        // Title was just set on the backend — refresh sidebar tab label
        onFirstMessage?.();
      }

      setMessages(prev => [...prev, { role:"assistant", content: res.reply, sources: res.sources }]);
      setGaps(res.knowledge_gaps || []);
      setPhase(res.phase || "discovery");
      if (res.knowledge_updates) onKbUpdate?.(res.knowledge_updates);
      setInitialized(true);
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  function onKey(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
  }

  const initials = businessName?.[0]?.toUpperCase() || "B";

  function safeContent(content) {
    const t = (content || "").trim();
    if (t.startsWith("{") || t.startsWith("```")) {
      const candidates = [
        t,
        t.replace(/^```[a-zA-Z0-9]*\n?/, "").replace(/\n?```$/, "").trim(),
      ];
      for (const s of candidates) {
        try {
          const p = JSON.parse(s);
          if (typeof p.reply === "string") return p.reply;
        } catch {}
      }
    }
    return content;
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", flex:1, minHeight:0 }}>

      {/* Topbar */}
      <div style={{ padding:"10px 16px", borderBottom:"1px solid rgba(90,70,40,0.1)",
        display:"flex", alignItems:"center", gap:10, background:"white", flexShrink:0 }}>
        <div style={{ width:30, height:30, borderRadius:"50%", background:"#1a2744",
          display:"flex", alignItems:"center", justifyContent:"center",
          color:"white", fontSize:12, fontWeight:700, flexShrink:0 }}>B</div>
        <div style={{ flex:1 }}>
          <div style={{ fontSize:13, fontWeight:600, color:"#1a2744" }}>
            {businessName ? `${businessName} — Business Buddy` : "Business Buddy"}
          </div>
          <div style={{ fontSize:11, color:"#888" }}>
            {phase === "consulting" ? "Advising from full business context" : "Building knowledge of your business"}
          </div>
        </div>

        {/* Hat selector */}
        <select value={activeHat} onChange={e => setActiveHat(e.target.value)}
          style={{ fontSize:11, border:"1px solid rgba(90,70,40,0.2)", borderRadius:6,
            padding:"3px 8px", background:"white", color: HAT_COLORS[activeHat], fontWeight:600,
            fontFamily:"inherit", cursor:"pointer", outline:"none" }}>
          <option value="auto">Auto mode</option>
          <option value="cfo">CFO</option>
          <option value="marketer">Marketing</option>
          <option value="ops">Operations</option>
          <option value="hr">People</option>
          <option value="strategy">Strategy</option>
        </select>

        <span style={{ fontSize:10, fontWeight:600, padding:"3px 9px", borderRadius:20,
          background: phase === "consulting" ? "#e8f9f3" : "#fdf3e0",
          color: phase === "consulting" ? "#085041" : "#854f0b" }}>
          {phase === "consulting" ? "Consulting" : "Discovering"}
        </span>
      </div>

      {/* Messages */}
      <div style={{ flex:1, overflowY:"auto", padding:"16px", display:"flex",
        flexDirection:"column", gap:12 }}>
        {messages.map((m, i) => (
          <div key={i} style={{ display:"flex", flexDirection: m.role === "user" ? "row-reverse" : "row",
            gap:8, alignItems:"flex-start", animation:"fadeUp 0.2s ease" }}>
            <div style={{ width:28, height:28, borderRadius:"50%", flexShrink:0,
              background: m.role === "assistant" ? "#1a2744" : "#e8f9f3",
              display:"flex", alignItems:"center", justifyContent:"center",
              fontSize:11, fontWeight:700,
              color: m.role === "assistant" ? "white" : "#085041" }}>
              {m.role === "assistant" ? "B" : initials}
            </div>
            <div style={{ maxWidth:"78%" }}>
              <div style={{
                padding:"10px 13px", fontSize:13, lineHeight:1.65,
                wordBreak:"break-word",
                whiteSpace: m.role === "assistant" ? "normal" : "pre-wrap",
                borderRadius: m.role === "assistant" ? "2px 12px 12px 12px" : "12px 2px 12px 12px",
                background: m.role === "assistant" ? "white" : "#1a2744",
                border: m.role === "assistant" ? "1px solid rgba(90,70,40,0.1)" : "none",
                color: m.role === "assistant" ? "#1a1612" : "white",
              }}>
                {m.role === "assistant"
                  ? <ReactMarkdown components={{
                      p:      ({node, ...p}) => <p style={{margin:"0 0 8px"}} {...p}/>,
                      ul:     ({node, ...p}) => <ul style={{margin:"4px 0 8px",paddingLeft:18}} {...p}/>,
                      ol:     ({node, ...p}) => <ol style={{margin:"4px 0 8px",paddingLeft:18}} {...p}/>,
                      li:     ({node, ...p}) => <li style={{marginBottom:3}} {...p}/>,
                      strong: ({node, ...p}) => <strong style={{fontWeight:700}} {...p}/>,
                      h1:     ({node, ...p}) => <div style={{fontWeight:700,fontSize:15,margin:"8px 0 4px"}} {...p}/>,
                      h2:     ({node, ...p}) => <div style={{fontWeight:700,fontSize:14,margin:"6px 0 4px"}} {...p}/>,
                      h3:     ({node, ...p}) => <div style={{fontWeight:600,fontSize:13,margin:"4px 0 3px"}} {...p}/>,
                      code:   ({node, inline, ...p}) => inline
                        ? <code style={{background:"rgba(90,70,40,0.08)",borderRadius:3,padding:"1px 4px",fontSize:12}} {...p}/>
                        : <pre style={{background:"rgba(90,70,40,0.06)",borderRadius:6,padding:"8px 10px",fontSize:12,overflowX:"auto",margin:"6px 0"}}><code {...p}/></pre>,
                    }}>{safeContent(m.content)}</ReactMarkdown>
                  : safeContent(m.content)}
              </div>
              {m.role === "assistant" && m.sources && <SourcesBadge sources={m.sources} />}
            </div>
          </div>
        ))}

        {loading && (
          <div style={{ display:"flex", gap:8, alignItems:"flex-start" }}>
            <div style={{ width:28, height:28, borderRadius:"50%", background:"#1a2744",
              display:"flex", alignItems:"center", justifyContent:"center",
              color:"white", fontSize:11, fontWeight:700, flexShrink:0 }}>B</div>
            <div style={{ padding:"12px 14px", background:"white",
              border:"1px solid rgba(90,70,40,0.1)", borderRadius:"2px 12px 12px 12px",
              display:"flex", gap:4, alignItems:"center" }}>
              {[0,1,2].map(i => (
                <span key={i} style={{ width:6, height:6, borderRadius:"50%",
                  background:"#888", display:"inline-block",
                  animation:`blink 1.2s ${i*0.2}s infinite` }} />
              ))}
            </div>
          </div>
        )}

        {error && (
          <div style={{ padding:"8px 12px", background:"#fdf0ee", color:"#c0392b",
            borderRadius:8, fontSize:13, border:"1px solid rgba(192,57,43,0.15)" }}>
            {error}
          </div>
        )}

        <div ref={endRef} />
      </div>

      {/* Gap chips */}
      {gaps.length > 0 && !loading && (
        <div style={{ padding:"0 16px 8px", display:"flex", flexWrap:"wrap", gap:5 }}>
          <span style={{ fontSize:10, color:"#888", alignSelf:"center" }}>Still needs:</span>
          {gaps.map((g, i) => (
            <button key={i} onClick={() => sendMessage(`Here's info about ${g}: `)}
              style={{ fontSize:11, padding:"3px 10px", background:"#fdf3e0", color:"#854f0b",
                border:"1px solid rgba(184,131,42,0.25)", borderRadius:20, cursor:"pointer",
                fontFamily:"inherit", transition:"background 0.15s" }}>
              {g}
            </button>
          ))}
        </div>
      )}

      {/* Input */}
      <div style={{ padding:"10px 16px 14px", borderTop:"1px solid rgba(90,70,40,0.1)",
        display:"flex", gap:8, alignItems:"flex-end", background:"white", flexShrink:0 }}>
        <textarea ref={taRef} value={input} onChange={e => setInput(e.target.value)}
          onKeyDown={onKey} rows={2}
          placeholder={phase === "discovery" ? "Tell me about your business…" : "Ask your buddy anything…"}
          style={{ flex:1, resize:"none", fontFamily:"inherit", fontSize:13,
            border:"1px solid rgba(90,70,40,0.2)", borderRadius:8,
            padding:"9px 12px", lineHeight:1.5, color:"#1a1612",
            background:"#f8f7f4", outline:"none", maxHeight:100 }} />
        <button onClick={toggleVoice} title={SR ? (listening ? "Stop recording" : "Voice input") : "Not supported in this browser"}
          style={{ width:38, height:38, borderRadius:8, flexShrink:0, alignSelf:"flex-end",
            background: listening ? "#c0392b" : SR ? "#f0f0f0" : "#e0e0e0",
            border:"none", fontSize:16, cursor: SR ? "pointer" : "not-allowed",
            transition:"background 0.15s", display:"flex", alignItems:"center", justifyContent:"center",
            animation: listening ? "pulse 1s infinite" : "none" }}>
          {listening ? (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="white">
              <rect x="6" y="6" width="12" height="12" rx="2"/>
            </svg>
          ) : (
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
              stroke={SR ? "#444" : "#aaa"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="2" width="6" height="11" rx="3"/>
              <path d="M5 10a7 7 0 0 0 14 0"/>
              <line x1="12" y1="17" x2="12" y2="21"/>
              <line x1="9"  y1="21" x2="15" y2="21"/>
            </svg>
          )}
        </button>
        <button onClick={() => sendMessage()} disabled={!input.trim() || loading}
          style={{ width:38, height:38, borderRadius:8, flexShrink:0, alignSelf:"flex-end",
            background: input.trim() && !loading ? "#1a2744" : "#ccc",
            border:"none", color:"white", fontSize:16, cursor: input.trim() && !loading ? "pointer" : "not-allowed",
            transition:"background 0.15s", display:"flex", alignItems:"center", justifyContent:"center" }}>
          ↑
        </button>
      </div>

      <style>{`
        @keyframes fadeUp { from { opacity:0; transform:translateY(5px) } to { opacity:1; transform:translateY(0) } }
        @keyframes blink  { 0%,80%,100%{ opacity:0.2 } 40%{ opacity:1 } }
        @keyframes pulse  { 0%,100%{ opacity:1 } 50%{ opacity:0.5 } }
      `}</style>
    </div>
  );
}
