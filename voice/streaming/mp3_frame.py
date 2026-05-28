"""MP3 frame detection for ultra-low-latency playback start (Phase 58)."""

from __future__ import annotations

_BITRATE_TABLE = {
    (0, 0): (0, 0, 0, 0, 0),
    (0, 1): (32, 32, 32, 32, 8),
    (0, 2): (64, 48, 40, 48, 16),
    (0, 3): (96, 56, 48, 56, 24),
    (1, 0): (32, 32, 32, 32, 8),
    (1, 1): (64, 48, 40, 48, 16),
    (1, 2): (96, 56, 48, 56, 24),
    (1, 3): (128, 64, 56, 64, 32),
    (2, 0): (160, 80, 64, 80, 40),
    (2, 1): (192, 96, 80, 96, 48),
    (2, 2): (224, 112, 96, 112, 56),
    (2, 3): (256, 128, 112, 128, 64),
    (3, 0): (288, 160, 128, 160, 80),
    (3, 1): (320, 192, 160, 192, 96),
    (3, 2): (352, 224, 192, 224, 112),
    (3, 3): (384, 256, 224, 256, 128),
}


def _frame_length(header: bytes) -> int | None:
    if len(header) < 4 or header[0] != 0xFF or (header[1] & 0xE0) != 0xE0:
        return None
    version = (header[1] >> 3) & 0x03
    layer = (header[1] >> 1) & 0x03
    if layer != 1:  # Layer III only
        return None
    bitrate_idx = (header[2] >> 4) & 0x0F
    sample_idx = (header[2] >> 2) & 0x03
    padding = (header[2] >> 1) & 0x01
    if bitrate_idx == 0 or bitrate_idx == 15 or sample_idx == 3:
        return None
    bitrate = _BITRATE_TABLE.get((version, bitrate_idx), (0, 0, 0, 0, 0))[sample_idx]
    if bitrate <= 0:
        return None
    return int((144000 * bitrate) / 44100) + padding


def find_first_decodable_frame(data: bytes) -> tuple[int, int] | None:
    """Return (offset, frame_length) for first complete MP3 frame."""
    limit = min(len(data), 8192)
    for idx in range(limit - 4):
        frame_len = _frame_length(data[idx : idx + 4])
        if frame_len is None:
            continue
        if idx + frame_len <= len(data):
            return idx, frame_len
    return None


def extract_playable_prefix(data: bytes) -> tuple[bytes, bytes]:
    """Split buffer into first decodable frame(s) and remainder."""
    found = find_first_decodable_frame(data)
    if found is None:
        return b"", data
    offset, frame_len = found
    end = offset + frame_len
    return bytes(data[:end]), bytes(data[end:])
