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
cpdef run(list varlist)
cpdef listdel(lst, index)
cpdef hitlist_del(list hitlist, int index, dict targets_dict)

# Profile helper functions (globalized)
cpdef add(Profile profile, int pin_index)
cpdef bint remove(Profile profile, int pin_index)
cpdef hide(Profile profile)
cpdef reveal(Profile profile)
cpdef bint update(Profile profile)
cpdef bint burn(Profile profile)

cdef class Empty:
    cdef public tuple code
    cdef public dict targets

cdef class Profile:
    cdef public Gate source
    cdef public Gate target
    cdef public vector[int] index
    cdef public int output

cdef class Gate:
    cdef public object sources
    cdef public dict targets
    cdef public list hitlist
    cdef public int inputlimit
    cdef public int[4] book
    cdef public int output
    cdef public int prev_output
    cdef public tuple code
    cdef public str name
    cdef public str custom_name
    
    cpdef process(self)
    cpdef rename(self, str name)
    cpdef bint isready(self)
    cpdef connect(self, Gate source, int index)
    cpdef bypass(self)
    cpdef sync(self)
    cpdef burn(self)
    cpdef propagate(self)
    cpdef disconnect(self, int index)
    cpdef reset(self)
    cpdef hide(self)
    cpdef reveal(self)
    cpdef bint setlimits(self, int size)
    cpdef str getoutput(self)
    cpdef json_data(self)
    cpdef copy_data(self, set cluster)
    cpdef decode(self, list code)
    cpdef clone(self, dict dictionary, dict pseudo)
    cpdef load_to_cluster(self, set cluster)

cdef class Variable(Gate):
    cpdef bint setlimits(self, int size)
    cpdef connect(self, Gate source, int index)
    cpdef disconnect(self, int index)
    cpdef toggle(self, int source)
    cpdef reset(self)
    cpdef bint isready(self)
    cpdef process(self)
    cpdef json_data(self)
    cpdef clone(self, dict dictionary, dict pseudo)
    cpdef copy_data(self, set cluster)
    cpdef hide(self)
    cpdef reveal(self)

cdef class Probe(Gate):
    cpdef bint setlimits(self, int size)
    cpdef bint isready(self)
    cpdef process(self)

cdef class InputPin(Probe):
    cpdef copy_data(self, set cluster)

cdef class OutputPin(Probe):
    cpdef copy_data(self, set cluster)

cdef class NOT(Gate):
    cpdef process(self)

cdef class AND(Gate):
    cpdef process(self)

cdef class NAND(Gate):
    cpdef process(self)

cdef class OR(Gate):
    cpdef process(self)

cdef class NOR(Gate):
    cpdef process(self)

cdef class XOR(Gate):
    cpdef process(self)

cdef class XNOR(Gate):
    cpdef process(self)