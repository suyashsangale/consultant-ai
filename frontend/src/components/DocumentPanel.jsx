import { useState, useEffect, useRef } from "react";
import { api, uploadDocument } from "../api";

const FILE_ICONS = { pdf: "PDF", pptx: "PPT", ppt: "PPT", docx: "DOC", doc: "DOC", txt: "TXT" };
const STATUS_COLOR = {
  ready:      { bg: "#e8f9f3", color: "#085041", label: "Ready"      },
  processing: { bg: "#fdf3e0", color: "#854f0b", label: "Processing" },
  failed:     { bg: "#fdf0ee", color: "#c0392b", label: "Failed"     },
};

function formatBytes(bytes) {
  if (bytes < 1024)        return bytes + " B";
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

function DocRow({ doc, onDelete, onRefresh }) {
  const st    = STATUS_COLOR[doc.status] || STATUS_COLOR.processing;
  const icon  = FILE_ICONS[doc.file_type] || "FILE";
  const [deleting, setDeleting] = useState(false);

  async function handleDelete() {
    if (!confirm(`Delete "${doc.original_name}"? This removes all its chunks from search.`)) return;
    setDeleting(true);
    try {
      await api.deleteDocument(doc.id);
      onDelete(doc.id);
    } catch (e) {
      alert(e.message);
      setDeleting(false);
    }
  }

  return (
    <div style={{
      display: "flex", alignItems: "flex-start", gap: 10,
      padding: "9px 10px", borderRadius: 8,
      border: "1px solid rgba(90,70,40,0.1)", background: "white",
      marginBottom: 5,
    }}>
      {/* Type badge */}
      <div style={{
        width: 34, height: 34, borderRadius: 6, flexShrink: 0,
        background: "#f0ede8", display: "flex", alignItems: "center",
        justifyContent: "center", fontSize: 9, fontWeight: 700, color: "#6b6458",
      }}>
        {icon}
      </div>

      {/* Info */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 12, fontWeight: 600, color: "#1a1612",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        }}>
          {doc.original_name}
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 3 }}>
          <span style={{
            fontSize: 10, fontWeight: 600, padding: "1px 7px",
            borderRadius: 10, background: st.bg, color: st.color,
          }}>
            {st.label}
          </span>
          <span style={{ fontSize: 10, color: "#888" }}>{formatBytes(doc.file_size)}</span>
          {doc.status === "ready" && (
            <span style={{ fontSize: 10, color: "#888" }}>{doc.chunk_count} chunks</span>
          )}
        </div>
        {doc.status === "failed" && doc.error_message && (
          <div style={{ fontSize: 10, color: "#c0392b", marginTop: 2, lineHeight: 1.3 }}>
            {doc.error_message.slice(0, 80)}
          </div>
        )}
        {doc.status === "processing" && (
          <div style={{ fontSize: 10, color: "#888", marginTop: 2 }}>
            Extracting text and building embeddings…
          </div>
        )}
      </div>

      {/* Actions */}
      <div style={{ display: "flex", gap: 4, flexShrink: 0 }}>
        {doc.status === "processing" && (
          <button onClick={onRefresh}
            style={{ fontSize: 10, padding: "3px 7px", border: "1px solid rgba(90,70,40,0.2)",
              borderRadius: 5, background: "transparent", cursor: "pointer",
              color: "#888", fontFamily: "inherit" }}>
            ↻
          </button>
        )}
        <button onClick={handleDelete} disabled={deleting}
          style={{ fontSize: 10, padding: "3px 7px", border: "1px solid rgba(192,57,43,0.2)",
            borderRadius: 5, background: "transparent", cursor: "pointer",
            color: "#c0392b", fontFamily: "inherit" }}>
          {deleting ? "…" : "✕"}
        </button>
      </div>
    </div>
  );
}

