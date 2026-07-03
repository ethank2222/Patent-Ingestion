export default function SummaryPanel({ summary, status }) {
  if (!summary && status === "idle") {
    return <div className="empty">No summary generated yet.</div>;
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

  const payload = summary.summary_json || {};
  const keyPoints = Array.isArray(payload.key_points) ? payload.key_points : [];
  const potentialUses = Array.isArray(payload.potential_uses) ? payload.potential_uses : [];
  const compactSummary = typeof payload.summary === "string" ? payload.summary : "";

  return (
    <article className="summary-content">
      <div className="summary-meta">
        <span>Generated: {summary.generated_at || "-"}</span>
      </div>
      {compactSummary ? (
        <>
          <p className="summary-lead">{compactSummary}</p>
          {keyPoints.length > 0 && (
            <>
              <h2>Key Points</h2>
              <ul>
                {keyPoints.map((point) => (
                  <li key={point}>{point}</li>
                ))}
              </ul>
            </>
          )}
          {potentialUses.length > 0 && (
            <>
              <h2>Potential Uses</h2>
              <ul>
                {potentialUses.map((use) => (
                  <li key={use}>{use}</li>
                ))}
              </ul>
            </>
          )}
          {payload.caveat && <p className="caveat">{payload.caveat}</p>}
        </>
      ) : (
        <pre>{summary.summary_markdown}</pre>
      )}
    </article>
  );
}
