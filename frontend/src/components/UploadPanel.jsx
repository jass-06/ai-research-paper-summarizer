import { useRef, useState } from "react";
import { api } from "../api";

const MAX_MB = 25;

export default function UploadPanel({ onUploaded, notify }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);
  const [queue, setQueue] = useState([]); // [{name, state}]

  const handleFiles = async (fileList) => {
    const files = Array.from(fileList || []);
    if (!files.length) return;
    const rejected = files.filter((f) => !f.name.toLowerCase().endsWith(".pdf"));
    if (rejected.length) notify(`Skipped ${rejected.length} non-PDF file(s).`);
    const pdfs = files.filter((f) => f.name.toLowerCase().endsWith(".pdf"));
    const tooBig = pdfs.filter((f) => f.size > MAX_MB * 1024 * 1024);
    if (tooBig.length) notify(`Skipped ${tooBig.length} file(s) over ${MAX_MB} MB.`);
    const ok = pdfs.filter((f) => f.size <= MAX_MB * 1024 * 1024);

    setQueue(ok.map((f) => ({ name: f.name, state: "waiting" })));
    for (const [i, file] of ok.entries()) {
      setQueue((q) => q.map((x, j) => (j === i ? { ...x, state: "uploading" } : x)));
      try {
        onUploaded(await api.uploadPaper(file));
        setQueue((q) => q.map((x, j) => (j === i ? { ...x, state: "uploaded" } : x)));
      } catch (e) {
        setQueue((q) => q.map((x, j) => (j === i ? { ...x, state: "failed" } : x)));
        notify(`${file.name}: ${e.message}`);
      }
    }
    if (inputRef.current) inputRef.current.value = "";
    setTimeout(() => setQueue([]), 2500);
  };

  const busy = queue.some((x) => x.state === "uploading" || x.state === "waiting");

  return (
    <div>
      <div
        className={`upload-box ${dragging ? "dragging" : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleFiles(e.dataTransfer.files); }}
        onClick={() => !busy && inputRef.current?.click()}
        role="button"
        tabIndex={0}
      >
        <div className="upload-icon">⇪</div>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 600, marginBottom: 4 }}>
            {dragging ? "Drop your PDFs here" : "Drag & drop research papers, or click to choose"}
          </div>
          <div className="muted small">PDF only · up to {MAX_MB} MB each · multiple files allowed</div>
        </div>
        <input ref={inputRef} type="file" accept="application/pdf,.pdf" multiple hidden
               onChange={(e) => handleFiles(e.target.files)} />
        <span className="btn">{busy ? "Uploading…" : "Choose files"}</span>
      </div>
      {queue.length > 0 && (
        <div className="queue">
          {queue.map((q, i) => (
            <div key={i} className="queue-row">
              <span className="queue-name">{q.name}</span>
              <span className={`badge ${q.state === "failed" ? "error" : q.state === "uploaded" ? "done" : "processing"}`}>
                {q.state}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
