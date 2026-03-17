from Gates cimport CPP_Gate,vector
from libc.stdint cimport uint16_t
cdef tuple namelist
cdef object get(int choice, vector[CPP_Gate]& gate_infolist)
cdef tuple decode(object code)