# distutils: language = c++
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, MODE
from libc.stdint cimport uint16_t,uint8_t
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
    cdef cppclass CPP_Gate:
        void* gate
        uint8_t type
        uint8_t output
        uint8_t value
        uint8_t scheduled
        uint16_t inputlimit
        uint16_t book[4]
        vector[Profile] hitlist
        CPP_Gate()
        CPP_Gate(void* g, uint8_t t, uint16_t lim)

cdef void hide(Profile& profile)
cdef void reveal(Profile& profile, Gate source, vector[CPP_Gate]& gate_infolist)
cdef void pop(vector[Profile]& hitlist, int target, int pin_index)

cdef class Gate:
# --- 4-BYTE ALIGNED (HOT C-TYPES) ---
    cdef public uint8_t id
    cdef int info
    
    # --- 8-BYTE ALIGNED (COLD PYTHON OBJECTS) ---
    cdef public list sources
    cdef public tuple code
    cdef public str codename
    cdef public str custom_name

    cdef void process(self, vector[CPP_Gate]& gate_infolist)
    cpdef void rename(self, str name)

    cdef void connect(self, Gate source, int index, vector[CPP_Gate]& gate_infolist)
    cdef void disconnect(self, int index, vector[CPP_Gate]& gate_infolist)
    cdef void reset(self, vector[CPP_Gate]& gate_infolist)
    cdef void hide(self, vector[CPP_Gate]& gate_infolist)
    cdef void reveal(self, vector[CPP_Gate]& gate_infolist)
    cdef bint setlimits(self, int size, vector[CPP_Gate]& gate_infolist)
    cpdef str getoutput(self)
    cdef list full_data(self, vector[CPP_Gate]& gate_infolist)
    cdef list partial_data(self, vector[CPP_Gate]& gate_infolist)
    cdef void clone(self, list dictionary, dict pseudo, vector[CPP_Gate]& gate_infolist)
    cpdef void load_to_cluster(self, list cluster)

cdef class Variable(Gate):
    pass

cdef class Probe(Gate):
    pass


cdef class NOT(Gate):
    pass

