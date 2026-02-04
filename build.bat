@echo off
echo Building Cython modules...
python setup.py build_ext --inplace --compiler=mingw32
echo.
pause
