# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
from libcpp.vector cimport vector
from libcpp.deque cimport deque
from libcpp.unordered_set cimport unordered_set
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, FLIPFLOP, MODE,AND_ID,OR_ID,NOT_ID,XOR_ID,NAND_ID,NOR_ID,XNOR_ID,VARIABLE_ID,PROBE_ID,INPUT_PIN_ID,OUTPUT_PIN_ID,IC_ID

cdef inline void create(vector[Profile]& hitlist, Gate target, int pin_index,int output):
    cdef void* target_ptr = <void*>target
    hitlist.push_back(Profile(target_ptr, pin_index, output))
    target.book[output] += 1

cdef inline void add(vector[Profile]& hitlist, Gate target, int pin_index,int output):
    cdef void* target_ptr = <void*>target
    hitlist.push_back(Profile())
    cdef Profile* start = hitlist.data()
    cdef Profile* profile = start+hitlist.size()-1
    cdef int i=hitlist.size()-1
    while profile>start and profile.target != target_ptr:
        profile[0]=(profile-1)[0]
        profile-=1
    profile.target=target_ptr
    profile.index=pin_index
    profile.output=output

    target.book[output] += 1


cdef inline void remove(vector[Profile]& hitlist,Gate target, int pin_index):
    target.sources[pin_index] = None
    cdef void* target_ptr = <void*>target
    cdef Profile* profile= hitlist.data()
    cdef Profile* end = profile+hitlist.size()
    while profile<end:
        if profile.target == target_ptr and profile.index == pin_index:
            target.book[profile.output] -= 1
            while profile<end-1:
                profile[0]=profile[1]
                profile+=1
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


# cdef class Profile:
#     def __init__(self, Gate target, int index, int output):
#         self.target = target
#         target.book[output] += 1
#         self.index.push_back(index)
#         self.output = output
#         self.red_flag = False

#     def __repr__(self):
#         return f"{self.target} {self.index} {self.output}"
    
#     def __str__(self):
#         return f"{self.target} {self.index} {self.output}"

cdef class Gate:
    # it handles inputs, outputs, and  processing logic

    def __init__(self):
        # who feeds into this gate? (inputs)
        self.sources: list = [None, None]
        # who does this gate feed into? (outputs)
        self.inputlimit = 2
        # keeps track of what kind of inputs we have (high, low, etc)
        self.book[:] = [0, 0, 0, 0]
        
        # current and previous state
        self.output = UNKNOWN
        self.prev_output = UNKNOWN
        
        # identity details
        self.code = ()
        self.name = ''
        self.custom_name = ''

    # cpdef void propagate(self,Queue &queue,Fuse &fuse):
    #     propagate(self,queue,fuse)

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
        pass
       
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
        if source.hitlist.size()>len(self.sources):
            if source in self.sources:
                add(source.hitlist, self, index, source.output)
            else:
                create(source.hitlist, self, index, source.output)
        else:
            add(source.hitlist, self, index, source.output)
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
        if source is None:
            return
        remove(source.hitlist, self, index)
        # recalculate everything
        self.process()

   
    cdef void reset(self):
        self.output = UNKNOWN
        cdef int i
        cdef int n
        i=0
        cdef int* book = self.book
        n=4
        cdef Profile* hitlist = self.hitlist.data()
        cdef int sums=0
        for i in range(n):
            sums+=book[i]
        book[:]=[0, 0, 0, sums]
        self.prev_output = UNKNOWN
        for i in range(self.hitlist.size()):
            hitlist[i].output=UNKNOWN

    cdef void hide(self):
        # disconnect from targets (this gate's outputs)
        cdef Gate target
        cdef Gate src
        cdef int loc
        cdef int index
        cdef Profile* hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            hide(hitlist[i])
        
        # disconnect from sources (this gate's inputs)
        cdef Profile* src_hitlist
        for index, source in enumerate(self.sources):
            if source:
                src = <Gate>source
                remove(src.hitlist, self, index)
                self.sources[index] = source
        
        # recalculate targets
        for i in range(self.hitlist.size()):
            target = <Gate>hitlist[i].target
            if target != self:
                target.process()

        self.output = UNKNOWN
        self.book[:] = [0, 0, 0, 0]

    cdef void reveal(self):
        # reconnect to sources (rebuild this gate's inputs)
        cdef int loc
        cdef Profile* profile
        cdef Profile* hitlist = self.hitlist.data()
        cdef Gate src
        for i, source in enumerate(self.sources):
            if source:
                src = <Gate>source
                add(src.hitlist, self, i, src.output)
        self.process()
        
        # reconnect to targets (this gate's outputs)
        for i in range(self.hitlist.size()):
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
        self.sources = [None]
    cpdef bint setlimits(self,int size):
        return False
    cpdef void connect(self, Gate source, int index):
        pass
    cpdef void disconnect(self, int index):
        pass
    cdef void toggle(self, int source):
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
        if MODE != DESIGN:
            self.output = self.value
        else:
            self.output = UNKNOWN

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
        cdef Profile* profile
        cdef Gate target
        cdef Profile* hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            hide(hitlist[i])

        for i in range(self.hitlist.size()):
            target = <Gate>hitlist[i].target
            if target != self:
                target.process()

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
        self.sources = [None]

    cpdef bint setlimits(self,int size):
        return False

    cdef bint isready(self):
        if MODE==DESIGN:
            return False
        elif self.sources[0] is not None:
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
        if MODE != DESIGN and self.sources[0]:
            self.output = self.sources[0].output
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
        if MODE != DESIGN and self.sources[0]:
            if self.sources[0].output == UNKNOWN:
                self.output = UNKNOWN
            else:
                self.output = self.sources[0].output^1
        else:
            self.output = UNKNOWN


