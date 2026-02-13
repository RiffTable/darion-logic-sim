from Gates cimport NOT, AND, NAND, OR, NOR, XOR, XNOR, Variable, Probe, InputPin, OutputPin
from IC cimport IC

# Define the map at the module level for efficiency
cdef list _gateobjects = [
    NOT,
    AND,
    NAND,
    OR,
    NOR,
    XOR,
    XNOR,
    Variable,
    Probe,
    InputPin,
    OutputPin,
    IC
]

cpdef object get(int choice):
    return _gateobjects[choice]()