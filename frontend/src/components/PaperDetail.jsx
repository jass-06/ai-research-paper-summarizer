import { useEffect, useState } from "react";
import { api, displayTitle, isPending } from "../api";

const TABS = ["Summary", "Keywords & Topics", "Related Papers", "Ask the Paper", "Notes"];
const SUGGESTED = [
  "What dataset or sample was used?",
  "What are the main limitations?",
  "Explain the method in simple terms.",
];

export default function PaperDetail({ paperId, onBack, onChanged, notify }) {
  const [paper, setPaper] = useState(null);
  const [tab, setTab] = useState("Summary");
  const [notesDraft, setNotesDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const [question, setQuestion] = useState("");
  const [qa, setQa] = useState([]);
  const [asking, setAsking] = useState(false);

  useEffect(() => {
    let timer;
    let cancelled = false;
    const load = async () => {
      try {
        const p = await api.getPaper(paperId);
        if (cancelled) return;
        setPaper(p);
        setNotesDraft((d) => (d === "" ? p.notes || "" : d));
        onChanged?.(p);
        if (isPending(p)) timer = setTimeout(load, 3000);
      } catch (e) {
        notify(e.message);
      }
    };
    load();
    return () => { cancelled = true; clearTimeout(timer); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [paperId]);

  if (!paper) return <div className="empty-state">Loading…</div>;

  const saveNotes = async () => {
    setSaving(true);
    try {
      const updated = await api.updateNotes(paper.id, notesDraft);
      setPaper(updated);
      onChanged?.(updated);
      notify("Notes saved", "ok");
    } catch (e) {
      notify(e.message);
    } finally {
      setSaving(false);
    }
  };

  const reprocess = async () => {
    try {
      const updated = await api.reprocess(paper.id);
      setPaper(updated);
      onChanged?.(updated);
      // restart polling
      const poll = async () => {
        const p = await api.getPaper(paper.id);
        setPaper(p);
        onChanged?.(p);
        if (isPending(p)) setTimeout(poll, 3000);
      };
      setTimeout(poll, 1500);
    } catch (e) {
      notify(e.message);
    }
  };

  const ask = async (q) => {
    const text = (q ?? question).trim();
    if (text.length < 3) return;
    setAsking(true);
    try {
      const res = await api.ask(paper.id, text);
      setQa((prev) => [{ q: text, ...res }, ...prev]);
      setQuestion("");
    } catch (e) {
      notify(e.message);
    } finally {
      setAsking(false);
    }
  };

  const sections = (paper.summary || "").split(/\n\s*\n/).filter(Boolean).map((block) => {
    const m = block.match(/^\s*([A-Za-z ]{3,30}):\s*([\s\S]*)$/);
    return m ? { head: m[1], body: m[2] } : { head: null, body: block };
  });
  const related = paper.related_papers || [];

  return (
    <div>
      <button className="btn secondary" onClick={onBack} style={{ marginBottom: 16 }}>← Back</button>

      <div className="card">
        <div className="detail-header">
          <div style={{ minWidth: 0 }}>
            <div className="detail-title">{displayTitle(paper)}</div>
            <div className="muted small" style={{ margin: "4px 0 8px" }}>
              {paper.original_filename}
              {paper.page_count ? ` · ${paper.page_count} page${paper.page_count === 1 ? "" : "s"}` : ""}
              {paper.word_count ? ` · ${paper.word_count.toLocaleString()} words` : ""}
              {paper.processing_seconds ? ` · processed in ${paper.processing_seconds}s` : ""}
              {paper.model_used ? ` · ${paper.model_used}` : ""}
            </div>
            <span className={`badge ${paper.status}`}>{isPending(paper) && <span className="spinner" />}{paper.status}</span>
            {paper.difficulty && <span className="badge neutral" style={{ marginLeft: 6 }}>{paper.difficulty}</span>}
          </div>
          <div className="actions">
            <a className="btn secondary" href={api.pdfUrl(paper.id)} target="_blank" rel="noreferrer">Open PDF</a>
            {paper.status === "done" && (
              <a className="btn secondary" href={api.exportUrl(paper.id)}>Export .md</a>
            )}
            {(paper.status === "error" || paper.status === "done") && (
              <button className="btn" onClick={reprocess}>{paper.status === "error" ? "Retry" : "Re-run AI"}</button>
            )}
          </div>
        </div>
        {paper.tldr && <div className="tldr"><b>TL;DR</b> {paper.tldr}</div>}
        {paper.status === "error" && <div className="error-text">{paper.error_message}</div>}
        {isPending(paper) && (
          <div className="muted" style={{ marginTop: 8 }}>Processing — this page refreshes automatically…</div>
        )}
      </div>

      {paper.status === "done" && (
        <>
          <div className="tabs">
            {TABS.map((t) => (
              <button key={t} className={`tab ${tab === t ? "active" : ""}`} onClick={() => setTab(t)}>{t}</button>
            ))}
          </div>

          {tab === "Summary" && (
            <div className="card">
              {sections.map((s, i) => (
                <div key={i} className="summary-section">
                  {s.head && <div className="summary-head">{s.head}</div>}
                  <div className="summary-body">{s.body}</div>
                </div>
              ))}
            </div>
          )}

          {tab === "Keywords & Topics" && (
            <div className="card">
              <div className="card-title">Topics</div>
              {(paper.topics || []).map((t, i) => <span className="keyword-pill topic" key={i}>{t}</span>)}
              {!paper.topics?.length && <div className="muted">No topics extracted.</div>}
              <div className="card-title" style={{ marginTop: 18 }}>Keywords</div>
              {(paper.keywords || []).map((k, i) => <span className="keyword-pill" key={i}>{k}</span>)}
              {!paper.keywords?.length && <div className="muted">No keywords extracted.</div>}
            </div>
          )}

          {tab === "Related Papers" && (
            <div className="card">
              {related.length === 0 && <div className="muted">No related papers found.</div>}
              {related.map((r, i) => (
                <div key={i} className="related-row">
                  <div className="related-title">
                    {r.url ? <a href={r.url} target="_blank" rel="noreferrer">{r.title}</a> : r.title}
                    <span className={`badge ${r.verified ? "done" : "neutral"}`} style={{ marginLeft: 8 }}>
                      {r.verified ? "verified · arXiv" : "AI suggestion"}
                    </span>
                  </div>
                  <div className="muted small">
                    {[r.authors, r.year].filter(Boolean).join(" · ")}{r.authors || r.year ? " — " : ""}{r.reason}
                  </div>
                </div>
              ))}
              <div className="muted small" style={{ marginTop: 12 }}>
                "Verified" papers were found on arXiv using this paper's keywords. "AI suggestions" are research
                directions from the model and should be checked before you cite them.
              </div>
            </div>
          )}

          {tab === "Ask the Paper" && (
            <div className="card">
              <div className="ask-row">
                <input className="search" style={{ margin: 0 }} placeholder="Ask anything about this paper…"
                       value={question} onChange={(e) => setQuestion(e.target.value)}
                       onKeyDown={(e) => e.key === "Enter" && ask()} />
                <button className="btn" onClick={() => ask()} disabled={asking}>{asking ? "Thinking…" : "Ask"}</button>
              </div>
              <div style={{ margin: "10px 0" }}>
                {SUGGESTED.map((s) => (
                  <button key={s} className="chip" onClick={() => ask(s)} disabled={asking}>{s}</button>
                ))}
              </div>
              {qa.map((item, i) => (
                <div key={i} className="qa">
                  <div className="qa-q">Q: {item.q}</div>
                  <div className="qa-a">{item.answer}</div>
                  <details>
                    <summary className="muted small">Show the {item.excerpts.length} passages used</summary>
                    {item.excerpts.map((ex, j) => <div key={j} className="excerpt">[{j + 1}] {ex}</div>)}
                  </details>
                </div>
              ))}
            </div>
          )}

          {tab === "Notes" && (
            <div className="card">
              <textarea rows={10} value={notesDraft} onChange={(e) => setNotesDraft(e.target.value)}
                        placeholder="Write your own study notes here… (included in the Markdown export)" />
              <button className="btn" style={{ marginTop: 12 }} onClick={saveNotes} disabled={saving}>
                {saving ? "Saving…" : "Save notes"}
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}
