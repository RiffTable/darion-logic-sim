from Gates cimport Gate,NOT, Variable, Probe
from IC cimport IC
from Const cimport *
cdef tuple namelist=(
    'AND',
    'NAND',
    'OR',
    'NOR',
    'XOR',
    'XNOR',
    'NOT',
    'Variable',
    'Probe',
    'In',
    'Out',
    'IC',
)

cdef object get(int choice):
    if DEBUG:
        if choice==IC_ID:return IC(choice,namelist[choice])
        else:return Gate(choice,namelist[choice])
    else:
        if choice==IC_ID:return IC(choice,None)
        else:return Gate(choice,None)


cdef tuple decode(object code):
    if len(code) == 2:
        return tuple(code)
    return (code[0], code[1], decode(code[2]))