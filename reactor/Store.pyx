from Gates cimport Gate,CPP_Gate,vector,Profile
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
    cdef uint8_t lim
    cdef IC ic
    cdef size_t old_cap, new_size
    cdef CPP_Gate* old_base
    cdef CPP_Gate* new_base
    cdef Py_ssize_t diff
    cdef CPP_Gate* info
    cdef Profile* profile
    cdef Profile* end

    if choice==IC_ID:
        ic = IC(choice,namelist[choice])
        ic.gate_infolist_ptr = &gate_infolist
        ic.gate_verse = gate_verse
        return ic
    else:
        gate = Gate(choice,namelist[choice])
        lim = 1 if choice >= VARIABLE_ID else 2
        
        old_cap = gate_infolist.capacity()
        new_size = gate_infolist.size() + 1
        if new_size > old_cap:
            old_base = gate_infolist.data()
            gate_infolist.reserve(old_cap * 2 if old_cap > 0 else 8)
            new_base = gate_infolist.data()
            diff = new_base - old_base
            
            for g in gate_verse:
                if (<Gate>g).info != NULL:
                    (<Gate>g).info = (<Gate>g).info + diff
                    
            for i in range(gate_infolist.size()):
                info = &gate_infolist[i]
                profile = info.hitlist.data()
                end = profile + info.hitlist.size()
                while profile < end:
                    profile.target = profile.target + diff
                    profile += 1
            
        gate_infolist.emplace_back(CPP_Gate(choice, lim))
        gate.location = gate_infolist.size()-1
        gate.info = &gate_infolist[gate.location]
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