# distutils: language = c++
from libcpp.vector cimport vector
from Gates cimport Gate, Profile,CPP_Gate
from libcpp.unordered_map cimport unordered_map
cdef class IC:  
    cdef public list inputs
    cdef public list internal
    cdef public list outputs
    cdef public str codename
    cdef public str custom_name
    cdef public tuple code
    cdef public list map
    cdef public int id
    cdef public str tag
    cdef public str description
    cdef vector[CPP_Gate]* gate_infolist_ptr
    cdef public list gate_verse

    cpdef object getcomponent(self, int choice)
    cpdef void addgate(self, object source)
    cpdef void configure(self, list dictionary)
    cpdef void load_components(self, list dictionary, unordered_map[int,int]& pseudo)
    cpdef list full_data(self)
    cpdef list partial_data(self)
    cpdef void clone(self, unordered_map[int,int]& pseudo)
    cpdef void implement(self, unordered_map[int,int]& pseudo)
    cpdef void hide(self)
    cpdef void reveal(self)
    cpdef void reset(self)
    cpdef void load_to_cluster(self, list cluster)
    cpdef void showinputpins(self)
    cpdef void showoutputpins(self)
    cpdef void info(self)
    # cdef purge(self)
