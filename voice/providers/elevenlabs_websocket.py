"""ElevenLabs WebSocket realtime TTS session (Phase 58)."""

from __future__ import annotations

import base64
import json
import os
import threading
import time
from typing import Iterator

from core.logger import setup_logger
from voice.engines.base import SynthesisChunk

logger = setup_logger("jarvis.voice.providers.elevenlabs_ws")

_session: "ElevenLabsWebSocketSession | None" = None
_session_lock = threading.Lock()


def _use_websocket() -> bool:
    try:
        import config as cfg

        return bool(getattr(cfg, "ELEVENLABS_WEBSOCKET_ENABLED", True))
    except Exception:
        return True


def get_elevenlabs_ws_session() -> "ElevenLabsWebSocketSession":
    global _session
    with _session_lock:
        if _session is None:
            _session = ElevenLabsWebSocketSession()
        return _session


def prewarm_elevenlabs_websocket_at_startup() -> None:
    if not _use_websocket():
        return
    try:
        session = get_elevenlabs_ws_session()
        if session.is_available():
            session.prewarm()
    except Exception as exc:
        logger.debug("ElevenLabs websocket prewarm skipped: %s", exc)


def reset_elevenlabs_ws_for_tests() -> None:
    global _session
    with _session_lock:
        if _session is not None:
            _session.close()
        _session = None


class ElevenLabsWebSocketSession:
    """Persistent ElevenLabs stream-input websocket with keepalive."""

    def __init__(self) -> None:
        self._ws = None
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._keepalive_stop = threading.Event()
        self._keepalive_thread: threading.Thread | None = None
        self._prewarmed = False
        self._last_connect_ms: float | None = None
        self._last_first_byte_ms: float | None = None

    def _api_key(self) -> str:
        return (os.getenv("ELEVENLABS_API_KEY") or "").strip()

    def _voice_id(self, voice: str = "") -> str:
        return (voice or os.getenv("ELEVENLABS_VOICE_ID") or "").strip()

    def _model_id(self) -> str:
        return (os.getenv("ELEVENLABS_MODEL_ID") or "eleven_turbo_v2_5").strip()

    def is_available(self) -> bool:
        return bool(self._api_key() and self._voice_id(""))

    @property
    def last_connect_ms(self) -> float | None:
        return self._last_connect_ms

    @property
    def last_first_byte_ms(self) -> float | None:
        return self._last_first_byte_ms

    def prewarm(self) -> None:
        with self._lock:
            self._ensure_connected(voice="")
            self._prewarmed = True

    def close(self) -> None:
        with self._lock:
            self._keepalive_stop.set()
            if self._keepalive_thread and self._keepalive_thread.is_alive():
                self._keepalive_thread.join(timeout=1.0)
            self._keepalive_thread = None
            if self._ws is not None:
                try:
                    self._ws.close()
                except Exception:
                    pass
            self._ws = None
            self._prewarmed = False

    def cancel(self) -> None:
        self._cancel.set()

    def _ensure_connected(self, *, voice: str) -> None:
        if self._ws is not None:
            return
        try:
            import websocket
        except ImportError as exc:
            raise RuntimeError("websocket-client not installed") from exc

        voice_id = self._voice_id(voice)
        model = self._model_id()
        url = (
            f"wss://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream-input"
            f"?model_id={model}&output_format=mp3_44100_128"
        )
        t0 = time.perf_counter()
        self._ws = websocket.create_connection(
            url,
            header=[f"xi-api-key: {self._api_key()}"],
            timeout=10,
        )
        self._last_connect_ms = (time.perf_counter() - t0) * 1000.0
        init = {
            "text": " ",
            "voice_settings": {
                "stability": 0.45,
                "similarity_boost": 0.75,
                "use_speaker_boost": True,
            },
            "generation_config": {"chunk_length_schedule": [50, 80, 120, 160]},
        }
        self._ws.send(json.dumps(init))
        self._start_keepalive()

    def _start_keepalive(self) -> None:
        if self._keepalive_thread and self._keepalive_thread.is_alive():
            return
        self._keepalive_stop.clear()

        def _loop() -> None:
            interval = 20.0
            try:
                import config as cfg

                interval = float(getattr(cfg, "ELEVENLABS_WS_KEEPALIVE_SECONDS", 20))
            except Exception:
                pass
            while not self._keepalive_stop.wait(interval):
                with self._lock:
                    if self._ws is None:
                        break
                    try:
                        self._ws.ping()
                    except Exception:
                        try:
                            self._ws.close()
                        except Exception:
                            pass
                        self._ws = None
                        break

        self._keepalive_thread = threading.Thread(
            target=_loop,
            name="jarvis-elevenlabs-ws-keepalive",
            daemon=True,
        )
        self._keepalive_thread.start()

    def stream(
        self,
        text: str,
        *,
        voice: str = "",
        prosody: object | None = None,
    ) -> Iterator[SynthesisChunk]:
        del prosody
        if not text.strip():
            return
        if not self.is_available():
            raise RuntimeError("ElevenLabs websocket not configured")

        self._cancel.clear()
        with self._lock:
            try:
                self._ensure_connected(voice=voice)
            except Exception:
                self._ws = None
                raise
            ws = self._ws
            assert ws is not None
            ws.send(json.dumps({"text": text.strip()}))
            ws.send(json.dumps({"text": ""}))

        t0 = time.perf_counter()
        first = True
        while not self._cancel.is_set():
            try:
                raw = ws.recv()
            except Exception as exc:
                with self._lock:
                    self._ws = None
                raise RuntimeError(f"ElevenLabs websocket recv failed: {exc}") from exc
            if raw is None:
                break
            if isinstance(raw, str):
                try:
                    payload = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                if payload.get("isFinal"):
                    break
                audio_b64 = payload.get("audio")
                if not audio_b64:
                    continue
                data = base64.b64decode(audio_b64)
            else:
                data = raw
            if not data:
                continue
            if first:
                first = False
                self._last_first_byte_ms = (time.perf_counter() - t0) * 1000.0
            yield SynthesisChunk(data=data, mime="audio/mpeg", viseme_hint=0.75)
