from __future__ import annotations

import csv
from collections import Counter
from functools import lru_cache
from pathlib import Path

from app.models.schemas import CandidateRecord, DatasetSummary
from app.services.metadata_extractor import (
    extract_skills,
    extract_years_experience,
    infer_domain,
    infer_role,
    infer_seniority,
    strip_html,
)


class ResumeRepository:
    def __init__(self, data_path: str) -> None:
        self.data_path = Path(data_path)

    @lru_cache(maxsize=1)
    def load_candidates(self) -> list[CandidateRecord]:
        if not self.data_path.exists():
            raise FileNotFoundError(
                f"Resume dataset not found at '{self.data_path}'. Add Resume.csv to continue."
            )

        with self.data_path.open("r", encoding="utf-8", errors="ignore", newline="") as handle:
            reader = csv.DictReader(handle)
            candidates: list[CandidateRecord] = []
            for index, row in enumerate(reader, start=1):
                raw_text = row.get("Resume_str") or row.get("resume_text") or ""
                resume_html = row.get("Resume_html") or row.get("resume_html") or ""
                resume_text = raw_text.strip() or strip_html(resume_html)
                category = row.get("Category") or row.get("category") or ""
                candidate_id = (
                    row.get("ID")
                    or row.get("candidate_id")
                    or f"candidate-{index}"
                )
                if not resume_text.strip():
                    continue
                candidates.append(
                    CandidateRecord(
                        candidate_id=str(candidate_id),
                        resume_text=resume_text.strip(),
                        resume_html=resume_html.strip(),
                        category=category.strip(),
                        inferred_skills=extract_skills(resume_text),
                        inferred_years_experience=extract_years_experience(resume_text),
                        inferred_seniority=infer_seniority(resume_text),
                        inferred_role_hint=infer_role(resume_text),
                        inferred_domain=infer_domain(resume_text),
                    )
                )
        return candidates

    def summarize(self) -> DatasetSummary:
        candidates = self.load_candidates()
        categories = sorted({candidate.category for candidate in candidates if candidate.category})
        skill_counter = Counter()
        for candidate in candidates:
            skill_counter.update(candidate.inferred_skills)
        return DatasetSummary(
            total_candidates=len(candidates),
            categories=categories[:50],
            top_skills=[skill for skill, _ in skill_counter.most_common(15)],
        )

    def dataset_fingerprint(self) -> str:
        if not self.data_path.exists():
            raise FileNotFoundError(
                f"Resume dataset not found at '{self.data_path}'. Add Resume.csv to continue."
            )
        stat = self.data_path.stat()
        return f"{self.data_path.name}:{stat.st_size}:{int(stat.st_mtime)}"
