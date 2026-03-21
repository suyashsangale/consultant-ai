export default function SourcesBadge({ sources }) {
  if (!sources) return null;
  const { kb_categories = [], doc_chunks = 0 } = sources;
  if (kb_categories.length === 0 && doc_chunks === 0) return null;

  const parts = [];
  if (kb_categories.length > 0)
    parts.push(`${kb_categories.length} KB area${kb_categories.length > 1 ? "s" : ""}`);
  if (doc_chunks > 0)
    parts.push(`${doc_chunks} doc passage${doc_chunks > 1 ? "s" : ""}`);

  return (
    <div style={{ marginTop: 6, display: "flex", alignItems: "center", gap: 5, flexWrap: "wrap" }}>
      <span style={{
        fontSize: 10, color: "#7c6f5b", fontWeight: 500,
        padding: "2px 8px", borderRadius: 20,
        background: "rgba(90,70,40,0.06)",
        border: "1px solid rgba(90,70,40,0.12)",
        display: "inline-flex", alignItems: "center", gap: 4,
      }}>
        <svg width="9" height="9" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
        </svg>
        Based on {parts.join(" + ")}
      </span>
      {kb_categories.slice(0, 3).map(cat => (
        <span key={cat} style={{
          fontSize: 10, color: "#888",
          padding: "2px 7px", borderRadius: 20,
          background: "rgba(90,70,40,0.04)",
          border: "1px solid rgba(90,70,40,0.1)",
        }}>{cat}</span>
      ))}
      {kb_categories.length > 3 && (
        <span style={{ fontSize: 10, color: "#aaa" }}>+{kb_categories.length - 3} more</span>
      )}
    </div>
  );
}
