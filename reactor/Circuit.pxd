# distutils: language = c++
from Gates cimport Gate, Variable, Profile, CPP_Gate, vector
from libcpp.vector cimport vector
from Const cimport LIMIT
from IC cimport IC
cdef class Circuit:
    cdef public list objlist
    cdef public list copydata
    cdef public list gate_verse
    cdef public int counter
    cdef public unsigned long long eval_count
    cdef int queue[2][LIMIT]
    cdef vector[CPP_Gate] gate_infolist
    cpdef object getcomponent(self, int choice)
    cpdef object getobj(self, tuple code)
    cpdef list get_components(self)
    cpdef list get_variables(self)
    cpdef list get_ics(self)
    cpdef void listComponent(self)
    cpdef void listVar(self)
    cpdef bint setlimits(self, Gate gate, int size)
    cpdef void optimize(self)
    cpdef void connect(self, Gate target, int source, int index)
    cpdef void toggle(self, int target, int value)
    cpdef void disconnect(self, Gate target, int index)
    cpdef void delobj(self, object obj)
    cpdef IC build_ic(self)
    cpdef IC getIC(self, location)
    cpdef object get_ic(self, str location)
    cpdef IC load_ic(self, list crct)
    cpdef void save_as_ic(self, str location, str ic_name, str tag, str description, list components)
    cpdef void readfromjson(self, str location)
    cpdef void writetojson(self, str location)
    cpdef void refresh(self)
    cpdef void renewobj(self, object obj)
    cpdef void hide(self, list gatelist)
    cpdef void reveal(self, list gatelist)
    cpdef void output(self, Gate gate)
    cpdef void ic_pin_change(self)
    cpdef void reorder(self, object gate, int index)
    cpdef void generate(self, list circuit)
    cdef bytearray table(self,vector[int] &var,vector[int] &gate)
    cpdef str truthTable(self, list variables, list outputs)
    cpdef void rank_reset(self)
    cpdef void clearcircuit(self)
    cpdef void simulate(self, int Mode)
    cpdef void reset(self)
    cpdef void copy(self, list components)
    cpdef list paste(self)
    cpdef void transfer_info(self, Gate gate, int id)
    cdef void turnoff(self, int gate) nogil
    cdef void propagate(self, int origin) nogil
    cdef void burn(self, Py_ssize_t index, Py_ssize_t size, int* read_queue, int* write_queue) nogil
