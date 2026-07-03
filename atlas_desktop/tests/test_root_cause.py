"""#10 Root Cause Mode tests."""
from atlas_desktop import root_cause as rc


def test_parse_error_python_traceback():
    err = (
        "Traceback (most recent call last):\n"
        '  File "app/svc.py", line 42, in handle\n'
        '    raise ValueError("boom")\n'
        "ValueError: boom"
    )
    p = rc.parse_error(err)
    assert p["exception_type"] == "ValueError"
    assert "boom" in p["exception_message"]
    assert p["frames"] and p["frames"][-1]["func"] == "handle"
    assert p["frames"][-1]["file"].endswith("app/svc.py")


def test_parse_error_pytest_assertion():
    err = (
        "tests/test_auth.py:31: in test_login\n"
        "    assert resp.status_code == 200\n"
        "E   AssertionError: assert 401 == 200"
    )
    p = rc.parse_error(err)
    assert p["exception_type"] == "AssertionError"
    assert p["frames"][-1]["file"].endswith("tests/test_auth.py")


def test_analyze_root_cause_resolves_frame_to_symbol(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "svc.py").write_text(
        "def helper():\n    return 1\n\n"
        "def handle(req):\n    x = helper()\n    raise ValueError('boom')\n",
        encoding="utf-8",
    )
    state = {"index": {"files": [{"path": "app/svc.py"}]}, "scan": {}, "graph": {}}
    err = (
        "Traceback (most recent call last):\n"
        '  File "app/svc.py", line 6, in handle\n'
        "    raise ValueError('boom')\n"
        "ValueError: boom"
    )
    res = rc.analyze_root_cause(str(tmp_path), err, state)
    assert res["ok"]
    assert res["exception"]["type"] == "ValueError"
    syms = res["root_cause_symbols"]
    assert syms and syms[0]["role"] == "raise_site"
    assert syms[0]["file"] == "app/svc.py"
    assert syms[0]["symbol"] == "handle"
    assert syms[0].get("start_line") == 4  # def handle
    assert res["confidence"] in {"MEDIUM", "HIGH"}
    assert res["investigation_order"]
