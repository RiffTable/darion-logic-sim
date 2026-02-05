import os
import sys
import glob
from setuptools import setup, Extension
from Cython.Build import cythonize

# --- CONFIGURATION ---
source_dir = "engine"
source_files = glob.glob(os.path.join(source_dir, "*.pyx"))

extensions = []

for source in source_files:
    # FIX: Use only the filename ("Gates") instead of the path ("engine.Gates")
    # This avoids the "invalid module name" error caused by the hyphen in "engine"
    module_name = os.path.basename(source)[:-4]
    
    # Determine settings
    if "Gates" in module_name:
        language = "c++"
        link_args = ["-static"] # Bundle C++ DLLs
    else:
        # Const.pyx and test.pyx can be C or C++
        language = "c"
        link_args = []

    ext = Extension(
        module_name, # Name is now just "Gates", "Const", etc.
        sources=[source],
        language=language,
        extra_compile_args=["-O2"],
        extra_link_args=link_args, 
    )
    extensions.append(ext)

# --- BUILD ---
setup(
    name="Logic Sim Compiled",
    ext_modules=cythonize(extensions, compiler_directives={'language_level': "3"}),
)

# --- BULK RENAME & CLEANUP ---
print("\n--- Cleaning up ---")
ext_suffix = ".pyd" if sys.platform == "win32" else ".so"
target_folder = "engine"

# Ensure target directory exists
if not os.path.exists(target_folder):
    os.makedirs(target_folder)

# Move the built files into engine/
for file in glob.glob(f"*{ext_suffix}"):
    basename = os.path.basename(file)
    name_parts = basename.split(".")
    
    if len(name_parts) >= 2:
        # Construct simple name: Gates.pyd
        clean_name = f"{name_parts[0]}{ext_suffix}"
        dest = os.path.join(target_folder, clean_name)
        
        if os.path.exists(dest):
            os.remove(dest)
            
        try:
            os.rename(file, dest)
            print(f"Updated: {dest}")
        except OSError as e:
            print(f"Error moving {file}: {e}")

print("--- Build Complete ---")

# --- CLEANUP C/C++ FILES ---
# Remove generated .c and .cpp files from Cython compilation
print("\n--- Cleaning up C/C++ files ---")

# Look for C/C++ files in the same location as .pyx files
c_files = glob.glob("engine/*.c") + glob.glob("engine/*.cpp")
# Also check root directory in case any were generated there
c_files += glob.glob("*.c") + glob.glob("*.cpp")

for c_file in c_files:
    try:
        os.remove(c_file)
        print(f"Removed: {c_file}")
    except OSError as e:
        print(f"Error removing {c_file}: {e}")

print("--- Cleanup Done ---")
