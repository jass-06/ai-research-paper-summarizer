import { useCallback, useEffect, useRef, useState } from "react";
import { api, isPending } from "./api";
import UploadPanel from "./components/UploadPanel";
import PaperList from "./components/PaperList";
import PaperDetail from "./components/PaperDetail";
import ComparePanel from "./components/ComparePanel";

const NAV = [
  { key: "Dashboard", icon: "◧" },
  { key: "Papers", icon: "☰" },
  { key: "Compare", icon: "⇄" },
];

export default function App() {
  const [nav, setNav] = useState("Dashboard");
  const [papers, setPapers] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [health, setHealth] = useState(null);
  const [offline, setOffline] = useState(false);
  const [query, setQuery] = useState("");
  const [toast, setToast] = useState(null);
  const toastTimer = useRef();

  const notify = useCallback((msg, kind = "error") => {
    setToast({ msg, kind });
    clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 4500);
  }, []);

  const refresh = useCallback(async () => {
    try {
      setPapers(await api.listPapers(query));
      setOffline(false);
    } catch {
      setOffline(true);
    }
  }, [query]);

  useEffect(() => {
    const t = setTimeout(refresh, 250); // debounce search typing
    return () => clearTimeout(t);
  }, [refresh]);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth(null));
  }, [offline]);

  // Live updates: poll while any paper is still processing (v1 only polled the detail page)
  const anyPending = papers.some(isPending);
  useEffect(() => {
    if (!anyPending) return;
    const t = setInterval(refresh, 3000);
    return () => clearInterval(t);
  }, [anyPending, refresh]);

  const handleUploaded = (paper) => setPapers((prev) => [paper, ...prev]);

  const handleDelete = async (id) => {
    const p = papers.find((x) => x.id === id);
    if (!window.confirm(`Delete "${p?.original_filename}"? This also removes its stored files.`)) return;
    try {
      await api.deletePaper(id);
      setPapers((prev) => prev.filter((x) => x.id !== id));
      if (selectedId === id) setSelectedId(null);
      notify("Paper deleted", "ok");
    } catch (e) {
      notify(e.message);
    }
  };

  const handleChanged = (u) => setPapers((prev) => prev.map((p) => (p.id === u.id ? u : p)));

  const done = papers.filter((p) => p.status === "done");
  const counts = {
    total: papers.length,
    done: done.length,
    pending: papers.filter(isPending).length,
    failed: papers.filter((p) => p.status === "error").length,
    pages: papers.reduce((s, p) => s + (p.page_count || 0), 0),
  };
  const topicCounts = {};
  done.forEach((p) => (p.topics || []).forEach((t) => (topicCounts[t] = (topicCounts[t] || 0) + 1)));
  const topTopics = Object.entries(topicCounts).sort((a, b) => b[1] - a[1]).slice(0, 8);

  const go = (key) => { setNav(key); setSelectedId(null); setQuery(""); };

  return (
    <div className="layout">
      <aside className="sidebar">
        <div className="brand">📄 PaperAI</div>
        {NAV.map(({ key, icon }) => (
          <button key={key} className={`nav-item ${nav === key && !selectedId ? "active" : ""}`}
                  onClick={() => go(key)}>
            <span className="nav-icon">{icon}</span>{key}
          </button>
        ))}

        <div className="system-panel">
          <div className="system-title">System status</div>
          {health ? (
            <>
              <StatusRow label="API" ok value={`v${health.version}`} />
              <StatusRow label="Database" ok={health.database} value={health.database_engine} />
              <StatusRow label="Storage" ok value={health.storage_backend} />
              <StatusRow label="Processing" ok value={health.processing_mode.split(" ")[0]} />
              <StatusRow label="AI" ok={health.ai_configured}
                         value={health.ai_configured ? health.ai_provider : "no key"} />
              <StatusRow label="arXiv" ok={health.arxiv_enabled} value={health.arxiv_enabled ? "on" : "off"} />
            </>
          ) : (
            <StatusRow label="API" ok={false} value="offline" />
          )}
        </div>
      </aside>

      <main className="main">
        {offline && (
          <div className="banner">
            Can't reach the backend. Start it with <code>uvicorn app.main:app --reload</code> inside{" "}
            <code>backend/</code>, then this page reconnects automatically.
          </div>
        )}
        {health && !health.ai_configured && (
          <div className="banner warn">
            No AI key configured — add <code>GROQ_API_KEY</code> to <code>.env</code> (free at console.groq.com)
            or set <code>AI_PROVIDER=mock</code> to try the app with placeholder output.
          </div>
        )}
        {health?.ai_provider === "mock" && (
          <div className="banner info">Mock AI mode — summaries are placeholders, not real AI output.</div>
        )}

        {selectedId ? (
          <PaperDetail paperId={selectedId} onBack={() => setSelectedId(null)}
                       onChanged={handleChanged} notify={notify} />
        ) : nav === "Compare" ? (
          <ComparePanel papers={done} notify={notify} onOpen={setSelectedId} />
        ) : (
          <>
            <div className="page-title">{nav === "Dashboard" ? "Research Dashboard" : "Your Papers"}</div>
            <div className="page-subtitle">
              {nav === "Dashboard"
                ? "Upload papers and get structured AI insights, verified related work and Q&A."
                : "Search, open, retry or delete your uploaded papers."}
            </div>

            {nav === "Dashboard" && (
              <>
                <div className="stat-grid">
                  <Stat value={counts.total} label="Total papers" />
                  <Stat value={counts.done} label="Processed" tone="green" />
                  <Stat value={counts.pending} label="In progress" tone="blue" />
                  <Stat value={counts.failed} label="Failed" tone="red" />
                  <Stat value={counts.pages} label="Pages read" />
                </div>
                {topTopics.length > 0 && (
                  <div className="card">
                    <div className="card-title">Topics across your library</div>
                    {topTopics.map(([t, c]) => (
                      <span className="keyword-pill" key={t}>{t} <b>{c}</b></span>
                    ))}
                  </div>
                )}
              </>
            )}

            <UploadPanel onUploaded={handleUploaded} notify={notify} />

            {nav === "Papers" && (
              <input className="search" placeholder="Search by file name, title or summary…"
                     value={query} onChange={(e) => setQuery(e.target.value)} />
            )}
            <PaperList papers={nav === "Dashboard" ? papers.slice(0, 5) : papers}
                       onSelect={setSelectedId} onDelete={handleDelete} />
            {nav === "Dashboard" && papers.length > 5 && (
              <button className="btn secondary" onClick={() => go("Papers")}>View all {papers.length} papers →</button>
            )}
          </>
        )}
      </main>

      {toast && <div className={`toast ${toast.kind}`}>{toast.msg}</div>}
    </div>
  );
}

function Stat({ value, label, tone }) {
  return (
    <div className="stat-card">
      <div className={`stat-value ${tone || ""}`}>{value}</div>
      <div className="stat-label">{label}</div>
    </div>
  );
}

function StatusRow({ label, ok, value }) {
  return (
    <div className="status-row">
      <span className={`dot ${ok ? "ok" : "bad"}`} />
      <span className="status-label">{label}</span>
      <span className="status-value">{value}</span>
    </div>
  );
}
