"""Windows playback routing for subprocess TTS (default / Sonar / persisted target)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from core.logger import setup_logger

logger = setup_logger("jarvis.voice.windows_audio_routing")

_CYCLE_TARGET_INDEX = 0

PLAYBACK_TARGETS: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("default", (), "Windows default playback"),
    ("sonar_gaming", ("sonar", "gaming"), "SteelSeries Sonar — Gaming"),
    ("sonar_chat", ("sonar", "chat"), "SteelSeries Sonar — Chat"),
    ("sonar_media", ("sonar", "media"), "SteelSeries Sonar — Media"),
)


@dataclass(frozen=True)
class ResolvedPlaybackRoute:
    device_index: int | None
    device_label: str
    target_id: str
    windows_default_name: str
    sonar_detected: bool
    env_value: str


def force_windows_default_output() -> bool:
    try:
        import config as cfg

        return bool(
            getattr(cfg, "TTS_FORCE_WINDOWS_DEFAULT_OUTPUT", False)
            or getattr(cfg, "TTS_FORCE_DEFAULT_WINDOWS_DEVICE", False)
        )
    except Exception:
        return False


def detect_steelseries_sonar() -> bool:
    try:
        from voice.audio_devices import list_playback_devices

        for dev in list_playback_devices():
            name = dev.name.lower()
            if "sonar" in name and "steelseries" in name:
                return True
            if "sonar" in name and ("gaming" in name or "chat" in name or "media" in name):
                return True
    except Exception:
        pass
    return False


def find_playback_target_device(target_id: str):
    from voice.audio_devices import PlaybackDeviceInfo, default_playback_device, list_playback_devices

    if target_id == "default":
        return default_playback_device()

    patterns = next((p for tid, p, _ in PLAYBACK_TARGETS if tid == target_id), ())
    if not patterns:
        return None

    best: PlaybackDeviceInfo | None = None
    for dev in list_playback_devices():
        name = dev.name.lower()
        if all(part in name for part in patterns):
            if best is None or dev.is_default:
                best = dev
    return best


def get_windows_default_playback_name() -> str:
    from voice.audio_devices import default_playback_device

    default = default_playback_device()
    return default.name if default else "n/a"


def get_sounddevice_default_label() -> str:
    try:
        import sounddevice as sd

        idx = int(sd.default.device[1])
        dev = sd.query_devices(idx)
        return str(dev.get("name", f"device-{idx}"))
    except Exception as exc:
        return f"unavailable ({exc})"


def get_playback_target() -> str:
    from voice.audio_devices import get_persisted_playback_target

    return get_persisted_playback_target()


def resolve_subprocess_playback_route() -> ResolvedPlaybackRoute:
    from voice.audio_devices import (
        default_playback_device,
        get_persisted_playback_target,
        get_session_output_device,
        get_session_output_label,
    )

    windows_default = get_windows_default_playback_name()
    sonar = detect_steelseries_sonar()
    session_idx = get_session_output_device()
    session_label = get_session_output_label()
    target_id = get_persisted_playback_target()

    device_index: int | None = None
    device_label = ""

    if session_idx is not None:
        device_index = session_idx
        device_label = session_label or f"device-{session_idx}"
        target_id = target_id or "session"
    elif target_id and target_id != "default":
        dev = find_playback_target_device(target_id)
        if dev is not None:
            device_index = dev.index
            device_label = dev.name
    elif force_windows_default_output():
        default = default_playback_device()
        if default is not None:
            device_index = default.index
            device_label = default.name
            target_id = "default"

    if device_index is None:
        env_value = "default"
        device_label = device_label or "sapi_default"
    else:
        env_value = str(device_index)

    return ResolvedPlaybackRoute(
        device_index=device_index,
        device_label=device_label,
        target_id=target_id or "default",
        windows_default_name=windows_default,
        sonar_detected=sonar,
        env_value=env_value,
    )


def log_tts_route_before_subprocess(*, label: str = "TTS_SUBPROCESS") -> ResolvedPlaybackRoute:
    route = resolve_subprocess_playback_route()
    print(
        f"[TTS_ROUTE] default_output={route.windows_default_name} "
        f"target={route.target_id} device_index={route.device_index or 'default'} "
        f"device={route.device_label} sonar={route.sonar_detected}",
        flush=True,
    )
    logger.info(
        "%s route default=%s target=%s idx=%s sonar=%s",
        label,
        route.windows_default_name,
        route.target_id,
        route.device_index,
        route.sonar_detected,
    )
    return route


def subprocess_env_with_audio_route(
    base: dict[str, str] | None = None,
) -> dict[str, str]:
    route = resolve_subprocess_playback_route()
    env = dict(os.environ)
    if base:
        env.update(base)
    env["JARVIS_AUDIO_OUTPUT_DEVICE"] = route.env_value
    env["JARVIS_AUDIO_OUTPUT_LABEL"] = route.device_label[:120]
    env["JARVIS_PLAYBACK_TARGET"] = route.target_id
    return env


def build_routed_pyttsx3_subprocess_code(text: str) -> str:
    """Child: pyttsx3 WAV + sounddevice when JARVIS_AUDIO_OUTPUT_DEVICE is set."""
    escaped = repr(text)
    return (
        "import os,tempfile,wave\n"
        f"text={escaped}\n"
        'dev=os.environ.get("JARVIS_AUDIO_OUTPUT_DEVICE","")\n'
        "if dev and dev!='default':\n"
        " import pyttsx3\n"
        " import numpy as np\n"
        " import sounddevice as sd\n"
        " idx=int(dev)\n"
        " fd,path=tempfile.mkstemp(suffix='.wav')\n"
        " os.close(fd)\n"
        " e=pyttsx3.init()\n"
        " e.save_to_file(text,path)\n"
        " e.runAndWait()\n"
        " with wave.open(path,'rb') as w:\n"
        "  ch=w.getnchannels();sw=w.getsampwidth();fr=w.getframerate()\n"
        "  raw=w.readframes(w.getnframes())\n"
        " os.remove(path)\n"
        ' dtype={1:"int8",2:"int16",4:"int32"}.get(sw,"int16")\n'
        " a=np.frombuffer(raw,dtype=dtype)\n"
        " if ch>1:\n"
        "  a=a.reshape(-1,ch)[:,0]\n"
        " peak=float(np.iinfo(dtype).max)\n"
        " s=a.astype('float32')/max(1.0,peak)\n"
        " sd.play(s,fr,device=idx)\n"
        " sd.wait()\n"
        "else:\n"
        " import pyttsx3\n"
        " e=pyttsx3.init()\n"
        " e.say(text)\n"
        " e.runAndWait()\n"
    )


def sonar_channel_recommendations() -> list[str]:
    if not detect_steelseries_sonar():
        return []
    lines = ["SteelSeries Sonar detected. Recommended playback targets:"]
    for target_id, _patterns, label in PLAYBACK_TARGETS:
        if not target_id.startswith("sonar_"):
            continue
        dev = find_playback_target_device(target_id)
        if dev is not None:
            lines.append(f"  - {label}: [{dev.index}] {dev.name}")
        else:
            lines.append(f"  - {label}: (not found — run cycle windows playback target)")
    return lines


def format_windows_audio_routing_report() -> str:
    from voice.audio_devices import (
        get_persisted_playback_target,
        get_session_output_device,
        get_session_output_label,
        is_audible_route_verified,
        list_pyttsx3_voices,
    )
    from voice.tts_backend import get_active_tts_backend
    from voice.tts_subprocess import SHELL_SUBPROCESS_BACKEND

    route = resolve_subprocess_playback_route()
    lines = [
        "Windows audio routing",
        f"  Windows default playback: {route.windows_default_name}",
        f"  sounddevice default: {get_sounddevice_default_label()}",
        f"  Subprocess backend: {SHELL_SUBPROCESS_BACKEND}",
        f"  Active TTS backend: {get_active_tts_backend()}",
        f"  Sonar detected: {'yes' if route.sonar_detected else 'no'}",
        f"  Persisted playback target: {get_persisted_playback_target()}",
        f"  Audible route verified: {'yes' if is_audible_route_verified() else 'no'}",
        f"  Session output device: {get_session_output_label() or 'none'} "
        f"(index {get_session_output_device() if get_session_output_device() is not None else 'n/a'})",
        f"  Resolved subprocess route: {route.device_label} "
        f"(index {route.device_index if route.device_index is not None else 'default'})",
        f"  TTS_FORCE_WINDOWS_DEFAULT_OUTPUT: {'yes' if force_windows_default_output() else 'no'}",
        "  pyttsx3 voices (SAPI):",
    ]
    for name in list_pyttsx3_voices()[:6]:
        lines.append(f"    - {name}")
    lines.extend(sonar_channel_recommendations())
    return "\n".join(lines)


def persist_audible_playback_route(
    *,
    target_id: str,
    device_index: int | None,
    device_label: str,
) -> None:
    from voice.audio_devices import (
        set_audible_route_verified,
        set_persisted_playback_target,
        set_session_output_device,
    )

    set_persisted_playback_target(target_id)
    set_audible_route_verified(True)
    if device_index is not None:
        set_session_output_device(device_index, label=device_label)


def cycle_windows_playback_target() -> tuple[bool, str]:
    """Cycle Sonar/default targets, speak test phrase, modal yes/no to persist."""
    global _CYCLE_TARGET_INDEX
    from voice.tts_subprocess import speak_subprocess_pyttsx3

    if not PLAYBACK_TARGETS:
        return False, "No playback targets configured."

    target_id, _patterns, label = PLAYBACK_TARGETS[_CYCLE_TARGET_INDEX % len(PLAYBACK_TARGETS)]
    _CYCLE_TARGET_INDEX += 1

    dev = find_playback_target_device(target_id)
    device_index = dev.index if dev else None
    device_label = dev.name if dev else route_label_for_target(target_id)

    if device_index is not None:
        from voice.audio_devices import set_session_output_device

        set_session_output_device(device_index, label=device_label)

    phrase = f"JARVIS routing test on {label}."
    log_tts_route_before_subprocess(label="TTS_ROUTE_CYCLE")
    result = speak_subprocess_pyttsx3(phrase)
    if not result.ok:
        err = (result.stderr or "").strip() or f"exit {result.exit_code}"
        return False, f"Routing test failed on {label}: {err}"

    from voice.audio_verified import ask_user_audible_confirmation

    heard = ask_user_audible_confirmation(
        f"Did you hear the test on {label}? say yes or no"
    )
    if heard is True:
        persist_audible_playback_route(
            target_id=target_id,
            device_index=device_index,
            device_label=device_label,
        )
        return True, (
            f"Audible route saved: {label}\n"
            f"  target={target_id}\n"
            f"  device=[{device_index}] {device_label}\n"
            f"{format_windows_audio_routing_report()}"
        )
    if heard is False:
        return True, (
            f"No route saved for {label}. Say 'cycle windows playback target' to try the next."
        )
    return True, f"Routing test on {label} cancelled or timed out."


def route_label_for_target(target_id: str) -> str:
    for tid, _p, label in PLAYBACK_TARGETS:
        if tid == target_id:
            return label
    return target_id
