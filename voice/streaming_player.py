"""Streaming / interruptible playback (Phase 41/57/58)."""

from __future__ import annotations

import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

from core.logger import setup_logger
from voice.streaming.mp3_frame import find_first_decodable_frame

logger = setup_logger("jarvis.voice.streaming")

_stop_event = threading.Event()
_pause_event = threading.Event()
_speaking = threading.Event()
_playback_lock = threading.Lock()
_sd_stream = None


def request_stop_speaking() -> None:
    _stop_event.set()
    _pause_playback_device()


def pause_playback_immediately() -> None:
    _pause_event.set()
    _pause_playback_device()


def clear_stop_request() -> None:
    _stop_event.clear()
    _pause_event.clear()


def is_stop_requested() -> bool:
    return _stop_event.is_set() or _pause_event.is_set()


def is_playback_paused() -> bool:
    return _pause_event.is_set()


def is_speaking() -> bool:
    return _speaking.is_set()


def _pause_playback_device() -> None:
    global _sd_stream
    try:
        import sounddevice as sd

        sd.stop()
    except Exception:
        pass
    _sd_stream = None


def _adaptive_buffer_target(*, inter_arrival_ms: list[float]) -> int:
    if not inter_arrival_ms:
        return 2048
    try:
        import config as cfg

        if not getattr(cfg, "REALTIME_STREAM_ADAPTIVE_BUFFER", True):
            return 2048
    except Exception:
        pass
    avg = sum(inter_arrival_ms) / len(inter_arrival_ms)
    jitter = max(inter_arrival_ms) - min(inter_arrival_ms) if len(inter_arrival_ms) > 1 else avg
    # Higher jitter -> slightly larger buffer, capped for sub-800ms target
    target = int(1800 + jitter * 8)
    return max(1400, min(target, 6000))


def play_pcm_chunks(chunks: list[bytes], *, sample_rate: int = 24000) -> bool:
    from voice.playback_guard import should_play_audio

    if not should_play_audio():
        return not is_stop_requested()
    try:
        import numpy as np
        import sounddevice as sd
    except ImportError as exc:
        raise RuntimeError(f"sounddevice/numpy required for PCM playback: {exc}") from exc

    payload = b"".join(chunks)
    if not payload:
        return True
    samples = np.frombuffer(payload, dtype=np.int16).astype(np.float32) / 32768.0
    _speaking.set()
    try:
        if is_stop_requested():
            return False
        sd.play(samples, sample_rate)
        total = len(samples) / float(sample_rate)
        elapsed = 0.0
        while elapsed < total:
            if is_stop_requested():
                sd.stop()
                return False
            time.sleep(0.015)
            elapsed += 0.015
        sd.wait()
        return True
    finally:
        _speaking.clear()


def play_mp3_file(path: Path, *, frame_ms: int = 50) -> bool:
    from voice.playback_guard import should_play_audio
    from voice.tts_playback_trace import (
        log_tts_debug,
        record_playback_failure,
        record_playback_finish,
        record_playback_start,
    )

    if not should_play_audio():
        return not is_stop_requested()
    from voice.tts_edge import _play_mp3

    record_playback_start(engine="edge_mp3", device="default", path="mp3_file")
    _speaking.set()
    t0 = time.perf_counter()
    try:
        if is_stop_requested():
            return False
        log_tts_debug("mp3_playback_start", path=str(path))
        _play_mp3(path)
        log_tts_debug("mp3_playback_finish")
        record_playback_finish(
            engine="edge_mp3",
            ok=True,
            elapsed_ms=(time.perf_counter() - t0) * 1000.0,
        )
        return not is_stop_requested()
    except Exception as exc:
        record_playback_failure(exc, engine="edge_mp3", path="mp3_file")
        raise
    finally:
        _speaking.clear()


def play_wav_file(path: Path) -> bool:
    from voice.playback_guard import should_play_audio

    if not should_play_audio():
        return not is_stop_requested()
    try:
        import sounddevice as sd
        import soundfile as sf
    except ImportError as exc:
        raise RuntimeError(f"sounddevice/soundfile required: {exc}") from exc
    data, rate = sf.read(str(path), dtype="float32")
    _speaking.set()
    try:
        if is_stop_requested():
            return False
        sd.play(data, rate)
        total = len(data) / float(rate)
        elapsed = 0.0
        while elapsed < total:
            if is_stop_requested():
                sd.stop()
                return False
            time.sleep(0.015)
            elapsed += 0.015
        sd.wait()
        return True
    finally:
        _speaking.clear()


