import os
import sys
import glob
from setuptools import setup, Extension
from Cython.Build import cythonize
import sysconfig

# --- CONFIGURATION ---
# Adjusted for running from scripts/ directory
source_dir = "../reactor"
source_files = glob.glob(os.path.join(source_dir, "*.pyx"))

extensions = []

for source in source_files:
    module_name = os.path.splitext(os.path.basename(source))[0]
    
    # Determine settings
    if "Gates" in module_name or "Circuit" in module_name:
        language = "c++"
        if sys.platform == "win32":
            link_args = ["-static"] # Bundle C++ DLLs
        else:
            link_args = []
    else:
        # Const.pyx and test.pyx can be C or C++
        language = "c"
        link_args = []

    ext = Extension(
        module_name,
        sources=[source],
        language=language,
        include_dirs=[source_dir], # Make sure it finds headers in reactor/
        extra_compile_args=["-O2"],
        extra_link_args=link_args, 
    )
    extensions.append(ext)

# --- BUILD ---
setup(
    name="Logic Sim Compiled",
    ext_modules=cythonize(extensions, compiler_directives={'language_level': "3"}, annotate=True),
)

# --- CLEANUP & MOVE ---
print("\n--- Cleaning up ---")
generated_suffix = sysconfig.get_config_var("EXT_SUFFIX") or (".pyd" if sys.platform == "win32" else ".so")
target_suffix = ".pyd" if sys.platform == "win32" else ".so"
target_folder = "../reactor"  # Keep compiled binaries in reactor folder

# Move the built files into reactor/
# They might be built in the current directory (scripts/) due to inplace build
for file in glob.glob(f"*{generated_suffix}"):
    basename = os.path.basename(file)
    # python 3 names have tag info e.g. .cp311-win_amd64.pyd
    # We want simple X.pyd
    simple_name = basename.split(".")[0] + target_suffix
    
    dest = os.path.join(target_folder, simple_name)
    
    if os.path.exists(dest):
        os.remove(dest)
        
    try:
        os.rename(file, dest)
        print(f"Moved: {file} -> {dest}")
    except OSError as e:
        print(f"Error moving {file}: {e}")

print("--- Build Complete ---")

# --- CLEANUP C/C++ FILES ---
print("\n--- Cleaning up C/C++ files & Reports ---")
c_files = glob.glob(os.path.join(source_dir, "*.c")) + glob.glob(os.path.join(source_dir, "*.cpp"))
html_files = glob.glob(os.path.join(source_dir, "*.html"))
c_files += glob.glob("*.c") + glob.glob("*.cpp")
html_files += glob.glob("*.html")

for html_file in html_files:
    try:
        os.remove(html_file)
        print(f"Removed Report: {html_file}")
    except OSError as e:
        print(f"Error removing {html_file}: {e}")

for c_file in c_files:
    try:
        os.remove(c_file)
        print(f"Removed Source: {c_file}")
    except OSError as e:
        print(f"Error removing {c_file}: {e}")

print("--- Cleanup Done ---")
