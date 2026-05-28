"""OCR via pytesseract (local only)."""

from __future__ import annotations

from dataclasses import dataclass, field

from config import TESSERACT_CMD, VISION_OCR_ENABLED, VISION_OCR_LANGUAGE
from core.logger import setup_logger

logger = setup_logger("jarvis.vision.ocr")


@dataclass
class OCRResult:
    text: str = ""
    lines: list[str] = field(default_factory=list)
    confidence: float | None = None
    language: str = ""
    error: str | None = None


def _configure_tesseract() -> None:
    import pytesseract

    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD


def _tesseract_available() -> bool:
    try:
        import pytesseract

        _configure_tesseract()
        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def extract_text(image) -> OCRResult:
    """Extract visible text from a PIL image."""
    if not VISION_OCR_ENABLED:
        return OCRResult(
            error="OCR is disabled (VISION_OCR_ENABLED=false).",
            language=VISION_OCR_LANGUAGE,
        )

    if image is None:
        return OCRResult(error="No image provided for OCR.")

    if not _tesseract_available():
        return OCRResult(
            error=(
                "Tesseract OCR is not available. Install Tesseract on Windows "
                "and set TESSERACT_CMD in .env if not on PATH."
            ),
            language=VISION_OCR_LANGUAGE,
        )

    try:
        import pytesseract

        _configure_tesseract()
        text = pytesseract.image_to_string(image, lang=VISION_OCR_LANGUAGE)
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        conf: float | None = None
        try:
            data = pytesseract.image_to_data(
                image, lang=VISION_OCR_LANGUAGE, output_type=pytesseract.Output.DICT
            )
            confs = [
                float(c)
                for c in data.get("conf", [])
                if str(c).replace("-", "").isdigit() and float(c) >= 0
            ]
            if confs:
                conf = sum(confs) / len(confs)
        except Exception:
            pass

        return OCRResult(
            text=text.strip(),
            lines=lines,
            confidence=conf,
            language=VISION_OCR_LANGUAGE,
        )
    except Exception as exc:
        logger.warning("OCR failed: %s", exc)
        return OCRResult(error=str(exc), language=VISION_OCR_LANGUAGE)
