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
            
cdef inline void pop(vector[Profile]& hitlist,void* target, int pin_index):
    cdef Profile* profile= hitlist.data()
    cdef Profile* end = profile+hitlist.size()
    while profile<end:
        if profile.target == target and profile.index == pin_index:
            profile[0]=(end-1)[0]
            hitlist.pop_back()
            break
        profile+=1

cdef inline void hide(Profile& profile):
    cdef Gate target = <Gate>profile.target
    target.book[profile.output] -= 1
    target.sources[profile.index] = None
    profile.output = UNKNOWN

cdef inline void reveal(Profile& profile,Gate source):
    cdef Gate target = <Gate>profile.target
    target.book[UNKNOWN] += 1
    target.sources[profile.index] = source

cdef class Gate:
    def __init__(self, int id, str name):
        self.id = id
        self.codename = name
        self.info=NULL
        if id >= VARIABLE_ID:
            self.inputlimit = 1
            self.sources: list = [None]
        else:
            self.inputlimit = 2
            self.sources:list=[None,None]
        self.output = UNKNOWN
        self.value = 0
        self.scheduled = False
        self.code = ()
        self.custom_name = ''

    def __repr__(self):
        return self.codename if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.codename if self.custom_name == '' else self.custom_name

    @property
    def hitlist(self):
        cdef list result = []
        cdef size_t i
        cdef size_t size = self.hitlist.size()
        cdef Profile* profile = self.hitlist.data()
        for i in range(size):
            result.append(<Gate>profile[i].target)
        return result

    cdef void process(self):
        cdef uint16_t* book
        cdef int gate_type
        cdef int limit
        cdef int low
        cdef int high
        cdef int realsource
        cdef Gate source
        
        if MODE == DESIGN:
            self.output = UNKNOWN
        else:
            if self.id==VARIABLE_ID:
                self.output=self.value
            limit=self.inputlimit
            gate_type=self.id
            if limit == 1:
                if gate_type==VARIABLE_ID:
                    self.output=self.value
                else:
                    source=<Gate>PyList_GET_ITEM(self.sources, 0)
                    if source is None:
                        self.output=UNKNOWN
                    elif source.output>=ERROR:
                        self.output=source.output
                    else:
                        self.output=source.output^(gate_type==NOT_ID)
            else:
                book = self.book
                high = book[HIGH]
                low = book[LOW]
                realsource = high+low
                if likely(realsource==limit) or unlikely(realsource and realsource+book[ERROR]+book[UNKNOWN]==limit):
                    if gate_type<=NAND_ID:self.output = (low==0)^(gate_type&1)
                    elif gate_type<=NOR_ID:self.output = (high>0)^(gate_type&1)
                    else:self.output = (high&1)^(gate_type&1)
                else:
                    self.output = UNKNOWN
       
    cpdef void rename(self,str name):
        self.custom_name = name

    cdef void connect(self, Gate source,int index):
        if self.id==VARIABLE_ID or self.sources[index] is not None:
            return
        cdef CPP_Gate* source_info=source.info
        cdef CPP_Gate* self_info=self.info
        source_info.hitlist.emplace_back(<void*>self, index, source.output)
        source.hitlist.emplace_back(<void*>self, index, source.output)
        self.sources[index] = source
        self.book[source.output] += 1
        self_info.book[source_info.output] += 1
        self_info.output = source.output
        if source.output==ERROR:
            self.output = ERROR
            self_info.output=ERROR
        else:
            self.process()
    cdef void disconnect(self,int index):
        if self.id==VARIABLE_ID or self.sources[index] is None:
            return
        cdef Gate source = self.sources[index]
        cdef CPP_Gate* source_info=source.info
        cdef CPP_Gate* self_info=self.info
        pop(source_info.hitlist, <void*>self, index)
        pop(source.hitlist, <void*>self, index)
        self.sources[index] = None
        self_info.book[self_info.output] -= 1
        self.book[source.output] -= 1
        self_info.output = UNKNOWN
        self.output=UNKNOWN
   
    cdef void reset(self):
        cdef uint16_t* book
        cdef CPP_Gate* info=self.info
        if self.id<VARIABLE_ID:
            book = self.book
            book[3] += book[0] + book[1] + book[2]
            book[0] = book[1] = book[2] = 0
        # dod
        if self.id<VARIABLE_ID:
            book = info.book
            book[3] += book[0] + book[1] + book[2]
            book[0] = book[1] = book[2] = 0
        self.output = UNKNOWN
        info.output=UNKNOWN
        cdef Profile* profile = self.hitlist.data()
        cdef Profile* end = profile + self.hitlist.size()
        while profile<end:
            profile.output=UNKNOWN
            profile+=1
        profile = info.hitlist.data()
        end = profile + info.hitlist.size()
        while profile<end:
            profile.output=UNKNOWN
            profile+=1

    cdef void hide(self):
        # disconnect from targets (this gate's outputs)
        cdef CPP_Gate* info=self.info
        cdef Py_ssize_t i
        cdef Py_ssize_t n=self.hitlist.size()
        cdef Profile* hitlist = self.hitlist.data()
        for i in range(n):
            hide(hitlist[i])
        n=info.hitlist.size()
        hitlist = info.hitlist.data()
        for i in range(n):
            hide(hitlist[i])
        # disconnect from sources (this gate's inputs)
        cdef list sources=self.sources
        
        n=len(sources)
        cdef Gate source
        cdef CPP_Gate* source_info
        if self.id!=VARIABLE_ID:
            for i in range(n):
                source=<Gate>PyList_GET_ITEM(sources,i)
                if source is not None:
                    source_info=source.info
                    pop(self.hitlist, <void*>source, i)
                    pop(source_info.hitlist, <void*>self, i)
        self.output=UNKNOWN
        cdef uint16_t* book
        if self.id<VARIABLE_ID:
            book = self.book
            book[0] = book[1] = book[2] = book[3] = 0
        if self.id<VARIABLE_ID:
            book = info.book
            book[0] = book[1] = book[2] = book[3] = 0

    cdef void reveal(self):
        cdef Profile* hitlist = self.hitlist.data()
        cdef Py_ssize_t i
        cdef list sources=self.sources
        cdef Py_ssize_t n=len(sources)
        cdef Gate source
        cdef CPP_Gate* source_info
        cdef CPP_Gate* info=self.info
        if self.id!=VARIABLE_ID:
            for i in range(n):
                source=<Gate>PyList_GET_ITEM(sources,i)
                if source is not None:
                    source_info=source.info
                    source.hitlist.emplace_back(<void*>self, i, source.output)
                    source_info.hitlist.emplace_back(<void*>self, i, self.output)
                    self.info.book[source_info.output]+=1
                    self.book[source.output]+=1
        n=self.hitlist.size()
        # reconnect to targets (this gate's outputs)
        for i in range(n):
            reveal(hitlist[i], self)    
        n=info.hitlist.size()
        hitlist = info.hitlist.data()
        for i in range(n):
            reveal(hitlist[i], self)    
        self.process()

    cpdef bint setlimits(self,int size):
        if size<2 or self.id>=VARIABLE_ID:
            return False
        cdef int i
        cdef int n

        if size>self.inputlimit:
            for _ in range(size-self.inputlimit):
                self.sources.append(None)
            self.inputlimit=size
            return True
        elif size<self.inputlimit:
            for i in range(size, self.inputlimit):
                if self.sources[i]:
                    return False
                i+=1
            self.sources = self.sources[:size]
            self.inputlimit=size
            return True
        return False

    cpdef str getoutput(self):
        if self.output == ERROR:
            return '1/0'
        if self.output == UNKNOWN:
            return 'X'
        return 'T' if self.output == HIGH else 'F'

    cpdef list full_data(self):
        cdef Gate source
        cdef list dictionary = [
            self.custom_name,
            self.code,
            self.inputlimit,
            self.value if self.id==VARIABLE_ID else [source.code if source else ('X', 'X') for source in self.sources],
            ]
        return dictionary

    cpdef list partial_data(self):
        cdef Gate source
        cdef list dictionary = [
            self.custom_name,
            self.code,
            self.inputlimit,
            self.value if self.id==VARIABLE_ID else [source.code if source and source.scheduled else ('X', 'X') for source in self.sources],
            ]
        return dictionary

    cpdef void clone(self, list dictionary,dict pseudo):
        self.custom_name = dictionary[CUSTOM_NAME]
        if self.id==VARIABLE_ID:
            self.value = dictionary[VALUE]
        else:
            self.setlimits(dictionary[INPUTLIMIT])
            for index,source in enumerate(dictionary[SOURCES]):
                if source[0]!='X':
                    self.connect(pseudo[decode(source)],index)

    cpdef void load_to_cluster(self,list cluster):
        cluster.append(self)
        self.scheduled=True

cdef class Variable(Gate):
    pass

cdef class Probe(Gate):
    pass

cdef class NOT(Gate):
    pass

