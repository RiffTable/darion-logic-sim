# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
from Gates cimport vector
from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM
from Const cimport *
from libc.string cimport memmove
            
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
    def __init__(self):
        self.sources: list = [None, None]
        self.inputlimit = 2
        self.output = UNKNOWN
        self.scheduled = False
        self.code = ()
        self.name = ''
        self.custom_name = ''

    def __repr__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.name if self.custom_name == '' else self.custom_name

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
        cdef int* book=self.book
        cdef int gate_type = self.id
        cdef int low=book[LOW]
        cdef int high=book[HIGH]
        cdef int realsource = high+low
        if MODE == DESIGN:
            self.output = UNKNOWN
        else:
            if realsource==self.inputlimit or (realsource and realsource+book[ERROR]+book[UNKNOWN]==self.inputlimit):
                if gate_type<=NAND_ID:self.output = (low==0)^(gate_type&1)
                elif gate_type<=NOR_ID:self.output = (high>0)^(gate_type&1)
                else:self.output = (high&1)^(gate_type&1)
            else:
                self.output = UNKNOWN
       
    cpdef void rename(self,str name):
        self.name = name

    cdef void connect(self, Gate source, int index):
        source.hitlist.emplace_back(<void*>self, index, source.output)
        self.sources[index] = source
        self.book[source.output] += 1
        if source.output==ERROR:
            self.output = ERROR
        else:
            self.process()
    cdef void disconnect(self,int index):
        cdef Gate source = self.sources[index]
        pop(source.hitlist, <void*>self, index)
        self.sources[index] = None
        self.book[source.output] -= 1
        self.process()
   
    cdef void reset(self):
        self.output = UNKNOWN
        cdef Profile* profile = self.hitlist.data()
        cdef Profile* end = profile + self.hitlist.size()
        cdef int* book = self.book
        book[3] += book[0] + book[1] + book[2]
        book[0] = book[1] = book[2] = 0
        while profile<end:
            profile.output=UNKNOWN
            profile+=1

    cdef void hide(self):
        # disconnect from targets (this gate's outputs)
        cdef Py_ssize_t i
        cdef Py_ssize_t n=self.hitlist.size()
        cdef Profile* hitlist = self.hitlist.data()
        for i in range(n):
            hide(hitlist[i])
        
        # disconnect from sources (this gate's inputs)
        cdef Profile* src_hitlist
        cdef list sources=self.sources
        n=len(sources)
        cdef Gate source
        for i in range(n):
            source=<Gate>PyList_GET_ITEM(sources,i)
            if source is not None:
                pop(source.hitlist, <void*>self, i)
        self.output=UNKNOWN
        cdef int* book = self.book
        book[0] = book[1] = book[2] = book[3] = 0

    cdef void reveal(self):
        cdef Profile* hitlist = self.hitlist.data()
        cdef Py_ssize_t i
        cdef list sources=self.sources
        cdef Py_ssize_t n=len(sources)
        cdef Gate source
        for i in range(n):
            source=<Gate>PyList_GET_ITEM(sources,i)
            if source is not None:
                source.hitlist.emplace_back(<void*>self, i, source.output)
                self.book[source.output]+=1
        n=self.hitlist.size()
        # reconnect to targets (this gate's outputs)
        for i in range(n):
            reveal(hitlist[i], self)        
        self.process()

    cpdef bint setlimits(self,int size):
        if size<2:
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

    cpdef list json_data(self):
        dictionary = [
            self.name,
            self.custom_name,
            self.code,
            self.inputlimit,
            [source.code if source else ('X', 'X') for source in self.sources],
            ]
        return dictionary

    cpdef list copy_data(self, set cluster):
        dictionary = [
            self.name,
            "",
            self.code,
            self.inputlimit,
            [source.code if source and source in cluster else ('X', 'X') for source in self.sources],
            ]
        return dictionary

    cdef tuple decode(self,list code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    cpdef void clone(self, list dictionary,dict pseudo):
        self.custom_name = dictionary[CUSTOM_NAME]
        self.setlimits(dictionary[INPUTLIMIT])
        for index,source in enumerate(dictionary[SOURCES]):
            if source[0]!='X':
                self.connect(pseudo[self.decode(source)],index)

    cpdef void load_to_cluster(self,set cluster):
        cluster.add(self)

cdef class Variable(Gate):
    def __cinit__(self):
        self.id = VARIABLE_ID
    def __init__(self):
        Gate.__init__(self)
        self.value = 0
        self.inputlimit = 1
        self.output = UNKNOWN if MODE == DESIGN else self.value
        self.sources.pop()
    cpdef bint setlimits(self,int size):
        return False
    cdef void connect(self, Gate source, int index):
        pass
    cdef void disconnect(self, int index):
        pass

    cdef void reset(self):
        self.output = UNKNOWN
        cdef Profile* profile = self.hitlist.data()
        cdef Profile* end = profile + self.hitlist.size()
        while profile != end:
            profile.output=UNKNOWN
            profile+=1
    
    cdef void process(self):
        if MODE == DESIGN:
            self.output = UNKNOWN
        else:
            self.output = self.value

    cpdef list json_data(self):
        dictionary = [
            self.name,
            self.custom_name,
            self.code,
            self.inputlimit,
            self.value,
        ]
        return dictionary

    cpdef void clone(self,list dictionary, dict pseudo):
        self.custom_name = dictionary[CUSTOM_NAME]
        self.value = dictionary[VALUE]

    cpdef list copy_data(self,set cluster):
        dictionary = [
            self.name,
            "",
            self.code,
            self.inputlimit,
            self.value,
            ]
        return dictionary

    cdef void hide(self):
        cdef Profile* hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            hide(hitlist[i])

    cdef void reveal(self):
        cdef Profile* hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            reveal(hitlist[i], self)

cdef class Probe(Gate):
    def __cinit__(self):
        self.id = PROBE_ID
    def __init__(self):
        Gate.__init__(self)
        self.inputlimit = 1
        self.sources.pop()

    cdef void connect(self, Gate source, int index):
        source.hitlist.emplace_back(<void*>self, index, source.output)
        self.sources[index] = source
        self.output=source.output
    cdef void disconnect(self,int index):
        cdef Gate source = self.sources[index]
        pop(source.hitlist, <void*>self, index)
        self.sources[index] = None
        self.output=UNKNOWN
   
    cdef void reset(self):
        self.output = UNKNOWN
        cdef Profile* profile = self.hitlist.data()
        cdef Profile* end = profile + self.hitlist.size()
        while profile<end:
            profile.output=UNKNOWN
            profile+=1

    cdef void hide(self):
        cdef Py_ssize_t i
        cdef Py_ssize_t n=self.hitlist.size()
        cdef Profile* hitlist = self.hitlist.data()
        for i in range(n):
            hide(hitlist[i])
        
        cdef Profile* src_hitlist
        cdef list sources=self.sources
        n=len(sources)
        cdef Gate source
        for i in range(n):
            source=<Gate>PyList_GET_ITEM(sources,i)
            if source is not None:
                pop(source.hitlist, <void*>self, i)
        self.output=UNKNOWN

    cdef void reveal(self):
        cdef Profile* hitlist = self.hitlist.data()
        cdef Py_ssize_t i
        cdef list sources=self.sources
        cdef Py_ssize_t n=len(sources)
        cdef Gate source=self.sources[0]
        if source:
            source.hitlist.emplace_back(<void*>self, 0, source.output)
            self.output=source.output
        n=self.hitlist.size()
        for i in range(n):
            reveal(hitlist[i], self)        

    cpdef bint setlimits(self,int size):
        return False


    cpdef list copy_data(self, set cluster):
        dictionary = [
            self.name,
            self.custom_name, 
            self.code,
            self.inputlimit,
            [source.code if source and source in cluster else ('X', 'X') for source in self.sources],
            ]
        return dictionary

    cpdef void clone(self, list dictionary, dict pseudo):
        self.custom_name = dictionary[CUSTOM_NAME]
        self.setlimits(dictionary[INPUTLIMIT])
        for index,source in enumerate(dictionary[SOURCES]):
            if source[0]!='X':
                self.connect(pseudo[self.decode(source)],index)

    cdef void process(self):
        cdef Gate source=self.sources[0]
        if MODE == DESIGN:
            self.output = UNKNOWN
        elif source is not None:
            self.output = source.output
        else:
            self.output = UNKNOWN

cdef class InputPin(Probe):
    def __cinit__(self):
        self.id = INPUT_PIN_ID

cdef class OutputPin(Probe):
    def __cinit__(self):
        self.id = OUTPUT_PIN_ID

cdef class NOT(Gate):
    """NOT gate - inverts the input"""
    def __cinit__(self):
        self.id = NOT_ID
    def __init__(self):
        Gate.__init__(self)
        self.inputlimit = 1
        self.sources = [None]

    cdef void connect(self, Gate source, int index):
        source.hitlist.emplace_back(<void*>self, index, source.output)
        self.sources[index] = source
        if source.output>=ERROR:
            self.output=source.output
        else:
            self.output=source.output^1
    cdef void disconnect(self,int index):
        cdef Gate source = self.sources[index]
        pop(source.hitlist, <void*>self, index)
        self.sources[index] = None
        self.output=UNKNOWN
   
    cdef void reset(self):
        self.output = UNKNOWN
        cdef Profile* profile = self.hitlist.data()
        cdef Profile* end = profile + self.hitlist.size()
        while profile<end:
            profile.output=UNKNOWN
            profile+=1

    cdef void hide(self):
        cdef Py_ssize_t i
        cdef Py_ssize_t n=self.hitlist.size()
        cdef Profile* hitlist = self.hitlist.data()
        for i in range(n):
            hide(hitlist[i])
        
        cdef Gate source=self.sources[0]
        if source:
            pop(source.hitlist, <void*>self, 0)
        self.output=UNKNOWN

    cdef void reveal(self):
        cdef Profile* hitlist = self.hitlist.data()
        cdef Py_ssize_t i
        cdef list sources=self.sources
        cdef Py_ssize_t n=len(sources)
        cdef Gate source=self.sources[0]
        if source:
            source.hitlist.emplace_back(<void*>self, 0, source.output)
            if source.output>=ERROR:
                self.output=source.output
            else:
                self.output=source.output^1
        n=self.hitlist.size()
        for i in range(n):
            reveal(hitlist[i], self)   

    cdef void process(self):
        cdef Gate source=self.sources[0]
        cdef int output
        if MODE == DESIGN or source is None:
            self.output = UNKNOWN
        else:
            output=source.output
            if output == UNKNOWN:
                self.output = UNKNOWN
            else:
                self.output = output^1

cdef class AND(Gate):
    """AND gate - outputs 1 only if all inputs are 1"""
    def __cinit__(self):
        self.id = AND_ID
    def __init__(self):
        Gate.__init__(self)

cdef class OR(Gate):
    """OR gate - outputs 1 if any input is 1"""
    def __cinit__(self):
        self.id = OR_ID
    def __init__(self):
        Gate.__init__(self)

cdef class XOR(Gate):
    """XOR gate - outputs 1 if odd number of inputs are 1"""
    def __cinit__(self):
        self.id = XOR_ID
    def __init__(self):
        Gate.__init__(self)

cdef class NAND(Gate):
    """NAND gate - NOT AND"""
    def __cinit__(self):
        self.id = NAND_ID
    def __init__(self):
        Gate.__init__(self)

cdef class NOR(Gate):
    """NOR gate - NOT OR"""
    def __cinit__(self):
        self.id = NOR_ID
    def __init__(self):
        Gate.__init__(self)


cdef class XNOR(Gate):
    """XNOR gate - NOT XOR"""
    def __cinit__(self):
        self.id = XNOR_ID
    def __init__(self):
        Gate.__init__(self)


