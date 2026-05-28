"""Piper local low-latency provider (Phase 57)."""

from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Iterator

from voice.engines.base import SynthesisChunk
from voice.providers.base import ProviderHealth, RealtimeTtsProvider, SpeechProsody
from voice.providers.streaming_base import CancellableStreamMixin


class PiperLocalProvider(CancellableStreamMixin, RealtimeTtsProvider):
    name = "piper"
    fallback_only = False

    def __init__(self) -> None:
        self._init_stream_state()

    def _bin(self) -> str:
        return (os.getenv("PIPER_BIN") or "piper").strip()

    def _model(self) -> str:
        return (os.getenv("PIPER_MODEL") or "").strip()

    def is_available(self) -> bool:
        model = self._model()
        if not model or not Path(model).is_file():
            return False
        try:
            proc = subprocess.run(
                [self._bin(), "--version"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            return proc.returncode == 0
        except (OSError, subprocess.TimeoutExpired):
            return False

    def health(self) -> ProviderHealth:
        if self.is_available():
            return ProviderHealth(
                name=self.name,
                available=True,
                latency_class="low",
                reason="piper_model_ready",
            )
        return ProviderHealth(
            name=self.name,
            available=False,
            reason="PIPER_MODEL missing or piper binary unavailable",
        )

    def stream(
        self,
        text: str,
        *,
        voice: str = "",
        rate_raw: str = "",
        prosody: SpeechProsody | None = None,
    ) -> Iterator[SynthesisChunk]:
        del rate_raw, prosody
        if not text.strip():
            return
        if not self.is_available():
            raise RuntimeError("Piper not configured")

        self._init_stream_state()
        model = voice or self._model()
        fd, wav_path = tempfile.mkstemp(suffix=".wav", prefix="jarvis_piper_rt_")
        os.close(fd)
        path = Path(wav_path)
        t0 = time.perf_counter()
        self._stream_t0 = t0
        try:
            proc = subprocess.Popen(
                [self._bin(), "--model", model, "--output_file", str(path)],
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                proc.stdin.write(text.encode("utf-8"))
                proc.stdin.close()
            except OSError:
                pass
            while proc.poll() is None:
                if self._stream_cancelled():
                    proc.kill()
                    return
                time.sleep(0.02)
            if proc.returncode != 0:
                raise RuntimeError(f"piper exited {proc.returncode}")
            data = path.read_bytes()
            if not data:
                return
            self._last_first_chunk_ms = (time.perf_counter() - t0) * 1000.0
            chunk_size = 8192
            first = True
            for idx in range(0, len(data), chunk_size):
                if self._stream_cancelled():
                    break
                payload = data[idx : idx + chunk_size]
                if first:
                    first = False
                yield SynthesisChunk(
                    data=payload,
                    mime="audio/wav",
                    viseme_hint=0.6,
                )
        finally:
            path.unlink(missing_ok=True)

    def last_time_to_first_audio_ms(self) -> float | None:
        return self._last_first_chunk_ms
