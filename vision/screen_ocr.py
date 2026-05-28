"""Phase 35 — local OCR for screen understanding (no cloud)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from config import (
    SCREEN_MAX_TEXT_CHARS,
    SCREEN_OCR_ENABLED,
    SCREEN_OCR_ENGINE,
    TESSERACT_CMD,
    VISION_OCR_LANGUAGE,
)
from core.logger import setup_logger

logger = setup_logger("jarvis.vision.screen_ocr")


@dataclass
class OcrBlock:
    text: str = ""
    left: int = 0
    top: int = 0
    width: int = 0
    height: int = 0
    confidence: float | None = None


@dataclass
class ScreenOcrResult:
    ok: bool = False
    text: str = ""
    blocks: list[OcrBlock] = field(default_factory=list)
    engine: str = ""
    warning: str = ""
    confidence: float | None = None
    error: str | None = None


def _normalize_text(text: str) -> str:
    out = re.sub(r"[ \t]+", " ", text or "")
    out = re.sub(r"\n{3,}", "\n\n", out).strip()
    if len(out) > SCREEN_MAX_TEXT_CHARS:
        out = out[: SCREEN_MAX_TEXT_CHARS - 3] + "..."
    return out


def _tesseract_available() -> bool:
    try:
        import pytesseract

        if TESSERACT_CMD:
            pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _run_tesseract(image: Any) -> ScreenOcrResult:
    import pytesseract

    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    lang = VISION_OCR_LANGUAGE
    raw = pytesseract.image_to_string(image, lang=lang)
    text = _normalize_text(raw.strip())

    blocks: list[OcrBlock] = []
    confs: list[float] = []
    try:
        data = pytesseract.image_to_data(
            image, lang=lang, output_type=pytesseract.Output.DICT
        )
        n = len(data.get("text", []))
        for i in range(n):
            word = (data["text"][i] or "").strip()
            if not word:
                continue
            try:
                c = float(data["conf"][i])
            except (TypeError, ValueError):
                c = -1.0
            if c >= 0:
                confs.append(c)
            blocks.append(
                OcrBlock(
                    text=word,
                    left=int(data["left"][i]),
                    top=int(data["top"][i]),
                    width=int(data["width"][i]),
                    height=int(data["height"][i]),
                    confidence=c if c >= 0 else None,
                )
            )
    except Exception as exc:
        logger.debug("OCR block data unavailable: %s", exc)

    avg_conf = sum(confs) / len(confs) if confs else None
    return ScreenOcrResult(
        ok=bool(text),
        text=text,
        blocks=blocks,
        engine="pytesseract",
        confidence=avg_conf,
    )


def _run_legacy_ocr(image: Any) -> ScreenOcrResult:
    from vision.ocr import extract_text

    legacy = extract_text(image)
    if legacy.error and not legacy.text:
        return ScreenOcrResult(
            ok=False,
            engine="legacy_ocr",
            warning=legacy.error,
            error=legacy.error,
        )
    return ScreenOcrResult(
        ok=bool(legacy.text),
        text=_normalize_text(legacy.text),
        engine="legacy_ocr",
        confidence=legacy.confidence,
        warning=legacy.error or "",
    )


def run_screen_ocr(image: Any) -> ScreenOcrResult:
    """Run local OCR with graceful degradation."""
    if not SCREEN_OCR_ENABLED:
        return ScreenOcrResult(
            ok=False,
            engine="disabled",
            error="OCR is disabled (SCREEN_OCR_ENABLED=false).",
        )
    if image is None:
        return ScreenOcrResult(ok=False, engine="none", error="No image for OCR.")

    engine = SCREEN_OCR_ENGINE or "auto"
    try:
        if engine in ("auto", "pytesseract", "tesseract") and _tesseract_available():
            return _run_tesseract(image)
        if engine == "auto":
            return _run_legacy_ocr(image)
        return ScreenOcrResult(
            ok=False,
            engine=engine,
            error=f"OCR engine '{engine}' is not available locally.",
        )
    except Exception as exc:
        logger.warning("Screen OCR failed: %s", exc)
        if engine == "auto":
            try:
                return _run_legacy_ocr(image)
            except Exception:
                pass
        return ScreenOcrResult(
            ok=False,
            engine=engine,
            error=str(exc),
            warning="OCR failed; returning degraded result.",
        )
