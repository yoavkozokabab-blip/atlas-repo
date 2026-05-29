"""Screen capture via mss (read-only, no input control)."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from config import (
    PROJECT_ROOT,
    SCREEN_CAPTURE_ALLOW,
    SCREEN_CAPTURE_MODE,
    SCREEN_CAPTURE_SAVE_DEBUG,
    SCREEN_CAPTURE_TEMP_DIR,
    SCREEN_UNDERSTANDING_DISABLED_MESSAGE,
    SCREEN_UNDERSTANDING_ENABLED,
    VISION_CAPTURE_DIR,
    VISION_DISABLED_MESSAGE,
    VISION_ENABLED,
    VISION_MAX_SCREENSHOT_AGE_SECONDS,
    VISION_SAVE_SCREENSHOTS,
)
from core.file_cleanup import remove_file_best_effort
from core.logger import setup_logger

logger = setup_logger("jarvis.vision.capture")


class VisionDisabledError(Exception):
    """Raised when VISION_ENABLED is false."""


class ScreenUnderstandingDisabledError(Exception):
    """Raised when SCREEN_UNDERSTANDING_ENABLED is false."""


@dataclass
class CaptureResult:
    """Phase 35 structured capture result (read-only)."""

    ok: bool = False
    mode: str = ""
    image: Any = None
    image_size: tuple[int, int] = (0, 0)
    active_window_title: str = ""
    active_process: str = ""
    warning: str = ""
    temp_path_used: str | None = None
    deleted_after_use: bool = False
    error: str | None = None


@dataclass
class ScreenshotResult:
    """Captured screen image metadata."""

    image: Any = None
    width: int = 0
    height: int = 0
    monitor: dict[str, Any] = field(default_factory=dict)
    saved_path: Path | None = None
    temp_path: Path | None = None
    error: str | None = None


def _ensure_vision_enabled() -> None:
    if not VISION_ENABLED:
        raise VisionDisabledError(VISION_DISABLED_MESSAGE)


def _capture_dir() -> Path:
    path = VISION_CAPTURE_DIR.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _prune_old_screenshots(directory: Path) -> None:
    """Delete screenshots older than VISION_MAX_SCREENSHOT_AGE_SECONDS."""
    if VISION_MAX_SCREENSHOT_AGE_SECONDS <= 0:
        return
    cutoff = datetime.now(timezone.utc).timestamp() - VISION_MAX_SCREENSHOT_AGE_SECONDS
    try:
        for item in directory.glob("*.png"):
            if item.stat().st_mtime < cutoff:
                item.unlink(missing_ok=True)
    except OSError as exc:
        logger.debug("Screenshot age-prune skipped: %s", exc)


# S2.7 — Maximum screenshot count.  Regardless of age, keep only the most
# recent _MAX_SCREENSHOTS files so the directory never grows without bound.
_MAX_SCREENSHOTS: int = 10


def _prune_screenshot_count(directory: Path) -> None:
    """Keep only the _MAX_SCREENSHOTS most recent PNG files in *directory*."""
    files: list[tuple[float, Path]] = []
    for item in directory.glob("*.png"):
        try:
            files.append((item.stat().st_mtime, item))
        except OSError as exc:
            logger.debug("Screenshot count-prune stat skipped for %s: %s", item, exc)
    files.sort(key=lambda pair: pair[0], reverse=True)
    for _mtime, old in files[_MAX_SCREENSHOTS:]:
        if not remove_file_best_effort(old):
            logger.debug("Screenshot count-prune could not remove %s", old)


def _save_image(image: Any, *, force_save: bool) -> Path | None:
    should_save = force_save or VISION_SAVE_SCREENSHOTS
    if not should_save:
        return None

    directory = _capture_dir()
    _prune_old_screenshots(directory)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = directory / f"{stamp}.png"
    image.save(dest, format="PNG")
    # S2.7: enforce count limit AFTER saving so we always keep the just-saved file.
    _prune_screenshot_count(directory)
    return dest.resolve()


def _grab_monitor(monitor_index: int = 0) -> tuple[Any, dict[str, Any]]:
    import mss
    from PIL import Image

    with mss.mss() as sct:
        monitors = sct.monitors
        idx = min(max(monitor_index, 0), len(monitors) - 1)
        mon = monitors[idx] if monitors else {"left": 0, "top": 0, "width": 0, "height": 0}
        shot = sct.grab(mon)
        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        info = {
            "index": idx,
            "left": mon.get("left", 0),
            "top": mon.get("top", 0),
            "width": shot.width,
            "height": shot.height,
        }
        return image, info


def capture_screen(*, save: bool = False) -> ScreenshotResult:
    """
    Capture primary monitor. Saves only if save=True or VISION_SAVE_SCREENSHOTS.
    """
    _ensure_vision_enabled()
    try:
        image, info = _grab_monitor(0)
        saved = _save_image(image, force_save=save)
        temp_path: Path | None = None
        if saved is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            temp_path = Path(tmp.name)
            image.save(temp_path, format="PNG")

        return ScreenshotResult(
            image=image,
            width=info.get("width", image.width),
            height=info.get("height", image.height),
            monitor=info,
            saved_path=saved,
            temp_path=temp_path,
        )
    except VisionDisabledError:
        raise
    except Exception as exc:
        logger.warning("Screen capture failed: %s", exc)
        return ScreenshotResult(error=str(exc))


def capture_active_window(*, save: bool = False) -> ScreenshotResult:
    """Capture the active window region when pygetwindow can resolve it."""
    _ensure_vision_enabled()
    try:
        from vision.window_info import get_active_window_info

        win = get_active_window_info()
        if win.error or win.width <= 0 or win.height <= 0:
            return capture_screen(save=save)

        import mss
        from PIL import Image

        box = {
            "left": max(0, win.left),
            "top": max(0, win.top),
            "width": win.width,
            "height": win.height,
        }
        with mss.mss() as sct:
            shot = sct.grab(box)
            image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")

        saved = _save_image(image, force_save=save)
        temp_path: Path | None = None
        if saved is None:
            tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
            tmp.close()
            temp_path = Path(tmp.name)
            image.save(temp_path, format="PNG")

        return ScreenshotResult(
            image=image,
            width=win.width,
            height=win.height,
            monitor={"active_window": win.title, **box},
            saved_path=saved,
            temp_path=temp_path,
        )
    except VisionDisabledError:
        raise
    except Exception as exc:
        logger.debug("Active window capture fallback: %s", exc)
        return capture_screen(save=save)


def cleanup_temp(path: Path | None) -> bool:
    return remove_file_best_effort(path)


def _screen_temp_dir() -> Path:
    rel = SCREEN_CAPTURE_TEMP_DIR
    path = rel if rel.is_absolute() else (PROJECT_ROOT / rel)
    path = path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _is_forbidden_save_path(path: Path) -> bool:
    parts = {p.lower() for p in path.resolve().parts}
    if "data" in parts:
        return True
    try:
        root = Path(__file__).resolve().parents[1]
        if path.resolve() == root.resolve():
            return True
    except OSError:
        pass
    return False


def _write_temp_image(image: Any) -> Path:
    directory = _screen_temp_dir()
    if _is_forbidden_save_path(directory):
        raise ValueError("SCREEN_CAPTURE_TEMP_DIR must not be project root or data/")
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    dest = directory / f"screen_{stamp}.png"
    image.save(dest, format="PNG")
    return dest.resolve()


def _grab_region(box: dict[str, int]) -> tuple[Any, int, int]:
    import mss
    from PIL import Image

    with mss.mss() as sct:
        shot = sct.grab(box)
        image = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
        return image, shot.width, shot.height


def safe_capture_screen(
    mode: str | None = None,
    *,
    window_meta: Any | None = None,
) -> CaptureResult:
    """
    Phase 35 capture — active window by default; full screen fallback when allowed.
    Does not save permanently unless SCREEN_CAPTURE_SAVE_DEBUG=true.
    """
    if not SCREEN_UNDERSTANDING_ENABLED:
        return CaptureResult(
            ok=False,
            mode=mode or SCREEN_CAPTURE_MODE,
            error=SCREEN_UNDERSTANDING_DISABLED_MESSAGE,
        )

    from vision.active_window import ActiveWindowMeta, get_active_window_metadata

    meta = window_meta if window_meta is not None else get_active_window_metadata()
    capture_mode = (mode or SCREEN_CAPTURE_MODE or "active_window").strip().lower()
    title = getattr(meta, "title", "") or ""
    process = getattr(meta, "process_name", "") or ""

    if getattr(meta, "is_blocked", False):
        return CaptureResult(
            ok=False,
            mode=capture_mode,
            active_window_title=title,
            active_process=process,
            warning=getattr(meta, "block_reason", "") or "Blocked secret-sensitive window.",
        )

    temp_path: Path | None = None
    deleted = False
    warning = getattr(meta, "warning", "") or ""

    def _finish(image: Any, w: int, h: int, used_mode: str, warn: str = "") -> CaptureResult:
        nonlocal temp_path, deleted
        if image is None:
            return CaptureResult(
                ok=False,
                mode=used_mode,
                active_window_title=title,
                active_process=process,
                warning=warn or warning,
                error="Capture produced no image.",
            )
        if SCREEN_CAPTURE_SAVE_DEBUG:
            try:
                temp_path = _write_temp_image(image)
            except Exception as exc:
                return CaptureResult(
                    ok=False,
                    mode=used_mode,
                    active_window_title=title,
                    active_process=process,
                    warning=str(exc),
                    error="Could not write debug screenshot to approved temp dir.",
                )
        return CaptureResult(
            ok=True,
            mode=used_mode,
            image=image,
            image_size=(w, h),
            active_window_title=title,
            active_process=process,
            warning=warn or warning,
            temp_path_used=str(temp_path) if temp_path else None,
            deleted_after_use=deleted,
        )

    try:
        if capture_mode == "full_screen":
            if not SCREEN_CAPTURE_ALLOW:
                return CaptureResult(
                    ok=False,
                    mode=capture_mode,
                    active_window_title=title,
                    active_process=process,
                    error="Full screen capture not allowed (SCREEN_CAPTURE_ALLOW=false).",
                )
            image, info = _grab_monitor(0)
            return _finish(image, info.get("width", image.width), info.get("height", image.height), "full_screen")

        # active_window (default)
        w = int(getattr(meta, "width", 0) or 0)
        h = int(getattr(meta, "height", 0) or 0)
        left = int(getattr(meta, "left", 0) or 0)
        top = int(getattr(meta, "top", 0) or 0)
        if w > 0 and h > 0:
            box = {"left": max(0, left), "top": max(0, top), "width": w, "height": h}
            try:
                image, cw, ch = _grab_region(box)
                return _finish(image, cw, ch, "active_window")
            except Exception as exc:
                warning = f"Active window region capture failed: {exc}"

        if SCREEN_CAPTURE_ALLOW:
            image, info = _grab_monitor(0)
            return _finish(
                image,
                info.get("width", image.width),
                info.get("height", image.height),
                "full_screen",
                warn=warning or "Fell back to full screen capture.",
            )
        return CaptureResult(
            ok=False,
            mode="active_window",
            active_window_title=title,
            active_process=process,
            warning=warning,
            error="Active window capture failed and full screen fallback is disabled.",
        )
    except Exception as exc:
        logger.warning("safe_capture_screen failed: %s", exc)
        return CaptureResult(
            ok=False,
            mode=capture_mode,
            active_window_title=title,
            active_process=process,
            warning=warning,
            error=str(exc),
        )


def delete_capture_temp(capture: CaptureResult) -> bool:
    """Remove temp screenshot used for OCR when debug saving is off."""
    if SCREEN_CAPTURE_SAVE_DEBUG:
        return False
    if not capture.temp_path_used:
        return False
    try:
        path = Path(capture.temp_path_used)
        deleted = cleanup_temp(path)
        capture.deleted_after_use = deleted
        return deleted
    except OSError:
        return False


def ensure_ocr_temp_path(capture: CaptureResult) -> Path | None:
    """Write in-memory image to approved temp dir for OCR engines that need a file."""
    if capture.temp_path_used:
        return Path(capture.temp_path_used)
    if capture.image is None:
        return None
    try:
        path = _write_temp_image(capture.image)
        capture.temp_path_used = str(path)
        return path
    except Exception as exc:
        capture.warning = f"Temp OCR path unavailable: {exc}"
        return None
