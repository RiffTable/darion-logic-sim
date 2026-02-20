
from Gates import AND, NAND, OR, NOR, XOR, XNOR, NOT, Variable, Probe, InputPin, OutputPin
from IC import IC


_gateobjects = (
    AND,
    NAND,
    OR,
    NOR,
    XOR,
    XNOR,
    NOT,
    Variable,
    Probe,
    InputPin,
    OutputPin,
    IC,
)

def get(choice):
    return _gateobjects[choice]()
