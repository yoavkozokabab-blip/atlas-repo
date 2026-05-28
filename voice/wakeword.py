"""openWakeWord detector — activates listening only, never executes commands."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import numpy as np

from config import (
    WAKE_WORD_DEBUG,
    WAKE_WORD_DISPLAY_PHRASES,
    WAKE_WORD_MODEL,
    WAKE_WORD_MODEL_PATH,
    WAKE_WORD_NOTIFY,
    WAKE_WORD_SAMPLE_RATE,
    WAKE_WORD_THRESHOLD,
)
from voice.wake_phrases import parse_wake_display_phrases, trained_phrase_for_model
from core.logger import setup_logger
from voice.privacy import validate_runtime_privacy

if TYPE_CHECKING:
    from core.app import JarvisApp

logger = setup_logger("jarvis.voice.wakeword")

CHUNK_SAMPLES = 1280  # ~80ms at 16 kHz
INFERENCE_FRAMEWORK = "onnx"

MODEL_NOT_FOUND_MSG = (
    "Wake word model not found. Download/provide WAKE_WORD_MODEL_PATH."
)

# Map user-facing model name to openWakeWord pre-trained id when needed
_MODEL_ALIASES: dict[str, str] = {
    "jarvis": "hey_jarvis",
    "hey_jarvis": "hey_jarvis",
    "alexa": "alexa",
    "mycroft": "hey_mycroft",
    "hey_mycroft": "hey_mycroft",
    "hey_rhasspy": "hey_rhasspy",
}


class WakeWordModelError(Exception):
    """Configured wake word model file is missing."""


@dataclass
class WakeWordModelResolution:
    """Result of resolving a wake word model path on disk."""

    model_name: str
    model_path: Path | None
    searched_paths: list[Path] = field(default_factory=list)
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.model_path is not None and self.model_path.is_file()


def resolve_oww_model_name(name: str) -> str:
    key = (name or "jarvis").strip().lower()
    return _MODEL_ALIASES.get(key, key)


def _openwakeword_resources_dir() -> Path:
    import openwakeword

    return Path(openwakeword.__file__).resolve().parent / "resources" / "models"


def _official_model_candidates(model_name: str, *, framework: str = INFERENCE_FRAMEWORK) -> list[Path]:
    """Paths from openwakeword.MODELS metadata (no download)."""
    import openwakeword

    entry = openwakeword.MODELS.get(model_name)
    if not entry:
        return []
    base = Path(entry["model_path"])
    candidates = [base]
    if framework == "onnx":
        candidates.insert(0, base.with_suffix(".onnx"))
    elif framework == "tflite":
        candidates = [base.with_suffix(".tflite") if base.suffix == ".onnx" else base]
    return candidates


def _glob_resource_models(base_name: str) -> list[Path]:
    resources = _openwakeword_resources_dir()
    if not resources.is_dir():
        return []
    found: list[Path] = []
    for pattern in (f"{base_name}*.onnx", f"{base_name}*.tflite"):
        found.extend(sorted(resources.glob(pattern)))
    return found


def resolve_wake_word_model(
    *,
    model: str | None = None,
    model_path: str | None = None,
    framework: str = INFERENCE_FRAMEWORK,
) -> WakeWordModelResolution:
    """
    Resolve wake word model to an existing file path.

    Order:
    1. WAKE_WORD_MODEL_PATH if set and exists
    2. openwakeword resources glob for resolved name (e.g. hey_jarvis*.onnx)
    3. official MODELS entry paths for resolved name
    """
    configured_name = resolve_oww_model_name(model or WAKE_WORD_MODEL)
    searched: list[Path] = []

    explicit = (model_path or WAKE_WORD_MODEL_PATH or "").strip()
    if explicit:
        p = Path(explicit).expanduser()
        searched.append(p)
        if p.is_file():
            return WakeWordModelResolution(
                model_name=configured_name,
                model_path=p.resolve(),
                searched_paths=searched,
            )

    for candidate in _glob_resource_models(configured_name):
        searched.append(candidate)
        if candidate.is_file():
            use = candidate
            if framework == "onnx" and candidate.suffix == ".tflite":
                onnx_variant = candidate.with_suffix(".onnx")
                searched.append(onnx_variant)
                if onnx_variant.is_file():
                    use = onnx_variant
            return WakeWordModelResolution(
                model_name=configured_name,
                model_path=use.resolve(),
                searched_paths=searched,
            )

    for candidate in _official_model_candidates(configured_name, framework=framework):
        searched.append(candidate)
        if candidate.is_file():
            return WakeWordModelResolution(
                model_name=configured_name,
                model_path=candidate.resolve(),
                searched_paths=searched,
            )

    return WakeWordModelResolution(
        model_name=configured_name,
        model_path=None,
        searched_paths=searched,
        error=MODEL_NOT_FOUND_MSG,
    )


def format_wake_word_model_status(resolution: WakeWordModelResolution | None = None) -> str:
    """Human-readable model resolution status for CLI / tray."""
    res = resolution or resolve_wake_word_model()
    display = ", ".join(parse_wake_display_phrases(WAKE_WORD_DISPLAY_PHRASES))
    trained = trained_phrase_for_model(res.model_name)
    lines = [
        f"Wake word model (openWakeWord): {res.model_name}",
        f"Model trained phrase: {trained}",
        f"Say to activate (UX): {display}",
        f"Detection threshold: {WAKE_WORD_THRESHOLD}",
        f"Configured WAKE_WORD_MODEL: {WAKE_WORD_MODEL}",
        f"Configured path: {WAKE_WORD_MODEL_PATH or '(not set)'}",
    ]
    if res.model_name == "hey_jarvis":
        lines.append(
            "Note: hey_jarvis is trained for 'Hey Jarvis'; short 'Jarvis' may need "
            "WAKE_WORD_THRESHOLD=0.55 if wake is inconsistent."
        )
    if res.ok and res.model_path:
        lines.append(f"Resolved model: {res.model_path}")
    else:
        lines.append(f"Resolved model: MISSING — {res.error or MODEL_NOT_FOUND_MSG}")
    lines.append("Searched paths:")
    if res.searched_paths:
        for p in res.searched_paths:
            mark = "FOUND" if p.is_file() else "missing"
            lines.append(f"  - [{mark}] {p}")
    else:
        lines.append("  (none)")
    if not res.ok:
        lines.append(
            "Hint: py -3 -c \"from openwakeword.utils import download_models; "
            f"download_models(model_names=['{res.model_name}'])\""
        )
    return "\n".join(lines)


def print_wake_word_model_status() -> WakeWordModelResolution:
    res = resolve_wake_word_model()
    print(format_wake_word_model_status(res), flush=True)
    return res


class WakeWordDetector:
    """
    Background wake word listener. On detection invokes on_wake callback only.
    """

    def __init__(
        self,
        app: "JarvisApp",
        on_wake: Callable[[float], None],
        *,
        model_factory: Callable | None = None,
        model_resolution: WakeWordModelResolution | None = None,
    ) -> None:
        self.app = app
        self.runtime = app.runtime
        self.on_wake = on_wake
        self._model_factory = model_factory
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._model = None
        self._resolved_name = resolve_oww_model_name(WAKE_WORD_MODEL)
        self._resolution = model_resolution or resolve_wake_word_model()
        self._model_file: Path | None = (
            self._resolution.model_path if self._resolution.ok else None
        )

    def start(self) -> bool:
        """Start detector thread. Returns False if model file is missing."""
        if self._thread and self._thread.is_alive():
            return True
        if not self._resolution.ok or self._model_file is None:
            msg = format_wake_word_model_status(self._resolution)
            self.runtime.increment_wake_error(MODEL_NOT_FOUND_MSG)
            self.runtime.set_wake_word(False)
            logger.error("Wake word not started — model missing")
            print(msg, flush=True)
            return False
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._detect_loop,
            name="jarvis-wakeword",
            daemon=True,
        )
        self._thread.start()
        display = ", ".join(parse_wake_display_phrases())
        logger.info(
            "WakeWordDetector started model=%s trained=%s phrases=[%s] threshold=%.2f path=%s",
            self._resolved_name,
            trained_phrase_for_model(self._resolved_name),
            display,
            WAKE_WORD_THRESHOLD,
            self._model_file,
        )
        return True

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)
        self._thread = None
        self._model = None

    def _load_model(self):
        if self._model_factory is not None:
            return self._model_factory()
        if self._model_file is None:
            raise WakeWordModelError(MODEL_NOT_FOUND_MSG)
        from openwakeword.model import Model

        return Model(
            wakeword_models=[str(self._model_file)],
            inference_framework=INFERENCE_FRAMEWORK,
        )

    def _in_cooldown(self) -> bool:
        return time.monotonic() < self.runtime.wake_word_cooldown_until

    def _detector_suspended(self) -> bool:
        return self.runtime.wake_word_listening_active or self._in_cooldown()

    def _detect_loop(self) -> None:
        for w in validate_runtime_privacy():
            logger.info("Privacy: %s", w)

        try:
            from voice.microphone import MicrophoneError, check_microphone_available

            check_microphone_available()
        except Exception as exc:
            self.runtime.increment_wake_error(str(exc))
            logger.warning("Wake word mic unavailable: %s", exc)
            return

        try:
            self._model = self._load_model()
        except Exception as exc:
            self.runtime.increment_wake_error(f"Model load failed: {exc}")
            logger.warning("Wake word model failed: %s", exc)
            print(format_wake_word_model_status(self._resolution), flush=True)
            return

        try:
            import sounddevice as sd
        except ImportError as exc:
            self.runtime.increment_wake_error(str(exc))
            return

        rate = WAKE_WORD_SAMPLE_RATE
        device = None
        from config import STT_DEVICE

        if STT_DEVICE:
            try:
                device = int(STT_DEVICE)
            except ValueError:
                device = None

        try:
            with sd.InputStream(
                samplerate=rate,
                channels=1,
                dtype="int16",
                blocksize=CHUNK_SAMPLES,
                device=device,
            ) as stream:
                while not self._stop.is_set():
                    if not self.runtime.running or not self.runtime.wake_word_enabled:
                        time.sleep(0.2)
                        continue
                    if self._detector_suspended():
                        time.sleep(0.1)
                        continue

                    try:
                        chunk, _overflowed = stream.read(CHUNK_SAMPLES)
                    except Exception as exc:
                        self.runtime.increment_wake_error(str(exc))
                        time.sleep(1.0)
                        continue

                    audio = np.squeeze(chunk)
                    if audio.size == 0:
                        continue

                    try:
                        self._model.predict(audio)
                    except Exception as exc:
                        self.runtime.increment_wake_error(str(exc))
                        if WAKE_WORD_DEBUG:
                            logger.debug("predict error: %s", exc)
                        continue

                    score = self._best_score()
                    if score >= WAKE_WORD_THRESHOLD:
                        self._handle_detection(score)
        except Exception as exc:
            self.runtime.increment_wake_error(str(exc))
            logger.warning("Wake word detect loop ended: %s", exc)

    def _best_score(self) -> float:
        if self._model is None:
            return 0.0
        best = 0.0
        buffer = getattr(self._model, "prediction_buffer", {}) or {}
        for _name, scores in buffer.items():
            if not scores:
                continue
            try:
                val = float(scores[-1])
            except (TypeError, IndexError):
                continue
            if val > best:
                best = val
        return best

    def _handle_detection(self, score: float) -> None:
        if self._detector_suspended():
            return
        try:
            from voice.wake_diagnostics import record_wake_detected

            record_wake_detected()
        except Exception:
            pass
        self.runtime.record_wake_detection(score)
        if WAKE_WORD_DEBUG:
            logger.info("Wake word detected score=%.3f", score)
        if WAKE_WORD_NOTIFY:
            try:
                from ui.notifications import notify

                notify("JARVIS", "Wake word detected — listening…")
            except Exception as exc:
                logger.debug("Wake notify failed: %s", exc)
        try:
            from ui.overlay_app import notify_overlay_wake_detected

            notify_overlay_wake_detected()
        except Exception as exc:
            logger.debug("Overlay wake notify failed: %s", exc)
        try:
            self.on_wake(score)
        except Exception as exc:
            self.runtime.increment_wake_error(str(exc))
            logger.warning("on_wake callback failed: %s", exc)
