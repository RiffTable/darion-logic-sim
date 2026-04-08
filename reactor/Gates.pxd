# distutils: language = c++
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, MODE
from libc.stdint cimport uint16_t,uint8_t,int8_t
from libcpp.unordered_map cimport unordered_map
cdef extern from "<vector>" namespace "std" nogil:
    cdef cppclass vector[T, ALLOCATOR=*]:
        cppclass iterator:
            T& operator*()
            iterator operator++()
            bint operator!=(iterator)
            bint operator==(iterator)
            
        vector()
        
        T& operator[](int)
        T& at(int)
        T& front()
        T& back()           
        T* data()           

        void push_back(T&)
        void emplace_back(...)  
        void pop_back()         
        void clear()
        void reserve(int)
        void resize(int)
        
        bint empty()
        int size()
        int capacity()
        iterator begin()
        iterator end()

cdef class Gate
cdef class Variable

cdef extern from "Profile.h":
    cdef cppclass Profile:
        int target
        int index
        int output
        Profile()
        Profile(int target, int pin_index, int output)
    cdef cppclass Task:
        int gate_loc
        unsigned int time
        int location
        Task() nogil
        Task(int gate_loc, unsigned int time, int location) nogil
        bint operator>(const Task& other) nogil
    cdef cppclass CPP_Gate:
        int8_t type
        uint8_t output
        uint8_t value
        uint8_t scheduled
        uint8_t mark
        uint8_t update
        uint16_t inputlimit
        uint16_t book[4]
        vector[Profile] hitlist
        CPP_Gate()
        CPP_Gate(uint8_t t, uint16_t lim)

cdef void hide(Profile& profile, CPP_Gate* gate_infolist, list gate_verse)
cdef void reveal(Profile& profile, Gate source, list gate_verse)
cdef void pop(vector[Profile]& hitlist, CPP_Gate* gate_infolist, int target, int pin_index)

cdef class Gate:
# --- 4-BYTE ALIGNED (HOT C-TYPES) ---
    cdef public int8_t id
    cdef public int location
    cdef vector[CPP_Gate]* location_ptr
    # --- 8-BYTE ALIGNED (COLD PYTHON OBJECTS) ---
    cdef public list _sources
    cdef public list gate_verse
    cdef public tuple code
    cdef public str codename
    cdef public str custom_name

    cdef void process(self)
    cpdef void rename(self, str name)
    cpdef void deregister(self)
    cdef void connect(self, int source, int index)
    cdef void disconnect(self, int index)
    cdef void reset(self)
    cdef void hide(self)
    cdef void reveal(self)
    cpdef bint setlimits(self, int size)
    cpdef str getoutput(self)
    cpdef list full_data(self)
    cpdef list partial_data(self)
    cdef void clone(self, list dictionary, unordered_map[int,int]& pseudo)
    cpdef void load_to_cluster(self, list cluster)
    cpdef bint set_pulse(self, int val, int time_type)
    cpdef bint clock(self)

cdef class Variable(Gate):
    pass

cdef class Probe(Gate):
    pass


cdef class NOT(Gate):
    pass

