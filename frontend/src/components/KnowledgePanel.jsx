const KB_CATS = [
  { id:"overview",     label:"Overview"     },
  { id:"products",     label:"Products"     },
  { id:"customers",    label:"Customers"    },
  { id:"revenue",      label:"Revenue"      },
  { id:"team",         label:"Team"         },
  { id:"competition",  label:"Competition"  },
  { id:"history",      label:"History"      },
  { id:"now",          label:"Priorities"   },
  { id:"future",       label:"Future plans" },
  { id:"ops",          label:"Operations"   },
];

function pct(data) {
  return Math.round(
    KB_CATS.filter(c => data[c.id] && Object.keys(data[c.id]).length > 0).length
    / KB_CATS.length * 100
  );
}

export default function KnowledgePanel({ kb, businessName, phase }) {
  const data  = kb?.data || {};
  const p     = pct(data);
  const color = p > 60 ? "#0f6e56" : p > 30 ? "#b8832a" : "#888";

  return (
    <aside style={{
      width: 220, minWidth: 220, display:"flex", flexDirection:"column",
      borderRight: "1px solid rgba(90,70,40,0.12)",
      background: "#faf9f6", overflow: "hidden",
    }}>
      {/* Header */}
      <div style={{ padding:"14px 14px 12px", borderBottom:"1px solid rgba(90,70,40,0.1)" }}>
        <div style={{ fontSize:10, fontWeight:600, textTransform:"uppercase", letterSpacing:"0.12em", color:"#888", marginBottom:4 }}>
          Business intelligence
        </div>
        <div style={{ fontSize:14, fontWeight:600, color:"#1a2744", wordBreak:"break-word", minHeight:20 }}>
          {businessName || "—"}
        </div>
        <div style={{ fontSize:11, color: phase === "consulting" ? "#0f6e56" : "#b8832a",
          fontWeight:500, marginTop:3, textTransform:"capitalize" }}>
          {phase === "consulting" ? "Consulting mode" : "Discovery mode"}
        </div>

        {/* Progress bar */}
        <div style={{ marginTop:10 }}>
          <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
            <span style={{ fontSize:11, color:"#888" }}>Knowledge built</span>
            <span style={{ fontSize:11, fontWeight:600, color }}>{p}%</span>
          </div>
          <div style={{ height:4, background:"rgba(90,70,40,0.12)", borderRadius:2 }}>
            <div style={{ height:4, width:`${p}%`, background: color, borderRadius:2, transition:"width 0.6s ease" }} />
          </div>
        </div>
      </div>

      {/* Category list */}
      <div style={{ flex:1, overflowY:"auto", padding:8, display:"flex", flexDirection:"column", gap:4 }}>
        {KB_CATS.map(cat => {
          const catData = data[cat.id];
          const facts   = catData ? Object.entries(catData).filter(([,v]) => v).slice(0,3) : [];
          const filled  = facts.length > 0;

          return (
            <div key={cat.id} style={{
              borderRadius:8, padding:"7px 8px",
              border: filled ? "1px solid #9fe1cb" : "1px solid rgba(90,70,40,0.1)",
              background: filled ? "#e8f9f3" : "white",
              transition:"all 0.3s",
            }}>
              <div style={{ display:"flex", alignItems:"center", gap:6 }}>
                <div style={{
                  width:14, height:14, borderRadius:3, flexShrink:0,
                  background: filled ? "#1d9e75" : "rgba(90,70,40,0.15)",
                  display:"flex", alignItems:"center", justifyContent:"center",
                }}>
                  <span style={{ fontSize:8, color:"white", fontWeight:700 }}>
                    {filled ? "✓" : cat.id[0].toUpperCase()}
                  </span>
                </div>
                <span style={{ fontSize:11, fontWeight:600, color: filled ? "#085041" : "#888" }}>
                  {cat.label}
                </span>
              </div>

              {filled && (
                <div style={{ marginTop:4 }}>
                  {facts.map(([k, v], i) => (
                    <div key={i} style={{ fontSize:10, color:"#0f6e56", lineHeight:1.4 }}>
                      <span style={{ fontWeight:600 }}>{k.replace(/_/g," ")}: </span>
                      {String(v).length > 30 ? String(v).slice(0,30) + "…" : String(v)}
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
