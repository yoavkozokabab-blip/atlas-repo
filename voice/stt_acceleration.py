"""STT device/backend auto-detection (local only, no cloud)."""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger("jarvis.voice.stt.acceleration")

# Set by tests to inject probe results.
_probe_override: AccelerationProbe | None = None
_runtime: SttRuntimeChoice | None = None
_gpu_warning_printed = False


@dataclass(frozen=True)
class AccelerationProbe:
    cuda_device_count: int
    cuda_reason: str
    directml_available: bool
    directml_reason: str
    openvino_available: bool
    openvino_reason: str
    onnx_providers: tuple[str, ...]

    def summary_lines(self) -> list[str]:
        lines = [
            f"  CUDA devices: {self.cuda_device_count} ({self.cuda_reason})",
            f"  DirectML available: {'yes' if self.directml_available else 'no'}",
            f"  DirectML: {self.directml_reason}",
            f"  OpenVINO: {'yes' if self.openvino_available else 'no'} ({self.openvino_reason})",
            f"  ONNX providers: {', '.join(self.onnx_providers) or '(none)'}",
        ]
        return lines


@dataclass(frozen=True)
class SttRuntimeChoice:
    backend: str
    whisper_device: str
    compute_type: str
    acceleration: str
    onnx_provider: str
    reason: str
    fallback_reason: str | None
    gpu_warning: str | None
    device_request: str

    @property
    def label(self) -> str:
        if self.backend == "onnx_directml":
            return f"{self.backend}/{self.onnx_provider} ({self.compute_type})"
        return f"{self.backend}/{self.whisper_device} ({self.compute_type}) [{self.acceleration}]"


def probe_acceleration() -> AccelerationProbe:
    if _probe_override is not None:
        return _probe_override

    onnx_providers: list[str] = []
    directml = False
    directml_reason = "onnxruntime not available"
    try:
        import onnxruntime as ort

        onnx_providers = list(ort.get_available_providers())
        directml = "DmlExecutionProvider" in onnx_providers
        directml_reason = (
            "DmlExecutionProvider listed"
            if directml
            else "DmlExecutionProvider not in onnxruntime (try: pip install onnxruntime-directml)"
        )
    except Exception as exc:
        directml_reason = str(exc)

    if not directml:
        try:
            import onnxruntime_directml  # noqa: F401

            import onnxruntime as ort

            onnx_providers = list(ort.get_available_providers())
            directml = "DmlExecutionProvider" in onnx_providers
            if directml:
                directml_reason = "onnxruntime-directml package loaded"
        except ImportError:
            pass

    cuda_count = 0
    cuda_reason = "ctranslate2 unavailable"
    try:
        import ctranslate2 as ct

        cuda_count = int(ct.get_cuda_device_count())
        cuda_reason = "ctranslate2 CUDA device count"
    except Exception as exc:
        cuda_reason = str(exc)

    openvino = False
    openvino_reason = "openvino not installed"
    try:
        import openvino  # noqa: F401

        openvino = True
        openvino_reason = "OpenVINO runtime import OK"
    except ImportError:
        pass
    except Exception as exc:
        openvino_reason = str(exc)

    return AccelerationProbe(
        cuda_device_count=cuda_count,
        cuda_reason=cuda_reason,
        directml_available=directml,
        directml_reason=directml_reason,
        openvino_available=openvino,
        openvino_reason=openvino_reason,
        onnx_providers=tuple(onnx_providers),
    )


def get_onnx_providers(*, prefer_directml: bool) -> list[str]:
    """ORT provider chain for onnx-asr (DirectML first when requested and available)."""
    probe = probe_acceleration()
    if prefer_directml and probe.directml_available:
        return ["DmlExecutionProvider", "CPUExecutionProvider"]
    return ["CPUExecutionProvider"]


def resolve_stt_runtime(
    *,
    device_request: str,
    acceleration_auto: bool,
    fast_profile: bool,
    compute_type_override: str,
    prefer_directml: bool,
) -> SttRuntimeChoice:
    probe = probe_acceleration()
    req = (device_request or "auto").strip().lower()
    auto = acceleration_auto or req in {"", "auto"}

    if req in {"cuda", "gpu"} and not auto:
        if probe.cuda_device_count > 0:
            compute = compute_type_override or "float16"
            return SttRuntimeChoice(
                backend="faster_whisper",
                whisper_device="cuda",
                compute_type=compute,
                acceleration="cuda",
                onnx_provider="CUDAExecutionProvider",
                reason=f"STT_DEVICE={req} (explicit)",
                fallback_reason=None,
                gpu_warning=None,
                device_request=req,
            )
        compute = compute_type_override or "int8"
        return SttRuntimeChoice(
            backend="faster_whisper",
            whisper_device="cpu",
            compute_type=compute,
            acceleration="cpu",
            onnx_provider="CPUExecutionProvider",
            reason=f"STT_DEVICE={req} requested but no CUDA GPU",
            fallback_reason=probe.cuda_reason,
            gpu_warning="CUDA unavailable; using CPU int8 for STT.",
            device_request=req,
        )

    if req == "cpu" and not auto:
        compute = compute_type_override or "int8"
        return SttRuntimeChoice(
            backend="faster_whisper",
            whisper_device="cpu",
            compute_type=compute,
            acceleration="cpu",
            onnx_provider="CPUExecutionProvider",
            reason="STT_DEVICE=cpu (explicit)",
            fallback_reason=None,
            gpu_warning=None,
            device_request=req,
        )

    if probe.cuda_device_count > 0:
        compute = compute_type_override or "float16"
        return SttRuntimeChoice(
            backend="faster_whisper",
            whisper_device="cuda",
            compute_type=compute,
            acceleration="cuda",
            onnx_provider="CUDAExecutionProvider",
            reason=f"{probe.cuda_reason}: {probe.cuda_device_count} device(s)",
            fallback_reason=None,
            gpu_warning=None,
            device_request=req if req else "auto",
        )

    if prefer_directml and probe.directml_available:
        compute = compute_type_override or "fp32"
        return SttRuntimeChoice(
            backend="onnx_directml",
            whisper_device="dml",
            compute_type=compute,
            acceleration="directml",
            onnx_provider="DmlExecutionProvider",
            reason="STT_PREFER_DIRECTML=true and DmlExecutionProvider available",
            fallback_reason=None,
            gpu_warning=None,
            device_request=req if req else "auto",
        )

    fallback_reason: str | None = None
    gpu_warning: str | None = None
    if prefer_directml and not probe.directml_available:
        fallback_reason = (
            f"STT_PREFER_DIRECTML=true but DirectML unavailable: {probe.directml_reason}"
        )
        gpu_warning = "GPU STT acceleration unavailable; using CPU fast profile."

    compute = compute_type_override or "int8"
    reason = "No CUDA GPU; using faster-whisper CPU"
    if prefer_directml:
        reason = "DirectML preferred but unavailable; faster-whisper CPU"

    return SttRuntimeChoice(
        backend="faster_whisper",
        whisper_device="cpu",
        compute_type=compute,
        acceleration="cpu",
        onnx_provider="CPUExecutionProvider",
        reason=reason,
        fallback_reason=fallback_reason,
        gpu_warning=gpu_warning,
        device_request=req if req else "auto",
    )


