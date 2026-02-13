
# Constants file mirroring Const.pxd/Const.pyx

HIGH = 1
LOW = 0
ERROR = 2
UNKNOWN = 3

DESIGN = 0
SIMULATE = 1
FLIPFLOP = 2

ADD = 1
DELETE = 2
CONNECT = 3
DISCONNECT = 4
PASTE = 5
TOGGLE = 6
SETLIMITS = 7

LIMIT = 100

NOT_ID = 0
AND_ID = 1
NAND_ID = 2
OR_ID = 3
NOR_ID = 4
XOR_ID = 5
XNOR_ID = 6
VARIABLE_ID = 7
PROBE_ID = 8
INPUT_PIN_ID = 9
OUTPUT_PIN_ID = 10
IC_ID = 11
TOTAL = 12

# Alias for backward compatibility if needed, though IC_ID is preferred
IC = IC_ID

# Global Mode
MODE = DESIGN

def set_MODE(mode):
    global MODE
    MODE = mode

def get_MODE():
    global MODE
    return MODE
