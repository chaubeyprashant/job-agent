"""
Tailor a base resume to a job.

Uses **Groq** (Llama 3.3 70B) when ``APP_GROQ_API_KEY`` is set; otherwise returns the original LaTeX.
"""

from __future__ import annotations

import re
from typing import Iterable

from app.config import get_settings
from app.schemas.job import JobParseResult
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
    """Resume tailoring via Groq Cloud."""

    async def tailor_resume(
        self,
        base_latex: str,
        job_data: JobParseResult,
        *,
        job_description: str | None = None,
        force_heuristic: bool = False,
    ) -> str:
        """
        Produce a job-targeted LaTeX resume.

        When a Groq API key is configured and ``force_heuristic`` is false, calls
        Groq with the full job description (or parsed hints) and the resume LaTeX.
        Otherwise it returns the original LaTeX.
        """
        settings = get_settings()
        key = (settings.groq_api_key or "").strip()
        jd = (job_description or "").strip() or _job_data_to_text(job_data)

        if not force_heuristic and key:
            try:
                from app.services.groq_tailor import tailor_resume_groq_async

                tailored = await tailor_resume_groq_async(
                    base_latex,
                    jd,
                    job_data,
                )
                logger.info(
                    "Tailored resume via Groq (model=%s)",
                    settings.groq_model,
                )
                return tailored
            except Exception as exc:
                from fastapi import HTTPException
                raise HTTPException(status_code=400, detail=f"Groq API Error: {exc}") from exc

        logger.info("No Groq API key configured, returning original LaTeX.")
        return base_latex
