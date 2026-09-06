# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
# cython: nonecheck=False
from Gates cimport vector
from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM
from Const cimport *
from libc.string cimport memmove
from Store cimport decode
from libc.stdint cimport uint16_t
            
cdef inline void pop(vector[Profile]& hitlist,CPP_Gate* target, int pin_index):
    cdef Profile* profile= hitlist.data()
    cdef Profile* end = profile+hitlist.size()
    while profile<end:
        if profile.target == target and profile.index == pin_index:
            profile[0]=(end-1)[0]
            hitlist.pop_back()
            break
        profile+=1

cdef inline void hide(Profile& profile):
    cdef CPP_Gate* target_info = <CPP_Gate*>profile.target
    cdef Gate target = <Gate>target_info.gate
    target_info.book[profile.output] -= 1
    target_info.invalid += 1
    target.sources[profile.index] = None
    profile.output = UNKNOWN

cdef inline void reveal(Profile& profile,Gate source):
    cdef CPP_Gate* target_info = <CPP_Gate*>profile.target
    cdef Gate target = <Gate>target_info.gate
    target_info.book[UNKNOWN] += 1
    target_info.invalid -= 1
    target.sources[profile.index] = source

cdef class Gate:
    def __init__(self, int id, str name):
        self.id = id
        self.codename = name
        self.location = -1
        cdef uint8_t limit = 1 if id >= BUFFER_ID else 2
        self.info = new CPP_Gate(<void*>self, id, limit)
        if id >= BUFFER_ID:
            self.sources: list = [None]
        else:
            self.sources:list=[None,None]
        self.code = ()
        self.custom_name = ''

    def __dealloc__(self):
        if self.info != NULL:
            del self.info

    def __repr__(self):
        return self.codename if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.codename if self.custom_name == '' else self.custom_name

    @property
    def hitlist(self):
        cdef list result = []
        cdef size_t i
        cdef size_t size = self.info.hitlist.size()
        cdef Profile* profile = self.info.hitlist.data()
        for i in range(size):
            result.append(<Gate>(<CPP_Gate*>profile[i].target).gate)
        return result

    cdef void process(self):
        cdef uint8_t* book
        cdef int gate_type
        cdef int limit
        cdef int low
        cdef int high
        cdef int realsource
        
        if MODE == DESIGN:
            self.info.output = UNKNOWN
        else:
            if self.id==VARIABLE_ID:
                self.info.output = self.info.flags & FLAG_VALUE
            else:
                limit=self.info.inputlimit
                gate_type=self.id
                book = self.info.book
                high = book[HIGH]
                low = book[LOW]
                realsource = high+low
                if likely(realsource==limit) or unlikely(realsource and realsource+book[UNKNOWN]==limit):
                    if gate_type<=NAND_ID:self.info.output = (low==0)^(gate_type&1)
                    elif gate_type<=NOR_ID:self.info.output = (high>0)^(gate_type&1)
                    else:self.info.output = (high&1)^(gate_type&1)
                else:
                    self.info.output = UNKNOWN
       
    cpdef void rename(self,str name):
        self.custom_name = name

    cdef void connect(self, Gate source,int index):
        if self.id==VARIABLE_ID or self.sources[index] is not None:
            return
        source.info.hitlist.emplace_back(<CPP_Gate*>self.info, index, source.info.output)
        self.sources[index] = source
        self.info.book[UNKNOWN] -= 1
        self.info.book[source.info.output] += 1
        self.info.invalid -= 1
        if source.info.output==UNKNOWN:
            self.info.output = UNKNOWN
        else:
            self.process()

    cdef void disconnect(self,int index):
        if self.id==VARIABLE_ID or self.sources[index] is None:
            return
        cdef Gate source = self.sources[index]
        pop(source.info.hitlist, <CPP_Gate*>self.info, index)
        self.sources[index] = None
        self.info.book[source.info.output] -= 1
        self.info.book[UNKNOWN] += 1
        self.info.invalid += 1
        self.info.output=UNKNOWN
   
    cdef void reset(self):
        cdef uint8_t* book
        if self.id!= VARIABLE_ID:
            book = self.info.book
            book[UNKNOWN] += book[LOW] + book[HIGH]
            book[LOW] = book[HIGH] = 0
        self.info.output = UNKNOWN
        cdef Profile* profile = self.info.hitlist.data()
        cdef Profile* end = profile + self.info.hitlist.size()
        while profile<end:
            profile.output=UNKNOWN
            profile+=1

    cdef void hide(self):
        # disconnect from targets (this gate's outputs)
        cdef Py_ssize_t i
        cdef Py_ssize_t n=self.info.hitlist.size()
        cdef Profile* hitlist = self.info.hitlist.data()
        for i in range(n):
            hide(hitlist[i])
        # disconnect from sources (this gate's inputs)
        cdef list sources=self.sources
        
        n=len(sources)
        cdef Gate source
        if self.id!=VARIABLE_ID:
            for i in range(n):
                source=<Gate>PyList_GET_ITEM(sources,i)
                if source is not None:
                    pop(source.info.hitlist, <CPP_Gate*>self.info, i)
        self.info.output=UNKNOWN
        cdef uint8_t* book
        if self.id != VARIABLE_ID:
            book = self.info.book
            book[LOW] = book[HIGH] = book[UNKNOWN] = 0
            self.info.invalid = self.info.inputlimit

    cdef void reveal(self):
        cdef Profile* hitlist = self.info.hitlist.data()
        cdef Py_ssize_t i
        cdef list sources=self.sources
        cdef Py_ssize_t n=len(sources)
        cdef Gate source
        if self.id!=VARIABLE_ID:
            for i in range(n):
                source=<Gate>PyList_GET_ITEM(sources,i)
                if source is not None:
                    source.info.hitlist.emplace_back(<CPP_Gate*>self.info, i, source.info.output)
                    self.info.book[source.info.output]+=1
                    self.info.invalid -= 1
        n=self.info.hitlist.size()
        # reconnect to targets via Python-side hitlist only
        for i in range(n):
            reveal(hitlist[i], self)
        self.process()

    cpdef bint setlimits(self,int size):
        if size<2 or self.id>=BUFFER_ID:
            return False
        cdef int limit=self.info.inputlimit
        if size>limit:
            self.sources.extend([None]*(size-limit))
            self.info.inputlimit=size
            self.info.book[UNKNOWN] += (size-limit)
            self.info.invalid += (size-limit)
            self.process()
            return True
        elif size<limit:
            for i in range(size,limit):
                if self.sources[i]:return False
            self.sources=self.sources[:size]
            self.info.inputlimit=size
            self.info.book[UNKNOWN] -= (limit-size)
            self.info.invalid -= (limit-size)
            self.process()
            return True
        return False

    cpdef str getoutput(self):
        if self.info.output == UNKNOWN:
            return 'X'
        return 'T' if self.info.output == HIGH else 'F'

    @property
    def output(self):
        '''Current output value of this gate'''
        return self.info.output

    @property
    def invalid(self):
        return self.info.invalid
        
    @property
    def inputlimit(self):
        return self.info.inputlimit
        
    @property
    def book(self):
        return [self.info.book[0], self.info.book[1], self.info.book[2]]

    @property
    def value(self):
        '''Stored toggle value'''
        return bool(self.info.flags & FLAG_VALUE)

    @value.setter
    def value(self, val):
        if val: self.info.flags |= FLAG_VALUE
        else: self.info.flags &= ~FLAG_VALUE

    @property
    def scheduled(self):
        return bool(self.info.flags & FLAG_SCHEDULED)

    @scheduled.setter
    def scheduled(self, val):
        if val: self.info.flags |= FLAG_SCHEDULED
        else: self.info.flags &= ~FLAG_SCHEDULED

    cpdef list full_data(self):
        cdef Gate source
        cdef list dictionary = [
            self.custom_name,
            self.id,
            self.location,
            self.info.inputlimit,
            bool(self.info.flags & FLAG_VALUE) if self.id==VARIABLE_ID else [source.location if source else -1 for source in self.sources],
            ]
        return dictionary

    cpdef list partial_data(self):
        cdef Gate source
        cdef list dictionary = [
            self.custom_name,
            self.id,
            self.location,
            self.info.inputlimit,
            bool(self.info.flags & FLAG_VALUE) if self.id==VARIABLE_ID else [source.location if source and (source.info.flags & FLAG_SCHEDULED) else -1 for source in self.sources],
            ]
        return dictionary

    cpdef void clone(self, list dictionary, dict pseudo):
        self.custom_name = dictionary[CUSTOM_NAME]
        if self.id==VARIABLE_ID:
            if dictionary[VALUE]: self.info.flags |= FLAG_VALUE
            else: self.info.flags &= ~FLAG_VALUE
        else:
            self.setlimits(dictionary[INPUTLIMIT])
            for index,source_loc in enumerate(dictionary[SOURCES]):
                if source_loc != -1 and source_loc in pseudo:
                    self.connect(pseudo[source_loc], index)

    cpdef void load_to_cluster(self,list cluster):
        cluster.append(self)
        self.info.flags |= FLAG_SCHEDULED

cdef class Variable(Gate):
    pass

cdef class Probe(Gate):
    pass

cdef class NOT(Gate):
    pass
