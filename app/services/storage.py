from __future__ import annotations

import json
import sqlite3
from datetime import datetime

from app.models.schemas import ResultListResponse, ResultRow, ShortlistResult


class ResultStore:
    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS shortlist_results (
                    request_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    role TEXT NOT NULL,
                    payload TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS system_state (
                    state_key TEXT PRIMARY KEY,
                    state_value TEXT NOT NULL
                )
                """
            )
            conn.commit()

    def save(self, result: ShortlistResult) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO shortlist_results (request_id, created_at, role, payload)
                VALUES (?, ?, ?, ?)
                """,
                (
                    result.request_id,
                    result.created_at.isoformat(),
                    result.jd.role,
                    result.model_dump_json(),
                ),
            )
            conn.commit()

    def list_results(self) -> ResultListResponse:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT payload
                FROM shortlist_results
                ORDER BY created_at DESC
                """
            ).fetchall()

        items: list[ResultRow] = []
        for (payload,) in rows:
            parsed = ShortlistResult.model_validate(json.loads(payload))
            top_candidate = parsed.candidates[0] if parsed.candidates else None
            items.append(
                ResultRow(
                    request_id=parsed.request_id,
                    created_at=parsed.created_at,
                    role=parsed.jd.role,
                    top_candidate_id=top_candidate.candidate_id if top_candidate else None,
                    top_recommendation=top_candidate.recommendation if top_candidate else None,
                )
            )
        return ResultListResponse(items=items)

    def get_state(self, key: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT state_value
                FROM system_state
                WHERE state_key = ?
                """,
                (key,),
            ).fetchone()
        return row[0] if row else None

    def set_state(self, key: str, value: str) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO system_state (state_key, state_value)
                VALUES (?, ?)
                """,
                (key, value),
            )
            conn.commit()
