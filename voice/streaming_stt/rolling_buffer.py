"""Thread-safe rolling PCM buffer for streaming STT."""

from __future__ import annotations

import threading

import numpy as np


class RollingAudioBuffer:
    """Keeps the last N seconds of mono float32 audio at a fixed sample rate."""

    def __init__(self, *, sample_rate: int, max_seconds: float) -> None:
        self.sample_rate = int(sample_rate)
        self.max_samples = max(1, int(self.sample_rate * max(0.5, max_seconds)))
        self._lock = threading.Lock()
        self._chunks: list[np.ndarray] = []
        self._total_samples = 0
        self._generation = 0

    @property
    def total_samples(self) -> int:
        with self._lock:
            return self._total_samples

    @property
    def generation(self) -> int:
        with self._lock:
            return self._generation

    def append(self, chunk: np.ndarray) -> None:
        if chunk is None or chunk.size == 0:
            return
        flat = np.squeeze(chunk).astype(np.float32, copy=False)
        if flat.ndim > 1:
            flat = flat[:, 0]
        with self._lock:
            self._chunks.append(flat)
            self._total_samples += flat.shape[0]
            self._trim_locked()
            self._generation += 1

    def _trim_locked(self) -> None:
        while self._total_samples > self.max_samples and self._chunks:
            drop = self._chunks[0]
            if drop.shape[0] <= self._total_samples - self.max_samples:
                self._chunks.pop(0)
                self._total_samples -= drop.shape[0]
            else:
                need = self._total_samples - self.max_samples
                self._chunks[0] = drop[need:]
                self._total_samples -= need
                break

    def snapshot(self) -> np.ndarray:
        with self._lock:
            if not self._chunks:
                return np.array([], dtype=np.float32)
            if len(self._chunks) == 1:
                return self._chunks[0].copy()
            return np.concatenate(self._chunks, axis=0).copy()

    def clear(self) -> None:
        with self._lock:
            self._chunks.clear()
            self._total_samples = 0
            self._generation += 1

    def duration_seconds(self) -> float:
        with self._lock:
            return self._total_samples / float(self.sample_rate)
