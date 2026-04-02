"""
Compute a 0–100 match score between a parsed job and a resume.

Uses weighted components from configuration (no hardcoded weights in logic).
"""

from __future__ import annotations

import re
from typing import Iterable

from app.config import get_settings
from app.schemas.job import JobParseResult
from app.schemas.resume import Resume
from app.utils.logging import get_logger

logger = get_logger(__name__)


class MatchingService:
    """Similarity scoring for job ↔ resume alignment."""

    def __init__(self) -> None:
        self._settings = get_settings()

    def calculate_score(self, job: JobParseResult, resume: Resume) -> float:
        """
        Return a score from 0–100 combining skill overlap, keywords, and experience.

        Args:
            job: Parsed job posting.
            resume: Candidate resume.

        Returns:
            Float between 0 and 100 (inclusive).
        """
        w1 = self._settings.matching_weight_skill_overlap
        w2 = self._settings.matching_weight_keyword_match
        w3 = self._settings.matching_weight_experience_relevance
        s1 = self._skill_overlap(job, resume) * 100.0
        s2 = self._keyword_match(job, resume) * 100.0
        s3 = self._experience_relevance(job, resume) * 100.0
        total = w1 * s1 + w2 * s2 + w3 * s3
        score = round(min(100.0, max(0.0, total)), 2)
        logger.debug("Match score=%s (skills=%s kw=%s exp=%s)", score, s1, s2, s3)
        return score

    def _all_resume_skills(self, resume: Resume) -> set[str]:
        s = resume.skills
        return self._norm_set(s.primary + s.secondary + s.tools)

    def _norm_set(self, items: Iterable[str]) -> set[str]:
        return {self._norm_token(x) for x in items if x.strip()}

    def _norm_token(self, s: str) -> str:
        return re.sub(r"\s+", " ", s.strip().lower())

    def _skill_overlap(self, job: JobParseResult, resume: Resume) -> float:
        need = self._norm_set(job.must_have_skills + job.good_to_have_skills)
        have = self._all_resume_skills(resume)
        if not need:
            return 0.5
        inter = len(need & have)
        # Jaccard-style balance
        union = len(need | have) or 1
        return inter / union

    def _resume_blob(self, resume: Resume) -> str:
        parts: list[str] = []
        b = resume.basics
        parts.extend([b.name, b.headline or "", b.summary or ""])
        for e in resume.experience:
            parts.extend([e.title, e.company, " ".join(e.highlights)])
        for p in resume.projects:
            parts.extend([p.name, p.description or "", " ".join(p.tech), " ".join(p.highlights)])
        return " ".join(parts).lower()

    def _keyword_match(self, job: JobParseResult, resume: Resume) -> float:
        blob = self._resume_blob(resume)
        keys = [k.lower() for k in job.keywords[:50]]
        if not keys:
            return 0.5
        hits = sum(1 for k in keys if k in blob)
        return hits / len(keys)

    def _experience_relevance(self, job: JobParseResult, resume: Resume) -> float:
        role = job.role.lower()
        job_tokens = set(re.findall(r"[a-z]{3,}", role))
        scored: list[float] = []
        for e in resume.experience:
            text = f"{e.title} {e.company} {' '.join(e.highlights)}".lower()
            et = set(re.findall(r"[a-z]{3,}", text))
            if not job_tokens:
                scored.append(0.5)
            else:
                scored.append(len(job_tokens & et) / len(job_tokens))
        if not scored:
            return 0.4
        return sum(scored) / len(scored)
