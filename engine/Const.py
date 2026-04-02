

HIGH = 1
LOW = 0
ERROR = 2
UNKNOWN = 3

DESIGN = 0
SIMULATE = 1
FLIPFLOP = 2

OSCILLATE = 0.008
VISUALIZE = 0.008

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

# List-based serialization indices
NAME = -1
CUSTOM_NAME = NAME+1
CODE = NAME+2
COMPONENTS = NAME+3
INPUTLIMIT = COMPONENTS
SOURCES = NAME+4
VALUE = SOURCES
MAP = SOURCES
TAG = SOURCES+1
DESCRIPTION = SOURCES+2

MODE = DESIGN
DEBUG= True
def set_MODE(mode):
    global MODE
    MODE = mode

def get_MODE():
    return MODE

def set_DEBUG():
    global DEBUG
    DEBUG=True

def set_timings(fps: float, ratio: float):
    global VISUALIZE, OSCILLATE
    VISUALIZE = fps * (1 - ratio)
    OSCILLATE = fps * ratio

def get_oscillate():
    return OSCILLATE

def get_visualize():
    return VISUALIZE
