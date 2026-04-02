
cpdef void set_MODE(Py_ssize_t mode):
    global MODE
    MODE = mode 

cpdef Py_ssize_t get_MODE():
    return MODE

cpdef void set_DEBUG():
    global DEBUG
    DEBUG = True

cpdef void set_timings(double fps, double ratio):
    global VISUALIZE, OSCILLATE
    VISUALIZE = fps * (1 - ratio)
    OSCILLATE = fps * ratio

cpdef double get_oscillate():
    return OSCILLATE

cpdef double get_visualize():
    return VISUALIZE