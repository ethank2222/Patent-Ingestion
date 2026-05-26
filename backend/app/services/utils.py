from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from typing import Any


def parse_date(value: Any) -> date | None:
    if value is None:
        return None
    if isinstance(value, date):
        return value
    text = str(value).strip()
    if not text:
        return None

    candidates = ["%Y-%m-%d", "%Y%m%d", "%m/%d/%Y", "%Y/%m/%d"]
    for fmt in candidates:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def normalize_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text if text else None


def ensure_list(value: Any) -> list:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    # Simple and deterministic estimate without external tokenizers.
    return max(1, len(text) // 4)


def make_source_hash(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def make_summary_cache_key(publication_number: str, model_name: str, prompt_version: str, source_hash: str, summary_mode: str) -> str:
    return f"{publication_number}:{model_name}:{prompt_version}:{summary_mode}:{source_hash}"