cdef class AND(Gate):
    """AND gate - outputs 1 only if all inputs are 1"""
    def __cinit__(self):
        self.id = AND_ID
    def __init__(self):
        Gate.__init__(self)
    cdef void process(self):
        self.prev_output = self.output
        cdef int* book = self.book

        cdef int realsource=book[HIGH]+book[LOW]
        cdef int inputlimit=self.inputlimit
        if MODE == DESIGN:
            # if we are designing, nothing works yet
            self.output = UNKNOWN
        else:
            if realsource == inputlimit:
                self.output = book[LOW]==0
            elif MODE == FLIPFLOP and realsource and realsource+book[UNKNOWN]+book[ERROR] == inputlimit:
                self.output = book[LOW]==0
            else:
                self.output = UNKNOWN


cdef class NAND(Gate):
    """NAND gate - NOT AND"""
    def __cinit__(self):
        self.id = NAND_ID
    def __init__(self):
        Gate.__init__(self)
    cdef void process(self):
        self.prev_output = self.output
        cdef int* book = self.book

        cdef int realsource=book[HIGH]+book[LOW]
        cdef int inputlimit=self.inputlimit
        if MODE == DESIGN:
            # if we are designing, nothing works yet
            self.output = UNKNOWN
        else:
            if realsource == inputlimit:
                self.output = book[LOW]!=0
            elif MODE == FLIPFLOP and realsource and realsource+book[UNKNOWN]+book[ERROR] == inputlimit:
                self.output = book[LOW]!=0
            else:
                self.output = UNKNOWN

cdef class OR(Gate):
    """OR gate - outputs 1 if any input is 1"""
    def __cinit__(self):
        self.id = OR_ID
    def __init__(self):
        Gate.__init__(self)
    cdef void process(self):
        self.prev_output = self.output
        cdef int* book = self.book

        cdef int realsource=book[HIGH]+book[LOW]
        cdef int inputlimit=self.inputlimit
        if MODE == DESIGN:
            # if we are designing, nothing works yet
            self.output = UNKNOWN
        else:
            if realsource == inputlimit:
                self.output = book[HIGH]!=0
            elif MODE == FLIPFLOP and realsource and realsource+book[UNKNOWN]+book[ERROR] == inputlimit:
                self.output = book[HIGH]!=0
            else:
                self.output = UNKNOWN

cdef class NOR(Gate):
    """NOR gate - NOT OR"""
    def __cinit__(self):
        self.id = NOR_ID
    def __init__(self):
        Gate.__init__(self)
    cdef void process(self):
        self.prev_output = self.output
        cdef int* book = self.book

        cdef int realsource=book[HIGH]+book[LOW]
        cdef int inputlimit=self.inputlimit
        if MODE == DESIGN:
            # if we are designing, nothing works yet
            self.output = UNKNOWN
        else:
            if realsource == inputlimit:
                self.output = book[HIGH]==0
            elif MODE == FLIPFLOP and realsource and realsource+book[UNKNOWN]+book[ERROR] == inputlimit:
                self.output = book[HIGH]==0
            else:
                self.output = UNKNOWN

cdef class XOR(Gate):
    """XOR gate - outputs 1 if odd number of inputs are 1"""
    def __cinit__(self):
        self.id = XOR_ID
    def __init__(self):
        Gate.__init__(self)
    cdef void process(self):
        self.prev_output = self.output
        cdef int* book = self.book

        cdef int realsource=book[HIGH]+book[LOW]
        cdef int inputlimit=self.inputlimit
        if MODE == DESIGN:
            # if we are designing, nothing works yet
            self.output = UNKNOWN
        else:
            if realsource == inputlimit:
                self.output = book[HIGH] &1
            elif MODE == FLIPFLOP and realsource and realsource+book[UNKNOWN]+book[ERROR] == inputlimit:
                self.output = book[HIGH] &1
            else:
                self.output = UNKNOWN

cdef class XNOR(Gate):
    """XNOR gate - NOT XOR"""
    def __cinit__(self):
        self.id = XNOR_ID
    def __init__(self):
        Gate.__init__(self)
    cdef void process(self):
        self.prev_output = self.output
        cdef int* book = self.book

        cdef int realsource=book[HIGH]+book[LOW]
        cdef int inputlimit=self.inputlimit
        if MODE == DESIGN:
            # if we are designing, nothing works yet
            self.output = UNKNOWN
        else:
            if realsource == inputlimit:
                self.output = (book[HIGH] &1) ^ 1
            elif MODE == FLIPFLOP and realsource and realsource+book[UNKNOWN]+book[ERROR] == inputlimit:
                self.output = (book[HIGH] &1) ^ 1
            else:
                self.output = UNKNOWN


