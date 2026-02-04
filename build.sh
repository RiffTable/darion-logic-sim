#!/bin/bash
echo "Building Cython modules..."
python3 setup.py build_ext --inplace
echo ""
echo "Done!"
