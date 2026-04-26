from __future__ import annotations

import json
from typing import Any
from urllib import error, request


class BackendApiClient:
    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    def healthcheck(self) -> dict[str, Any]:
        return self._get("/health")

    def create_shortlist(self, jd_text: str) -> dict[str, Any]:
        return self._post("/api/v1/shortlist", {"jd": {"text": jd_text}})

    def list_results(self) -> dict[str, Any]:
        return self._get("/api/v1/results")

    def dataset_summary(self) -> dict[str, Any]:
        return self._get("/api/v1/dataset-summary")

    def search_index_status(self) -> dict[str, Any]:
        return self._get("/api/v1/search-index-status")

    def sync_search_index(self, force: bool = False) -> dict[str, Any]:
        suffix = "?force=true" if force else ""
        return self._post(f"/api/v1/admin/sync-search-index{suffix}", {})

    def _get(self, path: str) -> dict[str, Any]:
        req = request.Request(f"{self.base_url}{path}", method="GET")
        with request.urlopen(req, timeout=120.0) as response:
            return json.loads(response.read().decode("utf-8"))

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self.base_url}{path}",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=180.0) as response:
            return json.loads(response.read().decode("utf-8"))
