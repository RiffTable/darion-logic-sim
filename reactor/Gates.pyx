# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
from Gates cimport vector
from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM
from Const cimport *
from libc.string cimport memmove
cdef inline void create(vector[Profile]& hitlist, Gate target, int pin_index,int output):
    cdef void* target_ptr = <void*>target
    hitlist.emplace_back(target_ptr, pin_index, output)
    target.book[output] += 1

cdef inline void add(vector[Profile]& hitlist, Gate target, int pin_index,int output):
    cdef void* target_ptr = <void*>target
    hitlist.emplace_back()
    cdef Profile* start= hitlist.data()
    cdef Profile* final=start+hitlist.size()-1
    cdef Profile* end = final-1
    cdef Profile* mid
    while start<=end:
        mid = start+(end-start)/2
        if mid.target > target_ptr:
            end = mid-1
        elif mid.target < target_ptr:
            start = mid+1            
        else: 
            if mid.index<pin_index:
                start = mid+1
            else:
                end = mid-1
    memmove(start+1, start, (final-start)*sizeof(Profile))
    start.target = target_ptr
    start.index = pin_index
    start.output = output

    target.book[output] += 1

cdef inline void remove(vector[Profile]& hitlist,Gate target, int pin_index):
    cdef void* target_ptr = <void*>target
    cdef Profile* start= hitlist.data()
    cdef Profile* final=start+hitlist.size()
    cdef Profile* end = final-1
    cdef Profile* mid
    while start<=end:
        mid = start+(end-start)/2
        if mid.target == target_ptr:
            if mid.index==pin_index:
                target.book[mid.output] -= 1
                memmove(mid, mid+1, (final-mid-1)*sizeof(Profile))
                hitlist.pop_back()
                return
            elif mid.index<pin_index:
                start = mid+1
            else:
                end = mid-1
        elif mid.target < target_ptr:
            start = mid+1
        else:
            end = mid-1

            
