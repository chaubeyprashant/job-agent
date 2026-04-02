"""
Import a :class:`~app.schemas.resume.Resume` from plain text (e.g. PDF extraction).

Heuristic only — complex layouts may need manual JSON edits or a future LLM step.
"""

from __future__ import annotations

import re
from io import BytesIO

from pypdf import PdfReader

from app.schemas.resume import (
    Basics,
    EducationItem,
    ExperienceItem,
    Resume,
    Skills,
)

_EMAIL = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
)
_PHONE = re.compile(
    r"(?:\+?\d{1,3}[\s\-]?)?(?:\(?\d{3}\)?[\s\-]?)?\d{3}[\s\-]?\d{4}",
)
_URL = re.compile(r"https?://[^\s<>)\]]+", re.I)

_SKILL_TOKENS = frozenset(
    {
        "python",
        "java",
        "javascript",
        "typescript",
        "react",
        "node",
        "sql",
        "postgresql",
        "aws",
        "docker",
        "kubernetes",
        "git",
        "fastapi",
        "django",
        "flask",
        "redis",
        "kafka",
        "graphql",
        "rest",
        "api",
        "linux",
        "agile",
        "ci/cd",
        "terraform",
        "gcp",
        "azure",
        "mongodb",
        "pandas",
        "numpy",
        "spark",
        "machine learning",
        "pytorch",
        "tensorflow",
    }
)


def extract_text_from_pdf_bytes(data: bytes) -> str:
    """Extract concatenated text from a PDF using pypdf."""
    reader = PdfReader(BytesIO(data))
    parts: list[str] = []
    for page in reader.pages:
        t = page.extract_text()
        if t:
            parts.append(t)
    return "\n\n".join(parts).strip()


def resume_from_plaintext(text: str) -> Resume:
    """
    Build a structured resume from arbitrary text (best-effort).

    Always returns a valid :class:`Resume`; review and edit in the UI if needed.
    """
    cleaned = text.strip()
    if not cleaned:
        raise ValueError("No text to import")

    lines = [ln.strip() for ln in cleaned.replace("\r", "\n").split("\n")]
    lines = [ln for ln in lines if ln]
    if not lines:
        raise ValueError("No text to import")

    email_m = _EMAIL.search(cleaned)
    email = email_m.group(0) if email_m else None

    phone_m = _PHONE.search(cleaned)
    phone = phone_m.group(0).strip() if phone_m else None

    links = list(dict.fromkeys(_URL.findall(cleaned)))[:8]

    name = _guess_name(lines, email)
    headline = _guess_headline(lines, name)

    primary, secondary, tools = _infer_skill_buckets(cleaned)

    bullets = _extract_bullet_lines(lines)
    experience: list[ExperienceItem] = []
    if bullets:
        experience.append(
            ExperienceItem(
                company="Imported",
                title="Experience",
                location=None,
                start="Import",
                end="Present",
                highlights=bullets[:20],
            )
        )

    education = _parse_education_section(cleaned)

    summary = _build_summary(cleaned, name, max_chars=6000)

    return Resume(
        basics=Basics(
            name=name,
            headline=headline,
            summary=summary,
            email=email,
            phone=phone,
            location=None,
            links=links,
        ),
        skills=Skills(primary=primary, secondary=secondary, tools=tools),
        experience=experience,
        projects=[],
        education=education,
    )


def _guess_name(lines: list[str], email: str | None) -> str:
    for i, ln in enumerate(lines[:5]):
        if email and email in ln:
            continue
        if _EMAIL.match(ln) or _URL.match(ln):
            continue
        if len(ln) <= 100 and not ln.lower().startswith("http"):
            return ln[:120]
    return "Imported candidate"


def _guess_headline(lines: list[str], name: str) -> str | None:
    for ln in lines[1:6]:
        if ln == name:
            continue
        if _EMAIL.search(ln) or _PHONE.search(ln):
            continue
        if len(ln) <= 160:
            return ln
    return None


def _infer_skill_buckets(text: str) -> tuple[list[str], list[str], list[str]]:
    lower = text.lower()
    found: list[str] = []
    for tok in _SKILL_TOKENS:
        if tok in lower:
            found.append(tok.title() if tok != "ci/cd" else "CI/CD")
    # de-dupe preserve order
    seen: set[str] = set()
    uniq: list[str] = []
    for s in found:
        k = s.lower()
        if k not in seen:
            seen.add(k)
            uniq.append(s)

    # Split: first half primary, next secondary, tools empty or last few
    if len(uniq) <= 8:
        return uniq, [], []
    mid = max(4, len(uniq) // 2)
    return uniq[:mid], uniq[mid : mid + 8], uniq[mid + 8 : mid + 16]


def _extract_bullet_lines(lines: list[str]) -> list[str]:
    out: list[str] = []
    for ln in lines:
        s = ln.lstrip()
        if s.startswith(("•", "-", "*", "–", "—")):
            t = re.sub(r"^[•\-\*–—]\s*", "", ln).strip()
            if len(t) > 3:
                out.append(t)
    return out


def _parse_education_section(text: str) -> list[EducationItem]:
    """Pull a few lines after Education / Academic header."""
    lower = text.lower()
    markers = ("education", "academic", "university", "degree")
    idx = -1
    for m in markers:
        i = lower.find(m)
        if i != -1 and (idx == -1 or i < idx):
            idx = i
    if idx == -1:
        return []
    snippet = text[idx : idx + 800]
    edu_lines = [ln.strip() for ln in snippet.splitlines() if ln.strip()][1:6]
    items: list[EducationItem] = []
    for ln in edu_lines:
        if len(ln) < 4:
            continue
        if _EMAIL.search(ln):
            continue
        items.append(
            EducationItem(
                institution=ln[:200],
                degree="",
                field=None,
                end=None,
            )
        )
        if len(items) >= 2:
            break
    return items


def _build_summary(text: str, name: str, *, max_chars: int) -> str:
    """Use full text as summary (trimmed) so tailoring still has context."""
    t = re.sub(r"\s+", " ", text).strip()
    if len(t) <= max_chars:
        return t
    return t[: max_chars - 3] + "..."
