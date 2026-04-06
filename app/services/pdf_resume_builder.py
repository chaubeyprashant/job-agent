"""
PDF resume utilities: extract text from uploaded PDF, build a new professional PDF.

Uses ``pypdf`` for reading and ``reportlab`` for generating.
"""

from __future__ import annotations

import io
import json
import re
from typing import Any

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
)

from app.utils.logging import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """Read every page of a PDF and return joined plain text."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    parts: list[str] = []
    for page in reader.pages:
        text = page.extract_text()
        if text:
            parts.append(text.strip())
    full = "\n\n".join(parts)
    if not full.strip():
        raise ValueError("Could not extract any text from the uploaded PDF.")
    return full


# ---------------------------------------------------------------------------
# PDF generation from structured JSON
# ---------------------------------------------------------------------------

# Colour palette – dark charcoal headings, medium grey body, accent line
_HEADING_COLOR = colors.HexColor("#1a1a2e")
_SUBHEADING_COLOR = colors.HexColor("#2d2d44")
_BODY_COLOR = colors.HexColor("#333333")
_ACCENT_COLOR = colors.HexColor("#3d7cf0")
_MUTED_COLOR = colors.HexColor("#666666")


def _build_styles() -> dict[str, ParagraphStyle]:
    """Create a set of professional resume paragraph styles."""
    base = getSampleStyleSheet()
    return {
        "name": ParagraphStyle(
            "ResumeName",
            parent=base["Title"],
            fontName="Helvetica-Bold",
            fontSize=20,
            leading=24,
            textColor=_HEADING_COLOR,
            alignment=TA_CENTER,
            spaceAfter=2 * mm,
        ),
        "contact": ParagraphStyle(
            "ResumeContact",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9,
            leading=12,
            textColor=_MUTED_COLOR,
            alignment=TA_CENTER,
            spaceAfter=4 * mm,
        ),
        "section": ParagraphStyle(
            "ResumeSection",
            parent=base["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=12,
            leading=15,
            textColor=_ACCENT_COLOR,
            spaceBefore=6 * mm,
            spaceAfter=2 * mm,
        ),
        "subtitle": ParagraphStyle(
            "ResumeSubtitle",
            parent=base["Normal"],
            fontName="Helvetica-Bold",
            fontSize=10.5,
            leading=13,
            textColor=_SUBHEADING_COLOR,
            spaceAfter=1 * mm,
        ),
        "meta": ParagraphStyle(
            "ResumeMeta",
            parent=base["Normal"],
            fontName="Helvetica-Oblique",
            fontSize=9,
            leading=11,
            textColor=_MUTED_COLOR,
            spaceAfter=1.5 * mm,
        ),
        "body": ParagraphStyle(
            "ResumeBody",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.5,
            textColor=_BODY_COLOR,
            alignment=TA_JUSTIFY,
            spaceAfter=1 * mm,
        ),
        "bullet": ParagraphStyle(
            "ResumeBullet",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=12.5,
            textColor=_BODY_COLOR,
            leftIndent=12,
            bulletIndent=0,
            spaceAfter=1 * mm,
        ),
        "skill_line": ParagraphStyle(
            "ResumeSkill",
            parent=base["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            leading=13,
            textColor=_BODY_COLOR,
            spaceAfter=1 * mm,
        ),
    }


def _safe(text: Any) -> str:
    """Escape XML entities for ReportLab Paragraph."""
    if text is None:
        return ""
    text = str(text)
    text = text.replace("&", "&amp;")
    text = text.replace("<", "&lt;")
    text = text.replace(">", "&gt;")
    return text


def _section_hr() -> HRFlowable:
    return HRFlowable(
        width="100%",
        thickness=0.5,
        color=colors.HexColor("#d0d0d0"),
        spaceAfter=2 * mm,
        spaceBefore=0,
    )


def build_resume_pdf(structured: dict[str, Any]) -> bytes:
    """
    Build a professional single-column resume PDF from structured JSON.

    Expected JSON shape:
    {
      "name": "...",
      "contact": "email | phone | location | linkedin",
      "summary": "...",
      "experience": [
        {
          "title": "...",
          "company": "...",
          "dates": "...",
          "bullets": ["...", ...]
        }
      ],
      "education": [
        {
          "degree": "...",
          "school": "...",
          "dates": "...",
          "details": "..."          // optional
        }
      ],
      "skills": ["...", ...] | {"category": ["skill", ...], ...},
      "certifications": ["...", ...],   // optional
      "projects": [                     // optional
        {
          "name": "...",
          "description": "...",
          "bullets": ["...", ...]
        }
      ]
    }
    """
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
    )
    styles = _build_styles()
    story: list[Any] = []

    # --- Name ---
    name = structured.get("name", "")
    if name:
        story.append(Paragraph(_safe(name), styles["name"]))

    # --- Contact ---
    contact = structured.get("contact", "")
    if contact:
        story.append(Paragraph(_safe(contact), styles["contact"]))
        story.append(_section_hr())

    # --- Summary / Objective ---
    summary = structured.get("summary", "")
    if summary:
        story.append(Paragraph("PROFESSIONAL SUMMARY", styles["section"]))
        story.append(_section_hr())
        story.append(Paragraph(_safe(summary), styles["body"]))

    # --- Experience ---
    experience = structured.get("experience", [])
    if experience:
        story.append(Paragraph("EXPERIENCE", styles["section"]))
        story.append(_section_hr())
        for exp in experience:
            title_line = exp.get("title", "")
            company = exp.get("company", "")
            dates = exp.get("dates", "")
            if title_line:
                label = f"<b>{_safe(title_line)}</b>"
                if company:
                    label += f"  —  {_safe(company)}"
                story.append(Paragraph(label, styles["subtitle"]))
            if dates:
                story.append(Paragraph(_safe(dates), styles["meta"]))
            for bullet in exp.get("bullets", []):
                story.append(
                    Paragraph(
                        f"•  {_safe(bullet)}",
                        styles["bullet"],
                    )
                )
            story.append(Spacer(1, 2 * mm))

    # --- Education ---
    education = structured.get("education", [])
    if education:
        story.append(Paragraph("EDUCATION", styles["section"]))
        story.append(_section_hr())
        for edu in education:
            degree = edu.get("degree", "")
            school = edu.get("school", "")
            dates = edu.get("dates", "")
            details = edu.get("details", "")
            label = ""
            if degree:
                label = f"<b>{_safe(degree)}</b>"
            if school:
                label += f"  —  {_safe(school)}" if label else f"<b>{_safe(school)}</b>"
            if label:
                story.append(Paragraph(label, styles["subtitle"]))
            if dates:
                story.append(Paragraph(_safe(dates), styles["meta"]))
            if details:
                story.append(Paragraph(_safe(details), styles["body"]))
            story.append(Spacer(1, 1.5 * mm))

    # --- Skills ---
    skills = structured.get("skills", [])
    if skills:
        story.append(Paragraph("SKILLS", styles["section"]))
        story.append(_section_hr())
        if isinstance(skills, dict):
            for category, items in skills.items():
                items_str = ", ".join(items) if isinstance(items, list) else str(items)
                story.append(
                    Paragraph(
                        f"<b>{_safe(category)}:</b>  {_safe(items_str)}",
                        styles["skill_line"],
                    )
                )
        elif isinstance(skills, list):
            # If it's a flat list, join them
            story.append(
                Paragraph(_safe(", ".join(str(s) for s in skills)), styles["body"])
            )

    # --- Certifications ---
    certs = structured.get("certifications", [])
    if certs:
        story.append(Paragraph("CERTIFICATIONS", styles["section"]))
        story.append(_section_hr())
        for cert in certs:
            story.append(Paragraph(f"•  {_safe(str(cert))}", styles["bullet"]))

    # --- Projects ---
    projects = structured.get("projects", [])
    if projects:
        story.append(Paragraph("PROJECTS", styles["section"]))
        story.append(_section_hr())
        for proj in projects:
            proj_name = proj.get("name", "")
            desc = proj.get("description", "")
            if proj_name:
                story.append(Paragraph(f"<b>{_safe(proj_name)}</b>", styles["subtitle"]))
            if desc:
                story.append(Paragraph(_safe(desc), styles["body"]))
            for bullet in proj.get("bullets", []):
                story.append(Paragraph(f"•  {_safe(bullet)}", styles["bullet"]))
            story.append(Spacer(1, 1.5 * mm))

    doc.build(story)
    return buf.getvalue()


def parse_groq_json(raw_text: str) -> dict[str, Any]:
    """
    Parse the JSON returned by Groq.  Handles code-fence wrapping.
    """
    text = raw_text.strip()
    # Strip markdown code fence
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        logger.error("Failed to parse Groq JSON output: %s", exc)
        logger.debug("Raw text: %s", text[:2000])
        raise ValueError(
            "AI returned invalid JSON. Please try again."
        ) from exc
