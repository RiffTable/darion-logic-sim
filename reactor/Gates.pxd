# distutils: language = c++
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, MODE

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
    cdef public int id
    cdef public int inputlimit
    cdef public int output
    cdef public bint scheduled
    
    # --- 4-BYTE ALIGNED CONTINUED (ARRAYS) ---
    cdef public list sources
    cdef public int book[4]
    
    # --- 8-BYTE ALIGNED (C++ VECTORS) ---
    cdef vector[Profile] hitlist
    
    # --- 8-BYTE ALIGNED (COLD PYTHON OBJECTS) ---
    cdef public tuple code
    cdef public str name
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
    cpdef dict json_data(self)
    cpdef dict copy_data(self, set cluster)
    cdef tuple decode(self, list code)
    cpdef void clone(self, dict dictionary, dict pseudo)
    cpdef void load_to_cluster(self, set cluster)

cdef class Variable(Gate):
    cdef public int value

cdef class Probe(Gate):
    pass

cdef class InputPin(Probe):
    pass

cdef class OutputPin(Probe):
    pass

cdef class NOT(Gate):
    pass

cdef class AND(Gate):
    pass

cdef class NAND(Gate):
    pass

cdef class OR(Gate):
    pass

cdef class NOR(Gate):
    pass

cdef class XOR(Gate):
    pass

cdef class XNOR(Gate):
    pass