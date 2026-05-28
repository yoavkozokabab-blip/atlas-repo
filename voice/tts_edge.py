"""Microsoft Edge neural TTS (edge-tts) — natural voice, local/free."""

from __future__ import annotations

import asyncio
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from core.logger import setup_logger
from voice.tts_config import resolve_edge_tts_rate

logger = setup_logger("jarvis.voice.tts.edge")


class EdgeTTSError(Exception):
    """edge-tts synthesis or playback failed."""


def _format_subprocess_failure(label: str, exc: Exception) -> str:
    parts = [f"{label}: {exc}"]
    if isinstance(exc, subprocess.CalledProcessError):
        stderr = (exc.stderr or "").strip() if exc.stderr is not None else ""
        stdout = (exc.stdout or "").strip() if exc.stdout is not None else ""
        if stderr:
            parts.append(f"stderr={stderr}")
        if stdout:
            parts.append(f"stdout={stdout}")
    return " | ".join(parts)


def _play_mp3_playsound(path: Path) -> None:
    from playsound import playsound

    playsound(str(path), block=True)


def _play_mp3_powershell_wmp(path: Path) -> None:
    uri = path.resolve().as_uri().replace("'", "''")
    script = (
        "$w = New-Object -ComObject WMPlayer.OCX; "
        f"$w.URL = '{uri}'; "
        "$w.controls.play(); "
        "while ($w.playState -eq 3) { Start-Sleep -Milliseconds 80 }; "
        "$w.close()"
    )
    result = subprocess.run(
        ["powershell", "-NoProfile", "-Command", script],
        check=False,
        timeout=120,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        msg = f"Windows MP3 playback (PowerShell/WMP) failed rc={result.returncode}"
        if detail:
            msg = f"{msg} stderr/stdout={detail}"
        logger.warning(msg)
        raise EdgeTTSError(msg)


def _play_mp3_mci(path: Path) -> None:
    """Windows MCI fallback via ctypes (stdlib, no extra package)."""
    import ctypes

    winmm = ctypes.windll.winmm
    alias = "jarvis_tts"
    path_str = str(path.resolve()).replace("\\", "\\\\").replace('"', '\\"')
    open_cmd = f'open "{path_str}" type mpegvideo alias {alias}'
    buf = ctypes.create_unicode_buffer(512)

    def _mci(cmd: str) -> None:
        err = winmm.mciSendStringW(cmd, buf, len(buf), None)
        if err:
            raise EdgeTTSError(f"Windows MCI playback failed ({cmd}): error {err}")

    try:
        _mci(open_cmd)
        _mci(f"play {alias} wait")
    finally:
        try:
            winmm.mciSendStringW(f"close {alias}", buf, len(buf), None)
        except Exception:
            pass


def _play_mp3(path: Path) -> None:
    """Blocking playback of a short MP3 file."""
    from voice.playback_guard import should_play_audio

    if not should_play_audio():
        return
    failures: list[str] = []

    try:
        _play_mp3_playsound(path)
        return
    except Exception as exc:
        failures.append(_format_subprocess_failure("playsound", exc))
        logger.debug("playsound unavailable: %s", exc)

    if sys.platform == "win32":
        try:
            _play_mp3_powershell_wmp(path)
            return
        except EdgeTTSError as exc:
            failures.append(str(exc))
        except Exception as exc:
            failures.append(_format_subprocess_failure("powershell/WMP", exc))
            logger.warning("PowerShell/WMP MP3 playback failed: %s", exc)

        try:
            _play_mp3_mci(path)
            return
        except Exception as exc:
            failures.append(_format_subprocess_failure("MCI", exc))
            logger.warning("MCI MP3 playback failed: %s", exc)

    raise EdgeTTSError(
        "MP3 playback failed — " + "; ".join(failures) if failures else "no backend"
    )


async def _synthesize_mp3(text: str, voice: str, rate: str, out_path: Path) -> None:
    import edge_tts

    communicate = edge_tts.Communicate(text, voice=voice, rate=rate)
    await communicate.save(str(out_path))


def speak_edge_tts(
    text: str,
    *,
    voice: str,
    rate_raw: str,
) -> None:
    """
    Synthesize with edge-tts and play audio (blocking).
    Raises EdgeTTSError on failure.
    """
    if not voice:
        raise EdgeTTSError("TTS_VOICE is not set for edge-tts")
    rate = resolve_edge_tts_rate(rate_raw)
    fd, name = tempfile.mkstemp(suffix=".mp3", prefix="jarvis_tts_")
    os.close(fd)
    path = Path(name)
    try:
        asyncio.run(_synthesize_mp3(text, voice, rate, path))
        if not path.is_file() or path.stat().st_size < 32:
            raise EdgeTTSError("edge-tts produced empty audio")
        _play_mp3(path)
    except EdgeTTSError:
        raise
    except Exception as exc:
        raise EdgeTTSError(f"edge-tts failed: {exc}") from exc
    finally:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
