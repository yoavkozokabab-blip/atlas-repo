"""Discover installed apps from Start Menu (and registry display names)."""

from __future__ import annotations

import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from apps.safety import SafetyError, validate_launch_path, validate_resolved_target

_START_MENU_DIRS: list[Path] = []


def _start_menu_roots() -> list[Path]:
    global _START_MENU_DIRS
    if _START_MENU_DIRS:
        return _START_MENU_DIRS
    roots: list[Path] = []
    program_data = Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData"))
    appdata = Path(os.environ.get("APPDATA", ""))
    candidates = [
        program_data / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        appdata / "Microsoft" / "Windows" / "Start Menu" / "Programs",
    ]
    for p in candidates:
        if p.is_dir():
            roots.append(p)
    _START_MENU_DIRS = roots
    return roots


HEBREW_APP_ALIASES: dict[str, str] = {
    "דיסקורד": "discord",
    "ספוטיפיי": "spotify",
    "סטים": "steam",
    "כרום": "chrome",
    "קרסור": "cursor",
}


def normalize_app_query(query: str) -> str:
    """Normalize user app name (English or Hebrew) to slug."""
    raw = unicodedata.normalize("NFKC", query).strip()
    if raw in HEBREW_APP_ALIASES:
        return HEBREW_APP_ALIASES[raw]
    slug = app_slug(raw)
    return HEBREW_APP_ALIASES.get(slug, slug)


def app_slug(display_name: str) -> str:
    """Stable id from display name."""
    text = unicodedata.normalize("NFKC", display_name).strip().lower()
    text = re.sub(r"[^a-z0-9\u0590-\u05ff]+", "_", text)
    text = text.strip("_")
    return text or "app"


@dataclass(frozen=True)
class DiscoveredApp:
    app_id: str
    display_name: str
    shortcut_path: Path
    target_path: Path | None = None
    source: str = "start_menu"

    def to_dict(self) -> dict:
        return {
            "app_id": self.app_id,
            "display_name": self.display_name,
            "shortcut_path": str(self.shortcut_path),
            "target_path": str(self.target_path) if self.target_path else None,
            "source": self.source,
        }


def _resolve_lnk_target(lnk_path: Path) -> Path | None:
    """Best-effort .lnk target path without shell execution."""
    try:
        data = lnk_path.read_bytes()
    except OSError:
        return None
    # UTF-16 local path after LocalBasePath marker in shell link
    for marker in (b"LocalBasePath", b"LocalBasePathW"):
        idx = data.find(marker)
        if idx < 0:
            continue
        chunk = data[idx + len(marker) : idx + len(marker) + 520]
        for encoding in ("utf-16-le", "ascii"):
            try:
                raw = chunk.decode(encoding, errors="ignore")
            except Exception:
                continue
            match = re.search(r"([A-Za-z]:\\[^\x00\n\r]+)", raw)
            if match:
                candidate = Path(match.group(1).strip())
                if candidate.suffix:
                    return candidate
    return None


def _display_name_from_lnk(path: Path) -> str:
    return path.stem.strip() or path.name


def _iter_shortcuts(roots: list[Path] | None = None) -> list[DiscoveredApp]:
    roots = roots or _start_menu_roots()
    found: dict[str, DiscoveredApp] = {}
    for root in roots:
        if not root.is_dir():
            continue
        for lnk in root.rglob("*.lnk"):
            if not lnk.is_file():
                continue
            display = _display_name_from_lnk(lnk)
            slug = app_slug(display)
            if not slug:
                continue
            target = _resolve_lnk_target(lnk)
            if target is not None:
                try:
                    target = validate_resolved_target(target)
                except SafetyError as exc:
                    if "does not exist" in str(exc).lower():
                        target = None
                    else:
                        continue
            key = str(lnk.resolve()).lower()
            if key in found:
                continue
            app = DiscoveredApp(
                app_id=slug,
                display_name=display,
                shortcut_path=lnk.resolve(),
                target_path=target,
                source="start_menu",
            )
            found[key] = app
    return list(found.values())


def _registry_display_names() -> dict[str, str]:
    """Optional uninstall registry display names (names only, not used for launch)."""
    names: dict[str, str] = {}
    try:
        import winreg
    except ImportError:
        return names

    keys = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for hive, subkey in keys:
        try:
            with winreg.OpenKey(hive, subkey) as root:
                for i in range(winreg.QueryInfoKey(root)[0]):
                    try:
                        sub_name = winreg.EnumKey(root, i)
                        with winreg.OpenKey(root, sub_name) as appkey:
                            display, _ = winreg.QueryValueEx(appkey, "DisplayName")
                            if display and isinstance(display, str):
                                names[app_slug(display)] = display.strip()
                    except OSError:
                        continue
        except OSError:
            continue
    return names


def discover_installed_apps(
    *,
    start_menu_roots: list[Path] | None = None,
    include_registry_names: bool = True,
) -> list[DiscoveredApp]:
    """Scan Start Menu shortcuts; merge registry display names for search hints only."""
    apps = _iter_shortcuts(start_menu_roots)
    if include_registry_names:
        reg_names = _registry_display_names()
        by_id = {a.app_id: a for a in apps}
        for slug, display in reg_names.items():
            if slug not in by_id:
                continue
    return sorted(apps, key=lambda a: a.display_name.lower())


def search_discovered_apps(
    query: str,
    apps: list[DiscoveredApp] | None = None,
) -> list[DiscoveredApp]:
    """Match query against app_id and display_name."""
    catalog = apps if apps is not None else discover_installed_apps()
    q = app_slug(query) if query else ""
    if not q:
        return catalog[:50]
    matches: list[DiscoveredApp] = []
    for app in catalog:
        if q == app.app_id or q in app.app_id or q in app_slug(app.display_name):
            matches.append(app)
        elif query.lower() in app.display_name.lower():
            matches.append(app)
    return matches


def find_best_match(
    query: str,
    apps: list[DiscoveredApp] | None = None,
) -> tuple[list[DiscoveredApp], str]:
    """Return (matches, normalized_query)."""
    norm = app_slug(query)
    catalog = apps if apps is not None else discover_installed_apps()
    exact = [a for a in catalog if a.app_id == norm]
    if exact:
        return exact, norm
    partial = search_discovered_apps(query, catalog)
    return partial, norm
