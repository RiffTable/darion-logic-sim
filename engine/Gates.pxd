# distutils: language = c++
from libcpp.vector cimport vector
from libcpp.deque cimport deque
from libcpp.unordered_set cimport unordered_set
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, FLIPFLOP, MODE

# Forward declarations to handle circular references
cdef class Gate
cdef class Profile
cdef class Variable

# Standalone helper functions
cpdef run(list varlist)
cpdef str table(list gatelist, list varlist)

# Helper functions for Profile
cdef hitlist_del(vector[void*]& hitlist, int index)
cdef int locate(Gate target, vector[void*]& agent_hitlist)
cdef create(vector[void*]& hitlist, Gate target, int pin_index,int output)
cdef add(Profile profile, int pin_index)
cdef remove(Profile profile, int pin_index)
cdef hide(Profile profile)
cdef reveal(Profile profile,Gate source)
cdef bint update(Profile profile, int new_output)
cdef void clear_fuse()


cdef class Empty:
    cdef public tuple code
    cdef public int output

cdef class Profile:
    cdef public Gate target
    cdef vector[int] index
    cdef public int output
    cdef public bint red_flag

cdef class Gate:
    # Public attributes
    cdef public object sources    # Generic object to handle list[Gate] or int (for Variable)
    cdef public int inputlimit
    cdef public int book[4]              # Fixed-size array for signal counts
    cdef public int output
    cdef public int prev_output
    
    # Identity
    cdef public tuple code
    cdef public str name
    cdef public str custom_name
    
    # Internal logic
    cdef vector[void*] hitlist

    # Methods
    cdef process(self)
    cpdef rename(self, str name)
    cdef bint isready(self)
    cpdef connect(self, Gate source, int index)
    cdef bypass(self)
    cdef sync(self)
    cdef burn(self)
    cpdef propagate(self)
    cpdef disconnect(self, int index)
    cdef reset(self)
    cdef hide(self)
    cdef reveal(self)
    cpdef bint setlimits(self, int size)
    cpdef str getoutput(self)
    cdef purge(self)
    # Serialization / Cloning
    cpdef json_data(self)
    cpdef copy_data(self, set cluster)
    cdef decode(self, list code)
    cpdef clone(self, dict dictionary, dict pseudo)
    cpdef load_to_cluster(self, set cluster)

cdef class Variable(Gate):
    cdef toggle(self, int source)

cdef class Probe(Gate):
    pass

cdef class InputPin(Probe):
    pass

cdef class OutputPin(Probe):
    pass

# Logic Gates
cdef class NOT(Gate):
    pass

cdef class AND(Gate):
    pass

cdef class NAND(Gate):
    pass

cdef class OR(Gate):
    pass

cdef class NOR(Gate):
    pass

cdef class XOR(Gate):
    pass

cdef class XNOR(Gate):
    pass