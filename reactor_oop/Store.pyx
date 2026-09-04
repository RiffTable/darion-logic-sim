from Gates cimport Gate,CPP_Gate,Profile,vector
from libcpp.vector cimport vector
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
    cdef Gate gate
    if choice==IC_ID:return IC(choice,namelist[choice])
    else:        
        gate = Gate(choice,namelist[choice])
        gate.info.type = choice
        return gate


cdef tuple decode(object code):
    if len(code) == 2:
        return tuple(code)
    return (code[0], code[1], decode(code[2]))