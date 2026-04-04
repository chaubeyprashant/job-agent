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
    """Service for compiling LaTeX source to PDF using a Docker container."""

    def __init__(self):
        self.settings = get_settings()
        self.image = "noahwu/minimal-latex:latest"  # Verified ARM64-native minimal image

    async def compile_to_pdf(self, latex_content: str) -> bytes:
        """
        Compile LaTeX string to PDF bytes via Docker.
        
        Args:
            latex_content: The full LaTeX source document.
            
        Returns:
            PDF file content as bytes.
            
        Raises:
            RuntimeError: If compilation fails or docker is unreachable.
        """
        # Create a temporary workspace inside the project's data directory
        workspace_base = self.settings.data_dir / "tmp"
        workspace_base.mkdir(parents=True, exist_ok=True)
        
        with tempfile.TemporaryDirectory(dir=workspace_base) as tmp_dir_name:
            tmp_dir = Path(tmp_dir_name)
            tex_file = tmp_dir / "resume.tex"
            pdf_file = tmp_dir / "resume.pdf"
            
            # Write the LaTeX content
            tex_file.write_text(latex_content, encoding="utf-8")
            
            # Use absolute path for Docker volume mounting
            abs_tmp_dir = tmp_dir.resolve()
            
            # Docker command to run pdflatex
            # --rm: remove container after run
            # -v: mount the tmp dir to /data in the container
            # -w: set working directory to /data
            docker_cmd = [
                "docker", "run", "--rm",
                "-v", f"{abs_tmp_dir}:/data",
                "-w", "/data",
                self.image,
                "pdflatex", "-interaction=nonstopmode", "resume.tex"
            ]
            
            logger.info("Compiling LaTeX to PDF via Docker: %s", " ".join(docker_cmd))
            
            process = await asyncio.create_subprocess_exec(
                *docker_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode().strip() or stdout.decode().strip()
                logger.error("LaTeX compilation failed: %s", error_msg)
                raise RuntimeError(f"LaTeX compilation failed: {error_msg}")
            
            if not pdf_file.exists():
                logger.error("pdflatex finished but resume.pdf was not found.")
                raise RuntimeError("PDF file was not generated.")
            
            # Return the PDF content
            return pdf_file.read_bytes()

compiler_service = LatexCompilerService()
