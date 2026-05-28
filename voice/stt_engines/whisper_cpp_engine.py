"""whisper.cpp CLI backend (optional local binary)."""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

from config import STT_SAMPLE_RATE, WHISPER_CPP_BINARY, WHISPER_CPP_MODEL
from voice.stt_engines.base import (
    PartialCallback,
    STTEngine,
    SttEngineCapabilities,
    SttHypothesis,
    logprob_to_confidence,
)


class WhisperCppEngine(STTEngine):
    name = "whisper_cpp"

    def is_available(self) -> bool:
        if not WHISPER_CPP_BINARY or not WHISPER_CPP_MODEL:
            return False
        return Path(WHISPER_CPP_BINARY).is_file() and Path(WHISPER_CPP_MODEL).is_file()

    def capabilities(self) -> SttEngineCapabilities:
        return SttEngineCapabilities(streaming=False, offline=True, multilingual=True)

    def transcribe(
        self,
        audio_path: Path,
        *,
        language: str,
        on_partial: PartialCallback | None = None,
    ) -> SttHypothesis:
        del on_partial
        out_json = tempfile.mktemp(suffix=".json")
        cmd = [
            WHISPER_CPP_BINARY,
            "-m",
            WHISPER_CPP_MODEL,
            "-f",
            str(audio_path),
            "-l",
            language,
            "-oj",
            "-of",
            out_json.replace(".json", ""),
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if proc.returncode != 0:
            raise RuntimeError(f"whisper.cpp failed: {proc.stderr[:200]}")
        path = Path(out_json)
        if not path.is_file():
            path = Path(out_json.replace(".json", ".json"))
        text = ""
        avg_lp = None
        if path.is_file():
            data = json.loads(path.read_text(encoding="utf-8"))
            text = (data.get("text") or "").strip()
            segs = data.get("segments") or []
            lps = [s.get("avg_logprob") for s in segs if s.get("avg_logprob") is not None]
            if lps:
                avg_lp = sum(float(x) for x in lps) / len(lps)
            path.unlink(missing_ok=True)
        return SttHypothesis(
            text=text,
            engine=self.name,
            confidence=logprob_to_confidence(avg_lp),
            language=language,
            avg_logprob=avg_lp,
            metadata={"sample_rate": STT_SAMPLE_RATE},
        )
