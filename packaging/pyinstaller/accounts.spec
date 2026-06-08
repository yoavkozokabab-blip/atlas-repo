# -*- mode: python ; coding: utf-8 -*-
# Atlas Accounts Service — PyInstaller one-folder (Phase 192)
# Produces dist/AtlasAccounts/AtlasAccounts.exe — the frozen FastAPI/uvicorn
# accounts service that Atlas.exe launches automatically.

import sys
from pathlib import Path

SPEC_DIR = Path(SPEC).resolve().parent
ROOT = SPEC_DIR.parents[1]
LIB = ROOT / "accounts_service" / ".lib"

# Make vendored deps importable for build-time collection.
for p in (str(ROOT), str(LIB)):
    if p not in sys.path:
        sys.path.insert(0, p)

from PyInstaller.utils.hooks import collect_all, collect_submodules

_COLLECT_PACKAGES = [
    "fastapi", "starlette", "uvicorn", "pydantic", "pydantic_core",
    "sqlalchemy", "jwt", "passlib", "bcrypt", "anyio", "sniffio", "h11",
    "click", "dotenv", "email_validator", "multipart", "python_multipart",
    "dns", "idna", "greenlet", "annotated_types", "typing_inspection",
    "colorama", "starlette",
]

datas = []
binaries = []
hiddenimports = []
for pkg in _COLLECT_PACKAGES:
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception:
        pass

# The accounts service package itself (exclude tests).
hiddenimports += [
    name for name in collect_submodules("accounts_service")
    if ".tests" not in name and not name.endswith(".tests")
]
# Common dynamic imports.
hiddenimports += [
    "uvicorn.loops.auto", "uvicorn.loops.asyncio",
    "uvicorn.protocols.http.auto", "uvicorn.protocols.http.h11_impl",
    "uvicorn.protocols.websockets.auto", "uvicorn.protocols.websockets.wsproto_impl",
    "uvicorn.lifespan.on", "uvicorn.lifespan.off",
    "email_validator", "passlib.handlers.bcrypt",
]
hiddenimports = sorted(set(hiddenimports))

a = Analysis(
    [str(SPEC_DIR / "accounts_entry.py")],
    pathex=[str(ROOT), str(LIB)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "jarvis_desktop", "builder_core", "tkinter", "_tkinter",
        "pytest", "tests", "voice", "browser", "trading", "playwright",
        "sounddevice", "faster_whisper", "onnxruntime", "pytesseract",
        "pyautogui", "mss", "PySide6", "external_repos", "matplotlib",
        "numpy", "pandas", "scipy",
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
    name="AtlasAccounts",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AtlasAccounts",
)
