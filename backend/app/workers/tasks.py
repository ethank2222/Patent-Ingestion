from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app

from ..extensions import db
from ..models import SummaryJob
from ..services.summarization_service import SummarizationService


def execute_summary_job(summary_id: int, summary_job_id: str) -> None:
    job = SummaryJob.query.filter_by(job_id=summary_job_id).first()
    if job is None:
        return

    started = datetime.now(timezone.utc)
    job.status = "running"
    job.started_at = started
    db.session.commit()

    service = SummarizationService(current_app.settings)

    try:
        summary = service.run_summary(summary_id)
        finished = datetime.now(timezone.utc)
        job.status = "completed"
        job.summary_id = summary.id
        job.finished_at = finished
        job.latency_ms = int((finished - started).total_seconds() * 1000)
        db.session.commit()
    except Exception as exc:
        finished = datetime.now(timezone.utc)
        job.status = "failed"
        job.error_message = str(exc)
        job.finished_at = finished
        job.latency_ms = int((finished - started).total_seconds() * 1000)
        db.session.commit()
        raise
