# -*- mode: python ; coding: utf-8 -*-
# Atlas Desktop — PyInstaller one-folder, windowed (Phase 152)

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


SPEC_DIR = Path(SPEC).resolve().parent
ROOT = SPEC_DIR.parents[1]


def existing_datas():
    datas = [
        (str(ROOT / "atlas_desktop" / "static"), "atlas_desktop/static"),
        (str(ROOT / "atlas_desktop" / "demo"), "atlas_desktop/demo"),
        (str(ROOT / "atlas_desktop" / "atlas_knowledge"), "atlas_desktop/atlas_knowledge"),
    ]
    quickstart = ROOT / "docs" / "ATLAS_QUICKSTART.md"
    if quickstart.is_file():
        datas.append((str(quickstart), "docs"))
    build_info = SPEC_DIR.parent / "installer" / "build_info.json"
    if build_info.is_file():
        datas.append((str(build_info), "packaging/installer"))
    return datas


def desktop_hidden_imports():
    modules = []
    for package in ("atlas_desktop", "builder_core"):
        modules.extend(
            name
            for name in collect_submodules(package)
            if ".tests" not in name and not name.endswith(".tests")
        )
    modules.extend(["yaml", "tkinter", "_tkinter"])
    return sorted(set(modules))


icon_path = ROOT / "packaging" / "installer" / "assets" / "atlas.ico"
icon = str(icon_path) if icon_path.is_file() else None

a = Analysis(
    [str(SPEC_DIR / "atlas_entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=existing_datas(),
    hiddenimports=desktop_hidden_imports(),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "fastapi",
        "uvicorn",
        "starlette",
        "pytest",
        "tests",
        "voice",
        "browser",
        "trading",
        "playwright",
        "sounddevice",
        "faster_whisper",
        "onnxruntime",
        "pytesseract",
        "pyautogui",
        "mss",
        "PySide6",
        "external_repos",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Atlas",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="Atlas",
)