def _flush_mp3_buffer(
    buffer: bytearray,
    *,
    on_first_playback: Callable[[], None] | None,
    on_first_decodable: Callable[[], None] | None,
    first_playback_sent: list[bool],
    first_decodable_sent: list[bool],
) -> None:
    if not buffer:
        return
    playable = bytes(buffer)
    found = find_first_decodable_frame(playable)
    if found and not first_decodable_sent[0]:
        if on_first_decodable:
            on_first_decodable()
        first_decodable_sent[0] = True
        offset, frame_len = found
        playable = playable[offset : offset + frame_len]
    if not first_playback_sent[0] and on_first_playback:
        on_first_playback()
        first_playback_sent[0] = True
    fd, p = tempfile.mkstemp(suffix=".mp3", prefix="jarvis_chunk_")
    import os

    os.close(fd)
    path = Path(p)
    try:
        path.write_bytes(playable)
        buffer.clear()
        if is_stop_requested():
            return
        from voice.tts_edge import _play_mp3

        with _playback_lock:
            if is_stop_requested():
                return
            _play_mp3(path)
    finally:
        path.unlink(missing_ok=True)


def stream_mp3_chunks_incremental(
    chunk_iter,
    *,
    on_viseme=None,
    frame_ms: int = 50,
    on_first_playback: Callable[[], None] | None = None,
    on_first_byte: Callable[[], None] | None = None,
    on_first_decodable: Callable[[], None] | None = None,
    on_adaptive_target: Callable[[int], None] | None = None,
    min_play_bytes: int | None = None,
    first_play_max_wait_ms: float | None = None,
) -> bool:
    """Play MP3 chunks — start at first decodable frame with adaptive buffering."""
    from voice.playback_guard import should_play_audio

    del min_play_bytes, first_play_max_wait_ms, frame_ms
    test_no_play = not should_play_audio()
    buffer = bytearray()
    first_playback_sent = [False]
    first_decodable_sent = [False]
    first_byte_sent = [False]
    inter_arrivals: list[float] = []
    last_arrival = time.perf_counter()
    _speaking.set()
    try:
        for chunk in chunk_iter:
            if is_stop_requested():
                return False
            mime = getattr(chunk, "mime", "audio/mpeg") or "audio/mpeg"
            if mime.startswith("audio/pcm") and chunk.data:
                if test_no_play:
                    if on_first_playback:
                        on_first_playback()
                    continue
                return play_pcm_chunks([bytes(chunk.data)])
            if chunk.data:
                now = time.perf_counter()
                inter_arrivals.append((now - last_arrival) * 1000.0)
                last_arrival = now
                if not first_byte_sent[0]:
                    first_byte_sent[0] = True
                    if on_first_byte:
                        on_first_byte()
                buffer.extend(chunk.data)
            if on_viseme and getattr(chunk, "viseme_hint", None):
                try:
                    on_viseme(chunk.viseme_hint)
                except Exception:
                    pass
            target = _adaptive_buffer_target(inter_arrival_ms=inter_arrivals[-6:])
            if on_adaptive_target:
                on_adaptive_target(target)
            has_frame = find_first_decodable_frame(bytes(buffer)) is not None
            if not has_frame:
                continue
            ready = not first_playback_sent[0] or len(buffer) >= target
            if not ready:
                continue
                if test_no_play:
                    buffer.clear()
                    if on_first_decodable and not first_decodable_sent[0]:
                        on_first_decodable()
                    if on_first_playback and not first_playback_sent[0]:
                        on_first_playback()
                    continue
                _flush_mp3_buffer(
                    buffer,
                    on_first_playback=on_first_playback,
                    on_first_decodable=on_first_decodable,
                    first_playback_sent=first_playback_sent,
                    first_decodable_sent=first_decodable_sent,
                )
                if is_stop_requested():
                    return False
        if buffer and not is_stop_requested():
            if test_no_play:
                if on_first_playback:
                    on_first_playback()
                return True
            _flush_mp3_buffer(
                buffer,
                on_first_playback=on_first_playback,
                on_first_decodable=on_first_decodable,
                first_playback_sent=first_playback_sent,
                first_decodable_sent=first_decodable_sent,
            )
        return not is_stop_requested()
    finally:
        _speaking.clear()


def play_mp3_chunks(chunks: list[bytes], *, frame_ms: int = 50) -> bool:
    def _iter():
        for data in chunks:
            yield type("Chunk", (), {"data": data, "mime": "audio/mpeg", "viseme_hint": 0.6})()

    return stream_mp3_chunks_incremental(_iter(), frame_ms=frame_ms)


def reset_streaming_player() -> None:
    request_stop_speaking()
    _speaking.clear()
    clear_stop_request()
