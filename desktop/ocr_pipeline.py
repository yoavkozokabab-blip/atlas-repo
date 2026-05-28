"""OCR pipeline with fallbacks (Phase 67)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import config
from core.logger import setup_logger

logger = setup_logger("jarvis.desktop.ocr")


@dataclass
class OcrDiagnostics:
    tesseract_installed: bool
    image_captured: bool
    screenshot_path: str
    text_length: int
    engine: str
    confidence: float | None
    windows_ocr_available: bool
    accessibility_fallback_used: bool


def tesseract_installed() -> bool:
    try:
        from vision.screen_ocr import _tesseract_available

        return _tesseract_available()
    except Exception:
        return False


def windows_ocr_available() -> bool:
    try:
        import winrt  # noqa: F401

        return True
    except Exception:
        return False


def _run_windows_ocr(image: Any) -> tuple[str, float | None]:
    try:
        import asyncio
        from io import BytesIO

        from PIL import Image
        from winrt.windows.graphics.imaging import BitmapDecoder
        from winrt.windows.media.ocr import OcrEngine
        from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

        buf = BytesIO()
        image.save(buf, format="PNG")
        raw = buf.getvalue()

        async def _ocr() -> tuple[str, float | None]:
            stream = InMemoryRandomAccessStream()
            writer = DataWriter(stream)
            writer.write_bytes(raw)
            await writer.store_async()
            stream.seek(0)
            decoder = await BitmapDecoder.create_async(stream)
            software = await decoder.get_software_bitmap_async()
            engine = OcrEngine.try_create_from_user_profile_languages()
            if engine is None:
                return "", None
            result = await engine.recognize_async(software)
            lines = [ln.text for ln in result.lines if ln.text]
            return "\n".join(lines).strip(), None

        return asyncio.run(_ocr())
    except Exception as exc:
        logger.debug("Windows OCR unavailable: %s", exc)
        return "", None


def _accessibility_text_fallback() -> tuple[str, str]:
    parts: list[str] = []
    try:
        from vision.active_window import get_active_window_metadata

        meta = get_active_window_metadata()
        if meta.title:
            parts.append(meta.title)
        if meta.process_name:
            parts.append(meta.process_name)
    except Exception:
        pass
    try:
        from vision.window_info import list_visible_windows

        for win in list_visible_windows()[:12]:
            if win.title:
                parts.append(win.title)
    except Exception:
        pass
    text = "\n".join(dict.fromkeys(p for p in parts if p))
    return text, "accessibility"


def extract_ocr_with_fallback(
    image: Any | None = None,
    *,
    screenshot_path: str = "",
) -> tuple[str, str, OcrDiagnostics]:
    """Returns (text, engine, diagnostics)."""
    path = screenshot_path
    captured = False
    if image is None and path and Path(path).is_file():
        captured = True
        try:
            from PIL import Image

            image = Image.open(path)
        except Exception:
            image = None
    if image is None:
        try:
            from desktop.vision_runtime import capture_active_monitor

            ok, cap_path, _msg = capture_active_monitor()
            if ok and cap_path:
                path = cap_path
                captured = True
                from PIL import Image

                image = Image.open(cap_path)
        except Exception:
            image = None

    tess_ok = tesseract_installed()
    text = ""
    engine = "none"
    confidence: float | None = None
    win_ok = windows_ocr_available()
    a11y_used = False

    if image is not None and tess_ok:
        try:
            from vision.screen_ocr import run_screen_ocr

            result = run_screen_ocr(image)
            text = result.text or ""
            engine = result.engine or "pytesseract"
            confidence = result.confidence
        except Exception as exc:
            logger.debug("Tesseract OCR failed: %s", exc)

    if not text.strip() and image is not None and win_ok:
        wtext, wconf = _run_windows_ocr(image)
        if wtext.strip():
            text = wtext
            engine = "windows_ocr"
            confidence = wconf

    if not text.strip():
        atext, aengine = _accessibility_text_fallback()
        if atext.strip():
            text = atext
            engine = aengine
            a11y_used = True

    diag = OcrDiagnostics(
        tesseract_installed=tess_ok,
        image_captured=captured,
        screenshot_path=path or "",
        text_length=len(text.strip()),
        engine=engine,
        confidence=confidence,
        windows_ocr_available=win_ok,
        accessibility_fallback_used=a11y_used,
    )
    return text, engine, diag
