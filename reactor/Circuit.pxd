# distutils: language = c++
from Gates cimport Gate, Variable, Profile, CPP_Gate, vector, Task
from libcpp.vector cimport vector
from libcpp.deque cimport deque
from Const cimport LIMIT, TOTAL
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
    cdef public list gate_verse
    cdef public int hidden
    cdef public unsigned long long eval_count
    cdef public object runner      # asyncio.Task or None (FLIPFLOP async runner)
    cdef unsigned int Global_Clock
    cdef unsigned int[12] Global_delay
    cdef priority_queue[Task, vector[Task], greater[Task]] time_queue
    cdef deque[int] visual_queue   # C++ deque of dirty gate locations for UI consumer
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
    cpdef void save_as_ic(self, str location, str ic_name, str tag, str description)
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
    cpdef str truthTable(self)
    cpdef void rank_reset(self)
    cpdef void clearcircuit(self)
    cpdef void simulate(self, int Mode)
    cpdef void custom_simulate(self, list varlist)
    cpdef void reset(self)
    cpdef void copy(self, list components)
    cpdef list paste(self)
    cpdef void transfer_info(self, Gate gate, int id)
    cdef void complete_task(self, Task task) nogil
    cdef void propagate(self, int origin) nogil
    cdef void sweep(self, int origin) nogil
    cpdef void batch_toggle(self, list batch)
    cpdef list geometry(self)
    cdef void batch_propagate(self, vector[int] origins) nogil
    cpdef bint visual_queue_empty(self)
    cpdef void visual_queue_clear(self)
    cpdef int pop_visual_queue(self)
    cpdef int visual_queue_size(self)
