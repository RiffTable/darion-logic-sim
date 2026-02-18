from Gates cimport NOT, AND, NAND, OR, NOR, XOR, XNOR, Variable, Probe, InputPin, OutputPin
from IC cimport IC

# Define the map at the module level for efficiency
cdef tuple _gateobjects = (
    NOT,
    AND,
    OR,
    XOR,
    NAND,
    NOR,
    XNOR,
    Variable,
    Probe,
    InputPin,
    OutputPin,
    IC
)

cdef object get(int choice):
    return _gateobjects[choice]()