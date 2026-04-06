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


async def tailor_resume_from_text(
    resume_text: str,
    job_description: str,
) -> str:
    """
    Tailor a plain-text resume for the given job and return **structured JSON**.

    The JSON is consumed by ``pdf_resume_builder.build_resume_pdf()``.
    """
    settings = get_settings()
    key = (settings.groq_api_key or "").strip()
    if not key:
        raise RuntimeError("Groq API key is not configured.")

    client = AsyncGroq(api_key=key, max_retries=2)

    jd = job_description.strip()
    if len(jd) > 100_000:
        jd = jd[:100_000] + "\n... [truncated]"

    system_prompt = """You are an expert resume writer and career strategist.

You will receive the text of a candidate's resume and a job description.
Your task is to tailor the resume content so the candidate appears like an excellent fit for the job.

OUTPUT: Return ONLY a valid JSON object (no markdown, no code fences, no commentary).

The JSON MUST follow this exact schema:
{
  "name": "Full Name",
  "contact": "email | phone | city, state | linkedin-url",
  "summary": "2-3 sentence professional summary tailored to the job",
  "experience": [
    {
      "title": "Job Title",
      "company": "Company Name",
      "dates": "Start – End",
      "bullets": [
        "Achievement or responsibility bullet 1",
        "Achievement or responsibility bullet 2"
      ]
    }
  ],
  "education": [
    {
      "degree": "Degree Name",
      "school": "University Name",
      "dates": "Year – Year",
      "details": "optional GPA, honors, relevant coursework"
    }
  ],
  "skills": {
    "Category": ["skill1", "skill2"]
  },
  "certifications": ["Cert 1", "Cert 2"],
  "projects": [
    {
      "name": "Project Name",
      "description": "One-line description",
      "bullets": ["detail 1", "detail 2"]
    }
  ]
}

RULES:
1) HEAVY REWRITE ALLOWED: Adapt the resume so they appear like a strong fit for the JOB.
2) Rewrite the summary / objective and the main job title to match the JD.
3) You may add skills required by the JD and weave them into experience bullets.
4) Rephrase or rewrite bullet points to emphasise transferable experiences.
5) Keep original employer names, school names, and approximate dates intact.
6) If a section is missing from the source resume, omit that key or use an empty array.
7) Return skills as a categorised object where possible (e.g. "Languages", "Frameworks", "Tools").
8) Keep the JSON valid – no trailing commas, no comments."""

    user_prompt = f"""
CANDIDATE_RESUME_TEXT:
{resume_text}

JOB_DESCRIPTION:
{jd}
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
