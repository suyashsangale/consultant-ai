import { useState } from "react";
import { api } from "../api";

const SCORE_COLORS = { 5: "#22c55e", 4: "#84cc16", 3: "#f59e0b", 2: "#f97316", 1: "#ef4444" };

export default function BuddyTest() {
  const [state, setState] = useState("idle");   // idle | generating | answering | scoring | results | error
  const [questions, setQuestions] = useState([]);
  const [answers, setAnswers] = useState({});   // { [question_id]: string }
  const [results, setResults] = useState(null);
  const [errMsg, setErrMsg] = useState("");

  async function startTest() {
    setState("generating");
    setErrMsg("");
    try {
      const res = await api.generateTest();
      setQuestions(res.questions);
      setAnswers({});
      setState("answering");
    } catch (e) {
      setErrMsg(e.message);
      setState("error");
    }
  }

  async function submitAnswers() {
    setState("scoring");
    try {
      const payload = {
        questions,
        answers: questions.map(q => ({
          question_id: q.id,
          answer: answers[q.id] || "",
        })),
      };
      const res = await api.scoreTest(payload);
      setResults(res);
      setState("results");
    } catch (e) {
      setErrMsg(e.message);
      setState("error");
    }
  }

  function reset() {
    setState("idle");
    setQuestions([]);
    setAnswers({});
    setResults(null);
  }

  // ── Idle ──
  if (state === "idle") return (
    <div style={{ padding: "0 20px 20px", textAlign: "center" }}>
      <div style={{ fontSize: 32, marginBottom: 8 }}>🧠</div>
      <div style={{ fontSize: 13, color: "#555", lineHeight: 1.6, marginBottom: 16 }}>
        Test how well your buddy knows your business — and whether <em>you</em> agree with what it thinks it knows.
      </div>
      <button onClick={startTest} style={{
        padding: "9px 22px", background: "#1a2744", color: "white",
        border: "none", borderRadius: 8, fontSize: 13, fontWeight: 600,
        cursor: "pointer", fontFamily: "inherit",
      }}>
        Start buddy test
      </button>
    </div>
  );

  // ── Generating / Scoring ──
  if (state === "generating" || state === "scoring") return (
    <div style={{ padding: "0 20px 20px", textAlign: "center", color: "#888", fontSize: 13 }}>
      <div style={{ fontSize: 24, marginBottom: 10 }}>
        {state === "generating" ? "📝" : "⚙️"}
      </div>
      {state === "generating" ? "Generating questions…" : "Scoring your answers…"}
    </div>
  );

  // ── Error ──
  if (state === "error") {
    const isRateLimit = errMsg.toLowerCase().includes("rate limit");
    return (
      <div style={{ padding: "0 20px 20px" }}>
        <div style={{ padding: "10px 14px", borderRadius: 8, fontSize: 12,
          border: `1px solid ${isRateLimit ? "rgba(245,158,11,0.3)" : "rgba(192,57,43,0.2)"}`,
          background: isRateLimit ? "#fffbeb" : "#fdf0ee",
          color: isRateLimit ? "#92400e" : "#c0392b", marginBottom: 12, lineHeight: 1.6 }}>
          {isRateLimit
            ? "⏱ Groq rate limit hit. Wait ~15 seconds then try again — the free tier throttles rapid requests."
            : errMsg}
        </div>
        <button onClick={reset} style={{
          fontSize: 12, padding: "6px 14px", border: "1px solid rgba(90,70,40,0.2)",
          borderRadius: 6, background: "transparent", cursor: "pointer", fontFamily: "inherit",
        }}>Try again</button>
      </div>
    );
  }

  // ── Answering ──
  if (state === "answering") return (
    <div style={{ padding: "0 20px 20px" }}>
      <div style={{ fontSize: 12, color: "#888", marginBottom: 14, lineHeight: 1.5 }}>
        Answer these {questions.length} questions based on what you know about your business. Your buddy will compare.
      </div>
      {questions.map((q, i) => (
        <div key={q.id} style={{ marginBottom: 14 }}>
          <div style={{ fontSize: 12, fontWeight: 600, color: "#1a2744", marginBottom: 5 }}>
            {i + 1}. {q.question}
          </div>
          <textarea
            value={answers[q.id] || ""}
            onChange={e => setAnswers(prev => ({ ...prev, [q.id]: e.target.value }))}
            rows={2}
            placeholder="Your answer…"
            style={{
              width: "100%", fontFamily: "inherit", fontSize: 12,
              border: "1px solid rgba(90,70,40,0.2)", borderRadius: 6,
              padding: "7px 10px", lineHeight: 1.5, color: "#1a1612",
              background: "#f8f7f4", resize: "none", boxSizing: "border-box",
            }}
          />
        </div>
      ))}
      <div style={{ display: "flex", gap: 8 }}>
        <button onClick={submitAnswers} style={{
          padding: "8px 18px", background: "#1a2744", color: "white",
          border: "none", borderRadius: 8, fontSize: 12, fontWeight: 600,
          cursor: "pointer", fontFamily: "inherit",
        }}>Submit answers</button>
        <button onClick={reset} style={{
          padding: "8px 14px", background: "transparent",
          border: "1px solid rgba(90,70,40,0.2)", borderRadius: 8,
          fontSize: 12, cursor: "pointer", fontFamily: "inherit", color: "#666",
        }}>Cancel</button>
      </div>
    </div>
  );

  // ── Results ──
  if (state === "results" && results) {
    const pct = Math.round((results.overall_score / 5) * 100);
    const col = results.overall_score >= 4 ? "#22c55e" : results.overall_score >= 3 ? "#f59e0b" : "#ef4444";
    return (
      <div style={{ padding: "0 20px 20px" }}>
        {/* Score bar */}
        <div style={{ marginBottom: 16 }}>
          <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: "#1a2744" }}>Agreement score</span>
            <span style={{ fontSize: 12, fontWeight: 700, color: col }}>
              {results.overall_score.toFixed(1)} / 5
            </span>
          </div>
          <div style={{ height: 8, borderRadius: 4, background: "#eee", overflow: "hidden" }}>
            <div style={{
              height: "100%", borderRadius: 4, width: `${pct}%`,
              background: col, transition: "width 0.6s ease",
            }} />
          </div>
        </div>

        <div style={{
          padding: "10px 12px", background: "#f7f6f3",
          borderRadius: 8, fontSize: 12, color: "#444",
          lineHeight: 1.6, marginBottom: 16,
          border: "1px solid rgba(90,70,40,0.08)",
        }}>
          {results.summary}
        </div>

        {results.results.map((r, i) => (
          <div key={r.question_id} style={{
            marginBottom: 12, padding: "10px 12px",
            borderRadius: 8, background: "white",
            border: `1px solid ${SCORE_COLORS[r.score]}33`,
          }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
              <span style={{ fontSize: 11, fontWeight: 600, color: "#1a2744" }}>{i + 1}. {r.question}</span>
              <span style={{
                fontSize: 11, fontWeight: 700, color: SCORE_COLORS[r.score],
                background: `${SCORE_COLORS[r.score]}18`,
                padding: "1px 7px", borderRadius: 20,
              }}>{r.score}/5</span>
            </div>
            <div style={{ fontSize: 11, color: "#555", marginBottom: 4 }}>
              <strong>You:</strong> {r.your_answer || <em style={{ color: "#aaa" }}>No answer</em>}
            </div>
            <div style={{ fontSize: 11, color: "#555", marginBottom: 4 }}>
              <strong>Buddy:</strong> {r.buddy_answer}
            </div>
            <div style={{ fontSize: 10, color: "#888", fontStyle: "italic" }}>{r.feedback}</div>
          </div>
        ))}

        <button onClick={reset} style={{
          width: "100%", padding: "8px", background: "transparent",
          border: "1px solid rgba(90,70,40,0.2)", borderRadius: 8,
          fontSize: 12, cursor: "pointer", fontFamily: "inherit", color: "#666",
        }}>Retake test</button>
      </div>
    );
  }

  return null;
}
