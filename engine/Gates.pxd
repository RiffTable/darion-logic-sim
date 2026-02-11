# distutils: language = c++
# Super-Engine/Gates.pxd
from libcpp.vector cimport vector

# Forward declarations
cdef class Empty
cdef class Gate
cdef class Profile
cdef class Variable
cdef class Probe
cdef class InputPin
cdef class OutputPin
cdef class NOT
cdef class AND
cdef class NAND
cdef class OR
cdef class NOR
cdef class XOR
cdef class XNOR

# Helper functions
cpdef str table(list gatelist, list varlist)
cpdef run(list varlist)
cdef hitlist_del(list hitlist, int index)
cdef int locate(Gate target, list agent_hitlist)
# Profile helper functions (globalized)
cdef add(Profile profile, int pin_index)
cdef bint remove(Profile profile, int pin_index)
cdef hide(Profile profile)
cdef reveal(Profile profile, Gate source)
cdef bint update(Profile profile, int new_output)
cdef bint burn(Profile profile)

cdef class Empty:
    cdef public tuple code
    cdef public int output

cdef class Profile:
    cdef public Gate target
    cdef public vector[int] index
    cdef public int output

cdef class Gate:
    cdef public object sources
    cdef public list hitlist
    cdef public int inputlimit
    cdef public int[4] book
    cdef public int output
    cdef public int prev_output
    cdef public tuple code
    cdef public str name
    cdef public str custom_name
    
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
    cpdef json_data(self)
    cpdef copy_data(self, set cluster)
    cdef decode(self, list code)
    cpdef clone(self, dict dictionary, dict pseudo)
    cpdef load_to_cluster(self, set cluster)

cdef class Variable(Gate):
    cpdef bint setlimits(self, int size)
    cpdef connect(self, Gate source, int index)
    cpdef disconnect(self, int index)
    cdef toggle(self, int source)
    cdef reset(self)
    cdef bint isready(self)
    cdef process(self)
    cpdef json_data(self)
    cpdef clone(self, dict dictionary, dict pseudo)
    cpdef copy_data(self, set cluster)
    cdef hide(self)
    cdef reveal(self)

cdef class Probe(Gate):
    cpdef bint setlimits(self, int size)
    cdef bint isready(self)
    cdef process(self)

cdef class InputPin(Probe):
    cpdef copy_data(self, set cluster)

cdef class OutputPin(Probe):
    cpdef copy_data(self, set cluster)

cdef class NOT(Gate):
    cdef process(self)

cdef class AND(Gate):
    cdef process(self)

cdef class NAND(Gate):
    cdef process(self)

cdef class OR(Gate):
    cdef process(self)

cdef class NOR(Gate):
    cdef process(self)

cdef class XOR(Gate):
    cdef process(self)

cdef class XNOR(Gate):
    cdef process(self)