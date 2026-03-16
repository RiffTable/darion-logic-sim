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
    cdef uint16_t lim
    if choice==IC_ID:return IC(choice,namelist[choice])
    else:
        gate = Gate(choice,namelist[choice])
        # inputlimit: gates with id >= VARIABLE_ID are single-input (1), others are 2
        lim = 1 if choice >= VARIABLE_ID else 2
        gate_infolist.emplace_back(CPP_Gate(<void*>gate, choice, lim))
        gate.info = gate_infolist.size()-1
        return gate


cdef tuple decode(object code):
    if len(code) == 2:
        return tuple(code)
    return (code[0], code[1], decode(code[2]))