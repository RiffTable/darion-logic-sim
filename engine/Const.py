

HIGH = 1
LOW = 0
ERROR = 2
UNKNOWN = 3

DESIGN = 0
SIMULATE = 1


UI_MODE = False

LIMIT = 100

AND_ID = 0
NAND_ID = 1
OR_ID = 2
NOR_ID = 3
XOR_ID = 4
XNOR_ID = 5
NOT_ID = 6
VARIABLE_ID = 7
PROBE_ID = 8
INPUT_PIN_ID = 9
OUTPUT_PIN_ID = 10
IC_ID = 11
TOTAL = 12

# List-based serialization indices
NAME = -1
CUSTOM_NAME = NAME+1
CODE = NAME+2
COMPONENTS = NAME+3
INPUTLIMIT = COMPONENTS
SOURCES = NAME+4
VALUE = SOURCES
MAP = SOURCES

MODE = DESIGN

def set_MODE(mode):
    global MODE
    MODE = mode

def get_MODE():
    return MODE

def set_UI_MODE(mode):
    global UI_MODE
    UI_MODE = mode

def get_UI_MODE():
    return UI_MODE
