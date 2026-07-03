import React, { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getPatent, getSummaryJob, requestSummary } from "../api";
import SummaryPanel from "../components/SummaryPanel";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export default function PatentDetailPage() {
  const { publicationNumber } = useParams();
  const [patent, setPatent] = useState(null);
  const [loadingPatent, setLoadingPatent] = useState(true);
  const [error, setError] = useState("");

  const [summary, setSummary] = useState(null);
  const [summaryStatus, setSummaryStatus] = useState("idle");
  const [jobMeta, setJobMeta] = useState(null);

  useEffect(() => {
    let active = true;

    async function loadPatent() {
      setLoadingPatent(true);
      setError("");
      try {
        const response = await getPatent(publicationNumber);
        if (active) {
          setPatent(response);
        }
      } catch (err) {
        if (active) {
          setError(err.message || "Failed to load patent details");
        }
      } finally {
        if (active) {
          setLoadingPatent(false);
        }
      }
    }

    loadPatent();
    return () => {
      active = false;
    };
  }, [publicationNumber]);

  async function pollJob(jobId) {
    for (let attempt = 0; attempt < 120; attempt += 1) {
      const statusPayload = await getSummaryJob(jobId);
      setJobMeta(statusPayload.job || null);

      const jobStatus = statusPayload.job?.status;
      if (statusPayload.summary && jobStatus === "completed") {
        setSummary(statusPayload.summary);
        setSummaryStatus("completed");
        return;
      }

      if (jobStatus === "failed") {
        setSummaryStatus("failed");
        setError(statusPayload.job?.error_message || "Summary generation failed");
        return;
      }

      setSummaryStatus(jobStatus || "running");
      await sleep(2000);
    }

    setSummaryStatus("failed");
    setError("Summary timed out. Please retry.");
  }

  async function handleGenerateSummary() {
    setError("");
    setSummaryStatus("queued");
    setSummary(null);

    try {
      const response = await requestSummary(publicationNumber);
      setJobMeta(response.job || null);

      if (response.summary) {
        setSummary(response.summary);
        setSummaryStatus("completed");
        return;
      }

      if (response.job?.job_id) {
        await pollJob(response.job.job_id);
      } else {
        setSummaryStatus("failed");
        setError("No job id returned by server.");
      }
    } catch (err) {
      setSummaryStatus("failed");
      setError(err.message || "Failed to generate summary");
    }
  }

  if (loadingPatent) {
    return <div className="loading">Loading patent...</div>;
  }

  if (error && !patent) {
    return (
      <section className="panel">
        <Link to="/" className="back-link">
          Back to list
        </Link>
        <div className="error">{error}</div>
      </section>
    );
  }

  if (!patent) {
    return null;
  }

  return (
    <section className="panel">
      <Link to="/" className="back-link">
        Back to list
      </Link>

      <h1>{patent.title || patent.publication_number}</h1>
      <div className="meta-grid">
        <div>
          <strong>Publication</strong>
          <span>{patent.publication_number}</span>
        </div>
        <div>
          <strong>Publication Date</strong>
          <span>{patent.publication_date || "-"}</span>
        </div>
        <div>
          <strong>Assignee</strong>
          <span>{patent.assignee || "-"}</span>
        </div>
      </div>

      <div className="summary-actions">
        <button onClick={handleGenerateSummary} disabled={summaryStatus === "running" || summaryStatus === "queued"}>
          {summaryStatus === "running" || summaryStatus === "queued" ? "Generating..." : "Generate Summary"}
        </button>
      </div>

      {jobMeta && (
        <p className="hint">
          Job: {jobMeta.job_id} | Status: {jobMeta.status}
        </p>
      )}

      {error && <div className="error">{error}</div>}

      <SummaryPanel summary={summary} status={summaryStatus} />

      {patent.abstract && (
        <section className="abstract-block">
          <h2>Patent Abstract</h2>
          <p>{patent.abstract}</p>
        </section>
      )}
    </section>
  );
}
