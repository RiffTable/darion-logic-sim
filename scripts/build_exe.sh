#!/usr/bin/env bash
# =============================================================
#   BLAZING FAST PYTHON TO BINARY  (Nuitka - Linux / macOS)
# =============================================================
#
#   Equivalent of build_exe.bat for POSIX platforms.
#
#   Features mirrored from the .bat:
#     • Standalone vs Onefile choice
#     • LTO (always on)
#     • Optional PGO-C (profile-guided optimisation)
#     • Python-flag stripping (docstrings / asserts / warnings / site)
#     • Explicit module/package includes for the Cython reactor
#     • Parallel C-compilation (nproc / sysctl)
#     • Auto-cleanup of intermediate build dirs
#
#   Platform differences vs Windows:
#     • No mt.exe / SegmentHeap manifest (Windows-only feature)
#     • Uses gcc/clang instead of MSVC
#     • Output is a native ELF binary (Linux) or Mach-O (macOS),
#       not a PE .exe
# =============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

echo "============================================================"
echo "  BLAZING FAST PYTHON TO BINARY (Nuitka - Linux/macOS)"
echo "============================================================"
echo ""

# ── 1. Python interpreter ─────────────────────────────────────
if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
    PY_CMD="$REPO_ROOT/.venv/bin/python"
    echo "[+] Using venv Python: $PY_CMD"
elif command -v python3 &>/dev/null; then
    PY_CMD="python3"
    echo "[+] Using system python3"
elif command -v python &>/dev/null; then
    PY_CMD="python"
    echo "[+] Using system python"
else
    echo "[ERROR] No Python interpreter found."
    exit 1
fi

# ── 2. Check Nuitka ───────────────────────────────────────────
if ! "$PY_CMD" -m nuitka --version &>/dev/null; then
    echo "[ERROR] Nuitka not found for $PY_CMD"
    echo "  Run: $PY_CMD -m pip install nuitka"
    exit 1
fi

# ── 3. Script to compile ──────────────────────────────────────
echo ""
read -rp "Enter the path to your Python script (e.g., Testing_script/speed_test.py): " SCRIPT_PATH

# Strip surrounding quotes if the user dragged-and-dropped
SCRIPT_PATH="${SCRIPT_PATH//\"/}"

