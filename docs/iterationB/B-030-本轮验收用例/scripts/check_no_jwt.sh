#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if rg -n --hidden -g '!runs/**' -g '!.git/**' 'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+' "$ROOT"; then
  echo "FAIL: raw JWT found; redact before commit" >&2
  exit 1
fi
echo "OK: no raw JWT in committed tree paths"
