"""
Render resume JSON to HTML via Jinja2 and export PDF using Playwright.

HTML/CSS live under the configured templates directory for easy branding changes.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape
from playwright.async_api import async_playwright

from app.config import get_settings
from app.schemas.resume import Resume
from app.utils.logging import get_logger

logger = get_logger(__name__)


class PdfService:
    """Jinja2 → HTML → PDF pipeline."""

    def __init__(self) -> None:
        self._settings = get_settings()
        self._templates_dir = Path(self._settings.templates_dir)
        self._output_dir = Path(self._settings.output_dir)
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._env = Environment(
            loader=FileSystemLoader(str(self._templates_dir)),
            autoescape=select_autoescape(["html", "xml"]),
        )

    def render_html(self, resume: Resume) -> str:
        """
        Render the resume using ``resume.html`` template.

        Args:
            resume: Resume model.

        Returns:
            HTML string.
        """
        template = self._env.get_template("resume.html")
        html = template.render(resume=resume.model_dump(mode="python"))
        return html

    async def generate_pdf(
        self,
        resume: Resume,
        output_filename: str | None = None,
    ) -> Path:
        """
        Write a PDF file to the configured output directory.

        Args:
            resume: Resume to render.
            output_filename: Optional ``*.pdf`` filename; random if omitted.

        Returns:
            Absolute path to the created PDF.
        """
        html = self.render_html(resume)
        name = output_filename or f"resume-{uuid.uuid4().hex}.pdf"
        if not name.lower().endswith(".pdf"):
            name = f"{name}.pdf"
        out_path = (self._output_dir / name).resolve()
        await self._html_to_pdf(html, out_path)
        logger.info("Wrote PDF %s", out_path)
        return out_path

    async def _html_to_pdf(self, html: str, out_path: Path) -> None:
        """Use headless Chromium to print HTML to PDF (matches modern CSS)."""
        out_path.parent.mkdir(parents=True, exist_ok=True)
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            try:
                page = await browser.new_page()
                await page.set_content(html, wait_until="load")
                await page.pdf(
                    path=str(out_path),
                    format=self._settings.pdf_format,
                    print_background=self._settings.pdf_print_background,
                    margin={"top": "12mm", "bottom": "12mm", "left": "12mm", "right": "12mm"},
                )
            finally:
                await browser.close()
