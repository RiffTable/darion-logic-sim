# distutils: language = c++
from Gates cimport Gate, Variable

cdef class Circuit:
    cdef public list objlist
    cdef public list canvas
    cdef public list varlist
    cdef public list iclist
    cdef public list copydata

    cpdef getcomponent(self, int choice)
    cpdef getobj(self, tuple code)
    cpdef delobj(self, tuple code)
    cpdef listComponent(self)
    cpdef listVar(self)
    cpdef setlimits(self, Gate gate, int size)
    cpdef connect(self, Gate target, Gate source, int index)
    cpdef toggle(self, Variable target, int value)
    cpdef disconnect(self, Gate target, int index)
    cpdef hideComponent(self, object gate)
    cpdef terminate(self, code)
    cpdef renewComponent(self, object gate)
    cpdef output(self, Gate gate)
    cpdef truthTable(self)
    cpdef decode(self, code)
    cpdef rank_reset(self)
    cpdef clearcircuit(self)
    cpdef simulate(self, int Mode)
    cpdef reset(self)
