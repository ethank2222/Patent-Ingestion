from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ..extensions import db
from ..models import Patent, PatentSection
from .uspto_client import USPTOClient
from .utils import ensure_list, estimate_tokens, make_source_hash, normalize_string, parse_date


class IngestionService:
    def __init__(self, settings):
        self.settings = settings
        self.client = USPTOClient(
            base_url=settings.uspto_api_base,
            api_key=settings.uspto_api_key,
            timeout_seconds=settings.uspto_timeout_seconds,
        )

    def ingest_recent(self, days: int | None = None, limit: int | None = None) -> dict[str, Any]:
        days = days or self.settings.default_ingest_days
        limit = limit or self.settings.default_ingest_limit
        end_date = datetime.now(timezone.utc).date()
        start_date = end_date - timedelta(days=days)

        processed = 0
        created = 0
        updated = 0
        errors = 0

        page_start = 0
        rows = min(200, limit)

        while processed < limit:
            remaining = limit - processed
            rows = min(rows, remaining)
            try:
                result = self.client.search_recent_publications(start_date=start_date, end_date=end_date, start=page_start, rows=rows)
                records = result.get("records", [])
            except Exception:
                if self.settings.use_sample_data_on_failure:
                    records = self._load_sample_records()
                else:
                    raise

            if not records:
                break

            for record in records:
                try:
                    normalized = self._normalize_record(record)
                    if not normalized.get("publication_number"):
                        continue
                    is_new = self._upsert_patent(normalized)
                    processed += 1
                    if is_new:
                        created += 1
                    else:
                        updated += 1
                    if processed >= limit:
                        break
                except Exception:
                    errors += 1

            if len(records) < rows:
                break
            page_start += rows

        db.session.commit()
        return {
            "processed": processed,
            "created": created,
            "updated": updated,
            "errors": errors,
            "window": {"start_date": start_date.isoformat(), "end_date": end_date.isoformat()},
        }

    def _upsert_patent(self, data: dict[str, Any]) -> bool:
        patent = Patent.query.filter_by(publication_number=data["publication_number"]).first()
        is_new = patent is None
        if patent is None:
            patent = Patent(publication_number=data["publication_number"])
            db.session.add(patent)

        patent.application_number = data.get("application_number")
        patent.kind_code = data.get("kind_code")
        patent.doc_type = data.get("doc_type") or "application_publication"
        patent.publication_date = data.get("publication_date")
        patent.filing_date = data.get("filing_date")
        patent.priority_date = data.get("priority_date")
        patent.title = data.get("title")
        patent.abstract = data.get("abstract")
        patent.assignee = data.get("assignee")
        patent.inventors_json = data.get("inventors", [])
        patent.cpc_codes_json = data.get("cpc_codes", [])
        patent.cpc_primary = (data.get("cpc_codes") or [None])[0]
        patent.source_system = data.get("source_system") or "uspto_odp"
        patent.source_url = data.get("source_url")
        patent.source_hash = data.get("source_hash")

        incoming_sections = data.get("sections", {})
        existing_by_type = {s.section_type: s for s in patent.sections}

        for section_type, section_text in incoming_sections.items():
            if not section_text:
                continue
            section = existing_by_type.get(section_type)
            if section is None:
                section = PatentSection(patent=patent, section_type=section_type)
                db.session.add(section)
            section.section_text = section_text
            section.token_count_estimate = estimate_tokens(section_text)

        return is_new

    def _normalize_record(self, record: dict[str, Any]) -> dict[str, Any]:
        publication_number = (
            normalize_string(record.get("publicationNumber"))
            or normalize_string(record.get("publicationNumberText"))
            or normalize_string(record.get("patentNumber"))
            or normalize_string(record.get("publicationSequenceNumber"))
        )

        application_number = normalize_string(record.get("applicationNumberText") or record.get("applicationNumber"))
        kind_code = normalize_string(record.get("kindCode") or record.get("publicationKindCode"))

        title = normalize_string(record.get("inventionTitle") or record.get("title"))
        abstract = self._normalize_multivalue(record.get("abstractText") or record.get("abstract"))

        assignee = normalize_string(
            record.get("assigneeName")
            or record.get("assigneeEntityName")
            or record.get("assignee")
            or record.get("applicantName")
        )

        inventors = self._extract_inventors(record)
        cpc_codes = self._extract_cpc_codes(record)

        publication_date = parse_date(record.get("publicationDate") or record.get("patentIssueDate") or record.get("grantDate"))
        filing_date = parse_date(record.get("filingDate") or record.get("applicationFilingDate"))
        priority_date = parse_date(record.get("priorityDate"))

        doc_type = "grant" if record.get("grantDate") or record.get("patentIssueDate") else "application_publication"

        sections = {
            "abstract": abstract or "",
            "claims": self._normalize_multivalue(record.get("claimsText") or record.get("claimText") or record.get("claims")),
            "summary": self._normalize_multivalue(record.get("summaryText") or record.get("summary")),
            "description": self._normalize_multivalue(
                record.get("descriptionText")
                or record.get("detailedDescriptionText")
                or record.get("specificationText")
                or record.get("description")
            ),
            "background": self._normalize_multivalue(record.get("backgroundText") or record.get("background")),
        }

        canonical_for_hash = {
            "publication_number": publication_number,
            "application_number": application_number,
            "kind_code": kind_code,
            "title": title,
            "abstract": abstract,
            "sections": sections,
            "assignee": assignee,
            "inventors": inventors,
            "cpc_codes": cpc_codes,
            "publication_date": publication_date.isoformat() if publication_date else None,
            "filing_date": filing_date.isoformat() if filing_date else None,
        }

        return {
            "publication_number": publication_number,
            "application_number": application_number,
            "kind_code": kind_code,
            "doc_type": doc_type,
            "publication_date": publication_date,
            "filing_date": filing_date,
            "priority_date": priority_date,
            "title": title,
            "abstract": abstract,
            "assignee": assignee,
            "inventors": inventors,
            "cpc_codes": cpc_codes,
            "sections": sections,
            "source_system": "uspto_odp",
            "source_url": None,
            "source_hash": make_source_hash(canonical_for_hash),
        }

    @staticmethod
    def _normalize_multivalue(value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if isinstance(value, list):
            parts: list[str] = []
            for item in value:
                if isinstance(item, str) and item.strip():
                    parts.append(item.strip())
                elif isinstance(item, dict):
                    text = item.get("text") or item.get("value")
                    if text:
                        parts.append(str(text).strip())
            return "\n".join(parts).strip()
        if isinstance(value, dict):
            text = value.get("text") or value.get("value")
            return str(text).strip() if text else ""
        return str(value).strip()

    @staticmethod
    def _extract_inventors(record: dict[str, Any]) -> list[str]:
        candidates = [
            record.get("inventorNameArrayText"),
            record.get("inventorNameBag"),
            record.get("inventors"),
        ]
        names: list[str] = []
        for candidate in candidates:
            for value in ensure_list(candidate):
                if isinstance(value, str):
                    text = value.strip()
                    if text:
                        names.append(text)
                elif isinstance(value, dict):
                    full_name = value.get("inventorNameText") or value.get("name")
                    if full_name:
                        names.append(str(full_name).strip())
        return sorted(set(names))

    @staticmethod
    def _extract_cpc_codes(record: dict[str, Any]) -> list[str]:
        candidates = [
            record.get("cpcClassificationBag"),
            record.get("cpcCodeBag"),
            record.get("cpcCodes"),
        ]
        codes: list[str] = []
        for candidate in candidates:
            for value in ensure_list(candidate):
                if isinstance(value, str) and value.strip():
                    codes.append(value.strip())
                elif isinstance(value, dict):
                    code = (
                        value.get("cpcClassificationSymbolText")
                        or value.get("cpcCode")
                        or value.get("code")
                    )
                    if code:
                        codes.append(str(code).strip())
        return sorted(set(codes))

    def _load_sample_records(self) -> list[dict[str, Any]]:
        sample_path = Path(__file__).resolve().parents[2] / "seed" / "sample_patents.json"
        if not sample_path.exists():
            return []
        with sample_path.open("r", encoding="utf-8") as f:
            payload = json.load(f)
        if isinstance(payload, dict):
            return payload.get("records", [])
        if isinstance(payload, list):
            return payload
        return []
