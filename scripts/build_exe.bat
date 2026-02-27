@echo off
setlocal EnableDelayedExpansion

echo ============================================================
echo   BLAZING FAST PYTHON TO EXE CONVERTER (Nuitka v2 - PGO)
echo ============================================================
echo.

:: ---------------------------------------------------------------
:: 1. Script selection
:: ---------------------------------------------------------------
set /p "SCRIPT_PATH=Enter the path to your Python script (e.g., Testing_script\speed_test.py): "

:: Remove quotes (drag-and-drop)
set "SCRIPT_PATH=!SCRIPT_PATH:"=!"

if not exist "!SCRIPT_PATH!" (
    echo [ERROR] File "!SCRIPT_PATH!" not found!
    pause
    exit /b 1
)

:: Extract basename
for %%f in ("!SCRIPT_PATH!") do set "BASENAME=%%~nf"

:: ---------------------------------------------------------------
:: 2. Build type
:: ---------------------------------------------------------------
echo.
echo Choose build type:
echo [1] Standalone  ^(folder + .exe - fastest startup, easiest to debug^)
echo [2] Onefile     ^(single .exe   - portable, ~1s extraction overhead^)
set /p BUILD_TYPE="Enter 1 or 2: "

:: ---------------------------------------------------------------
:: 3. PGO?
:: ---------------------------------------------------------------
echo.
echo Enable Profile Guided Optimization? ^(recommended - 10-30%% speed boost^)
echo [Y] Yes - compile twice, guided by a live benchmark run
echo [N] No  - single-pass compile, faster build time
set /p USE_PGO="Enter Y or N: "

:: ---------------------------------------------------------------
:: 4. Python / Nuitka runtime selector
:: ---------------------------------------------------------------
if exist ".venv\Scripts\python.exe" (
    set "PY_CMD=.venv\Scripts\python.exe"
) else (
    set "PY_CMD=python"
)

:: ---------------------------------------------------------------
:: 5. Detect logical CPU count for parallel C jobs
:: ---------------------------------------------------------------
for /f "tokens=2 delims==" %%C in (
    'wmic cpu get NumberOfLogicalProcessors /value 2^>nul ^| findstr "="'
) do set "CPU_COUNT=%%C"
if not defined CPU_COUNT set "CPU_COUNT=4"

echo.
echo [Config] C compiler jobs: !CPU_COUNT!

:: ---------------------------------------------------------------
:: 6. Output dirs and paths
:: ---------------------------------------------------------------
set "OUT_DIR=blazing_builds"

if /i "!BUILD_TYPE!"=="1" (
    set "BUILD_SWITCH=--standalone"
    set "TARGET_EXE=!OUT_DIR!\!BASENAME!.dist\!BASENAME!.exe"
) else if /i "!BUILD_TYPE!"=="2" (
    set "BUILD_SWITCH=--onefile"
    set "TARGET_EXE=!OUT_DIR!\!BASENAME!.exe"
) else (
    echo [ERROR] Invalid choice.
    pause
    exit /b 1
)

:: ---------------------------------------------------------------
:: 7. Build the Nuitka args string incrementally
::    (avoids cmd.exe mis-parsing of = signs inside ^ blocks)
::
::  --lto=yes                  : Link-Time Optimisation (inlines across TUs)
::  --jobs=N                   : Parallel C compilation (MSVC auto-selected)
::  --deployment               : Strip Nuitka debug guards / self-checks;
::                               produces a leaner, less suspicious binary
::  --python-flag=...          : Strip docstrings/asserts/warnings, skip site.py
::  --nofollow-import-to=      : Prune tkinter/test bloat from bundle
::  --include-module=...       : Force-bundle Cython .pyd extension targets
::  --include-package=...      : Keep orjson / psutil intact
::  --onefile-tempdir-spec=... : Extract to a STABLE named folder, NOT a random
::                               %TEMP%\<UUID> path - random UUID temp dirs are
::                               the #1 heuristic trigger for Windows Defender
:: ---------------------------------------------------------------
set "PYTHONPATH=%cd%\reactor;%cd%\control;%PYTHONPATH%"

