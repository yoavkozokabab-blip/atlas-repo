"""Playback device enumeration (Windows/sounddevice + pyttsx3 voices)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from config import AUDIO_ROUTING_PATH
from core.logger import setup_logger

logger = setup_logger("jarvis.voice.audio_devices")

_session_output_device: int | None = None
_session_output_label: str = ""
_persisted_playback_target: str = "default"
_audible_route_verified: bool = False


def _persist_routing() -> None:
    path = Path(AUDIO_ROUTING_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "output_device_index": _session_output_device,
        "output_device_label": _session_output_label,
        "playback_target": _persisted_playback_target,
        "audible_route_verified": _audible_route_verified,
    }
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.debug("audio routing persist failed: %s", exc)


def load_persisted_routing() -> None:
    global _session_output_device, _session_output_label
    global _persisted_playback_target, _audible_route_verified
    path = Path(AUDIO_ROUTING_PATH)
    if not path.is_file():
        return
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return
        idx = raw.get("output_device_index")
        _session_output_device = int(idx) if idx is not None and str(idx) != "" else None
        _session_output_label = str(raw.get("output_device_label", ""))[:120]
        _persisted_playback_target = str(raw.get("playback_target", "default"))[:40] or "default"
        _audible_route_verified = bool(raw.get("audible_route_verified", False))
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        logger.debug("audio routing load failed: %s", exc)


def get_persisted_playback_target() -> str:
    return _persisted_playback_target or "default"


def set_persisted_playback_target(target: str) -> None:
    global _persisted_playback_target
    _persisted_playback_target = (target or "default")[:40]
    _persist_routing()


def is_audible_route_verified() -> bool:
    return _audible_route_verified


def set_audible_route_verified(verified: bool = True) -> None:
    global _audible_route_verified
    _audible_route_verified = bool(verified)
    _persist_routing()


load_persisted_routing()


@dataclass(frozen=True)
class PlaybackDeviceInfo:
    index: int
    name: str
    hostapi: str
    is_default: bool


def get_session_output_device() -> int | None:
    return _session_output_device


def get_session_output_label() -> str:
    return _session_output_label


def set_session_output_device(index: int | None, *, label: str = "") -> None:
    global _session_output_device, _session_output_label
    _session_output_device = index
    _session_output_label = (label or "")[:120]
    _persist_routing()


def list_playback_devices() -> list[PlaybackDeviceInfo]:
    try:
        import sounddevice as sd
    except ImportError:
        return []
    default_out = -1
    try:
        default_out = int(sd.default.device[1])
    except (TypeError, ValueError, IndexError):
        pass
    out: list[PlaybackDeviceInfo] = []
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception as exc:
        logger.debug("query_devices failed: %s", exc)
        return out
    for idx, dev in enumerate(devices):
        if int(dev.get("max_output_channels", 0) or 0) < 1:
            continue
        api_idx = int(dev.get("hostapi", 0))
        host = hostapis[api_idx]["name"] if 0 <= api_idx < len(hostapis) else "unknown"
        out.append(
            PlaybackDeviceInfo(
                index=idx,
                name=str(dev.get("name", f"device-{idx}")),
                hostapi=str(host),
                is_default=idx == default_out,
            )
        )
    return out


def default_playback_device() -> PlaybackDeviceInfo | None:
    for dev in list_playback_devices():
        if dev.is_default:
            return dev
    devices = list_playback_devices()
    return devices[0] if devices else None


def list_pyttsx3_voices() -> list[str]:
    try:
        import pyttsx3
    except ImportError:
        return []
    try:
        engine = pyttsx3.init()
        voices = engine.getProperty("voices") or []
        names = [getattr(v, "name", str(v)) or "voice" for v in voices]
        try:
            engine.stop()
        except Exception:
            pass
        return names[:20]
    except Exception as exc:
        return [f"unavailable ({exc})"]


def format_audio_devices_report() -> str:
    from config import TTS_ENGINE
    from voice.audio_status import get_audio_status

    audio = get_audio_status()
    lines = ["Audio devices", "  Windows playback (sounddevice):"]
    devices = list_playback_devices()
    if not devices:
        lines.append("    (none — install sounddevice)")
    else:
        for dev in devices:
            mark = " [DEFAULT]" if dev.is_default else ""
            sel = " [SELECTED]" if _session_output_device == dev.index else ""
            lines.append(f"    [{dev.index}] {dev.name} ({dev.hostapi}){mark}{sel}")
    default = default_playback_device()
    lines.append(
        f"  Default output: {default.name if default else 'n/a'} (index {default.index if default else 'n/a'})"
    )
    lines.append("  pyttsx3 voices (SAPI — uses Windows default playback endpoint):")
    for name in list_pyttsx3_voices()[:8]:
        lines.append(f"    - {name}")
    lines.append(f"  Active playback backend: {audio.playback_backend}")
    if _session_output_label:
        lines.append(f"  Session routed device: {_session_output_label}")
    lines.append(f"  Config TTS_ENGINE: {TTS_ENGINE}")
    return "\n".join(lines)


def log_startup_audio_devices() -> None:
    default = default_playback_device()
    voices = list_pyttsx3_voices()
    try:
        import pyttsx3

        driver = "pyttsx3"
        try:
            engine = pyttsx3.init()
            driver = str(getattr(engine, "_driver", driver))
            engine.stop()
        except Exception:
            pass
    except ImportError:
        driver = "unavailable"
    logger.info(
        "Audio startup: default_output=%s pyttsx3_driver=%s voices=%s",
        default.name if default else "n/a",
        driver,
        voices[:3],
    )
    print(
        f"[INFO] Audio: default playback={default.name if default else 'n/a'}; "
        f"pyttsx3 driver={driver}",
        flush=True,
    )
