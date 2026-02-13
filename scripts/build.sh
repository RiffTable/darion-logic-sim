#!/bin/bash
set -e

# Change directory to the location of this script
cd "$(dirname "$0")"

echo "Building Cython modules..."
python3 setup.py build_ext --inplace

echo ""
echo "Done!"
