from Const cimport NOT as NOT_ID, AND as AND_ID, NAND as NAND_ID, OR as OR_ID, NOR as NOR_ID, XOR as XOR_ID, XNOR as XNOR_ID, VARIABLE as VARIABLE_ID, PROBE as PROBE_ID, INPUT_PIN as INPUT_PIN_ID, OUTPUT_PIN as OUTPUT_PIN_ID, IC as IC_ID
from Gates cimport NOT, AND, NAND, OR, NOR, XOR, XNOR, Variable, Probe, InputPin, OutputPin
from IC import IC

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