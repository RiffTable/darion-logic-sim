@echo off
setlocal EnableDelayedExpansion

cd /d %~dp0

:: ── 0. Parse arguments ───────────────────────────────────────────
set "SOURCE_TARGET=reactor"

:arg_loop
if "%~1"=="" goto arg_done
if "%~1"=="--reactor" (
    set "SOURCE_TARGET=reactor"
    shift
    goto arg_loop
)
if "%~1"=="--reactor_oop" (
    set "SOURCE_TARGET=reactor_oop"
    shift
    goto arg_loop
)
echo [ERROR] Unknown argument: %~1
echo   Usage: %~nx0 [--reactor ^| --reactor_oop]
exit /b 1

:arg_done

echo ============================================================
echo   DARION LOGIC SIM - CYTHON BUILD  (target: !SOURCE_TARGET!)
echo ============================================================
echo.

set "COMPILER="
set "COMPILER_FLAG="

:: ── 1. Try MSVC ──────────────────────────────────────────────────
:: Check 1a: cl.exe already on PATH (Developer Command Prompt)
where cl.exe >nul 2>&1
if !errorlevel! == 0 (
    echo [+] MSVC detected on PATH ^(cl.exe^)
    set "COMPILER=msvc"
    set "COMPILER_FLAG=--compiler=msvc"
    goto :build
)

:: Check 1b: vswhere finds a Visual Studio installation (distutils will find cl.exe itself)
set "VSWHERE="
if exist "%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe" (
    set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
) else if exist "%ProgramFiles%\Microsoft Visual Studio\Installer\vswhere.exe" (
    set "VSWHERE=%ProgramFiles%\Microsoft Visual Studio\Installer\vswhere.exe"
)

if defined VSWHERE (
    for /f "usebackq delims=" %%I in (
        `"!VSWHERE!" -latest -products * -requires Microsoft.VisualCpp.Tools.HostX64.TargetX64 -property installationPath 2^>nul`
    ) do (
        echo [+] MSVC detected via vswhere: %%I
        set "COMPILER=msvc"
        set "COMPILER_FLAG=--compiler=msvc"
        goto :build
    )
    :: Also try without the strict requirement (covers Build Tools installs)
    for /f "usebackq delims=" %%I in (
        `"!VSWHERE!" -latest -products * -property installationPath 2^>nul`
    ) do (
        echo [+] Visual Studio detected via vswhere: %%I
        set "COMPILER=msvc"
        set "COMPILER_FLAG=--compiler=msvc"
        goto :build
    )
)

:: ── 2. Try MinGW-w64 ─────────────────────────────────────────────
where gcc.exe >nul 2>&1
if !errorlevel! == 0 (
    for /f "delims=" %%G in ('where gcc.exe') do (
        echo [+] MinGW-w64 detected: %%G
        set "COMPILER=mingw32"
        set "COMPILER_FLAG=--compiler=mingw32"
        goto :build
    )
)

:: ── 3. Neither found ─────────────────────────────────────────────
echo [ERROR] No C++ compiler found!
echo   Options:
echo     - Install Visual Studio with the "Desktop development with C++" workload
echo     - Install MinGW-w64 and add its bin\ folder to PATH
echo   Then re-run this script.
echo.
pause
exit /b 1

:: ── 4. Build ─────────────────────────────────────────────────────
:build
echo [*] Compiler: !COMPILER!
echo.

python setup.py build_ext --inplace !COMPILER_FLAG! --source-dir "!SOURCE_TARGET!"

if !errorlevel! == 0 (
    echo.
    echo [SUCCESS] Build complete. .pyd files are in !SOURCE_TARGET!\
) else (
    echo.
    echo [FAILED] Build encountered errors ^(see above^).
)

echo.
pause
endlocal
