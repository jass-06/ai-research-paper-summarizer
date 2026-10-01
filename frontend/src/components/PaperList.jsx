import { displayTitle, isPending } from "../api";

export default function PaperList({ papers, onSelect, onDelete }) {
  if (!papers.length) {
    return <div className="empty-state">No papers here yet — upload one above to get started.</div>;
  }
  return (
    <div>
      {papers.map((p) => (
        <div className="card paper-card" key={p.id} onClick={() => onSelect(p.id)}>
          <div className="paper-row">
            <div style={{ flex: 1, minWidth: 0 }}>
              <div className="paper-title">{displayTitle(p)}</div>
              {p.tldr && <div className="paper-tldr">{p.tldr}</div>}
              <div className="muted small" style={{ marginTop: 4 }}>
                {p.title && p.title !== p.original_filename ? `${p.original_filename} · ` : ""}
                {new Date(p.created_at + (p.created_at.endsWith("Z") ? "" : "Z")).toLocaleString()}
                {p.page_count ? ` · ${p.page_count} page${p.page_count === 1 ? "" : "s"}` : ""}
                {p.difficulty ? ` · ${p.difficulty}` : ""}
              </div>
            </div>
            <span className={`badge ${p.status}`}>
              {isPending(p) && <span className="spinner" />}{p.status}
            </span>
            <button className="btn danger" style={{ marginLeft: 8 }}
                    onClick={(e) => { e.stopPropagation(); onDelete(p.id); }}>
              Delete
            </button>
          </div>
        </div>
      ))}
    </div>
  );
}
