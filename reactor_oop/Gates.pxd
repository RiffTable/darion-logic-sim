# distutils: language = c++
from Const cimport HIGH, LOW, UNKNOWN, DESIGN, SIMULATE, MODE
from libc.stdint cimport uint16_t, uint8_t, int8_t
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
        void* target
        uint8_t index
        uint8_t output
        Profile()
        Profile(CPP_Gate* target, uint8_t pin_index, uint8_t output)
    cdef cppclass Task:
        int gate_loc
        unsigned int time
        int location
        Task() nogil
        Task(int gate_loc, unsigned int time, int location) nogil
        bint operator>(const Task& other) nogil
    cdef cppclass CPP_Gate:
        void* gate
        int8_t type
        uint8_t output
        uint8_t inputlimit
        uint8_t flags
        uint8_t book[3]
        uint8_t invalid
        unsigned int target_time
        vector[Profile] hitlist
        CPP_Gate()
        CPP_Gate(void* g, int8_t t, uint8_t lim)

cdef void hide(Profile& profile)
cdef void reveal(Profile& profile,Gate source)
cdef void pop(vector[Profile]& hitlist, CPP_Gate* target, int pin_index)

cdef class Gate:
# --- 4-BYTE ALIGNED (HOT C-TYPES) ---
    cdef public uint8_t id
    cdef public int location       # index into gate_infolist (assigned by Circuit)
    cdef CPP_Gate* info
    
    # --- 8-BYTE ALIGNED (C++ VECTORS) ---
    cdef public list sources
    
    # --- 8-BYTE ALIGNED (COLD PYTHON OBJECTS) ---
    cdef public tuple code
    cdef public str codename
    cdef public str custom_name

    cdef void process(self)
    cpdef void rename(self, str name)

    cdef void connect(self, Gate source, int index)
    cdef void disconnect(self, int index)
    cdef void reset(self)
    cdef void hide(self)
    cdef void reveal(self)
    cpdef bint setlimits(self, int size)
    cpdef str getoutput(self)
    cpdef list full_data(self)
    cpdef list partial_data(self)
    cpdef void clone(self, list dictionary, dict pseudo)
    cpdef void load_to_cluster(self, list cluster)

cdef class Variable(Gate):
    pass

cdef class Probe(Gate):
    pass


cdef class NOT(Gate):
    pass

