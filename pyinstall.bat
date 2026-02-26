@echo off
SETLOCAL

:: --- CONFIG ---
SET "EXE_NAME=DarionLogicSim"
SET "MAIN_SCRIPT=Testing_script\speed_test.py"
SET "DIST_DIR=f:\darion-logic-sim\dist"

echo [1/3] Cleaning old builds...
if exist build rd /s /q build
if exist %EXE_NAME%.spec del %EXE_NAME%.spec

echo [2/3] Building Executable with Python...
python -m PyInstaller --console --onefile ^
    --name DarionLogicSim ^
    --add-data "reactor;reactor" ^
    --add-data "engine;engine" ^
    --add-data "control;control" ^
    Testing_script\speed_test.py
echo [3/3] Finalizing...
echo Success! Your exe is in %DIST_DIR%