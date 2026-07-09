#!/usr/bin/env python3
"""Generate docs/API.md from the live FastAPI OpenAPI schema.

Single source of truth for the API reference: the route decorators + tag
metadata in apps/orchestrator/main.py. Run after adding or retagging endpoints:

    python scripts/gen_api_docs.py

Writes docs/API.md (grouped by tag, one table per group).
"""
from __future__ import annotations

import pathlib
import sys
from collections import defaultdict

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
# Ensure `apps.orchestrator` is importable no matter where the script is run from.
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from apps.orchestrator.main import app  # noqa: E402

OUT = REPO_ROOT / "docs" / "API.md"


def main() -> None:
    schema = app.openapi()
    paths = schema.get("paths", {})
    tag_order = [t["name"] for t in app.openapi_tags]
    tag_desc = {t["name"]: t["description"] for t in app.openapi_tags}

    by_tag: dict[str, list[tuple[str, str, str]]] = defaultdict(list)
    for p, ops in sorted(paths.items()):
        for method, op in ops.items():
            if method not in ("get", "post", "put", "delete", "patch"):
                continue
            tags = op.get("tags") or ["Untagged"]
            summary = op.get("summary") or ""
            if not summary and op.get("description"):
                summary = op["description"].strip().split("\n")[0]
            by_tag[tags[0]].append((method.upper(), p, summary))

    lines: list[str] = [
        "# API Reference — Agentic SDLC Orchestrator",
        "",
        f"**Version:** {app.version}  ",
        "**Interactive docs:** `/docs` (Swagger UI) · `/redoc` (ReDoc) · "
        "`/openapi.json` (raw schema)",
        "",
        "> Auto-generated from the live OpenAPI schema. Regenerate with "
        "`python scripts/gen_api_docs.py`.",
        "",
        app.description.split("### Conventions")[0].strip(),
        "",
        "## Conventions",
        "",
    ]
    if "### Conventions" in app.description:
        lines.append(app.description.split("### Conventions")[1].strip())
        lines.append("")
    lines += ["## Endpoints", ""]

    total = 0
    used_groups = 0
    for tag in tag_order:
        ops = by_tag.get(tag, [])
        if not ops:
            continue
        used_groups += 1
        lines += [f"### {tag}", "", f"_{tag_desc.get(tag, '')}_", "",
                  "| Method | Path | Summary |", "|---|---|---|"]
        for method, p, summary in sorted(ops, key=lambda x: (x[1], x[0])):
            lines.append(f"| `{method}` | `{p}` | {summary or '—'} |")
            total += 1
        lines.append("")

    lines += ["---", f"_{total} endpoints across {used_groups} groups._"]
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {OUT.relative_to(REPO_ROOT)} — {total} endpoints, {used_groups} groups")


if __name__ == "__main__":
    main()
