from Gates cimport NOT, AND, NAND, OR, NOR, XOR, XNOR, Variable, Probe, InputPin, OutputPin
from IC cimport IC


cdef tuple _gateobjects = (
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
    IC
)

cdef object get(int choice):
    return _gateobjects[choice]()

cdef tuple decode(object code):
    if len(code) == 2:
        return tuple(code)
    return (code[0], code[1], decode(code[2]))