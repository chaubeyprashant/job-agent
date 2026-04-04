"""
Tailor a LaTeX resume using Groq Cloud.

Requires ``APP_GROQ_API_KEY`` (or ``GROQ_API_KEY``). See ``app.config.AppSettings``.
"""

from __future__ import annotations

import re

from groq import AsyncGroq

from app.config import get_settings
from app.schemas.job import JobParseResult
from app.utils.logging import get_logger

logger = get_logger(__name__)


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:latex|tex)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


async def tailor_resume_groq_async(
    base_latex: str,
    job_description: str,
    job_data: JobParseResult,
) -> str:
    """
    Call Groq to rewrite the LaTeX resume for the given job.

    Raises:
        RuntimeError: On empty response or API errors.
    """
    settings = get_settings()
    key = (settings.groq_api_key or "").strip()
    if not key:
        raise RuntimeError("Groq API key is not configured.")

    client = AsyncGroq(api_key=key, max_retries=2)
    
    jd = job_description.strip()
    if len(jd) > 100_000:
        jd = jd[:100_000] + "\n... [truncated]"

    hints = job_data.model_dump_json(indent=2)
    
    system_prompt = f"""You are an expert resume editor and LaTeX developer for technical and professional roles.

OUTPUT: Return ONE valid LaTeX document only. No markdown formatting, no code fences, no commentary. It MUST compile.

RULES for tailoring:
1) HEAVY REWRITE ALLOWED: Your main goal is to adapt the candidate's resume so that they appear like an excellent fit for the JOB_DESCRIPTION.
2) Rewrite the Summary, Objective, and the main Job Title at the top (e.g. changing "Senior Mobile Developer" to "Java Full Stack Developer" if the JD demands it).
3) You may add new skills (e.g., Java, Spring Boot, React, MySQL) required by the JD to the Skills section and weave them intelligently into the experience bullets.
4) Rephrase or completely rewrite existing bullet points to emphasize transferable experiences that align with the JD, while keeping the original employer names and dates intact.
5) NEVER change the LaTeX preamble or document structure. Only modify the content inside the environment blocks.
"""

    user_prompt = f"""
CANDIDATE_RESUME_LATEX:
{base_latex}

JOB_DESCRIPTION:
{jd}

PARSED_JOB_HINTS:
{hints}
"""

    response = await client.chat.completions.create(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=settings.groq_model,
        temperature=settings.groq_temperature,
    )

    text = response.choices[0].message.content or ""
    text = _strip_code_fence(text)
    
    if not text:
        raise RuntimeError("Groq returned empty text.")

    return text
