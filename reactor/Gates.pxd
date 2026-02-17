# distutils: language = c++
from libcpp.deque cimport deque
from libcpp.unordered_set cimport unordered_set
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, FLIPFLOP, MODE
# from libcpp cimport bool
# In reactor/Gates.pxd

# Ensure you DO NOT have 'from libcpp.vector cimport vector' anywhere in this file.

cdef extern from "<vector>" namespace "std" nogil:
    cdef cppclass vector[T, ALLOCATOR=*]:
        cppclass iterator:
            T& operator*()
            iterator operator++()
            bint operator!=(iterator)
            bint operator==(iterator)
            
        vector()
        
        # Element Access
        T& operator[](int)
        T& at(int)
        T& front()
        T& back()           # Required for 'queue.back()'
        T* data()           # Required for 'fuse.data()'

        # Modifiers
        void push_back(T&)
        void emplace_back(...)  # Your custom addition
        void pop_back()         # Required for 'queue.pop_back()'
        void clear()
        void reserve(int)
        void resize(int)
        
        # Capacity
        bint empty()
        int size()
        int capacity()

        # Iterators
        iterator begin()
        iterator end()

cdef class Gate
cdef class Variable

# Standalone helper functions

cdef extern from "Profile.h":
    cdef cppclass Profile:
        void* target
        int index
        int output
        Profile()
        Profile(void* target, int pin_index, int output)
        void flag()

ctypedef deque[void*] Queue
ctypedef vector[Profile*] Fuse
# Helper functions for Profile
cdef void create(vector[Profile]& hitlist, Gate target, int pin_index,int output)
cdef void add(vector[Profile]& hitlist, Gate target, int pin_index,int output)
cdef void remove(vector[Profile]& hitlist, Gate target, int pin_index)
cdef void hide(Profile& profile)
cdef void reveal(Profile& profile,Gate source)
cdef void pop(vector[Profile]& hitlist, Gate target, int pin_index)



cdef class Gate:
    # Public attributes
    cdef public list sources    
    cdef public int inputlimit
    cdef public int book[4]              
    cdef public int output
    cdef public int prev_output
    # cdef public int need_sort
    # Identity
    cdef public int id
    cdef public tuple code
    cdef public str name
    cdef public str custom_name
    
    # Internal logic
    cdef vector[Profile] hitlist

    # Methods
    cdef void process(self)
    cpdef void rename(self, str name)
    cdef bint isready(self)
    cpdef void connect(self, Gate source, int index)
    cpdef void disconnect(self, int index)
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
    cpdef void toggle(self, int source)

cdef class Probe(Gate):
    pass

cdef class InputPin(Probe):
    pass

cdef class OutputPin(Probe):
    pass

# Logic Gates
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