# Resolve relative paths against the repo root
if [[ ! "$SCRIPT_PATH" = /* ]]; then
    SCRIPT_PATH="$REPO_ROOT/$SCRIPT_PATH"
fi

if [[ ! -f "$SCRIPT_PATH" ]]; then
    echo "[ERROR] File \"$SCRIPT_PATH\" not found!"
    exit 1
fi

BASENAME="$(basename "${SCRIPT_PATH%.py}")"

# ── 4. Build type ─────────────────────────────────────────────
echo ""
echo "Choose build type:"
echo "[1] Standalone  (folder + binary - fastest startup, easiest to debug)"
echo "[2] Onefile     (single binary   - portable, ~1s extraction overhead)"
read -rp "Enter 1 or 2: " BUILD_TYPE

case "$BUILD_TYPE" in
    1)
        BUILD_SWITCH="--standalone"
        TARGET_BIN="blazing_builds/${BASENAME}.dist/${BASENAME}"
        ;;
    2)
        BUILD_SWITCH="--onefile"
        TARGET_BIN="blazing_builds/${BASENAME}"
        ;;
    *)
        echo "[ERROR] Invalid choice. Enter 1 or 2."
        exit 1
        ;;
esac

# ── 5. PGO? ───────────────────────────────────────────────────
echo ""
echo "Enable Profile Guided Optimization? (recommended - 10-30% speed boost)"
echo "[Y] Yes - compile twice, guided by a live benchmark run"
echo "[N] No  - single-pass compile, faster build time"
read -rp "Enter Y or N: " USE_PGO
USE_PGO="${USE_PGO^^}"   # uppercase

# PGO-C is incompatible with --onefile / --standalone in Nuitka
# (same caveat as on Windows - intermediate binary is not runnable)
if [[ "$USE_PGO" == "Y" && ( "$BUILD_SWITCH" == "--onefile" || "$BUILD_SWITCH" == "--standalone" ) ]]; then
    echo ""
    echo "[WARNING] C-level PGO is NOT supported with $BUILD_SWITCH mode."
    echo "          The intermediate PGO binary cannot execute itself."
    echo "          Falling back to standard LTO-only compile."
    USE_PGO="N"
fi

# ── 6. Detect CPU count ───────────────────────────────────────
if command -v nproc &>/dev/null; then
    CPU_COUNT="$(nproc)"
elif command -v sysctl &>/dev/null; then
    CPU_COUNT="$(sysctl -n hw.logicalcpu 2>/dev/null || echo 4)"
else
    CPU_COUNT=4
fi
echo ""
echo "[Config] C compiler jobs: $CPU_COUNT"

# ── 7. Output dir & PYTHONPATH ────────────────────────────────
OUT_DIR="blazing_builds"
mkdir -p "$OUT_DIR"

export PYTHONPATH="$REPO_ROOT/reactor:$REPO_ROOT/control:${PYTHONPATH:-}"

# ── 8. Build the Nuitka argument list ─────────────────────────
#
#   Flags mirrored from build_exe.bat:
#     --lto=yes                  : Link-Time Optimisation (inlines across TUs)
#     --jobs=N                   : Parallel C compilation
#     --deployment               : Strip Nuitka debug guards; leaner, less
#                                  suspicious binary
#     --python-flag=...          : Strip docstrings/asserts/warnings, skip site.py
#     --nofollow-import-to=      : Prune tkinter/test bloat from bundle
#     --include-module=...       : Force-bundle Cython .so extension targets
#     --include-package=...      : Keep orjson / psutil intact
#     --onefile-tempdir-spec=... : Stable named cache dir instead of random
#                                  /tmp/<UUID> - random temp dirs trigger AV
#                                  heuristics on Linux sandboxed distros too
#
# Stable onefile extraction dir: XDG_CACHE_HOME or ~/.cache fallback
ONEFILE_CACHE="${XDG_CACHE_HOME:-$HOME/.cache}/DarionLogicSim/$BASENAME"

NUITKA_ARGS=(
    "--output-dir=$OUT_DIR"
    "--lto=yes"
    "--jobs=$CPU_COUNT"
    "--deployment"
    "--python-flag=no_docstrings"
    "--python-flag=no_warnings"
    "--python-flag=no_asserts"
    "--python-flag=no_site"
    "--nofollow-import-to=tkinter"
    "--nofollow-import-to=unittest"
    "--nofollow-import-to=distutils"
    "--nofollow-import-to=test"
    "--include-module=Circuit"
    "--include-module=Const"
    "--include-module=Gates"
    "--include-module=IC"
    "--include-module=Store"
    "--include-module=Event_Manager"
    "--include-module=Control"
    "--include-package=orjson"
    "--include-package=psutil"
    "--company-name=Farhan"
    "--product-name=Darion Logic Sim"
    "--file-version=1.0.0.0"
    "--product-version=1.0.0.0"
    "--copyright=Farhan"
    "--file-description=Darion Logic Sim"
    "--onefile-tempdir-spec=$ONEFILE_CACHE"
)

# ── 9. BUILD ──────────────────────────────────────────────────
if [[ "$USE_PGO" == "Y" ]]; then
    echo ""
    echo "============================================================"
    echo "[1/3] PGO PASS 1 - Instrumented build (profiling binary)"
    echo "============================================================"

    "$PY_CMD" -m nuitka "${NUITKA_ARGS[@]}" "$BUILD_SWITCH" --pgo-c "$SCRIPT_PATH"

    if [[ ! -f "$TARGET_BIN" ]]; then
        echo "[ERROR] PGO pass 1 failed. Could not find $TARGET_BIN"
        exit 1
    fi

    echo ""
    echo "============================================================"
    echo "[2/3] PGO profiling run embedded in Nuitka pipeline..."
    echo "      Moving to cleanup."
    echo "============================================================"
    LAST_STEP="3/3"
else
    echo ""
    echo "============================================================"
    echo "[1/2] Compiling with Nuitka... (This may take a few minutes)"
    echo "============================================================"

    "$PY_CMD" -m nuitka "${NUITKA_ARGS[@]}" "$BUILD_SWITCH" "$SCRIPT_PATH"

    if [[ ! -f "$TARGET_BIN" ]]; then
        echo "[ERROR] Build failed. Could not find $TARGET_BIN"
        exit 1
    fi
    LAST_STEP="2/2"
fi

# ── 10. Cleanup temp build dirs ───────────────────────────────
echo ""
echo "============================================================"
echo "[$LAST_STEP] Cleaning up temporary build files..."
echo "============================================================"

BUILD_DIR="$OUT_DIR/${BASENAME}.build"
ONEFILE_DIR="$OUT_DIR/${BASENAME}.onefile-build"

if [[ -d "$BUILD_DIR" ]]; then
    echo "Removing: $BUILD_DIR"
    rm -rf "$BUILD_DIR"
fi
if [[ -d "$ONEFILE_DIR" ]]; then
    echo "Removing: $ONEFILE_DIR"
    rm -rf "$ONEFILE_DIR"
fi

echo ""
echo "============================================================"
echo "[SUCCESS] Optimised binary ready!"
echo "Output : $TARGET_BIN"
echo "Flags  : LTO + no_docstrings/asserts/site"
[[ "$USE_PGO" == "Y" ]] && echo "         + PGO-C (profile guided optimisation)"
echo "============================================================"
