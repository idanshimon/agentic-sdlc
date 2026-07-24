"""Static runnability gate: the review verdict must FAIL generated code that
won't run — syntax errors, and use of any name that is never defined/imported,
whether at module scope (import-time NameError) or inside a function
(call-time NameError). Uses Python's symtable so it generalizes to third-party
names (TestClient), stdlib (time/os), and typos — not a hand allowlist.

Regression guard for real defects found reviewing delivered PRs:
- PR#12 test: `TestClient(app)` at module scope, no `from fastapi.testclient import TestClient`
- PR#12 src/main.py: `os.environ` used, `os` never imported (startup NameError)
- PR#6 test: `time.time()` in a function, no top-level `import time`
"""
from __future__ import annotations

from apps.orchestrator.review_verdict import build_review_verdict


def _runnability(code: dict[str, str]):
    v = build_review_verdict(code, team="defaults")
    return [b for b in v.blockers if b.check == "static-runnability"]


def test_module_scope_undefined_name_is_a_blocker():
    # TestClient used at module scope but never imported -> import-time NameError
    code = {
        "tests/test_main.py": (
            "from main import app\n"
            "client = TestClient(app)\n"
            "def test_ok():\n"
            "    assert client is not None\n"
        ),
    }
    bl = _runnability(code)
    assert bl, "module-scope undefined name must block"
    assert any("TestClient" in b.detail for b in bl)
    assert any(b.rule == "runnability/v0.1.0/IMPORT-001" for b in bl)


def test_startup_missing_import_is_a_blocker():
    # os.environ at module scope with no `import os` -> service NameErrors at start
    code = {
        "src/main.py": (
            "import time\n"
            "PORT = int(os.environ.get('PORT', '8080'))\n"
        ),
    }
    bl = _runnability(code)
    assert any("os" in b.detail for b in bl), f"missing `import os` must block: {bl}"


def test_function_scope_undefined_name_is_a_blocker():
    # time.time() inside a function, no top-level `import time` -> call-time NameError
    code = {
        "tests/test_main.py": (
            "from main import app\n"
            "def test_recent():\n"
            "    ts = get_ts()\n"
            "    assert abs(time.time() - ts) < 5\n"
            "def get_ts():\n"
            "    return 0\n"
        ),
    }
    bl = _runnability(code)
    assert any("time" in b.detail for b in bl), f"function-scope NameError must block: {bl}"


def test_syntax_error_is_a_blocker():
    code = {"src/main.py": "def broken(:\n    pass\n"}
    bl = _runnability(code)
    assert any(b.rule == "runnability/v0.1.0/SYNTAX-001" for b in bl)


def test_clean_code_passes():
    code = {
        "src/main.py": (
            "import time\n"
            "import os\n"
            "from fastapi.testclient import TestClient\n"
            "from main import app\n"
            "client = TestClient(app)\n"
            "def now(n):\n"
            "    xs = [i for i in range(n)]\n"
            "    return time.time() + len(xs) + int(os.environ.get('X', '0'))\n"
        ),
    }
    assert not _runnability(code), "correct code must not trip the runnability gate"


def test_forward_reference_between_functions_not_flagged():
    # a() calls b() defined later at module scope — valid at runtime, must not flag
    code = {
        "src/main.py": (
            "def a():\n"
            "    return b()\n"
            "def b():\n"
            "    return 1\n"
            "HANDLER = a\n"
        ),
    }
    assert not _runnability(code), "forward references between module funcs are valid"


def test_builtins_and_comprehension_vars_not_flagged():
    code = {
        "src/main.py": (
            "def f(items):\n"
            "    return sorted(len(x) for x in items if isinstance(x, str))\n"
        ),
    }
    assert not _runnability(code), "builtins + comprehension locals must not flag"
