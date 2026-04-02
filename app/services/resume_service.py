"""
Tailor a base resume to a job.

Uses **Google Gemini** when ``APP_GEMINI_API_KEY`` is set; otherwise uses deterministic
heuristics (reorder skills, summary tweak, bullet ordering).
"""

from __future__ import annotations

import re
from typing import Iterable

from app.config import get_settings
from app.schemas.job import JobParseResult
from app.schemas.resume import ExperienceItem, ProjectItem, Resume, Skills
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _job_data_to_text(job_data: JobParseResult) -> str:
    """Approximate job text from parsed fields when raw JD is unavailable."""
    lines = [
        f"Role: {job_data.role}",
        f"Seniority: {job_data.seniority}",
        f"Must-have skills: {', '.join(job_data.must_have_skills)}",
        f"Nice-to-have: {', '.join(job_data.good_to_have_skills)}",
        f"Keywords: {', '.join(job_data.keywords[:40])}",
    ]
    if job_data.responsibilities:
        lines.append("Responsibilities:")
        lines.extend(f"- {r}" for r in job_data.responsibilities[:15])
    return "\n".join(lines)


class ResumeService:
    """Resume tailoring: Gemini (if configured) or rule-based fallback."""

    async def tailor_resume(
        self,
        base_resume: Resume,
        job_data: JobParseResult,
        *,
        job_description: str | None = None,
        force_heuristic: bool = False,
    ) -> Resume:
        """
        Produce a job-targeted resume.

        When a Gemini API key is configured and ``force_heuristic`` is false, calls
        Gemini with the full job description (or parsed hints) and the resume JSON.

        Args:
            base_resume: Source resume (truthful baseline).
            job_data: Parsed job fields.
            job_description: Raw job posting text (preferred for Gemini).
            force_heuristic: Skip Gemini and use rules only.

        Returns:
            New :class:`Resume` instance tailored to the job.
        """
        settings = get_settings()
        key = (settings.gemini_api_key or "").strip()
        jd = (job_description or "").strip() or _job_data_to_text(job_data)

        if not force_heuristic and key:
            try:
                from app.services.gemini_tailor import tailor_resume_gemini_async

                tailored = await tailor_resume_gemini_async(
                    base_resume,
                    jd,
                    job_data,
                )
                logger.info(
                    "Tailored resume via Gemini (model=%s)",
                    settings.gemini_model,
                )
                return tailored
            except Exception as exc:
                logger.warning(
                    "Gemini tailoring failed, using heuristic fallback: %s",
                    exc,
                    exc_info=True,
                )
                return self._tailor_heuristic(base_resume, job_data)

        return self._tailor_heuristic(base_resume, job_data)

    def _tailor_heuristic(self, base_resume: Resume, job_data: JobParseResult) -> Resume:
        """Deterministic reordering and summary line (no external AI)."""
        job_kw = _lower_set(job_data.must_have_skills + job_data.keywords[:30])
        skills = self._reorder_skills(base_resume.skills, job_kw)
        summary = self._enhance_summary(base_resume, job_data, job_kw)
        projects = self._sort_projects(base_resume.projects, job_kw)
        experience = self._reorder_highlights(base_resume.experience, job_kw)

        tailored = Resume(
            basics=base_resume.basics.model_copy(
                update={"summary": summary},
            ),
            skills=skills,
            experience=experience,
            projects=projects,
            education=list(base_resume.education),
        )
        logger.info("Tailored resume (heuristic) for job role=%s", job_data.role)
        return tailored

    def _reorder_skills(self, skills: Skills, job_kw: set[str]) -> Skills:
        def score_item(s: str) -> tuple[int, str]:
            sl = s.lower()
            sc = sum(1 for k in job_kw if k in sl or sl in k)
            return (-sc, sl)

        return Skills(
            primary=sorted(skills.primary, key=score_item),
            secondary=sorted(skills.secondary, key=score_item),
            tools=sorted(skills.tools, key=score_item),
        )

    def _candidate_keyword_coverage(self, resume: Resume, tokens: Iterable[str]) -> list[str]:
        """Keywords from the job that appear somewhere in the resume (honest subset)."""
        blob = " ".join(
            [
                resume.basics.summary or "",
                " ".join(resume.skills.primary + resume.skills.secondary + resume.skills.tools),
                *(
                    f"{e.title} {' '.join(e.highlights)}"
                    for e in resume.experience
                ),
            ]
        ).lower()
        covered: list[str] = []
        for t in tokens:
            tl = t.lower()
            if len(tl) < 2:
                continue
            if tl in blob:
                covered.append(t.strip())
        seen: set[str] = set()
        out: list[str] = []
        for c in covered:
            key = c.lower()
            if key not in seen:
                seen.add(key)
                out.append(c)
        return out[:8]

    def _enhance_summary(
        self, base_resume: Resume, job_data: JobParseResult, job_kw: set[str]
    ) -> str | None:
        base = (base_resume.basics.summary or "").strip()
        tokens = list(job_data.must_have_skills) + list(job_data.keywords)[:15]
        overlap = self._candidate_keyword_coverage(base_resume, tokens)
        if not overlap:
            return base or None
        extra = (
            f"Aligned experience with {job_data.role} needs, emphasizing "
            f"{', '.join(overlap[:5])}."
        )
        if not base:
            return extra
        if extra.lower() in base.lower():
            return base
        return f"{base}\n\n{extra}"

    def _sort_projects(self, projects: list[ProjectItem], job_kw: set[str]) -> list[ProjectItem]:
        def score(p: ProjectItem) -> tuple[int, str]:
            text = f"{p.name} {p.description or ''} {' '.join(p.tech)} {' '.join(p.highlights)}"
            tl = text.lower()
            sc = sum(1 for k in job_kw if k in tl)
            return (-sc, p.name.lower())

        return sorted(projects, key=score)

    def _reorder_highlights(
        self, experience: list[ExperienceItem], job_kw: set[str]
    ) -> list[ExperienceItem]:
        out: list[ExperienceItem] = []
        for e in experience:
            if not e.highlights:
                out.append(e)
                continue

            def hscore(h: str) -> tuple[int, str]:
                hl = h.lower()
                sc = sum(1 for k in job_kw if k in hl)
                return (-sc, hl)

            new_highlights = sorted(e.highlights, key=hscore)
            out.append(e.model_copy(update={"highlights": new_highlights}))
        return out


def _lower_set(items: Iterable[str]) -> set[str]:
    return {re.sub(r"\s+", " ", x.strip().lower()) for x in items if x.strip()}
