"""Phase 41 — TTS engine benchmark (local, read-only metrics)."""

from __future__ import annotations

import time

from voice.engines.registry import get_engine_chain
from voice.tts import sanitize_for_speech


def run_tts_benchmark(*, phrase: str = "JARVIS voice benchmark online.") -> str:
    safe = sanitize_for_speech(phrase)
    lines = ["TTS benchmark (local):", ""]
    for eng in get_engine_chain():
        lines.append(f"Engine: {eng.name}")
        lines.append(f"  available: {eng.is_available()} ({eng.availability_reason()})")
        caps = eng.capabilities()
        lines.append(
            f"  streaming={caps.streaming} neural={caps.neural} offline={caps.offline}"
        )
        if not eng.is_available():
            lines.append("")
            continue
        t0 = time.perf_counter()
        try:
            if caps.streaming:
                chunks = list(eng.synthesize_stream(safe, voice="en-US-JennyNeural", rate_raw="+0%"))
                ms = (time.perf_counter() - t0) * 1000.0
                lines.append(f"  stream synth: {ms:.0f} ms ({len(chunks)} chunks)")
            else:
                from pathlib import Path
                import tempfile
                import os

                fd, tmp = tempfile.mkstemp(suffix=".out")
                os.close(fd)
                path = Path(tmp)
                try:
                    eng.synthesize_file(
                        safe,
                        voice="en-US-JennyNeural",
                        rate_raw="+0%",
                        out_path=path,
                    )
                finally:
                    path.unlink(missing_ok=True)
                ms = (time.perf_counter() - t0) * 1000.0
                lines.append(f"  synth+play: {ms:.0f} ms")
        except Exception as exc:
            lines.append(f"  error: {exc}")
        lines.append("")
    lines.append("Note: benchmark measures synthesis path only; playback may add latency.")
    return "\n".join(lines)
