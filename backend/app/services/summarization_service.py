from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from ..extensions import db
from ..models import Patent, Summary
from .utils import make_source_hash, make_summary_cache_key


class SummarizationService:
    def __init__(self, settings):
        self.settings = settings
        self._client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def get_cached_summary(self, patent: Patent, summary_mode: str = "summary") -> Summary | None:
        source_hash = self._summary_source_hash(patent)
        cache_key = make_summary_cache_key(
            publication_number=patent.publication_number,
            model_name=self.settings.openai_summary_model,
            prompt_version=self.settings.prompt_version,
            source_hash=source_hash,
            summary_mode=summary_mode,
        )
        return Summary.query.filter_by(cache_key=cache_key, status="completed").order_by(Summary.generated_at.desc()).first()

    def create_summary_record(self, patent: Patent, summary_mode: str = "summary") -> Summary:
        source_hash = self._summary_source_hash(patent)
        cache_key = make_summary_cache_key(
            publication_number=patent.publication_number,
            model_name=self.settings.openai_summary_model,
            prompt_version=self.settings.prompt_version,
            source_hash=source_hash,
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
            source_hash_at_generation=source_hash,
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
            structured = self._generate_structured_summary(patent)
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

    def _build_source_text(self, patent: Patent) -> str:
        sections = {s.section_type: s.section_text for s in patent.sections}

        abstract = sections.get("abstract") or patent.abstract or ""
        claims = sections.get("claims") or ""
        summary_section = sections.get("summary") or ""
        max_chars = max(1000, self.settings.summary_source_char_limit)

        parts = [
            f"TITLE:\n{patent.title or ''}",
            f"ABSTRACT:\n{abstract}",
        ]

        if summary_section:
            parts.append(f"PATENT SUMMARY SECTION:\n{summary_section}")
        if not abstract and not summary_section and claims:
            parts.append(f"CLAIMS EXCERPT:\n{claims}")

        joined = "\n\n".join(parts)
        return joined[:max_chars]

    def _summary_source_hash(self, patent: Patent) -> str:
        source_text = self._build_source_text(patent)
        return make_source_hash(
            {
                "publication_number": patent.publication_number,
                "summary_source": source_text,
            }
        )

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3))
    def _generate_structured_summary(self, patent: Patent) -> dict[str, Any]:
        source_text = self._build_source_text(patent)

        if not self._client:
            return self._fallback_summary(patent, source_text)

        system_prompt = (
            "You summarize patents for a busy reader. Return strict JSON only with keys: "
            "summary, key_points, potential_uses, caveat. The summary must be no more than "
            "two concise sentences. key_points must contain up to three short strings about "
            "what the invention does. potential_uses must contain up to two short strings. "
            "Do not include quotes, evidence, claim charts, legal analysis, or implementation "
            "detail. Use only the supplied source text. If uncertain, say so in caveat."
        )

        user_prompt = (
            f"Publication Number: {patent.publication_number}\n"
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
            max_tokens=min(self.settings.summary_max_output_tokens, 550),
            temperature=0.1,
        )

        raw = completion.choices[0].message.content or "{}"
        parsed = json.loads(raw)
        self._validate_structured(parsed)
        return parsed

    @staticmethod
    def _validate_structured(payload: dict[str, Any]) -> None:
        required = [
            "summary",
            "key_points",
            "potential_uses",
            "caveat",
        ]
        missing = [k for k in required if k not in payload]
        if missing:
            raise ValueError(f"Summary JSON missing required keys: {', '.join(missing)}")

    def _fallback_summary(self, patent: Patent, source_text: str) -> dict[str, Any]:
        abstract = patent.abstract or source_text[:700]
        return {
            "summary": abstract or f"{patent.title or 'This patent'} needs an OpenAI API key before an AI summary can be generated.",
            "key_points": ["AI summary generation is unavailable because OPENAI_API_KEY is not configured."],
            "potential_uses": [],
            "caveat": "This is a fallback summary from stored metadata, not a model-generated summary.",
        }

    @staticmethod
    def _render_markdown(payload: dict[str, Any]) -> str:
        def _listify(value: Any) -> str:
            if isinstance(value, list):
                return "\n".join([f"- {item}" for item in value]) or "- None"
            return str(value)

        lines = [
            "## Summary",
            str(payload.get("summary", "")),
            "",
            "## Key Points",
            _listify(payload.get("key_points", [])),
        ]

        potential_uses = payload.get("potential_uses", [])
        if potential_uses:
            lines.extend(["", "## Potential Uses", _listify(potential_uses)])

        caveat = str(payload.get("caveat", "")).strip()
        if caveat:
            lines.extend(["", "## Caveat", caveat])

        return "\n".join(lines)
