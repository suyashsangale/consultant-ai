function timeAgo(dateStr) {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1)  return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24)  return `${hrs}h ago`;
  return `${Math.floor(hrs / 24)}d ago`;
}

export default function Sidebar({ convos = [], activeId, onSelect, onNew }) {
  return (
    <div style={{
      width: 240, minWidth: 240, display: "flex", flexDirection: "column",
      borderRight: "1px solid rgba(90,70,40,0.12)", background: "#f7f6f3",
      height: "100%",
    }}>

      {/* Header */}
      <div style={{
        padding: "14px 12px 10px", borderBottom: "1px solid rgba(90,70,40,0.1)",
        background: "#f7f6f3", flexShrink: 0,
      }}>
        <div style={{
          fontSize: 11, fontWeight: 700, color: "#aaa", letterSpacing: "0.08em",
          textTransform: "uppercase", marginBottom: 8, paddingLeft: 4,
        }}>
          Conversations
        </div>
        <button onClick={onNew} style={{
          width: "100%", padding: "8px 12px", background: "#1a2744", color: "white",
          border: "none", borderRadius: 8, fontSize: 12, fontWeight: 600, cursor: "pointer",
          fontFamily: "inherit", display: "flex", alignItems: "center", gap: 8,
        }}>
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
            stroke="white" strokeWidth="2.5" strokeLinecap="round">
            <line x1="12" y1="5" x2="12" y2="19"/>
            <line x1="5" y1="12" x2="19" y2="12"/>
          </svg>
          New conversation
        </button>
      </div>

      {/* Tab list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "6px 8px", display: "flex", flexDirection: "column", gap: 2 }}>
        {convos.length === 0 && (
          <div style={{ fontSize: 12, color: "#bbb", textAlign: "center", marginTop: "3rem", lineHeight: 1.7 }}>
            No conversations yet.<br/>Click + to start one.
          </div>
        )}

        {convos.map(c => {
          const isActive = activeId === c.id;
          return (
            <div key={c.id} onClick={() => onSelect(c.id)} style={{
              display: "flex", alignItems: "center", gap: 10,
              padding: "9px 10px", borderRadius: 8, cursor: "pointer",
              background: isActive ? "white" : "transparent",
              borderLeft: isActive ? "3px solid #1a2744" : "3px solid transparent",
              boxShadow: isActive ? "0 1px 4px rgba(0,0,0,0.07)" : "none",
              transition: "all 0.12s",
            }}>
              <div style={{
                width: 28, height: 28, borderRadius: 7, flexShrink: 0,
                background: isActive ? "#1a2744" : "#e5e2db",
                display: "flex", alignItems: "center", justifyContent: "center",
              }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none"
                  stroke={isActive ? "white" : "#888"} strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                </svg>
              </div>
              <div style={{ flex: 1, minWidth: 0 }}>
                <div style={{
                  fontSize: 12, fontWeight: isActive ? 600 : 500,
                  color: isActive ? "#1a2744" : "#444",
                  whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
                }}>
                  {c.title}
                </div>
                <div style={{ fontSize: 10, color: "#aaa", marginTop: 1 }}>
                  {timeAgo(c.updated_at || c.created_at)}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
