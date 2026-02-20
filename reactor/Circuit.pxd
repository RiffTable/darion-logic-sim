# distutils: language = c++
from Gates cimport Gate, Variable,Profile
from libcpp.vector cimport vector

ctypedef vector[void*] Queue

cdef void propagate(Gate origin,Queue &readqueue,Queue &writequeue,int wave_limit)
cdef void burn(Gate origin,Queue &readqueue,Queue &writequeue)

cdef class Circuit:
    cdef public list objlist
    cdef public list canvas
    cdef public list varlist
    cdef public list iclist
    cdef public list copydata
    cdef public int counter
    cdef Queue readqueue
    cdef Queue writequeue
    cpdef object getcomponent(self, int choice)
    cpdef object getobj(self, tuple code)
    cpdef void delobj(self, tuple code)
    cpdef void listComponent(self)
    cpdef void listVar(self)
    cpdef bint setlimits(self, Gate gate, int size)
    cpdef void connect(self, Gate target, Gate source, int index)
    cpdef void toggle(self, Variable target, int value)
    cpdef void disconnect(self, Gate target, int index)
    cpdef void hideComponent(self, object gate)
    cpdef void terminate(self, code)
    cpdef void renewComponent(self, object gate)
    cpdef void output(self, Gate gate)
    cpdef str truthTable(self)
    cpdef tuple decode(self, code)
    cpdef void rank_reset(self)
    cpdef void clearcircuit(self)
    cpdef void simulate(self, int Mode)
    cpdef void reset(self)