export default function DocumentPanel({ onKbUpdate }) {
  const [docs, setDocs]           = useState([]);
  const [dragging, setDragging]   = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const inputRef = useRef(null);
  const pollRef  = useRef(null);

  // Poll every 3s while any doc is processing
  useEffect(() => {
    loadDocs();
    pollRef.current = setInterval(() => {
      const hasProcessing = docs.some(d => d.status === "processing");
      if (hasProcessing) loadDocs();
    }, 3000);
    return () => clearInterval(pollRef.current);
  }, [docs.some(d => d.status === "processing")]);

  async function loadDocs() {
    try {
      const list = await api.listDocuments();
      setDocs(list);
    } catch (_) {}
  }

  async function handleFiles(files) {
    const allowed = ["pdf", "pptx", "ppt", "docx", "doc", "txt"];
    for (const file of files) {
      const ext = file.name.split(".").pop().toLowerCase();
      if (!allowed.includes(ext)) {
        setUploadError(`"${file.name}" is not a supported type (PDF, PPTX, DOCX, TXT).`);
        return;
      }
    }

    setUploadError("");
    setUploading(true);

    for (const file of files) {
      try {
        const doc = await uploadDocument(file);
        setDocs(prev => [doc, ...prev]);
      } catch (e) {
        setUploadError(e.message);
      }
    }
    setUploading(false);
  }

  function onDrop(e) {
    e.preventDefault();
    setDragging(false);
    const files = Array.from(e.dataTransfer.files);
    if (files.length) handleFiles(files);
  }

  function onFileInput(e) {
    const files = Array.from(e.target.files);
    if (files.length) handleFiles(files);
    e.target.value = "";
  }

  function removeDoc(id) {
    setDocs(prev => prev.filter(d => d.id !== id));
  }

  const processingCount = docs.filter(d => d.status === "processing").length;
  const readyCount      = docs.filter(d => d.status === "ready").length;

  return (
    <div style={{
      width: 260, minWidth: 260, display: "flex", flexDirection: "column",
      borderLeft: "1px solid rgba(90,70,40,0.12)", background: "#faf9f6",
    }}>
      {/* Header */}
      <div style={{ padding: "14px 14px 10px", borderBottom: "1px solid rgba(90,70,40,0.1)" }}>
        <div style={{ fontSize: 10, fontWeight: 600, textTransform: "uppercase",
          letterSpacing: "0.12em", color: "#888", marginBottom: 4 }}>
          Documents
        </div>
        <div style={{ fontSize: 13, fontWeight: 600, color: "#1a2744" }}>
          Knowledge sources
        </div>
        {docs.length > 0 && (
          <div style={{ fontSize: 11, color: "#888", marginTop: 2 }}>
            {readyCount} ready · {processingCount} processing
          </div>
        )}
      </div>

      {/* Drop zone */}
      <div
        onDragOver={e => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        onClick={() => inputRef.current?.click()}
        style={{
          margin: "10px", borderRadius: 8, padding: "16px 12px",
          border: `2px dashed ${dragging ? "#b8832a" : "rgba(90,70,40,0.2)"}`,
          background: dragging ? "#fdf3e0" : "transparent",
          cursor: "pointer", textAlign: "center", transition: "all 0.15s",
          flexShrink: 0,
        }}
      >
        <div style={{ fontSize: 22, marginBottom: 5, color: "#b8832a" }}>⊕</div>
        <div style={{ fontSize: 12, fontWeight: 600, color: "#1a2744" }}>
          {uploading ? "Uploading…" : "Drop files here"}
        </div>
        <div style={{ fontSize: 10, color: "#888", marginTop: 3 }}>
          PDF · PPTX · DOCX · TXT · up to 50 MB
        </div>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.pptx,.ppt,.docx,.doc,.txt"
          style={{ display: "none" }}
          onChange={onFileInput}
        />
      </div>

      {uploadError && (
        <div style={{ margin: "0 10px 8px", padding: "7px 10px", background: "#fdf0ee",
          color: "#c0392b", borderRadius: 6, fontSize: 11,
          border: "1px solid rgba(192,57,43,0.15)" }}>
          {uploadError}
        </div>
      )}

      {/* Document list */}
      <div style={{ flex: 1, overflowY: "auto", padding: "0 10px 10px" }}>
        {docs.length === 0 && (
          <div style={{ fontSize: 11, color: "#aaa", textAlign: "center",
            marginTop: "1.5rem", lineHeight: 1.6 }}>
            Upload a PDF, deck, or doc and your buddy will read it and extract knowledge automatically.
          </div>
        )}
        {docs.map(doc => (
          <DocRow
            key={doc.id}
            doc={doc}
            onDelete={removeDoc}
            onRefresh={loadDocs}
          />
        ))}
      </div>

      {/* How it works */}
      {docs.length > 0 && readyCount > 0 && (
        <div style={{
          margin: "0 10px 10px", padding: "8px 10px", borderRadius: 7,
          background: "#e8f9f3", border: "1px solid #9fe1cb",
        }}>
          <div style={{ fontSize: 10, fontWeight: 600, color: "#085041", marginBottom: 3 }}>
            How documents work
          </div>
          <div style={{ fontSize: 10, color: "#0f6e56", lineHeight: 1.5 }}>
            When you ask a question, relevant passages are automatically retrieved and shown to your buddy alongside its knowledge base.
          </div>
        </div>
      )}
    </div>
  );
}
