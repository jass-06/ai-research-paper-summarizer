import { useState } from "react";
import { api, displayTitle } from "../api";

export default function ComparePanel({ papers, notify, onOpen }) {
  const [selected, setSelected] = useState([]);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);

  const toggle = (id) =>
    setSelected((s) => (s.includes(id) ? s.filter((x) => x !== id) : s.length < 6 ? [...s, id] : s));

  const run = async () => {
    setLoading(true);
    setResult(null);
    try {
      setResult(await api.compare(selected));
    } catch (e) {
      notify(e.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <div className="page-title">Compare Papers</div>
      <div className="page-subtitle">
        Pick 2–6 processed papers to get a mini literature review: shared themes, differences and research gaps.
      </div>

      {papers.length < 2 ? (
        <div className="empty-state">You need at least two processed papers to compare.</div>
      ) : (
        <div className="card">
          {papers.map((p) => (
            <label key={p.id} className="check-row">
              <input type="checkbox" checked={selected.includes(p.id)} onChange={() => toggle(p.id)} />
              <span>{displayTitle(p)}</span>
            </label>
          ))}
          <button className="btn" style={{ marginTop: 12 }} disabled={selected.length < 2 || loading} onClick={run}>
            {loading ? "Comparing…" : `Compare ${selected.length || ""} papers`}
          </button>
        </div>
      )}

      {result && (
        <div className="card">
          <div className="card-title">Overview</div>
          <p>{result.overview}</p>
          <Section title="Common themes" items={result.common_themes} />
          <Section title="Key differences" items={result.differences} />
          <Section title="Research gaps (ideas for your own work)" items={result.research_gaps} highlight />
          <Section title="Suggested reading order" items={result.reading_order} ordered />
          <div className="muted small" style={{ marginTop: 8 }}>
            Open a paper:{" "}
            {papers.filter((p) => selected.includes(p.id)).map((p) => (
              <button key={p.id} className="chip" onClick={() => onOpen(p.id)}>{displayTitle(p).slice(0, 40)}</button>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function Section({ title, items, ordered, highlight }) {
  if (!items?.length) return null;
  const List = ordered ? "ol" : "ul";
  return (
    <div className={highlight ? "gap-box" : ""} style={{ marginTop: 14 }}>
      <div className="card-title">{title}</div>
      <List className="plain-list">{items.map((x, i) => <li key={i}>{x}</li>)}</List>
    </div>
  );
}
