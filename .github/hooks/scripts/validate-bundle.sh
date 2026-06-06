#!/usr/bin/env bash
# Validate the .github/hooks/ bundle: all files present, executable, parseable.
set -euo pipefail

HOOKS_DIR="$(dirname "$0")/.."
ERRORS=0

# Required JSON files
for hook in session-start user-prompt-submit pre-tool-use post-tool-use session-end; do
    json="$HOOKS_DIR/$hook.json"
    if [[ ! -f "$json" ]]; then
        echo "MISSING: $json" >&2
        ((ERRORS++))
        continue
    fi
    if ! jq empty "$json" 2>/dev/null; then
        echo "INVALID JSON: $json" >&2
        ((ERRORS++))
    fi
done

# Required scripts
for hook in session-start user-prompt-submit pre-tool-use post-tool-use session-end; do
    for ext in sh ps1; do
        script="$HOOKS_DIR/scripts/$hook.$ext"
        if [[ ! -f "$script" ]]; then
            echo "MISSING: $script" >&2
            ((ERRORS++))
        fi
    done
done

# Tools on PATH
for tool in jq curl; do
    if ! command -v "$tool" >/dev/null 2>&1; then
        echo "MISSING TOOL: $tool (required by hook scripts)" >&2
        ((ERRORS++))
    fi
done

if [[ $ERRORS -eq 0 ]]; then
    echo "✓ hook bundle valid (5 configs + 10 scripts, jq + curl available)"
    exit 0
else
    echo "✗ $ERRORS errors" >&2
    exit 1
fi
