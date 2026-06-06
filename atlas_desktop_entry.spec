# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules


ROOT = Path.cwd()


def existing_datas():
    datas = [
        ("jarvis_desktop/static", "jarvis_desktop/static"),
        ("jarvis_desktop/demo", "jarvis_desktop/demo"),
        ("jarvis_desktop/atlas_knowledge", "jarvis_desktop/atlas_knowledge"),
    ]
    docs_quickstart = ROOT / "docs" / "ATLAS_QUICKSTART.md"
    if docs_quickstart.is_file():
        datas.append((str(docs_quickstart), "docs"))
    return datas


def desktop_hidden_imports():
    modules = []
    for package in ("jarvis_desktop", "builder_core"):
        modules.extend(
            name
            for name in collect_submodules(package)
            if ".tests" not in name and not name.endswith(".tests")
        )
    modules.extend(["yaml", "tkinter", "_tkinter"])
    return sorted(set(modules))


icon_path = ROOT / "installer" / "assets" / "jarvis.ico"
icon = str(icon_path) if icon_path.is_file() else None

a = Analysis(
    ["atlas_desktop_entry.py"],
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
    upx=True,
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
    upx=True,
    upx_exclude=[],
    name="Atlas",
)
