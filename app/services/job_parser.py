"""
Job description parser: extracts structured fields without an external LLM.

Uses deterministic heuristics (regex, keyword lists) as a stand-in for an LLM.
Replace :meth:`parse` internals with an API call when ready.
"""

from __future__ import annotations

import re
from collections import Counter

from app.config import get_settings
from app.schemas.job import JobParseResult
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Common tech tokens (extend via config or data file in a future iteration)
_SKILL_LEXICON: frozenset[str] = frozenset(
    {
        "python",
        "java",
        "javascript",
        "typescript",
        "go",
        "golang",
        "rust",
        "c++",
        "cpp",
        "c#",
        "ruby",
        "php",
        "swift",
        "kotlin",
        "scala",
        "fastapi",
        "django",
        "flask",
        "react",
        "vue",
        "angular",
        "node",
        "nodejs",
        "sql",
        "postgresql",
        "postgres",
        "mysql",
        "mongodb",
        "redis",
        "kafka",
        "aws",
        "gcp",
        "azure",
        "docker",
        "kubernetes",
        "k8s",
        "terraform",
        "ci/cd",
        "git",
        "graphql",
        "rest",
        "api",
        "microservices",
        "machine learning",
        "ml",
        "pytorch",
        "tensorflow",
        "nlp",
        "llm",
        "pandas",
        "numpy",
        "spark",
        "snowflake",
        "etl",
        "elasticsearch",
        "linux",
        "agile",
        "scrum",
    }
)

_SENIORITY_PATTERN = re.compile(
    r"\b(junior|jr\.?|entry|mid|intermediate|senior|sr\.?|lead|"
    r"principal|staff|manager|director|head|chief)\b",
    re.I,
)

_ROLE_LINE = re.compile(
    r"^(?:title|position|role)\s*[:#\-]\s*(.+)$",
    re.I | re.M,
)


class JobParserService:
    """
    Parse raw job description text into :class:`JobParseResult`.

    This implementation is intentionally deterministic for tests and offline use.
    """

    def __init__(self) -> None:
        self._settings = get_settings()

    def parse(self, raw: str) -> JobParseResult:
        """
        Extract role, seniority, skills, keywords, and responsibilities.

        Args:
            raw: Full job posting as a single string.

        Returns:
            Structured :class:`JobParseResult`.
        """
        text = raw.strip()
        if not text:
            return JobParseResult(
                role="Unknown",
                seniority="mid",
                must_have_skills=[],
                good_to_have_skills=[],
                keywords=[],
                responsibilities=[],
            )

        role = self._infer_role(text)
        seniority = self._infer_seniority(text)
        bullets = self._extract_bullets(text)
        responsibilities = bullets[: self._settings.job_parser_max_responsibility_bullets]
        tokens = self._tokenize(text)
        found_skills = self._skills_from_tokens(tokens)
        must_have, nice = self._split_must_vs_nice(text, found_skills)
        keywords = self._keywords_from_text(text)

        result = JobParseResult(
            role=role,
            seniority=seniority,
            must_have_skills=must_have,
            good_to_have_skills=nice,
            keywords=keywords[: self._settings.job_parser_max_keywords],
            responsibilities=responsibilities,
        )
        logger.debug("Parsed job: role=%s seniority=%s", result.role, result.seniority)
        return result

    def _infer_role(self, text: str) -> str:
        m = _ROLE_LINE.search(text)
        if m:
            return m.group(1).strip()[:200]
        first = text.splitlines()[0].strip()
        if len(first) <= 120 and not first.lower().startswith("we "):
            return first
        return "Software Engineer"

    def _infer_seniority(self, text: str) -> str:
        m = _SENIORITY_PATTERN.search(text)
        if not m:
            return "mid"
        word = m.group(1).lower()
        if word in {"junior", "jr", "jr.", "entry"}:
            return "junior"
        if word in {"senior", "sr", "sr."}:
            return "senior"
        if word in {"lead", "principal", "staff"}:
            return word
        if word in {"mid", "intermediate"}:
            return "mid"
        if word in {"manager", "director", "head", "chief"}:
            return word
        return "mid"

    def _extract_bullets(self, text: str) -> list[str]:
        lines = []
        for line in text.splitlines():
            s = line.strip()
            if s.startswith(("-", "*", "•")):
                lines.append(s.lstrip("-*• ").strip())
            elif re.match(r"^\d+[\.)]\s+", s):
                lines.append(re.sub(r"^\d+[\.)]\s+", "", s).strip())
        return [x for x in lines if len(x) > 5]

    def _tokenize(self, text: str) -> list[str]:
        lowered = text.lower()
        return re.findall(r"[a-z][a-z0-9+#/\-]{1,}", lowered)

    def _skills_from_tokens(self, tokens: list[str]) -> list[str]:
        bigrams: list[str] = []
        for i in range(len(tokens) - 1):
            bigrams.append(f"{tokens[i]} {tokens[i + 1]}")
        candidates = set(tokens) | set(bigrams)
        hits: list[str] = []
        for c in candidates:
            if c in _SKILL_LEXICON:
                hits.append(c)
        # preserve frequency order
        order = [x for x, _ in Counter(hits).most_common()]
        return order

    def _split_must_vs_nice(self, text: str, skills: list[str]) -> tuple[list[str], list[str]]:
        """
        Partition skills: top-ranked as must-haves; optional section adds nice-to-haves.

        Deterministic stand-in for an LLM—swap with model-based extraction later.
        """
        lower = text.lower()
        nice_section_skills: list[str] = []
        for label in ("nice to have", "preferred", "bonus points"):
            idx = lower.find(label)
            if idx != -1:
                snippet = lower[idx : idx + 1200]
                for sk in skills:
                    if sk in snippet:
                        nice_section_skills.append(sk)
                break

        def dedupe(seq: list[str]) -> list[str]:
            seen: set[str] = set()
            out: list[str] = []
            for x in seq:
                if x not in seen:
                    seen.add(x)
                    out.append(x)
            return out

        nice_set = set(dedupe(nice_section_skills))
        must = [s for s in skills if s not in nice_set][:15]
        nice = [s for s in skills if s in nice_set][:15]
        if not nice and len(skills) > 8:
            must = skills[:8]
            nice = skills[8:16]
        return must, nice

    def _keywords_from_text(self, text: str) -> list[str]:
        tokens = self._tokenize(text)
        stop = frozenset(
            "the a an and or for with from this that our you we to in of on at as by "
            "is are was will be have has had not your all any".split()
        )
        counts = Counter(t for t in tokens if len(t) > 2 and t not in stop)
        return [w for w, _ in counts.most_common(60)]
