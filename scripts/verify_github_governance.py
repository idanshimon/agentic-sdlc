#!/usr/bin/env python3
"""Read-only verifier for GitHub-native enforcement posture."""
from __future__ import annotations

import argparse
import json
import subprocess


def gh(path: str):
    proc = subprocess.run(["gh", "api", path], text=True, capture_output=True)
    if proc.returncode:
        return None, proc.stderr.strip()
    return json.loads(proc.stdout), None


def verify(repo: str) -> dict:
    rulesets, rulesets_error = gh(f"repos/{repo}/rulesets")
    branch, branch_error = gh(f"repos/{repo}/branches/main/protection")
    actions, actions_error = gh(f"repos/{repo}/actions/permissions")
    environments, environments_error = gh(f"repos/{repo}/environments")
    runners, runners_error = gh(f"repos/{repo}/actions/runners")
    vulnerability, vulnerability_error = gh(f"repos/{repo}")

    required_checks: set[str] = set()
    if branch:
        contexts = branch.get("required_status_checks", {}).get("contexts", [])
        required_checks.update(contexts)
    for ruleset in rulesets or []:
        for rule in ruleset.get("rules", []):
            if rule.get("type") == "required_status_checks":
                for check in rule.get("parameters", {}).get("required_status_checks", []):
                    required_checks.add(check.get("context", ""))

    return {
        "repo": repo,
        "rulesets": {"active_count": len(rulesets or []), "error": rulesets_error},
        "branch_protection": {"configured": branch is not None, "error": branch_error},
        "required_checks": sorted(c for c in required_checks if c),
        "bundle_enforcement": {
            "status": "enforced" if "bundle-enforce" in required_checks else "advisory",
            "reason": None if "bundle-enforce" in required_checks else "bundle-enforce is not a required check",
        },
        "actions_policy": {"value": actions, "error": actions_error},
        "environments": {"value": environments, "error": environments_error},
        "runner_posture": {"value": runners, "error": runners_error},
        "security_features": {
            "value": (vulnerability or {}).get("security_and_analysis"),
            "error": vulnerability_error,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", help="owner/repo")
    args = parser.parse_args()
    report = verify(args.repo)
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["bundle_enforcement"]["status"] == "enforced" else 2


if __name__ == "__main__":
    raise SystemExit(main())
