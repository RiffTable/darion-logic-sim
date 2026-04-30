
cpdef void set_MODE(Py_ssize_t mode):
    global MODE
    MODE = mode 

cpdef Py_ssize_t get_MODE():
    return MODE

cpdef void set_DEBUG():
    global DEBUG
    DEBUG = True

cpdef void set_DELAY(double delay):
    global DELAY
    DELAY = delay

cpdef double get_DELAY():
    return DELAY
