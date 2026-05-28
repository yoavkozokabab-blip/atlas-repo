"""Iron Man / JARVIS overlay visual theme (PySide6 QSS + palette)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OverlayTheme:
    name: str = "jarvis_blue"
    accent: str = "#00d4ff"
    accent_dim: str = "#0066aa"
    glow: str = "#66e8ff"
    glow_outer: str = "#00a8cc"
    bg: str = "rgba(6, 12, 24, 200)"
    text: str = "#e8f4ff"
    text_dim: str = "#7eb8d8"
    error: str = "#ff6b6b"
    success: str = "#5dffb0"
    ring_width: int = 3
    font_family: str = "Segoe UI"
    title_size: int = 16
    body_size: int = 12
    window_width: int = 360
    window_height: int = 400
    circle_size: int = 140
    premium: bool = False
    full_screen: bool = False


_THEMES: dict[str, OverlayTheme] = {
    "premium_ironman_full": OverlayTheme(
        name="premium_ironman_full",
        accent="#00f0ff",
        accent_dim="#003d55",
        glow="#9dfbff",
        glow_outer="#00d4ff",
        bg="rgba(1, 6, 14, 230)",
        text="#ecfaff",
        text_dim="#6eb8d4",
        title_size=22,
        body_size=11,
        window_width=1920,
        window_height=1080,
        circle_size=220,
        ring_width=2,
        premium=True,
        full_screen=True,
    ),
    "premium_ironman": OverlayTheme(
        name="premium_ironman",
        accent="#00e8ff",
        accent_dim="#005577",
        glow="#7af0ff",
        glow_outer="#00b4d8",
        bg="rgba(4, 10, 22, 215)",
        text="#e6f7ff",
        text_dim="#5a9ab8",
        title_size=18,
        body_size=11,
        window_width=420,
        window_height=480,
        circle_size=160,
        premium=True,
    ),
    "jarvis_blue": OverlayTheme(
        name="jarvis_blue",
        accent="#00d4ff",
        accent_dim="#0055aa",
        glow="#88eeff",
        glow_outer="#00b8e6",
        bg="rgba(6, 14, 28, 200)",
    ),
    "jarvis_gold": OverlayTheme(
        name="jarvis_gold",
        accent="#ffc857",
        accent_dim="#aa7722",
        glow="#ffe6a0",
        glow_outer="#dd9922",
        bg="rgba(20, 14, 6, 200)",
        text="#fff8e8",
        text_dim="#c4a86a",
    ),
}


def resolve_overlay_theme_name() -> str:
    """Prefer OVERLAY_STYLE; fall back to OVERLAY_THEME."""
    try:
        from config import OVERLAY_STYLE, OVERLAY_THEME

        style = (OVERLAY_STYLE or "").strip().lower()
        if style in _THEMES:
            return style
        theme = (OVERLAY_THEME or "").strip().lower()
        if theme in _THEMES:
            return theme
    except Exception:
        pass
    return "premium_ironman_full"


def get_overlay_theme(name: str | None = None) -> OverlayTheme:
    key = (name or resolve_overlay_theme_name()).strip().lower()
    return _THEMES.get(key, _THEMES["premium_ironman_full"])


def window_stylesheet(theme: OverlayTheme, opacity: float) -> str:
    alpha = max(0.3, min(1.0, opacity))
    bg_alpha = int(200 * alpha)
    return f"""
    QWidget#jarvisOverlayRoot {{
        background-color: rgba(6, 12, 24, {bg_alpha});
        border: 1px solid {theme.accent_dim};
        border-radius: 20px;
    }}
    QLabel#statusLabel {{
        color: {theme.accent};
        font-family: "{theme.font_family}";
        font-size: {theme.title_size}px;
        font-weight: 600;
    }}
    QLabel#transcriptLabel, QLabel#resultLabel {{
        color: {theme.text};
        font-family: "{theme.font_family}";
        font-size: {theme.body_size}px;
    }}
    QLabel#hintLabel {{
        color: {theme.text_dim};
        font-family: "{theme.font_family}";
        font-size: 10px;
    }}
    QLabel#errorLabel {{
        color: {theme.error};
        font-family: "{theme.font_family}";
        font-size: {theme.body_size}px;
    }}
    """
