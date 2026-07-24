"""Static runnability gate: the review verdict must FAIL generated code that
won't run — syntax errors and use-before-import of stdlib modules (the exact
`time.time()` without `import time` bug found reviewing a delivered PR)."""
from __future__ import annotations

from apps.orchestrator.review_verdict import build_review_verdict


def test_missing_stdlib_import_is_a_blocker():
    # uses time.time() but never imports time -> NameError at runtime
    code = {
        "tests/test_main.py": (
            "def test_recent():\n"
            "    ts = get_alert_timestamp()\n"
            "    assert abs(time.time() - ts) < 5\n"
        ),
    }
    v = build_review_verdict(code, team="defaults")
    assert v.status == "FAIL"
    runnability = [b for b in v.blockers if b.check == "static-runnability"]
    assert runnability, "missing-import must produce a static-runnability blocker"
    assert any("time" in b.detail for b in runnability)


def test_syntax_error_is_a_blocker():
    code = {"src/main.py": "def broken(:\n    pass\n"}
    v = build_review_verdict(code, team="defaults")
    assert v.status == "FAIL"
    assert any(b.rule == "runnability/v0.1.0/SYNTAX-001" for b in v.blockers)


def test_properly_imported_stdlib_passes():
    code = {
        "src/main.py": (
            "import time\n"
            "def now() -> float:\n"
            "    return time.time()\n"
        ),
    }
    v = build_review_verdict(code, team="defaults")
    runnability = [b for b in v.blockers if b.check == "static-runnability"]
    assert not runnability, f"clean code must not trip runnability: {runnability}"


def test_import_alias_and_local_binding_not_flagged():
    # `time` bound locally (not the stdlib module) must not false-positive
    code = {
        "src/main.py": (
            "import datetime as dt\n"
            "def f(time):\n"          # param named time
            "    return time.hour\n"   # attribute on the PARAM, not stdlib
            "def g():\n"
            "    return dt.datetime.now()\n"  # aliased import used correctly
        ),
    }
    v = build_review_verdict(code, team="defaults")
    runnability = [b for b in v.blockers if b.check == "static-runnability"]
    assert not runnability, f"false positive on bound/aliased names: {runnability}"
