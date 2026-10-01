const API_URL = (import.meta.env.VITE_API_URL || "").replace(/\/$/, "");

export const apiUrl = (path) => `${API_URL}${path}`;

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(apiUrl(path), options);
  } catch {
    throw new Error("Cannot reach the backend. Is it running on port 8000?");
  }
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
    } catch { /* not JSON */ }
    throw new Error(detail || `Request failed (${res.status})`);
  }
  return res.json();
}

const json = (method, body) => ({
  method,
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request("/api/health"),
  stats: () => request("/api/stats"),
  listPapers: (q = "") => request(`/api/papers${q ? `?q=${encodeURIComponent(q)}` : ""}`),
  getPaper: (id) => request(`/api/papers/${id}`),
  uploadPaper: (file) => {
    const form = new FormData();
    form.append("file", file);
    return request("/api/papers/upload", { method: "POST", body: form });
  },
  updateNotes: (id, notes) => request(`/api/papers/${id}/notes`, json("PATCH", { notes })),
  reprocess: (id) => request(`/api/papers/${id}/reprocess`, { method: "POST" }),
  deletePaper: (id) => request(`/api/papers/${id}`, { method: "DELETE" }),
  ask: (id, question) => request(`/api/papers/${id}/ask`, json("POST", { question })),
  compare: (paper_ids) => request("/api/papers/compare", json("POST", { paper_ids })),
  pdfUrl: (id) => apiUrl(`/api/papers/${id}/pdf`),
  exportUrl: (id) => apiUrl(`/api/papers/${id}/export.md`),
};

export const isPending = (p) => p.status === "uploaded" || p.status === "processing";
export const displayTitle = (p) => p.title || p.original_filename;
