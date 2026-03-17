import faulthandler
faulthandler.enable()

import sys
import os

base_dir = os.getcwd()
sys.path.insert(0, os.path.join(base_dir, 'reactor'))
sys.path.insert(0, os.path.join(base_dir, 'control'))

from Gates import Gate
import Const

print("Creating Gate...")
g = Gate(2, 'AND')
print("Gate created.")

try:
    print("Accessing output...")
    out = g.output
    print("Output:", out)
except Exception as e:
    print("Exception:", e)
