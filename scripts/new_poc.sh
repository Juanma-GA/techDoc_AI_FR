#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
node "$ROOT/scripts/new_poc.mjs" "$@"
if [[ " $* " != *" --dry-run "* ]]; then
    bash "$ROOT/scripts/check_standard.sh"
fi
