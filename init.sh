#!/usr/bin/env bash
set -euo pipefail

# SHARP Harness — Dev Server Init
# Usage: bash init.sh
# Karpathy: Simplicity First — no Docker, no orchestration, just bash

echo "=== SHARP Harness Init ==="

# Detect Python command (prefer the one with SHARP deps)
PYTHON=""
# Check if we're in WSL (bash sees WSL python but SHARP is on Windows side)
if grep -qi microsoft /proc/version 2>/dev/null; then
  # WSL: use Windows Python via /mnt/c path
  WIN_PYTHON="/mnt/c/Users/shiva/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
  if [ -f "$WIN_PYTHON" ]; then
    PYTHON="$WIN_PYTHON"
  fi
fi
if [ -z "$PYTHON" ]; then
  for cmd in python3 python py; do
    if command -v "$cmd" &>/dev/null; then
      PYTHON="$cmd"
      break
    fi
  done
fi
if [ -z "$PYTHON" ]; then
  echo "ERROR: No Python found in PATH"
  exit 1
fi
echo "Using Python: $PYTHON"

# 1. Confirm directory (Think Before Coding)
if [ ! -f "sharp/__init__.py" ]; then
  echo "ERROR: Not in harness_system directory"
  echo "Usage: cd harness_system && bash init.sh"
  exit 1
fi
echo "[1/5] Directory confirmed"

# 2. Install in dev mode (idempotent)
echo "[2/5] Installing package..."
pip install -e "." -q 2>/dev/null && echo "  OK" || echo "  WARN: install failed, continuing"

# 3. Verify imports
echo "[3/5] Verifying imports..."
$PYTHON -c "from sharp import HarnessEngine, HarnessConfig; print('  Imports OK')" || {
  echo "  FATAL: Imports broken"
  exit 1
}

# 4. Smoke test (no LLM call)
echo "[4/5] Running smoke test..."
$PYTHON -c "
import asyncio
from sharp import HarnessEngine
engine = HarnessEngine()
print('  Engine created OK')
" 2>&1 || {
  echo "  FATAL: Engine creation failed"
  exit 1
}

# 5. Test suite quick check
echo "[5/5] Running test suite..."
if $PYTHON -m pytest tests/ -q --tb=no 2>&1 | tail -1; then
  echo ""
else
  echo "  WARN: Some tests may have failed"
fi

echo ""
echo "=== Init Complete ==="
echo "Ready for coding session."
