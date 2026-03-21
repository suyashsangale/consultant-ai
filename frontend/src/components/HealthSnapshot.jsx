import { useEffect, useState } from "react";
import { api } from "../api";

const CAT_LABELS = {
  overview: "Overview", products: "Products", customers: "Customers",
  revenue: "Revenue", team: "Team", competition: "Competition",
  history: "History", now: "Current State", future: "Future", ops: "Operations",
};

export default function HealthSnapshot() {
  const [snap, setSnap] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    api.getSnapshot()
      .then(setSnap)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) return (
    <div style={{ padding: 24, color: "#aaa", fontSize: 13 }}>Loading health data…</div>
  );
  if (!snap) return (
    <div style={{ padding: 24, color: "#c0392b", fontSize: 13 }}>Failed to load snapshot.</div>
  );

  const fill = snap.kb_fill_pct;
  const barColor = fill >= 70 ? "#22c55e" : fill >= 40 ? "#f59e0b" : "#ef4444";

  return (
    <div style={{ padding: "20px 20px 0" }}>
      {/* Fill gauge */}
      <div style={{ marginBottom: 20 }}>
        <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: "#1a2744" }}>Knowledge fill</span>
          <span style={{ fontSize: 12, fontWeight: 700, color: barColor }}>{fill}%</span>
        </div>
        <div style={{ height: 8, borderRadius: 4, background: "#eee", overflow: "hidden" }}>
          <div style={{
            height: "100%", borderRadius: 4, width: `${fill}%`,
            background: barColor, transition: "width 0.6s ease",
          }} />
        </div>
        <div style={{ fontSize: 11, color: "#888", marginTop: 5 }}>
          Phase: <strong style={{ color: snap.phase === "consulting" ? "#085041" : "#854f0b" }}>
            {snap.phase === "consulting" ? "Consulting" : "Discovering"}
          </strong>
        </div>
      </div>

      {/* Category grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 6, marginBottom: 20 }}>
        {Object.keys(CAT_LABELS).map(cat => {
          const filled = snap.filled_categories.includes(cat);
          return (
            <div key={cat} style={{
              display: "flex", alignItems: "center", gap: 6,
              padding: "5px 8px", borderRadius: 6,
              background: filled ? "#f0fdf4" : "#fafafa",
              border: `1px solid ${filled ? "rgba(34,197,94,0.2)" : "rgba(90,70,40,0.08)"}`,
            }}>
              <div style={{
                width: 7, height: 7, borderRadius: "50%", flexShrink: 0,
                background: filled ? "#22c55e" : "#d1d5db",
              }} />
              <span style={{ fontSize: 11, color: filled ? "#166534" : "#888", fontWeight: filled ? 600 : 400 }}>
                {CAT_LABELS[cat]}
              </span>
            </div>
          );
        })}
      </div>

      {/* Doc stats */}
      <div style={{ display: "flex", gap: 10, marginBottom: 4 }}>
        {[
          { label: "Documents", value: snap.total_documents },
          { label: "Passages", value: snap.total_chunks },
        ].map(s => (
          <div key={s.label} style={{
            flex: 1, padding: "10px 12px", borderRadius: 8,
            background: "#f7f6f3", border: "1px solid rgba(90,70,40,0.08)",
            textAlign: "center",
          }}>
            <div style={{ fontSize: 20, fontWeight: 700, color: "#1a2744" }}>{s.value}</div>
            <div style={{ fontSize: 10, color: "#888", marginTop: 2 }}>{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
