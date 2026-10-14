"""Provider-neutral visual analysis with a small, local OCR implementation."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import platform
import shutil
import subprocess
import tempfile
from typing import Mapping, Optional, Protocol


@dataclass(frozen=True, slots=True)
class VisualAnalysisResult:
    status: str
    analyzer_name: Optional[str] = None
    ocr_text: Optional[str] = None
    description: Optional[str] = None
    error_code: Optional[str] = None


class VisualAnalyzer(Protocol):
    """A visual provider must return explicit evidence or an explicit failure."""

    name: str

    def analyze(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        source_locator: Mapping[str, object],
    ) -> VisualAnalysisResult:
        ...


class DeferredVisualAnalyzer:
    """Phase 1 placeholder that never claims OCR or visual understanding."""

    name = "deferred"

    def analyze(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        source_locator: Mapping[str, object],
    ) -> VisualAnalysisResult:
        del image_bytes, mime_type, source_locator
        return VisualAnalysisResult(status="not_requested", analyzer_name=self.name)


class LocalOCRAnalyzer:
    """Extract visible text locally without assigning meaning to diagrams.

    macOS uses the built-in Vision framework. Other platforms may use a local
    Tesseract executable. Missing engines and images with no recognized text are
    represented explicitly as unavailable.
    """

    name = "local-ocr"

    def __init__(self, *, timeout_seconds: float = 20.0):
        self.timeout_seconds = timeout_seconds
        self._vision_script = Path(__file__).parents[2] / "tools" / "vision_ocr.swift"

    def _macos_binary(self) -> Optional[Path]:
        configured = os.getenv("ALEX_VISION_OCR_BIN", "").strip()
        target = (
            Path(configured).expanduser()
            if configured
            else Path(__file__).parents[2] / ".local-data" / "bin" / "vision_ocr"
        )
        if target.is_file() and os.access(target, os.X_OK):
            return target
        if platform.system() != "Darwin" or not self._vision_script.is_file() or not shutil.which("xcrun"):
            return None
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            compiled = subprocess.run(
                ["xcrun", "swiftc", str(self._vision_script), "-o", str(target)],
                capture_output=True,
                timeout=120,
                check=False,
            )
            if compiled.returncode == 0 and target.is_file():
                return target
        except (OSError, subprocess.TimeoutExpired):
            pass
        return None

    def _command(self, image_path: str) -> Optional[list[str]]:
        if platform.system() == "Darwin":
            binary = self._macos_binary()
            if binary is not None:
                return [str(binary), image_path]
        executable = shutil.which("tesseract")
        if executable:
            return [executable, image_path, "stdout", "--psm", "6"]
        return None

    def analyze(
        self,
        *,
        image_bytes: bytes,
        mime_type: str,
        source_locator: Mapping[str, object],
    ) -> VisualAnalysisResult:
        del source_locator
        if not image_bytes:
            return VisualAnalysisResult(
                status="unavailable", analyzer_name=self.name, error_code="empty_image"
            )
        suffixes = {
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jp2": ".jp2",
            "image/tiff": ".tiff",
            "image/bmp": ".bmp",
            "image/webp": ".webp",
        }
        suffix = suffixes.get((mime_type or "").lower())
        if not suffix:
            return VisualAnalysisResult(
                status="unavailable", analyzer_name=self.name, error_code="unsupported_image_type"
            )

        path = ""
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as handle:
                handle.write(image_bytes)
                path = handle.name
            command = self._command(path)
            if command is None:
                return VisualAnalysisResult(
                    status="unavailable", analyzer_name=self.name, error_code="ocr_engine_unavailable"
                )
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
                env={
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": os.environ.get("HOME", "/tmp"),
                    "LC_ALL": "C.UTF-8",
                    **(
                        {"TESSDATA_PREFIX": os.environ["TESSDATA_PREFIX"]}
                        if os.environ.get("TESSDATA_PREFIX")
                        else {}
                    ),
                },
            )
            if result.returncode != 0:
                return VisualAnalysisResult(
                    status="failed", analyzer_name=self.name, error_code="ocr_failed"
                )
            text = "\n".join(line.strip() for line in result.stdout.splitlines() if line.strip()).strip()
            if not text:
                return VisualAnalysisResult(
                    status="unavailable", analyzer_name=self.name, error_code="no_text_detected"
                )
            return VisualAnalysisResult(
                status="complete", analyzer_name=self.name, ocr_text=text[:20_000]
            )
        except subprocess.TimeoutExpired:
            return VisualAnalysisResult(
                status="failed", analyzer_name=self.name, error_code="ocr_timeout"
            )
        except OSError:
            return VisualAnalysisResult(
                status="failed", analyzer_name=self.name, error_code="ocr_failed"
            )
        finally:
            if path:
                try:
                    os.unlink(path)
                except OSError:
                    pass
