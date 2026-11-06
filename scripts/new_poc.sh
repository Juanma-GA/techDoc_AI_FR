#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
NODE_BIN="$(command -v node || command -v node.exe || true)"
if [[ -z "$NODE_BIN" ]]; then
    printf "Node.js 20+ is required to create an app.\n" >&2
    exit 1
fi
"$NODE_BIN" "$ROOT/framework/scripts/new_poc.mjs" --repo-root "$ROOT" "$@"