cdef inline void pop(vector[Profile]& hitlist,Gate target, int pin_index):
    cdef void* target_ptr = <void*>target
    cdef Profile* profile= hitlist.data()
    cdef Profile* end = profile+hitlist.size()
    while profile<end:
        if profile.target == target_ptr and profile.index == pin_index:
            target.book[profile.output] -= 1
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
# cdef inline bint search_source(list sources, void* source):
#     cdef size_t i
#     cdef size_t size = PyList_GET_SIZE(sources)
#     cdef void* item
#     for i in range(size):
#         item = PyList_GET_ITEM(sources, i)
#         if item == source:
#             return True
#     return False
cdef class Gate:
    # it handles inputs, outputs, and  processing logic
    def __init__(self):
        # who feeds into this gate? (inputs)
        self.sources: list = [None, None]
        # who does this gate feed into? (outputs)
        self.inputlimit = 2
        # keeps track of what kind of inputs we have (high, low, etc)
        # self.need_sort: bint = False
        # current and previous state
        self.output = UNKNOWN
        self.prev_output = UNKNOWN
        # identity details
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

    # calculates the output based on inputs
    cdef void process(self):
        cdef int* book=self.book
        cdef int gate_type = self.id
        cdef int low=book[LOW]
        cdef int high=book[HIGH]
        self.prev_output=self.output
        if MODE == DESIGN:
            self.output = UNKNOWN
        elif MODE == SIMULATE:
            if high+low==self.inputlimit:
                if gate_type<=NAND_ID:self.output = (low!=0)^(gate_type&1)
                elif gate_type<=NOR_ID:self.output = (high==0)^(gate_type&1)
                else:self.output = (high&1)^(gate_type==XNOR_ID)
            else:
                self.output = UNKNOWN
        else:
            if high+low and high+low+book[ERROR]+book[UNKNOWN]==self.inputlimit:
                if gate_type<=NAND_ID:self.output = (low!=0)^(gate_type&1)
                elif gate_type<=NOR_ID:self.output = (high==0)^(gate_type&1)
                else:self.output = (high&1)^(gate_type==XNOR_ID)
            else:
                self.output = UNKNOWN
        
       
    cpdef void rename(self,str name):
        self.name = name

    # checks if the gate is ready to calculate an output
    cdef bint isready(self):
        cdef int realsource
        cdef int inputlimit = self.inputlimit
        cdef int* book = self.book
        if MODE == DESIGN:
            # if we are designing, nothing works yet
            return False
        else:
            if MODE == SIMULATE:
                # in simulation, we need all inputs connected
                return book[HIGH]+book[LOW] == inputlimit
            else:
                # in flipflop MODE, we're a bit more lenient
                realsource = book[HIGH]+book[LOW]
                return realsource and realsource+book[UNKNOWN]+book[ERROR] == inputlimit

    # connect a source gate (input) to this gate
    cpdef void connect(self, Gate source, int index):
        if MODE==FLIPFLOP:
            add(source.hitlist, self, index, source.output)
        else:
            create(source.hitlist, self, index, source.output)
        # source.need_sort=True
        # actually plug it in
        self.sources[index] = source
        # if something is wrong with the input, react
        if source.output==ERROR:
            self.output = ERROR
        else:
            # otherwise, recalculate our output
            self.process()
    # remove a connection at a specific index
    cpdef void disconnect(self,int index):
        cdef Gate source = self.sources[index]
        if MODE==FLIPFLOP:
            remove(source.hitlist, self, index)
        else:
            pop(source.hitlist, self, index)
        self.sources[index] = None
        # source.need_sort=True
        # recalculate everything
        self.process()

   
    cdef void reset(self):
        self.prev_output = UNKNOWN
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
                if MODE==FLIPFLOP:
                    remove(source.hitlist, self, i)
                else:
                    pop(source.hitlist, self, i)
        
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
                if MODE==FLIPFLOP:
                    add(source.hitlist, self, i, source.output)
                else:
                    create(source.hitlist, self, i, source.output)
        self.process()
        n=self.hitlist.size()
        # reconnect to targets (this gate's outputs)
        for i in range(n):
            reveal(hitlist[i], self)        

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

    cpdef dict json_data(self):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source else ('X', 'X') for source in self.sources],
        }
        return dictionary

    cpdef dict copy_data(self, set cluster):
        dictionary = {
            "name": self.name,
            "custom_name": "", # Do not copy custom name for gates
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source and source in cluster else ('X', 'X') for source in self.sources],
            }
        return dictionary

    cdef tuple decode(self,list code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    cpdef void clone(self, dict dictionary,dict pseudo):
        self.custom_name = dictionary["custom_name"]
        self.setlimits(dictionary["inputlimit"])
        for index,source in enumerate(dictionary["source"]):
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
        self.sources.pop()
    cpdef bint setlimits(self,int size):
        return False
    cpdef void connect(self, Gate source, int index):
        pass
    cpdef void disconnect(self, int index):
        pass
    cpdef void toggle(self, int source):
        self.value = source
        self.process()

    cdef void reset(self):
        self.output = UNKNOWN
        self.prev_output = UNKNOWN
        cdef Profile* profile = self.hitlist.data()
        cdef Profile* end = profile + self.hitlist.size()
        while profile != end:
            profile.output=UNKNOWN
            profile+=1
    
    cdef void process(self):
        self.prev_output = self.output
        if MODE == DESIGN:
            self.output = UNKNOWN
        else:
            self.output = self.value

    cpdef dict json_data(self):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "value": self.value,
        }
        return dictionary

    cpdef void clone(self,dict dictionary, dict pseudo):
        self.custom_name = dictionary["custom_name"]
        self.value = dictionary["value"]

    cpdef dict copy_data(self,set cluster):
        dictionary = {
            "name": self.name,
            "custom_name": "", # Do not copy custom name for gates
            "code": self.code,
            "value": self.value,
            }
        return dictionary

    cdef void hide(self):
        # disconnect from target
        cdef Profile* hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            hide(hitlist[i])

    cdef void reveal(self):
        # connect to targets
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

    cpdef bint setlimits(self,int size):
        return False

    cdef bint isready(self):
        if MODE==DESIGN:
            return False
        elif self.sources[0]:
            return True
        else:
            return False
    cpdef dict copy_data(self, set cluster):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name, 
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source and source in cluster else ('X', 'X') for source in self.sources],
            }
        return dictionary

    cpdef void clone(self, dict dictionary, dict pseudo):
        self.custom_name = dictionary["custom_name"]
        self.setlimits(dictionary["inputlimit"])
        for index,source in enumerate(dictionary["source"]):
            if source[0]!='X':
                self.connect(pseudo[self.decode(source)],index)

    cdef void process(self):
        self.prev_output = self.output
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
    cdef void process(self):
        self.prev_output = self.output
        cdef Gate source=self.sources[0]
        cdef int output
        if MODE == DESIGN:
            self.output = UNKNOWN
        elif source is not None:
            output=source.output
            if output == UNKNOWN:
                self.output = UNKNOWN
            else:
                self.output = output^1
        else:
            self.output = UNKNOWN

cdef class AND(Gate):
    """AND gate - outputs 1 only if all inputs are 1"""
    def __cinit__(self):
        self.id = AND_ID
    def __init__(self):
        Gate.__init__(self)

cdef class NAND(Gate):
    """NAND gate - NOT AND"""
    def __cinit__(self):
        self.id = NAND_ID
    def __init__(self):
        Gate.__init__(self)

cdef class OR(Gate):
    """OR gate - outputs 1 if any input is 1"""
    def __cinit__(self):
        self.id = OR_ID
    def __init__(self):
        Gate.__init__(self)

cdef class NOR(Gate):
    """NOR gate - NOT OR"""
    def __cinit__(self):
        self.id = NOR_ID
    def __init__(self):
        Gate.__init__(self)

cdef class XOR(Gate):
    """XOR gate - outputs 1 if odd number of inputs are 1"""
    def __cinit__(self):
        self.id = XOR_ID
    def __init__(self):
        Gate.__init__(self)

cdef class XNOR(Gate):
    """XNOR gate - NOT XOR"""
    def __cinit__(self):
        self.id = XNOR_ID
    def __init__(self):
        Gate.__init__(self)


