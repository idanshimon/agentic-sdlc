import importlib.util
from pathlib import Path

_path = Path(__file__).resolve().parents[1] / "verify_github_governance.py"
_spec = importlib.util.spec_from_file_location("verify_github_governance", _path)
assert _spec and _spec.loader
module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(module)
verify = module.verify


def test_workflow_without_required_check_is_advisory(monkeypatch):
    def fake(path):
        if path.endswith("/rulesets"): return [], None
        if path.endswith("/protection"): return None, "HTTP 404"
        if path.endswith("/actions/permissions"): return {"enabled": True}, None
        return {"security_and_analysis": {}}, None
    monkeypatch.setattr(module, "gh", fake)
    report = verify("owner/repo")
    assert report["bundle_enforcement"]["status"] == "advisory"


def test_required_bundle_check_is_enforced(monkeypatch):
    def fake(path):
        if path.endswith("/rulesets"): return [], None
        if path.endswith("/protection"):
            return {"required_status_checks": {"contexts": ["bundle-enforce"]}}, None
        if path.endswith("/actions/permissions"): return {"enabled": True}, None
        return {"security_and_analysis": {}}, None
    monkeypatch.setattr(module, "gh", fake)
    report = verify("owner/repo")
    assert report["bundle_enforcement"]["status"] == "enforced"