def configure_stt_runtime(
    *,
    device_request: str,
    acceleration_auto: bool,
    fast_profile: bool,
    compute_type_override: str,
    prefer_directml: bool,
) -> SttRuntimeChoice:
    global _runtime
    _runtime = resolve_stt_runtime(
        device_request=device_request,
        acceleration_auto=acceleration_auto,
        fast_profile=fast_profile,
        compute_type_override=compute_type_override,
        prefer_directml=prefer_directml,
    )
    return _runtime


def get_stt_runtime() -> SttRuntimeChoice:
    if _runtime is None:
        import config

        return configure_stt_runtime(
            device_request=getattr(config, "STT_DEVICE_REQUEST", "auto"),
            acceleration_auto=getattr(config, "STT_ACCELERATION_AUTO", True),
            fast_profile=getattr(config, "STT_FAST_PROFILE", False)
            or getattr(config, "VOICE_PROFILE", "") == "fast",
            compute_type_override=getattr(config, "STT_COMPUTE_TYPE", ""),
            prefer_directml=getattr(config, "STT_PREFER_DIRECTML", False),
        )
    return _runtime


def force_cpu_fallback(*, reason: str) -> SttRuntimeChoice:
    return force_faster_whisper_fallback(reason=reason)


def force_faster_whisper_fallback(*, reason: str) -> SttRuntimeChoice:
    global _runtime, _gpu_warning_printed
    prev = _runtime
    _runtime = SttRuntimeChoice(
        backend="faster_whisper",
        whisper_device="cpu",
        compute_type="int8",
        acceleration="cpu",
        onnx_provider="CPUExecutionProvider",
        reason="CPU fallback after load failure",
        fallback_reason=reason,
        gpu_warning="GPU STT acceleration unavailable; using CPU fast profile.",
        device_request=prev.device_request if prev else "auto",
    )
    _gpu_warning_printed = False
    return _runtime


def format_acceleration_probe(probe: AccelerationProbe | None = None) -> str:
    p = probe or probe_acceleration()
    runtime = get_stt_runtime()
    lines = [
        "STT acceleration probe",
        *p.summary_lines(),
        f"  Chosen backend: {runtime.backend}",
        f"  Chosen provider: {runtime.onnx_provider}",
        f"  Chosen device: {runtime.whisper_device}",
    ]
    return "\n".join(lines)


def print_stt_acceleration_startup() -> None:
    global _gpu_warning_printed
    runtime = get_stt_runtime()
    probe = probe_acceleration()
    try:
        from voice.stt_directml import directml_diagnostics

        dml = directml_diagnostics()
        onnx_asr_ok = dml.get("onnx_asr_installed", False)
    except Exception:
        onnx_asr_ok = False

    print("--- STT backend (auto) ---", flush=True)
    print(f"  Backend: {runtime.backend}", flush=True)
    print(f"  Device: {runtime.whisper_device}", flush=True)
    print(f"  Compute: {runtime.compute_type}", flush=True)
    print(f"  Acceleration: {runtime.acceleration}", flush=True)
    print(f"  ONNX provider (chosen): {runtime.onnx_provider}", flush=True)
    print(f"  DirectML available: {'yes' if probe.directml_available else 'no'}", flush=True)
    print(f"  onnx-asr installed: {'yes' if onnx_asr_ok else 'no'}", flush=True)
    print(f"  Reason: {runtime.reason}", flush=True)
    if runtime.fallback_reason:
        print(f"  Fallback: {runtime.fallback_reason}", flush=True)
    for line in probe.summary_lines():
        print(line, flush=True)
    print("----------------------------", flush=True)
    if runtime.gpu_warning and not _gpu_warning_printed:
        print(f"[WARNING] {runtime.gpu_warning}", flush=True)
        logger.warning(runtime.gpu_warning)
        _gpu_warning_printed = True


def reset_stt_acceleration_state() -> None:
    global _probe_override, _runtime, _gpu_warning_printed
    _probe_override = None
    _runtime = None
    _gpu_warning_printed = False


def set_acceleration_probe_override(probe: AccelerationProbe | None) -> None:
    global _probe_override, _runtime
    _probe_override = probe
    _runtime = None
