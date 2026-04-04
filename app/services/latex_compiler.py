"""
LaTeX-to-PDF compilation service using Docker.
"""

from __future__ import annotations

import asyncio
import shutil
import tempfile
from pathlib import Path

from app.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class LatexCompilerService:
    """Compile LaTeX to PDF: Docker on dev machines, native ``pdflatex`` in production."""

    def __init__(self):
        self.settings = get_settings()
        self.image = "noahwu/minimal-latex:latest"  # Verified ARM64-native minimal image

    async def compile_to_pdf(self, latex_content: str) -> bytes:
        """
        Compile LaTeX string to PDF bytes.

        Uses Docker when the ``docker`` CLI is available (typical local dev). On hosts
        without Docker (e.g. Render), uses ``pdflatex`` from TeX Live installed in the image.
        """
        workspace_base = self.settings.data_dir / "tmp"
        workspace_base.mkdir(parents=True, exist_ok=True)

        with tempfile.TemporaryDirectory(dir=workspace_base) as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            tex_file = tmp_dir / "resume.tex"
            pdf_file = tmp_dir / "resume.pdf"

            tex_file.write_text(latex_content, encoding="utf-8")
            abs_tmp_dir = tmp_dir.resolve()

            if shutil.which("docker"):
                return await self._compile_with_docker(abs_tmp_dir, pdf_file)
            return await self._compile_with_pdflatex(tmp_dir, pdf_file)

    async def _compile_with_docker(self, abs_tmp_dir: Path, pdf_file: Path) -> bytes:
        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "-v",
            f"{abs_tmp_dir}:/data",
            "-w",
            "/data",
            self.image,
            "pdflatex",
            "-interaction=nonstopmode",
            "resume.tex",
        ]
        logger.info("Compiling LaTeX to PDF via Docker: %s", " ".join(docker_cmd))
        process = await asyncio.create_subprocess_exec(
            *docker_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            error_msg = stderr.decode().strip() or stdout.decode().strip()
            logger.error("LaTeX compilation failed: %s", error_msg)
            raise RuntimeError(f"LaTeX compilation failed: {error_msg}")
        if not pdf_file.exists():
            logger.error("pdflatex finished but resume.pdf was not found.")
            raise RuntimeError("PDF file was not generated.")
        return pdf_file.read_bytes()

    async def _compile_with_pdflatex(self, tmp_dir: Path, pdf_file: Path) -> bytes:
        pdflatex = shutil.which("pdflatex")
        if not pdflatex:
            raise RuntimeError(
                "pdflatex is not installed. Use Docker for local LaTeX, or install TeX Live on the server."
            )
        tex_name = "resume.tex"
        logger.info("Compiling LaTeX to PDF via pdflatex: cwd=%s", tmp_dir)
        process = await asyncio.create_subprocess_exec(
            pdflatex,
            "-interaction=nonstopmode",
            "-halt-on-error",
            tex_name,
            cwd=str(tmp_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            error_msg = stderr.decode().strip() or stdout.decode().strip()
            logger.error("LaTeX compilation failed: %s", error_msg)
            raise RuntimeError(f"LaTeX compilation failed: {error_msg}")
        if not pdf_file.exists():
            logger.error("pdflatex finished but resume.pdf was not found.")
            raise RuntimeError("PDF file was not generated.")
        return pdf_file.read_bytes()

compiler_service = LatexCompilerService()
