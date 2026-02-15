# distutils: language = c++
from libcpp.vector cimport vector
from libcpp.deque cimport deque
from libcpp.unordered_set cimport unordered_set
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, FLIPFLOP, MODE
# from libcpp cimport bool
cdef class Gate
cdef class Variable

# Standalone helper functions

cdef extern from "Profile.h":
    cdef cppclass Profile:
        void* target
        int index
        int output
        Profile()
        Profile(void* target, int pin_index, int output)

ctypedef deque[void*] Queue
ctypedef vector[Profile*] Fuse
# Helper functions for Profile
cdef void create(vector[Profile]& hitlist, Gate target, int pin_index,int output)
cdef void add(vector[Profile]& hitlist, Gate target, int pin_index,int output)
cdef void remove(vector[Profile]& hitlist, Gate target, int pin_index)
cdef void hide(Profile& profile)
cdef void reveal(Profile& profile,Gate source)



# cdef class Profile:
#     cdef public Gate target
#     cdef vector[int] index
#     cdef public int output
#     cdef public bint red_flag

cdef class Gate:
    # Public attributes
    cdef public list sources    
    cdef public int inputlimit
    cdef public int book[4]              
    cdef public int output
    cdef public int prev_output
    
    # Identity
    cdef public int id
    cdef public tuple code
    cdef public str name
    cdef public str custom_name
    
    # Internal logic
    cdef vector[Profile] hitlist

    # Methods
    cdef void process(self)
    cpdef void rename(self, str name)
    cdef bint isready(self)
    cpdef void connect(self, Gate source, int index)
    # cdef void bypass(self)
    # cdef void sync(self)
    # cpdef void propagate(self)
    cpdef void disconnect(self, int index)
    cdef void reset(self)
    cdef void hide(self)
    cdef void reveal(self)
    cpdef bint setlimits(self, int size)
    cpdef str getoutput(self)
    # cdef void purge(self)
    # Serialization / Cloning
    cpdef dict json_data(self)
    cpdef dict copy_data(self, set cluster)
    cdef tuple decode(self, list code)
    cpdef void clone(self, dict dictionary, dict pseudo)
    cpdef void load_to_cluster(self, set cluster)

cdef class Variable(Gate):
    cdef public int value
    cdef void toggle(self, int source)

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