from Gates cimport Gate,CPP_Gate,vector
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

cdef object get(int choice, vector[CPP_Gate]& gate_infolist):
    cdef Gate gate
    cdef int location
    if choice==IC_ID:return IC(choice,namelist[choice])
    else:        
        gate = Gate(choice,namelist[choice])
        gate_infolist.emplace_back(CPP_Gate(<void*>gate,choice))
        gate.info = &gate_infolist.back()
        return gate    


cdef tuple decode(object code):
    if len(code) == 2:
        return tuple(code)
    return (code[0], code[1], decode(code[2]))