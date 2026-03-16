# distutils: language = c++
from libcpp.vector cimport vector
from Gates cimport Gate, Profile,CPP_Gate

cdef class IC:
    cdef public list inputs
    cdef public list internal
    cdef public list outputs
    cdef public str codename
    cdef public str custom_name
    cdef public tuple code
    cdef public list map
    cdef public int id
    cdef public int counter
    cdef public str tag
    cdef public str description
    cdef vector[CPP_Gate] gate_infolist

    cpdef object getcomponent(self, int choice)
    cpdef void addgate(self, object source)
    cpdef void configure(self, list dictionary)
    cpdef void load_components(self, list dictionary, dict pseudo)
    cpdef list full_data(self)
    cpdef list partial_data(self)
    cpdef void clone(self, dict pseudo)
    cpdef void implement(self, dict pseudo)
    cpdef void hide(self)
    cpdef void reveal(self)
    cpdef void reset(self)
    cpdef void load_to_cluster(self, list cluster)
    cpdef void showinputpins(self)
    cpdef void showoutputpins(self)
    cpdef void info(self)
    # cdef purge(self)
