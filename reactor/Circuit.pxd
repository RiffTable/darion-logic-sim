# distutils: language = c++
from Gates cimport Gate, Variable,Profile
from libcpp.vector cimport vector

ctypedef vector[void*] Queue

cdef void propagate(Gate origin,Queue &queue,int wave_limit)
cdef void burn(Queue &queue,int index)

cdef class Circuit:
    cdef public list objlist
    cdef public list copydata
    cdef public int counter
    cdef Queue queue
    cpdef object getcomponent(self, int choice)
    cpdef object getobj(self, tuple code)
    cpdef list get_components(self)
    cpdef list get_variables(self)
    cpdef list get_ics(self)
    cpdef void listComponent(self)
    cpdef void listVar(self)
    cpdef bint setlimits(self, Gate gate, int size)
    cpdef void connect(self, Gate target, Gate source, int index)
    cpdef void toggle(self, Variable target, int value)
    cpdef void disconnect(self, Gate target, int index)
    cpdef void delobj(self, object gate)
    cpdef void renewobj(self, object gate)
    cpdef void hide(self, list gatelist)
    cpdef void reveal(self, list gatelist)
    cpdef void output(self, Gate gate)
    cpdef str truthTable(self)
    cpdef tuple decode(self, code)
    cpdef void rank_reset(self)
    cpdef void clearcircuit(self)
    cpdef void simulate(self, int Mode)
    cpdef void reset(self)
