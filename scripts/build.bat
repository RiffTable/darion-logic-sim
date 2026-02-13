@echo off
cd /d %~dp0
echo Building Cython modules...
python setup.py build_ext --inplace --compiler=mingw32
echo.
pause
