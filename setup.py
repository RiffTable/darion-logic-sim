import os
import sys
import glob
from distutils.core import setup
from Cython.Build import cythonize

# --- CONFIGURATION ---
# Method 1: Compile ALL .pyx files in the current directory
sources = "Super-Engine/*.pyx"

# Method 2: Compile specific files only (uncomment and use this if preferred)
# sources = ["module_a.pyx", "module_b.pyx", "utils.pyx"]

# --- BUILD ---
setup(
    name="My Compiled Modules",
    ext_modules=cythonize(sources, language_level=3),
)

# --- BULK RENAME (OPTIONAL) ---
# This loop finds all compiled extension files with long architecture tags 
# and renames them to the simple "filename.ext" format.
# Files are moved from root directory (where --inplace puts them) to Super-Engine/

print("\n--- Starting Bulk Rename ---")

# Determine file extension based on platform
# Windows: .pyd, Linux/macOS: .so
if sys.platform == "win32":
    ext = ".pyd"
else:
    ext = ".so"

# --inplace creates extension files in the root directory, not in Super-Engine
compiled_files = glob.glob(f"*{ext}")
target_dir = "Super-Engine"

# Ensure target directory exists
os.makedirs(target_dir, exist_ok=True)

for file in compiled_files:
    # Check if the file name looks like a tagged build (e.g., has dots inside)
    # Windows format: module.cp39-win_amd64.pyd
    # Linux format:   module.cpython-39-x86_64-linux-gnu.so
    # macOS format:   module.cpython-39-darwin.so
    basename = os.path.basename(file)
    parts = basename.split(".")
    
    # We expect at least 3 parts: [name, tag, extension] for tagged builds
    if len(parts) >= 3:
        simple_basename = f"{parts[0]}{ext}"
        target_path = os.path.join(target_dir, simple_basename)
        
        try:
            if os.path.exists(target_path):
                os.remove(target_path)  # Remove old version
            os.rename(file, target_path)
            print(f"Renamed & Moved: {file}  ->  {target_path}")
        except OSError as e:
            print(f"Error renaming {file}: {e}")

print("--- Done ---")
