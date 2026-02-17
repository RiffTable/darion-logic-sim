
from .Gates import NOT, AND, NAND, OR, NOR, XOR, XNOR, Variable, Probe, InputPin, OutputPin
from .IC import IC

# Define the map at the module level for efficiency
_gateobjects = (
    NOT,
    AND,
    OR,
    NAND,
    NOR,
    XOR,
    XNOR,
    Variable,
    Probe,
    InputPin,
    OutputPin,
    IC
)

def get(choice):
    try:
        if 0 <= choice < len(_gateobjects):
            return _gateobjects[choice]()
        return None
    except IndexError:
        return None
