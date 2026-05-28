"""Endpoint detection on a live stream (silence after speech, stream stays open)."""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np


@dataclass
class EndpointState:
    endpoint_reached: bool = False
    speech_detected: bool = False
    silence_ms: float = 0.0
    energy: float = 0.0
    vad_probability: float = 0.0


class StreamEndpointDetector:
    """
    Detect utterance end via trailing silence without stopping the microphone.
    """

    def __init__(
        self,
        *,
        silence_threshold: float,
        endpoint_silence_ms: float,
        min_speech_ms: float = 200.0,
        sample_rate: int = 16000,
        chunk_seconds: float = 0.10,
    ) -> None:
        self.silence_threshold = silence_threshold
        self.endpoint_silence_ms = max(100.0, endpoint_silence_ms)
        self.min_speech_samples = int(sample_rate * max(0.05, min_speech_ms / 1000.0))
        self.chunk_seconds = chunk_seconds
        self._speech_samples = 0
        self._trailing_silence_ms = 0.0
        self._speech_started = False
        self._endpoint = False

    @property
    def speech_started(self) -> bool:
        return self._speech_started

    @property
    def endpoint_reached(self) -> bool:
        return self._endpoint

    def reset(self) -> None:
        self._speech_samples = 0
        self._trailing_silence_ms = 0.0
        self._speech_started = False
        self._endpoint = False

    def observe_chunk(self, chunk: np.ndarray) -> EndpointState:
        if self._endpoint:
            return EndpointState(
                endpoint_reached=True,
                speech_detected=self._speech_started,
                silence_ms=self._trailing_silence_ms,
                energy=0.0,
                vad_probability=0.0,
            )
        flat = np.squeeze(chunk).astype(np.float64, copy=False)
        if flat.size == 0:
            return EndpointState(
                endpoint_reached=False,
                speech_detected=self._speech_started,
                silence_ms=self._trailing_silence_ms,
                energy=0.0,
                vad_probability=0.0,
            )
        rms = float(np.sqrt(np.mean(flat**2)))
        # Approximate VAD probability using RMS vs threshold ratio.
        vad_prob = max(0.0, min(1.0, rms / max(self.silence_threshold, 1e-9)))
        chunk_ms = self.chunk_seconds * 1000.0
        if rms >= self.silence_threshold:
            self._speech_started = True
            self._speech_samples += flat.shape[0]
            self._trailing_silence_ms = 0.0
        elif self._speech_started:
            self._trailing_silence_ms += chunk_ms
            if (
                self._speech_samples >= self.min_speech_samples
                and self._trailing_silence_ms >= self.endpoint_silence_ms
            ):
                self._endpoint = True
        return EndpointState(
            endpoint_reached=self._endpoint,
            speech_detected=self._speech_started,
            silence_ms=self._trailing_silence_ms,
            energy=rms,
            vad_probability=vad_prob,
        )
