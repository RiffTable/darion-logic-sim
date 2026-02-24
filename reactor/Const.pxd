cpdef enum:

    HIGH = 1
    LOW = 0
    ERROR = 2
    UNKNOWN = 3

    DESIGN = 0
    SIMULATE = 1

    LIMIT = 100


    AND_ID = 0
    NAND_ID = 1
    OR_ID = 2
    NOR_ID = 3
    XOR_ID = 4
    XNOR_ID = 5
    NOT_ID = 6
    VARIABLE_ID = 7
    PROBE_ID = 8
    INPUT_PIN_ID = 9
    OUTPUT_PIN_ID = 10
    IC_ID = 11
    TOTAL = 12

    NAME=-1
    CUSTOM_NAME=NAME+1
    CODE=NAME+2
    COMPONENTS=NAME+3
    INPUTLIMIT=COMPONENTS
    SOURCES=NAME+4
    VALUE=SOURCES
    MAP=SOURCES

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

cdef public int MODE 
cpdef void set_MODE(int mode)
cpdef int get_MODE()

