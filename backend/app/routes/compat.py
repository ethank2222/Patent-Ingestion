from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import String, cast, or_

from ..models import Patent
from ..services.utils import parse_date
from .patents import get_patent, list_patents
from .summaries import get_summary_job, request_summary

compat_bp = Blueprint("compat", __name__)


def _pagination_dict(pagination, page: int, page_size: int) -> dict:
    return {
        "page": page,
        "page_size": page_size,
        "total": pagination.total,
        "pages": pagination.pages,
        "has_next": pagination.has_next,
        "has_prev": pagination.has_prev,
    }


def _positive_int_arg(*names: str, default: int, maximum: int | None = None) -> int:
    for name in names:
        raw = request.args.get(name)
        if raw in {None, ""}:
            continue
        try:
            value = max(int(raw), 1)
            return min(value, maximum) if maximum else value
        except ValueError:
            return default
    return default


def _course_from_patent(patent: Patent) -> dict:
    return {
        "id": patent.publication_number,
        "slug": patent.publication_number,
        "title": patent.title or patent.publication_number,
        "description": patent.abstract or "",
        "summary": patent.abstract or "",
        "category": "Patent",
        "status": "published",
        "publication_number": patent.publication_number,
        "publication_date": patent.publication_date.isoformat() if patent.publication_date else None,
        "assignee": patent.assignee,
        "url": f"/patents/{patent.publication_number}",
    }


def _filtered_patents_query():
    q = request.args.get("q", "").strip()
    assignee = request.args.get("assignee", "").strip()
    from_date = parse_date(request.args.get("from_date"))
    to_date = parse_date(request.args.get("to_date"))
    sort = request.args.get("sort", "publication_date_desc")

    query = Patent.query

    if q:
        like = f"%{q}%"
        query = query.filter(
            or_(
                Patent.publication_number.ilike(like),
                Patent.title.ilike(like),
                Patent.abstract.ilike(like),
            )
        )

    if assignee:
        query = query.filter(Patent.assignee.ilike(f"%{assignee}%"))

    if from_date:
        query = query.filter(Patent.publication_date >= from_date)
    if to_date:
        query = query.filter(Patent.publication_date <= to_date)

    cpc_prefix = request.args.get("cpc_prefix", "").strip().upper()
    if cpc_prefix:
        query = query.filter(
            or_(
                Patent.cpc_primary.ilike(f"{cpc_prefix}%"),
                cast(Patent.cpc_codes_json, String).ilike(f"%{cpc_prefix}%"),
            )
        )

    if sort == "publication_date_asc":
        return query.order_by(Patent.publication_date.asc(), Patent.publication_number.asc())
    if sort == "title_asc":
        return query.order_by(Patent.title.asc())
    return query.order_by(Patent.publication_date.desc(), Patent.publication_number.desc())


@compat_bp.get("/v1/health")
def legacy_health() -> tuple:
    return jsonify({"status": "ok"}), 200


@compat_bp.get("/v1/patents")
def legacy_list_patents() -> tuple:
    return list_patents()


@compat_bp.get("/v1/patents/<string:publication_number>")
def legacy_get_patent(publication_number: str) -> tuple:
    return get_patent(publication_number)


@compat_bp.post("/v1/patents/<string:publication_number>/summaries")
def legacy_request_summary(publication_number: str) -> tuple:
    return request_summary(publication_number)


@compat_bp.get("/v1/summaries/<string:job_id>")
def legacy_get_summary_job(job_id: str) -> tuple:
    return get_summary_job(job_id)


@compat_bp.get("/v1/courses")
def legacy_courses() -> tuple:
    page = _positive_int_arg("page", default=1)
    page_size = _positive_int_arg("page_size", "per_page", "limit", default=20, maximum=100)
    pagination = _filtered_patents_query().paginate(page=page, per_page=page_size, error_out=False)
    courses = [_course_from_patent(patent) for patent in pagination.items]

    return (
        jsonify(
            {
                "courses": courses,
                "items": courses,
                "pagination": _pagination_dict(pagination, page, page_size),
                "compatibility": "Legacy /api/v1/courses mapped to patent records.",
            }
        ),
        200,
    )


@compat_bp.get("/v1/courses/<string:publication_number>")
def legacy_course_detail(publication_number: str) -> tuple:
    patent = Patent.query.filter_by(publication_number=publication_number).first()
    if not patent:
        return jsonify({"course": None, "error": "Patent record not found"}), 404

    course = _course_from_patent(patent)
    course["patent"] = patent.to_detail_dict()
    return jsonify({"course": course, "item": course}), 200
