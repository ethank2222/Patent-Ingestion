from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..extensions import db
from ..models import Patent, Summary, SummaryJob
from ..services.summarization_service import SummarizationService
from ..workers.queue import QueueManager

summaries_bp = Blueprint("summaries", __name__)


@summaries_bp.post("/patents/<string:publication_number>/summaries")
def request_summary(publication_number: str) -> tuple:
    patent = Patent.query.filter_by(publication_number=publication_number).first()
    if not patent:
        return jsonify({"error": "Patent not found"}), 404

    payload = request.get_json(silent=True) or {}
    summary_mode = (payload.get("mode") or "deep").strip().lower()
    requested_by = (payload.get("requested_by") or "anonymous").strip()

    if summary_mode not in {"brief", "standard", "deep"}:
        return jsonify({"error": "Invalid mode. Use one of: brief, standard, deep."}), 400

    service = SummarizationService(current_app.settings)
    cached = service.get_cached_summary(patent=patent, summary_mode=summary_mode)
    if cached:
        job = SummaryJob(
            patent_id=patent.id,
            summary_id=cached.id,
            status="completed",
            requested_by=requested_by,
            cache_hit=True,
        )
        db.session.add(job)
        db.session.commit()
        return jsonify({"job": job.to_dict(), "summary": cached.to_dict(), "cache_hit": True}), 200

    summary = service.create_summary_record(patent=patent, summary_mode=summary_mode)

    if summary.status == "completed":
        job = SummaryJob(
            patent_id=patent.id,
            summary_id=summary.id,
            status="completed",
            requested_by=requested_by,
            cache_hit=True,
        )
        db.session.add(job)
        db.session.commit()
        return jsonify({"job": job.to_dict(), "summary": summary.to_dict(), "cache_hit": True}), 200

    summary.status = "queued"

    job = SummaryJob(
        patent_id=patent.id,
        summary_id=summary.id,
        status="queued",
        requested_by=requested_by,
        cache_hit=False,
    )
    db.session.add(job)
    db.session.commit()

    queue = QueueManager(current_app.settings)
    queue_result = queue.enqueue_summary(summary_id=summary.id, summary_job_id=job.job_id)

    db.session.refresh(job)

    status_code = 202 if queue_result.get("enqueued") else 200
    body = {"job": job.to_dict(), "queue": queue_result, "cache_hit": False}

    if job.status == "completed":
        completed_summary = Summary.query.get(job.summary_id)
        if completed_summary:
            body["summary"] = completed_summary.to_dict()

    return jsonify(body), status_code


@summaries_bp.get("/summaries/<string:job_id>")
def get_summary_job(job_id: str) -> tuple:
    job = SummaryJob.query.filter_by(job_id=job_id).first()
    if not job:
        return jsonify({"error": "Job not found"}), 404

    body = {"job": job.to_dict()}
    if job.summary_id:
        summary = Summary.query.get(job.summary_id)
        if summary:
            body["summary"] = summary.to_dict()

    return jsonify(body), 200
