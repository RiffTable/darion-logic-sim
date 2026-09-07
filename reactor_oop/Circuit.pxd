from Gates cimport Gate, Variable, Profile, CPP_Gate, vector, Task
from Const cimport LIMIT
from IC cimport IC

cdef extern from "<queue>" namespace "std" nogil:
    cdef cppclass priority_queue[T, Container=*, Compare=*]:
        priority_queue()
        void push(T&)
        void pop()
        T top()
        bint empty()
        int size()
        void swap(priority_queue& other)

cdef extern from "<functional>" namespace "std" nogil:
    cdef cppclass greater[T]:
        pass

cdef class Circuit:
    cdef public list objlist
    cdef public list copydata
    cdef public int counter
    cdef public unsigned long long eval_count
    cdef public object runner
    cdef priority_queue[Task, vector[Task], greater[Task]] time_queue
    cdef priority_queue[unsigned int, vector[unsigned int], greater[unsigned int]] time_limit
    cdef unsigned int Global_Clock
    cdef CPP_Gate* queue[2][LIMIT]
    cdef void complete_task(self, Task task) nogil
    cpdef object getcomponent(self, int choice)
    cpdef object getobj(self, tuple code)
    cpdef list get_components(self)
    cpdef list get_variables(self)
    cpdef list get_ics(self)
    cpdef void listComponent(self)
    cpdef void listVar(self)
    cpdef bint setlimits(self, Gate gate, int size)
    cpdef void connect(self, Gate target, Gate source, int index)
    cpdef void toggle(self, Gate target, int value)
    cpdef double batch_toggle(self, list batch, int batch_size=*, bint perf_trace=*)
    cpdef void disconnect(self, Gate target, int index)
    cpdef void delobj(self, object gate)
    cpdef IC build_ic(self)
    cpdef IC getIC(self, location)
    cpdef object get_ic(self, str location)
    cpdef IC load_ic(self, list crct)
    cpdef void save_as_ic(self, str location, str ic_name, str tag, str description, list components)
    cpdef void readfromjson(self, str location)
    cpdef void writetojson(self, str location)
    cpdef void renewobj(self, object gate)
    cpdef void hide(self, list gatelist)
    cpdef void reveal(self, list gatelist)
    cpdef void output(self, Gate gate)
    cpdef void ic_pin_change(self)
    cpdef void reorder(self, object gate, int index)
    cpdef void generate(self, list circuit)
    cpdef str truthTable(self, list variables, list outputs)
    cpdef void rank_reset(self)
    cpdef void clearcircuit(self)
    cpdef void simulate(self, int Mode)
    cpdef void custom_simulate(self, list varlist)
    cpdef void reset(self)
    cpdef void copy(self, list components)
    cpdef list paste(self)
    cpdef void transfer_info(self, Gate gate, int id)
    cpdef void optimize(self)
    cpdef list geometry(self)
    cdef void turnoff(self, Gate gate)
    cdef void propagate(self, Gate origin)
    cdef void burn(self, Py_ssize_t index, Py_ssize_t size, CPP_Gate** read_queue, CPP_Gate** write_queue)