set "N=--output-dir=!OUT_DIR!"
set "N=!N! --lto=yes"
set "N=!N! --jobs=!CPU_COUNT!"
set "N=!N! --python-flag=no_docstrings"
set "N=!N! --python-flag=no_warnings"
set "N=!N! --python-flag=no_asserts"
set "N=!N! --python-flag=no_site"
set "N=!N! --nofollow-import-to=tkinter"
set "N=!N! --nofollow-import-to=unittest"
set "N=!N! --nofollow-import-to=distutils"
set "N=!N! --nofollow-import-to=test"
set "N=!N! --include-module=Circuit"
set "N=!N! --include-module=Const"
set "N=!N! --include-module=Gates"
set "N=!N! --include-module=IC"
set "N=!N! --include-module=Store"
set "N=!N! --include-module=Event_Manager"
set "N=!N! --include-module=Control"
set "N=!N! --include-package=orjson"
set "N=!N! --include-package=psutil"
set "N=!N! --company-name=Farhan"
set "N=!N! --product-name=Darion Logic Sim"
set "N=!N! --file-version=1.0.0.0"
set "N=!N! --product-version=1.0.0.0"
set "N=!N! --copyright=Farhan"
set "N=!N! --file-description=Darion Logic Sim"
set "N=!N! --deployment"
::
:: --onefile-tempdir-spec: stable extraction path avoids random %TEMP%\<UUID>
:: pattern that Windows Defender flags as suspicious. Uses %LOCALAPPDATA% which
:: is a known, permanent, user-writable location AV tools treat as safe.
set "N=!N! --onefile-tempdir-spec=%%LOCALAPPDATA%%\DarionLogicSim\!BASENAME!"

:: ---------------------------------------------------------------
:: 8. BUILD
:: ---------------------------------------------------------------

