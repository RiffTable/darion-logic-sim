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
    'Variable',
    'NOT',
    'Probe',
    'In',
    'Out',
    'IC',
)

cdef object get(int choice, vector[CPP_Gate]& gate_infolist):
    cdef Gate gate
    cdef uint16_t lim
    cdef IC ic
    if choice==IC_ID:
        ic = IC(choice,namelist[choice])
        ic.gate_infolist_ptr = &gate_infolist
        return ic
    else:
        gate = Gate(choice,namelist[choice])
        lim = 1 if choice >= VARIABLE_ID else 2
        gate_infolist.emplace_back(CPP_Gate(<void*>gate, choice, lim))
        gate.info = gate_infolist.size()-1
        gate.info_ptr = &gate_infolist
        return gate


cdef tuple decode(object code):
    if len(code) == 2:
        return tuple(code)
    return (code[0], code[1], decode(code[2]))