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
        void* target
        int index
        int output
        Profile()
        Profile(void* target, int pin_index, int output)

cdef void hide(Profile& profile)
cdef void reveal(Profile& profile,Gate source)
cdef void pop(vector[Profile]& hitlist, void* target, int pin_index)

cdef class Gate:
# --- 4-BYTE ALIGNED (HOT C-TYPES) ---
    cdef public uint8_t id
    cdef public uint16_t inputlimit
    cdef public uint8_t output
    cdef public uint8_t value
    cdef public bint scheduled
    
    # --- 4-BYTE ALIGNED CONTINUED (ARRAYS) ---
    cdef public uint16_t book[4]
    
    # --- 8-BYTE ALIGNED (C++ VECTORS) ---
    cdef vector[Profile] hitlist
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

