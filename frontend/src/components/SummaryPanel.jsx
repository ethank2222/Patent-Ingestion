export default function SummaryPanel({ summary, status }) {
  if (!summary && status === "idle") {
    return <div className="empty">No summary generated yet. Choose a mode and click Generate.</div>;
  }

  if (status === "running" || status === "queued") {
    return <div className="loading">Summary generation in progress...</div>;
  }

  if (status === "failed") {
    return <div className="error">Summary failed. Please retry.</div>;
  }

  if (!summary) {
    return null;
  }

  return (
    <article className="summary-content">
      <div className="summary-meta">
        <span>Model: {summary.model_name}</span>
        <span>Mode: {summary.summary_mode}</span>
        <span>Generated: {summary.generated_at || "-"}</span>
      </div>
      <pre>{summary.summary_markdown}</pre>
    </article>
  );
}
