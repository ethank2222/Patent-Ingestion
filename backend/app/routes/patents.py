from __future__ import annotations

from flask import Blueprint, jsonify, request
from sqlalchemy import cast, or_, String

from ..models import Patent
from ..services.utils import parse_date

patents_bp = Blueprint("patents", __name__)


@patents_bp.get("/patents")
def list_patents() -> tuple:
    page = max(int(request.args.get("page", 1)), 1)
    page_size = min(max(int(request.args.get("page_size", 20)), 1), 100)

    q = request.args.get("q", "").strip()
    doc_type = request.args.get("doc_type", "").strip()
    cpc_prefix = request.args.get("cpc_prefix", "").strip().upper()
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

    if doc_type:
        query = query.filter(Patent.doc_type == doc_type)

    if cpc_prefix:
        like_cpc = f"{cpc_prefix}%"
        query = query.filter(
            or_(
                Patent.cpc_primary.ilike(like_cpc),
                cast(Patent.cpc_codes_json, String).ilike(f"%{cpc_prefix}%"),
            )
        )

    if assignee:
        query = query.filter(Patent.assignee.ilike(f"%{assignee}%"))

    if from_date:
        query = query.filter(Patent.publication_date >= from_date)
    if to_date:
        query = query.filter(Patent.publication_date <= to_date)

    if sort == "publication_date_asc":
        query = query.order_by(Patent.publication_date.asc(), Patent.publication_number.asc())
    elif sort == "title_asc":
        query = query.order_by(Patent.title.asc())
    else:
        query = query.order_by(Patent.publication_date.desc(), Patent.publication_number.desc())

    pagination = query.paginate(page=page, per_page=page_size, error_out=False)

    return (
        jsonify(
            {
                "items": [patent.to_list_dict() for patent in pagination.items],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total": pagination.total,
                    "pages": pagination.pages,
                    "has_next": pagination.has_next,
                    "has_prev": pagination.has_prev,
                },
            }
        ),
        200,
    )


@patents_bp.get("/patents/<string:publication_number>")
def get_patent(publication_number: str) -> tuple:
    patent = Patent.query.filter_by(publication_number=publication_number).first()
    if not patent:
        return jsonify({"error": "Patent not found"}), 404
    return jsonify(patent.to_detail_dict()), 200
