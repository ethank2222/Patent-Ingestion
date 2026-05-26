from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from ..extensions import db
from ..services.ingestion_service import IngestionService

admin_bp = Blueprint("admin", __name__)


def _is_authorized() -> bool:
    expected = current_app.settings.admin_api_token
    auth_header = request.headers.get("Authorization", "")
    token_header = request.headers.get("X-Admin-Token", "")
    if auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1] == expected
    return token_header == expected


@admin_bp.post("/admin/ingest/incremental")
def ingest_incremental() -> tuple:
    if not _is_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    days = payload.get("days")
    limit = payload.get("limit")

    service = IngestionService(current_app.settings)
    result = service.ingest_recent(days=days, limit=limit)

    return jsonify({"status": "ok", "result": result}), 200


@admin_bp.post("/admin/ingest/backfill")
def ingest_backfill() -> tuple:
    if not _is_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    payload = request.get_json(silent=True) or {}
    days = payload.get("days", 365)
    limit = payload.get("limit", 2500)

    service = IngestionService(current_app.settings)
    result = service.ingest_recent(days=days, limit=limit)

    return jsonify({"status": "ok", "result": result, "mode": "backfill"}), 200


@admin_bp.post("/admin/bootstrap")
def bootstrap() -> tuple:
    if not _is_authorized():
        return jsonify({"error": "Unauthorized"}), 401

    db.create_all()
    return jsonify({"status": "ok", "message": "Database tables ensured."}), 200
