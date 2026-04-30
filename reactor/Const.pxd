cpdef enum:

    HIGH = 1
    LOW = 0
    ERROR = 2
    UNKNOWN = 2
    PRIMARY = 2

    DESIGN = 0
    SIMULATE = 1
    COMPILE = 3
    
    LIMIT = 250_000


    DEAD_ID=255
    AND_ID = 0
    NAND_ID = 1
    OR_ID = 2
    NOR_ID = 3
    XOR_ID = 4
    XNOR_ID = 5
    VARIABLE_ID = 6
    NOT_ID = 7
    PROBE_ID = 8
    INPUT_PIN_ID = 9
    OUTPUT_PIN_ID = 10
    IC_ID = 11
    TOTAL = 12

    NAME=-1
    CUSTOM_NAME=NAME+1
    ID=NAME+2
    LOCATION=NAME+3
    INPUTLIMIT=NAME+4
    SOURCES=NAME+5
    VALUE=SOURCES
    MAP=SOURCES
    TAG=NAME+4
    DESCRIPTION=NAME+6
    
cdef extern from *:
    """
    #if defined(__GNUC__) || defined(__clang__)
        #define likely(x)       __builtin_expect(!!(x), 1)
        #define unlikely(x)     __builtin_expect(!!(x), 0)
    #else
        #define likely(x)       (x)
        #define unlikely(x)     (x)
    #endif
    """
    bint likely(bint condition) nogil
    bint unlikely(bint condition) nogil

cdef public Py_ssize_t MODE = DESIGN
cpdef void set_MODE(Py_ssize_t mode)
cpdef Py_ssize_t get_MODE()

cdef public bint DEBUG = False
cpdef void set_DEBUG()

cdef public double DELAY = 0.01
cpdef void set_DELAY(double delay)
cpdef double get_DELAY()
