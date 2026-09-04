#!/usr/bin/env bash
# =============================================================
#   DARION LOGIC SIM - CYTHON REACTOR BUILD  (Linux / macOS)
# =============================================================
set -euo pipefail

# ── Resolve repo root ─────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── 0. Parse arguments ────────────────────────────────────────
SOURCE_TARGET="reactor"   # default

for arg in "$@"; do
    case "$arg" in
        --reactor)     SOURCE_TARGET="reactor" ;;
        --reactor_oop) SOURCE_TARGET="reactor_oop" ;;
        *)
            echo "[ERROR] Unknown argument: $arg"
            echo "  Usage: $0 [--reactor | --reactor_oop]"
            exit 1
            ;;
    esac
done

echo "============================================================"
echo "  DARION LOGIC SIM - CYTHON BUILD  (target: $SOURCE_TARGET)"
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
echo "[*] Building '$SOURCE_TARGET'..."
echo ""

export CFLAGS="-O3 -g -fno-omit-frame-pointer"
export CXXFLAGS="-O3 -g -fno-omit-frame-pointer"

echo "[*] Cleaning previous build cache..."
rm -rf build/
rm -rf *.so *.pyd

"$PY_CMD" setup.py build_ext --inplace $COMPILER_FLAG --source-dir "$SOURCE_TARGET"

STATUS=$?
echo ""
if [[ $STATUS -eq 0 ]]; then
    echo "[SUCCESS] Build complete. .so files are in $SOURCE_TARGET/"
else
    echo "[FAILED] Build encountered errors (see above)."
    exit $STATUS
fi
