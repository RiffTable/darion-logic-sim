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

cdef object get(int choice, vector[CPP_Gate]& gate_infolist, list gate_verse):
    '''Get a gate of a given type and add it to the gate_infolist and gate_verse
    for ICs, it does not add to gate_infolist or gate_verse, but instead just returns an IC object'''
    cdef Gate gate
    cdef uint16_t lim
    cdef IC ic
    if choice==IC_ID:
        ic = IC(choice,namelist[choice])
        ic.gate_infolist_ptr = &gate_infolist
        ic.gate_verse = gate_verse
        return ic
    else:
        gate = Gate(choice,namelist[choice])
        lim = 1 if choice >= VARIABLE_ID else 2
        gate_infolist.emplace_back(CPP_Gate(choice, lim))
        gate.location = gate_infolist.size()-1
        gate.location_ptr = &gate_infolist
        gate.gate_verse = gate_verse
        gate_verse.append(gate)
        return gate


cdef tuple decode(object code):
    '''Decode a gate code into a tuple of (gate_type, gate_rank, ic_code) or 
    (gate_type, gate_location, ic_code) for ICs
    this is used to reconstruct gates from serialised data'''
    if len(code) == 2:
        return tuple(code)
    return (code[0], code[1], decode(code[2]))