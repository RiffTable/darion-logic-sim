#!/usr/bin/env bash
# =============================================================
#   DARION LOGIC SIM - CYTHON REACTOR BUILD  (Linux / macOS)
# =============================================================
set -euo pipefail

# ── Resolve repo root ─────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "============================================================"
echo "  DARION LOGIC SIM - CYTHON REACTOR BUILD"
echo "============================================================"
echo ""

# ── 1. Python interpreter ─────────────────────────────────────
if [[ -x "$SCRIPT_DIR/../.venv/bin/python" ]]; then
    PY_CMD="$SCRIPT_DIR/../.venv/bin/python"
    echo "[+] Using venv Python: $PY_CMD"
elif command -v python3 &>/dev/null; then
    PY_CMD="python3"
    echo "[+] Using system python3"
elif command -v python &>/dev/null; then
    PY_CMD="python"
    echo "[+] Using system python"
else
    echo "[ERROR] No Python interpreter found. Install Python 3 and retry."
    exit 1
fi

# ── 2. Detect C++ compiler ────────────────────────────────────
COMPILER_FLAG=""

if command -v g++ &>/dev/null; then
    echo "[+] Compiler: g++ ($(g++ --version | head -1))"
    COMPILER_FLAG="--compiler=unix"
elif command -v clang++ &>/dev/null; then
    echo "[+] Compiler: clang++ ($(clang++ --version | head -1))"
    # Cython's distutils calls 'cc' / 'c++'; override via env
    export CC=clang
    export CXX=clang++
    COMPILER_FLAG="--compiler=unix"
else
    echo "[ERROR] No C/C++ compiler found!"
    echo "  Linux  : sudo apt install build-essential"
    echo "  macOS  : xcode-select --install"
    exit 1
fi

# ── 3. Ensure Cython is available ────────────────────────────
if ! "$PY_CMD" -c "import Cython" 2>/dev/null; then
    echo "[ERROR] Cython not found for $PY_CMD"
    echo "  Run: $PY_CMD -m pip install cython setuptools"
    exit 1
fi

# ── 4. Build ──────────────────────────────────────────────────
echo ""
echo "[*] Starting build..."
echo ""

"$PY_CMD" setup.py build_ext --inplace $COMPILER_FLAG

STATUS=$?
echo ""
if [[ $STATUS -eq 0 ]]; then
    echo "[SUCCESS] Build complete. .so files are in reactor/"
else
    echo "[FAILED] Build encountered errors (see above)."
    exit $STATUS
fi
