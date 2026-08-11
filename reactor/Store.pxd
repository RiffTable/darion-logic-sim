from Gates cimport CPP_Gate,vector,Profile
from libc.stdint cimport uint8_t
cdef tuple namelist
cdef object get(int choice, vector[CPP_Gate]& gate_infolist, vector[Profile]& global_hitlist, list gate_verse)
cdef tuple decode(object code)