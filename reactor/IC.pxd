# distutils: language = c++
from libcpp.vector cimport vector
from Gates cimport Gate, InputPin, OutputPin, Profile

cdef class IC:
    cdef public list inputs
    cdef public list internal
    cdef public list outputs
    cdef public str name
    cdef public str custom_name
    cdef public tuple code
    cdef public list map
    cdef public int id
    cdef public int counter

    cpdef getcomponent(self, int choice)
    cpdef addgate(self, object source)
    cpdef configure(self, dict dictionary)
    cdef decode(self, list code)
    cpdef load_components(self, dict dictionary, dict pseudo)
    cpdef json_data(self)
    cpdef clone(self, dict pseudo)
    cpdef load_to_cluster(self, set cluster)
    cpdef copy_data(self, set cluster)
    cpdef implement(self, dict pseudo)
    cpdef hide(self)
    cpdef reveal(self)
    cpdef reset(self)
    cpdef showinputpins(self)
    cpdef showoutputpins(self)
    cpdef info(self)
    # cdef purge(self)
