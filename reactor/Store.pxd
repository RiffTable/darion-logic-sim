from Gates cimport CPP_Gate,vector
cdef tuple namelist
cdef object get(int choice, vector[CPP_Gate] gate_infolist)
cdef tuple decode(object code)