:: ------------------------------------------------------------------
:: Nuitka C-level PGO is INCOMPATIBLE with --onefile / --standalone:
:: the instrumented intermediate binary is not a valid Win32 app at
:: that stage and crashes.  Auto-fall-back to LTO-only compile.
:: (Two flat if..if guards - no nested ^() inside () blocks, which
::  would be eaten by cmd's block-parser and cause "unexpected" errors)
:: ------------------------------------------------------------------
if /i "!USE_PGO!"=="Y" if /i "!BUILD_SWITCH!"=="--onefile" (
    echo.
    echo [WARNING] C-level PGO is NOT supported with --onefile mode.
    echo           The intermediate PGO binary is not a valid Win32 app.
    echo           Falling back to standard LTO-only compile.
    set "USE_PGO=N"
)
if /i "!USE_PGO!"=="Y" if /i "!BUILD_SWITCH!"=="--standalone" (
    echo.
    echo [WARNING] C-level PGO is NOT supported with --standalone mode.
    echo           Falling back to standard LTO-only compile.
    set "USE_PGO=N"
)

if /i "!USE_PGO!"=="Y" (
    echo.
    echo ============================================================
    echo [1/4] PGO PASS 1 - Instrumented build ^(profiling binary^)
    echo ============================================================

    !PY_CMD! -m nuitka !N! !BUILD_SWITCH! --pgo-c "!SCRIPT_PATH!"

    if not exist "!TARGET_EXE!" (
        echo [ERROR] PGO pass 1 failed. Could not find !TARGET_EXE!
        pause
        exit /b 1
    )

    echo.
    echo ============================================================
    echo [2/4] PGO profiling run embedded in Nuitka pipeline...
    echo       Moving to optimised relink.
    echo ============================================================

    echo.
    echo ============================================================
    echo [3/4] BUILD COMPLETE - applying Segment Heap manifest...
    echo ============================================================
) else (
    echo.
    echo ============================================================
    echo [1/3] Compiling with Nuitka... ^(This may take a few minutes^)
    echo ============================================================

    !PY_CMD! -m nuitka !N! !BUILD_SWITCH! "!SCRIPT_PATH!"

    if not exist "!TARGET_EXE!" (
        echo [ERROR] Build failed. Could not find !TARGET_EXE!
        pause
        exit /b 1
    )

    echo.
    echo ============================================================
    echo [2/3] Applying Segment Heap manifest...
    echo ============================================================
)

:: ---------------------------------------------------------------
:: 9. Inject Windows manifest (SegmentHeap + DPI-aware + longPathAware)
:: ---------------------------------------------------------------
::
::  DarionHeap.manifest lives at the repo root and is committed to source.
::  It enables:
::    - SegmentHeap       : low-fragmentation allocator (Win10 1809+)
::    - dpiAwareness      : PerMonitorV2 - no DWM scaling overhead
::    - longPathAware     : avoids \\?\  path-normalization overhead
::
::  If the file is missing it is regenerated from the hardcoded XML below.
:: ---------------------------------------------------------------
set "MANIFEST_FILE=%~dp0..\DarionHeap.manifest"

if not exist "!MANIFEST_FILE!" (
    echo [INFO] DarionHeap.manifest not found - regenerating from embedded XML...
    echo ^<?xml version="1.0" encoding="UTF-8" standalone="yes"?^>                               > "!MANIFEST_FILE!"
    echo ^<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0"^>             >> "!MANIFEST_FILE!"
    echo   ^<application xmlns="urn:schemas-microsoft-com:asm.v3"^>                              >> "!MANIFEST_FILE!"
    echo     ^<windowsSettings^>                                                                  >> "!MANIFEST_FILE!"
    echo       ^<heapType xmlns="http://schemas.microsoft.com/SMI/2020/WindowsSettings"^>SegmentHeap^</heapType^>     >> "!MANIFEST_FILE!"
    echo       ^<dpiAware xmlns="http://schemas.microsoft.com/SMI/2005/WindowsSettings"^>true/PM^</dpiAware^>         >> "!MANIFEST_FILE!"
    echo       ^<dpiAwareness xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings"^>PerMonitorV2^</dpiAwareness^> >> "!MANIFEST_FILE!"
    echo       ^<longPathAware xmlns="http://schemas.microsoft.com/SMI/2016/WindowsSettings"^>true^</longPathAware^>  >> "!MANIFEST_FILE!"
    echo     ^</windowsSettings^>                                                                 >> "!MANIFEST_FILE!"
    echo   ^</application^>                                                                       >> "!MANIFEST_FILE!"
    echo ^</assembly^>                                                                            >> "!MANIFEST_FILE!"
    echo [OK] Regenerated !MANIFEST_FILE!
)

:: --- Locate mt.exe: PATH first, then known SDK path, then full search ---
set "MT_EXE="
for /f "delims=" %%I in ('where mt.exe 2^>nul') do (
    if not defined MT_EXE set "MT_EXE=%%I"
)

if not defined MT_EXE (
    set "TYPICAL_MT=C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64\mt.exe"
    if exist "!TYPICAL_MT!" set "MT_EXE=!TYPICAL_MT!"
)

if not defined MT_EXE (
    echo Searching for mt.exe in Windows Kits...
    for /f "delims=" %%I in ('powershell -NoProfile -Command ^
        "$x=Get-ChildItem 'C:\Program Files (x86)\Windows Kits' -Filter mt.exe -Recurse -EA SilentlyContinue ^| Where-Object {$_.FullName -match '\\x64\\'} ^| Sort-Object FullName -Desc ^| Select-Object -First 1; if($x){$x.FullName}"') do set "MT_EXE=%%I"
)

if defined MT_EXE (
    echo Found mt.exe : !MT_EXE!
    echo Manifest     : !MANIFEST_FILE!
    "!MT_EXE!" -manifest "!MANIFEST_FILE!" -outputresource:"!TARGET_EXE!";1
    if !errorlevel! equ 0 (
        echo [OK] Manifest injected into !TARGET_EXE!
    ) else (
        echo [WARNING] mt.exe returned error !errorlevel! - check manifest XML.
    )
) else (
    echo [WARNING] mt.exe not found. Skipping manifest injection.
    echo           Install Windows 10 SDK to enable SegmentHeap optimisation.
)

:skip_manifest

:: ---------------------------------------------------------------
:: 10. Cleanup temp build dirs
:: ---------------------------------------------------------------
set "LAST_STEP=3/3"
if /i "!USE_PGO!"=="Y" set "LAST_STEP=4/4"

echo.
echo ============================================================
echo [!LAST_STEP!] Cleaning up temporary build files...
echo ============================================================

set "BUILD_DIR=!OUT_DIR!\!BASENAME!.build"
set "ONEFILE_DIR=!OUT_DIR!\!BASENAME!.onefile-build"

if exist "!BUILD_DIR!" (
    echo Removing: !BUILD_DIR!
    rd /s /q "!BUILD_DIR!"
)
if exist "!ONEFILE_DIR!" (
    echo Removing: !ONEFILE_DIR!
    rd /s /q "!ONEFILE_DIR!"
)

echo.
echo ============================================================
echo [SUCCESS] Optimised EXE ready!
echo Output : !TARGET_EXE!
echo Flags  : LTO + no_docstrings/asserts/site
if /i "!USE_PGO!"=="Y" echo          + PGO-C ^(profile guided optimisation^)
echo ============================================================
pause