from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from ..extensions import db
from ..models import Patent, Summary
from .utils import make_summary_cache_key


class SummarizationService:
    def __init__(self, settings):
        self.settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def get_cached_summary(self, patent: Patent, summary_mode: str = "deep") -> Summary | None:
        cache_key = make_summary_cache_key(
            publication_number=patent.publication_number,
            model_name=self.settings.openai_summary_model,
            prompt_version=self.settings.prompt_version,
            source_hash=patent.source_hash,
            summary_mode=summary_mode,
        )
        return Summary.query.filter_by(cache_key=cache_key, status="completed").order_by(Summary.generated_at.desc()).first()

    def create_summary_record(self, patent: Patent, summary_mode: str = "deep") -> Summary:
        cache_key = make_summary_cache_key(
            publication_number=patent.publication_number,
            model_name=self.settings.openai_summary_model,
            prompt_version=self.settings.prompt_version,
            source_hash=patent.source_hash,
            summary_mode=summary_mode,
        )
        existing = Summary.query.filter_by(cache_key=cache_key).order_by(Summary.created_at.desc()).first()
        if existing:
            return existing

        summary = Summary(
            patent_id=patent.id,
            status="queued",
            model_name=self.settings.openai_summary_model,
            prompt_version=self.settings.prompt_version,
            summary_mode=summary_mode,
            source_hash_at_generation=patent.source_hash,
            cache_key=cache_key,
        )
        db.session.add(summary)
        db.session.commit()
        return summary

    def run_summary(self, summary_id: int) -> Summary:
        summary = Summary.query.get(summary_id)
        if summary is None:
            raise ValueError(f"Summary {summary_id} not found")

        patent = Patent.query.get(summary.patent_id)
        if patent is None:
            raise ValueError(f"Patent {summary.patent_id} not found")

        summary.status = "running"
        db.session.commit()

        try:
            structured = self._generate_structured_summary(patent, summary.summary_mode)
            markdown = self._render_markdown(structured)

            summary.summary_json = structured
            summary.summary_markdown = markdown
            summary.status = "completed"
            summary.generated_at = datetime.now(timezone.utc)
            summary.error_message = None
            db.session.commit()
            return summary
        except Exception as exc:
            summary.status = "failed"
            summary.error_message = str(exc)
            db.session.commit()
            raise

    def _build_source_text(self, patent: Patent, summary_mode: str) -> str:
        sections = {s.section_type: s.section_text for s in patent.sections}

        abstract = sections.get("abstract") or patent.abstract or ""
        claims = sections.get("claims") or ""
        summary_section = sections.get("summary") or ""
        description = sections.get("description") or ""
        background = sections.get("background") or ""

        limits = {
            "brief": 6000,
            "standard": 12000,
            "deep": 24000,
        }
        max_chars = limits.get(summary_mode, limits["deep"])

        parts = [
            f"TITLE:\n{patent.title or ''}",
            f"ABSTRACT:\n{abstract}",
            f"CLAIMS:\n{claims}",
        ]

        if summary_mode in {"standard", "deep"}:
            parts.append(f"SUMMARY OF INVENTION:\n{summary_section}")
            parts.append(f"BACKGROUND:\n{background}")

        if summary_mode == "deep":
            parts.append(f"DETAILED DESCRIPTION:\n{description}")

        joined = "\n\n".join(parts)
        return joined[:max_chars]

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
    def _generate_structured_summary(self, patent: Patent, summary_mode: str) -> dict[str, Any]:
        source_text = self._build_source_text(patent, summary_mode)

        if not self._client:
            return self._fallback_summary(patent, source_text)

        system_prompt = (
            "You are a patent analyst. Return strict JSON only with keys: "
            "overview, problem_addressed, mechanism, key_claim_elements, novelty_signals, "
            "implementation_signals, applications, risks_and_unknowns, evidence. "
            "The evidence key must be a list of objects with keys: section, quote, rationale. "
            "If uncertain, say uncertain. Do not invent facts."
        )

        user_prompt = (
            f"Publication Number: {patent.publication_number}\n"
            f"Summary Mode: {summary_mode}\n\n"
            "Source Text:\n"
            f"{source_text}"
        )

        completion = self._client.chat.completions.create(
            model=self.settings.openai_summary_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=self.settings.summary_max_output_tokens,
            temperature=0.2,
        )

        raw = completion.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        self._validate_structured(parsed)
        return parsed

    @staticmethod
    def _validate_structured(payload: dict[str, Any]) -> None:
        required = [
            "overview",
            "problem_addressed",
            "mechanism",
            "key_claim_elements",
            "novelty_signals",
            "implementation_signals",
            "applications",
            "risks_and_unknowns",
            "evidence",
        ]
        missing = [k for k in required if k not in payload]
        if missing:
            raise ValueError(f"Summary JSON missing required keys: {', '.join(missing)}")

    def _fallback_summary(self, patent: Patent, source_text: str) -> dict[str, Any]:
        excerpt = source_text[:1200]
        claims_hint = "Claims text available." if "CLAIMS:" in source_text and len(source_text.split("CLAIMS:")) > 1 else "Claims text unavailable in source."
        return {
            "overview": f"{patent.title or 'Patent record'} focuses on a technical invention described in the source document.",
            "problem_addressed": "The invention appears to target limitations in existing approaches described in the background and claim language.",
            "mechanism": "Mechanism details require AI generation with an OpenAI API key. The system captured source sections and can generate this on-demand.",
            "key_claim_elements": [claims_hint],
            "novelty_signals": ["Novelty analysis pending full model-generated synthesis."],
            "implementation_signals": ["Implementation details should be extracted from the detailed description and claims."],
            "applications": ["Applications can be inferred from the problem domain and assignee context."],
            "risks_and_unknowns": ["Fallback summary is limited because OPENAI_API_KEY is not configured."],
            "evidence": [
                {
                    "section": "source_excerpt",
                    "quote": excerpt,
                    "rationale": "Fallback evidence excerpt from ingested source text.",
                }
            ],
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        def _listify(value: Any) -> str:
            if isinstance(value, list):
                return "\n".join([f"- {item}" for item in value]) or "- None"
            return str(value)

        evidence_entries = payload.get("evidence", [])
        evidence_lines: list[str] = []
        for item in evidence_entries:
            if isinstance(item, dict):
                section = item.get("section", "unknown")
                quote = item.get("quote", "")
                rationale = item.get("rationale", "")
                evidence_lines.append(f"- **{section}**: \"{quote}\" ({rationale})")

        if not evidence_lines:
            evidence_lines.append("- No evidence provided")

        return "\n".join(
            [
                "## Overview",
                str(payload.get("overview", "")),
                "",
                "## Problem Addressed",
                str(payload.get("problem_addressed", "")),
                "",
                "## Mechanism",
                str(payload.get("mechanism", "")),
                "",
                "## Key Claim Elements",
                _listify(payload.get("key_claim_elements", [])),
                "",
                "## Novelty Signals",
                _listify(payload.get("novelty_signals", [])),
                "",
                "## Implementation Signals",
                _listify(payload.get("implementation_signals", [])),
                "",
                "## Applications",
                _listify(payload.get("applications", [])),
                "",
                "## Risks And Unknowns",
                _listify(payload.get("risks_and_unknowns", [])),
                "",
                "## Evidence",
                "\n".join(evidence_lines),
            ]
        )
