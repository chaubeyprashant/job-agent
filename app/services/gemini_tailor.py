"""
Tailor a resume using Google Gemini (JSON output).

Requires ``APP_GEMINI_API_KEY`` (or ``GEMINI_API_KEY``). See ``app.config.AppSettings``.
"""

from __future__ import annotations

import asyncio
import re

import google.generativeai as genai
from pydantic import ValidationError

from app.config import get_settings
from app.schemas.job import JobParseResult
from app.schemas.resume import Resume
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Compact schema hint (full schema can exceed context; Pydantic validates output)
_RESUME_JSON_SHAPE = """
{
  "basics": {
    "name": "string",
    "headline": "string or null",
    "summary": "string or null",
    "email": "string or null",
    "phone": "string or null",
    "location": "string or null",
    "links": ["url strings"]
  },
  "skills": {
    "primary": ["string"],
    "secondary": ["string"],
    "tools": ["string"]
  },
  "experience": [
    {
      "company": "string",
      "title": "string",
      "location": "string or null",
      "start": "string",
      "end": "string or null",
      "highlights": ["string"]
    }
  ],
  "projects": [
    {
      "name": "string",
      "description": "string or null",
      "tech": ["string"],
      "highlights": ["string"]
    }
  ],
  "education": [
    {
      "institution": "string",
      "degree": "string",
      "field": "string or null",
      "end": "string or null"
    }
  ]
}
"""


def _strip_code_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t)
        t = re.sub(r"\s*```$", "", t)
    return t.strip()


def tailor_resume_gemini_sync(
    base: Resume,
    job_description: str,
    job_data: JobParseResult,
) -> Resume:
    """
    Call Gemini with JSON mode and validate against :class:`Resume`.

    Raises:
        RuntimeError: On empty response, API errors, or unrecoverable parse failure.
    """
    settings = get_settings()
    key = (settings.gemini_api_key or "").strip()
    if not key:
        raise RuntimeError("Gemini API key is not configured.")

    genai.configure(api_key=key)
    model = genai.GenerativeModel(settings.gemini_model)

    base_json = base.model_dump_json(indent=2)
    if len(base_json) > 100_000:
        base_json = base_json[:100_000] + "\n... [truncated]"

    jd = job_description.strip()
    if len(jd) > 100_000:
        jd = jd[:100_000] + "\n... [truncated]"

    hints = job_data.model_dump_json(indent=2)

    prompt = f"""You are an expert resume editor for technical and professional roles.

OUTPUT: Return ONE JSON object only. No markdown, no code fences, no commentary.

The JSON MUST match this structure (all keys required; use empty arrays where needed):
{_RESUME_JSON_SHAPE}

RULES (strict):
1) SOURCE OF TRUTH: The candidate's facts come ONLY from CANDIDATE_RESUME_JSON below.
2) Do NOT invent employers, job titles, dates, degrees, certifications, or metrics that are not supported by the source JSON.
3) Do NOT add skills that do not appear in the source (you may rephrase or move skills between primary/secondary/tools buckets).
4) Tailor for the job: rewrite summary and headline for the role; reorder skills and bullet points for relevance and ATS keywords; rephrase bullets for impact without changing meaning.
5) Preserve employment time ranges and company names exactly as in the source unless fixing obvious typos (avoid changing names).
6) If PARSED_JOB_HINTS conflict with JOB_DESCRIPTION, prefer facts in CANDIDATE_RESUME_JSON.

CANDIDATE_RESUME_JSON:
{base_json}

JOB_DESCRIPTION:
{jd}

PARSED_JOB_HINTS:
{hints}
"""

    generation_config = genai.GenerationConfig(
        response_mime_type="application/json",
        temperature=settings.gemini_temperature,
    )

    response = model.generate_content(
        prompt,
        generation_config=generation_config,
    )
    text = ""
    try:
        text = (response.text or "").strip()
    except ValueError:
        if response.candidates:
            for cand in response.candidates:
                if not cand.content or not cand.content.parts:
                    continue
                for part in cand.content.parts:
                    if hasattr(part, "text") and part.text:
                        text += part.text
        text = text.strip()
    if not text:
        raise RuntimeError("Gemini returned no text (blocked, safety filter, or empty).")

    text = _strip_code_fence(text)
    try:
        return Resume.model_validate_json(text)
    except ValidationError as exc:
        logger.warning("Gemini JSON failed validation, retrying with repair prompt: %s", exc)
        repair = model.generate_content(
            f"""The following JSON failed validation: {exc}

Fix it to satisfy the Resume schema. Return ONLY valid JSON, same structure.

Broken JSON:
{text[:50_000]}
""",
            generation_config=generation_config,
        )
        fixed = ""
        try:
            fixed = (repair.text or "").strip()
        except ValueError:
            if repair.candidates:
                for cand in repair.candidates:
                    if cand.content and cand.content.parts:
                        for part in cand.content.parts:
                            if hasattr(part, "text") and part.text:
                                fixed += part.text
        fixed = _strip_code_fence(fixed.strip())
        return Resume.model_validate_json(fixed)


async def tailor_resume_gemini_async(
    base: Resume,
    job_description: str,
    job_data: JobParseResult,
) -> Resume:
    """Run :func:`tailor_resume_gemini_sync` in a thread pool (non-blocking)."""
    return await asyncio.to_thread(tailor_resume_gemini_sync, base, job_description, job_data)
