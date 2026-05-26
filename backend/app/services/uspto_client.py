from __future__ import annotations

from datetime import date
from typing import Any

import httpx


class USPTOClient:
    def __init__(self, base_url: str, api_key: str, timeout_seconds: int = 30):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout_seconds

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["X-API-KEY"] = self.api_key
            headers["apikey"] = self.api_key
        return headers

    def search_recent_publications(self, start_date: date, end_date: date, start: int = 0, rows: int = 200) -> dict[str, Any]:
        endpoint = f"{self.base_url}/patent/applications/search"
        search_text = f"publicationDate:[{start_date.isoformat()} TO {end_date.isoformat()}]"
        params = {
            "searchText": search_text,
            "start": start,
            "rows": rows,
        }

        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(endpoint, params=params, headers=self._headers())
            if response.status_code in {400, 405, 415}:
                # Some ODP endpoints prefer POST payload for advanced queries.
                payload = {
                    "searchText": search_text,
                    "start": start,
                    "rows": rows,
                }
                response = client.post(endpoint, json=payload, headers=self._headers())
            response.raise_for_status()
            data = response.json()

        records = self._extract_records(data)
        return {"records": records, "raw": data}

    def get_application_metadata(self, application_number: str) -> dict[str, Any]:
        endpoint = f"{self.base_url}/patent/applications/{application_number}/meta-data"
        with httpx.Client(timeout=self.timeout) as client:
            response = client.get(endpoint, headers=self._headers())
            response.raise_for_status()
            return response.json()

    @staticmethod
    def _extract_records(payload: dict[str, Any]) -> list[dict[str, Any]]:
        candidate_keys = [
            "patentFileWrapperDataBag",
            "results",
            "data",
            "items",
            "applicationMetaDataBag",
            "response",
        ]

        for key in candidate_keys:
            value = payload.get(key)
            flattened = USPTOClient._flatten_bag(value)
            if flattened:
                return flattened

        flattened = USPTOClient._flatten_bag(payload)
        if flattened:
            return flattened
        return []

    @staticmethod
    def _flatten_bag(value: Any) -> list[dict[str, Any]]:
        if value is None:
            return []
        if isinstance(value, dict):
            return [value]
        if isinstance(value, list):
            records: list[dict[str, Any]] = []
            for item in value:
                if isinstance(item, dict):
                    records.append(item)
                elif isinstance(item, list):
                    records.extend(USPTOClient._flatten_bag(item))
            return records
        return []
