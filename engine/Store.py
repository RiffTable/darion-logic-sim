
from Gates import AND, NAND, OR, NOR, XOR, XNOR, NOT, Variable, Probe, In, Out
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
    In,
    Out,
    IC,
)

def get(choice):
    return _gateobjects[choice]()
