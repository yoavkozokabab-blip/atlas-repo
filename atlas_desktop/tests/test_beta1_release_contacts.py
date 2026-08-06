"""Beta1 release gate: one support address, and no third-party domain.

`useatlas.dev` resolves to an unrelated live product owned by someone else.
Any surface that shows it to a user, or that tells an operator to point Atlas
at it, is a defect. Historical audit records under `reports/` are evidence of
what was true at the time and are deliberately not rewritten.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from atlas_desktop import product_info

REPO_ROOT = Path(__file__).resolve().parents[2]
SUPPORT_EMAIL = "yoavkozokabab@gmail.com"
RETIRED_ADDRESSES = (
    "yoavkozlovski@gmail.com",
    "atlas.repo.support@gmail.com",
    "support@useatlas.dev",
)
# Directories that ship to a user or that an operator acts on.
SHIPPING_ROOTS = (
    "atlas_desktop",
    "accounts_service",
    "licensing",
    "scripts",
    "packaging",
)
SHIPPING_FILES = ("PRIVACY.md", "TERMS.md", "SECURITY.md", "README.md", ".env.example")
SKIP_DIR_PARTS = {"__pycache__", ".lib", "node_modules", "staging", "output", "dist"}
TEXT_SUFFIXES = {".py", ".md", ".html", ".js", ".css", ".json", ".ps1", ".txt", ".iss"}


def _shipping_files() -> list[Path]:
    found: list[Path] = []
    for name in SHIPPING_FILES:
        path = REPO_ROOT / name
        if path.is_file():
            found.append(path)
    for root in SHIPPING_ROOTS:
        base = REPO_ROOT / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in TEXT_SUFFIXES:
                continue
            if SKIP_DIR_PARTS & set(part.lower() for part in path.parts):
                continue
            found.append(path)
    return found


SHIPPING = _shipping_files()


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def test_shipping_surfaces_have_a_single_support_address() -> None:
    assert product_info.DEFAULT_SUPPORT_EMAIL == SUPPORT_EMAIL
    os.environ.pop("ATLAS_SUPPORT_EMAIL", None)
    assert product_info.support_email() == SUPPORT_EMAIL

    offenders = []
    for path in SHIPPING:
        text = _read(path)
        for address in RETIRED_ADDRESSES:
            if address in text and "test_beta1_release_contacts" not in path.name:
                offenders.append(f"{path.relative_to(REPO_ROOT)} -> {address}")
    assert offenders == [], f"retired support address still shipping: {offenders}"


def test_no_shipping_surface_points_at_a_domain_we_do_not_own() -> None:
    offenders = [
        str(path.relative_to(REPO_ROOT))
        for path in SHIPPING
        if "useatlas.dev" in _read(path) and path.name != Path(__file__).name
    ]
    assert offenders == [], f"third-party domain referenced: {offenders}"


def test_desktop_auth_base_is_the_live_production_host() -> None:
    """The packaged default must resolve, or first run fails for every user."""
    from atlas_desktop import accounts_client

    os.environ.pop("ATLAS_WEB_URL", None)
    base = accounts_client.web_base()
    assert base.startswith("https://"), base
    assert "useatlas.dev" not in base
    assert base == "https://atlas-repo-wu76.vercel.app"


@pytest.mark.parametrize("name", ["PRIVACY.md", "TERMS.md"])
def test_legal_documents_name_the_monitored_inbox(name: str) -> None:
    text = _read(REPO_ROOT / name)
    assert SUPPORT_EMAIL in text, f"{name} does not name the support inbox"
    assert not re.search(r"support@useatlas\.dev", text)
