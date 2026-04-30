

HIGH = 1
LOW = 0
ERROR = 2
UNKNOWN = 2
PRIMARY = 2

DESIGN = 0
SIMULATE = 1
COMPILE = 3

LIMIT = 500_000

AND_ID = 0
NAND_ID = 1
OR_ID = 2
NOR_ID = 3
XOR_ID = 4
XNOR_ID = 5
VARIABLE_ID = 6
NOT_ID = 7
PROBE_ID = 8
INPUT_PIN_ID = 9
OUTPUT_PIN_ID = 10
IC_ID = 11
TOTAL = 12

# List-based serialization indices  (reactor-compatible)
# Gate / IC row layout: [custom_name, id, location, inputlimit, sources_or_value]
CUSTOM_NAME = 0
ID          = 1
LOCATION    = 2
INPUTLIMIT  = 3
SOURCES     = 4
VALUE       = SOURCES

# IC row layout: [custom_name, IC_ID, code, tag, map, description]
MAP         = 4
TAG         = 3
DESCRIPTION = 5

# Legacy aliases kept so nothing else breaks
CODE        = 2
COMPONENTS  = MAP

MODE = DESIGN
DEBUG= True
DELAY = 0.01

def set_MODE(mode):
    global MODE
    MODE = mode

def get_MODE():
    return MODE

def set_DEBUG():
    global DEBUG
    DEBUG=True

def set_DELAY(delay):
    global DELAY
    DELAY = delay

def get_DELAY():
    return DELAY
