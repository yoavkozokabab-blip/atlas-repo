"""Regression: path normalisation must keep dot-directories such as `.github/`.

`str.lstrip("./")` strips every leading "." as well as "./", so a recommended file
like `.github/ISSUE_TEMPLATE/config.yml` came back as `github/ISSUE_TEMPLATE/config.yml`,
a path that does not exist in the repository.
"""

import pytest

from atlas_desktop.context_pack import _norm_path as context_norm
from builder_core.bug_intelligence.impact import _norm_path as impact_norm


@pytest.mark.parametrize("norm", [context_norm, impact_norm])
@pytest.mark.parametrize(
    "raw, expected",
    [
        (".github/ISSUE_TEMPLATE/config.yml", ".github/ISSUE_TEMPLATE/config.yml"),
        (".env.example", ".env.example"),
        ("./src/app.py", "src/app.py"),
        ("././src/app.py", "src/app.py"),
        ("/src/app.py", "src/app.py"),
        ("src\\pkg\\mod.py", "src/pkg/mod.py"),
        ("src/app.py", "src/app.py"),
    ],
)
def test_norm_path_keeps_dot_directories(norm, raw, expected):
    assert norm(raw) == expected
