type ReportRow = {
  reference: string;
  title: string;
  category: string;
  status: string;
  priority_level: string;
  department: string;
  created_at: string;
  deadline_at: string;
  landmark: string;
};

const escapeHtml = (value: unknown) => String(value ?? "").replace(/[&<>"']/g, character => ({
  "&": "&amp;",
  "<": "&lt;",
  ">": "&gt;",
  '"': "&quot;",
  "'": "&#39;",
}[character]!));

export function buildPrintableReport(rows: ReportRow[], demoMode: boolean) {
  const body = rows.map(row => `<tr><td>${escapeHtml(row.reference)}</td><td>${escapeHtml(row.title)}</td><td>${escapeHtml(row.category)}</td><td>${escapeHtml(row.status)}</td><td>${escapeHtml(row.priority_level)}</td><td>${escapeHtml(row.department)}</td><td>${escapeHtml(new Date(row.created_at).toLocaleDateString("en-IN"))}</td><td>${escapeHtml(new Date(row.deadline_at).toLocaleDateString("en-IN"))}</td><td>${escapeHtml(row.landmark)}</td></tr>`).join("");
  const label = demoMode
    ? "DEMONSTRATION DATA · Synthetic sample records; not real civic reports"
    : "Configured CivicTrack records · Generated from the current database";
  return `<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>CivicTrack service report</title><style>
    @page{size:A4 landscape;margin:14mm}*{box-sizing:border-box}body{font:12px/1.45 Arial,sans-serif;color:#203047;margin:0}header{display:flex;justify-content:space-between;align-items:flex-start;border-bottom:2px solid #294e82;padding-bottom:12px;margin-bottom:14px}h1{font-size:22px;margin:0 0 3px}p{margin:0;color:#65748a}.label{font-size:10px;font-weight:bold;color:#8c6425;background:#fff5dd;border:1px solid #efdeb7;padding:6px 8px;border-radius:4px}table{width:100%;border-collapse:collapse}th{text-align:left;background:#edf2f8;color:#4b607a;font-size:9px;text-transform:uppercase;letter-spacing:.04em}th,td{padding:7px;border:1px solid #dfe5ec;vertical-align:top}td{font-size:10px}tbody tr:nth-child(even){background:#fafbfd}.meta{margin:10px 0 14px;display:flex;justify-content:space-between;color:#6f7d90;font-size:10px}.empty{padding:24px;text-align:center;color:#748196}@media print{.no-print{display:none}}
  </style></head><body><header><div><h1>CivicTrack service report</h1><p>${escapeHtml(rows.length)} complaint records · Generated ${escapeHtml(new Date().toLocaleString("en-IN"))}</p></div><div class="label">${escapeHtml(label)}</div></header><div class="meta"><span>Report fields exclude resident names and contact information.</span><span>Save as PDF from the browser print dialog.</span></div>${rows.length ? `<table><thead><tr><th>Reference</th><th>Issue</th><th>Category</th><th>Status</th><th>Priority</th><th>Department</th><th>Reported</th><th>Target date</th><th>Area</th></tr></thead><tbody>${body}</tbody></table>` : `<div class="empty">No complaint records are available.</div>`}<script>window.addEventListener("load",()=>setTimeout(()=>window.print(),180));</script></body></html>`;
}
