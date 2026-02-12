# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
from libcpp.vector cimport vector
from libcpp.deque cimport deque
from libcpp.unordered_set cimport unordered_set
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, FLIPFLOP, MODE,AND as AND_ID,OR as OR_ID,NOT as NOT_ID,XOR as XOR_ID,NAND as NAND_ID,NOR as NOR_ID,XNOR as XNOR_ID,VARIABLE as VARIABLE_ID,PROBE as PROBE_ID


cdef deque[void*] q
cdef vector[Profile*] fuse

cpdef void run(list varlist):
    cdef Profile* profile
    cdef Variable variable
    cdef size_t i
    cdef size_t n
    cdef Profile* hitlist
    cdef Gate target
    cdef int* book
    for variable in varlist:
        variable.process()

    for variable in varlist:
        n=variable.hitlist.size()
        hitlist = variable.hitlist.data()
        for i in range(n):
            profile=&hitlist[i]
            target = <Gate>profile.target
            if target.output==ERROR:
                profile.output=variable.output
                target.sync()
                target.process()
                target.propagate()
            
            book=target.book
            book[profile.output]-=1
            book[variable.output]+=1
            profile.output=variable.output
            target.process()
            if target.prev_output!=target.output:
                target.propagate()

cdef void clear_fuse():
    cdef Profile* profile
    cdef size_t i
    cdef size_t size = fuse.size()
    for i in range(size):
        profile = fuse[i]
        profile.index*=-1
    fuse.clear()

cpdef str table(list gatelist, list varlist):
    from IC import IC
    # Declarations
    cdef list gate_list = []
    cdef list var_names, gate_names, inputs, output_vals, all_names, row_data, header_parts
    cdef list Table = []
    cdef str row, header, separator
    cdef int col_width, bit
    cdef Py_ssize_t i, j, n, k
    
    # Filter gatelist
    for item in gatelist:
        # Use simple type checking or isinstance depending on your import availability
        if isinstance(item, Variable): 
            continue
        elif isinstance(item, Gate):
            gate_list.append(item)
        else:
            # Assuming item is an IC
            for pin in item.outputs:
                gate_list.append(pin)

    n = len(varlist)
    # 1 << n is bitwise for 2^n
    cdef int rows_count = 1 << n
    cdef Variable var
    # Collect decoded variable names
    var_names = [v.name for v in varlist]
    gate_names = [v.name for v in gate_list]
    all_names = var_names + gate_names

    if len(all_names) > 0:
        col_width = max([len(name) for name in all_names]) + 2
    else:
        col_width = 4

    header_parts = [name.center(col_width) for name in all_names]
    header = " | ".join(header_parts)
    separator = "─" * len(header)

    Table.append(separator + '\n')
    Table.append(header + '\n')
    Table.append(separator + '\n')

    for i in range(rows_count):
        inputs = []
        for j in range(n):
            # Retrieve variable
            var = varlist[j]
            
            # Calculate bit
            bit = 1 if (i & (1 << (n - j - 1))) else 0
            
            var.toggle(bit)
            if var.prev_output != var.output:
                var.propagate()
            
            inputs.append("1" if bit else "0")
        
        # Calculate outputs
        output_vals = [str(gate.getoutput()) for gate in gate_list]
        
        row_data = inputs + output_vals
        row_parts = [val.center(col_width) for val in row_data]
        
        row = " | ".join(row_parts)
        Table.append(row + '\n')

    Table.append(separator + '\n')
    
    return "".join(Table)


cdef class Empty:
    def __init__(self):
        self.code = ('X', 'X')
        self.output = UNKNOWN
    def __repr__(self):
        return 'Empty'

    def __str__(self):
        return 'Empty'

Nothing = Empty()

cdef void create(vector[Profile]& hitlist, Gate target, int pin_index,int output):
    cdef void* target_ptr = <void*>target
    hitlist.push_back(Profile(target_ptr, pin_index, output))
    target.book[output] += 1

cdef void add(vector[Profile]& hitlist, Gate target, int pin_index,int output):
    cdef void* target_ptr = <void*>target
    hitlist.push_back(Profile())
    cdef int i=hitlist.size()-1
    while i>0 and hitlist[i-1].target != target_ptr:
        hitlist[i]=hitlist[i-1]
        i-=1
    hitlist[i].target=target_ptr
    hitlist[i].index=pin_index
    hitlist[i].output=output

    target.book[output] += 1


cdef void remove(vector[Profile]& hitlist,Gate target, int pin_index):
    target.sources[pin_index] = Nothing
    cdef void* target_ptr = <void*>target
    cdef size_t i = 0
    cdef size_t n = hitlist.size()
    for i in range(n):
        if hitlist[i].target == target_ptr and hitlist[i].index == pin_index:
            target.book[hitlist[i].output] -= 1
            hitlist.erase(hitlist.begin()+i)
            break

cdef void hide(Profile& profile):
    cdef Gate target = <Gate>profile.target
    target.book[profile.output] -= 1
    target.sources[profile.index] = Nothing
    profile.output = UNKNOWN


cdef void reveal(Profile& profile,Gate source):
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
        self.sources: list = [Nothing, Nothing]
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
        self.id = -1


    def __repr__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.name if self.custom_name == '' else self.custom_name

    # def __dealloc__(self):
    #     cdef size_t i
    #     # We must cast to PyObject* to decrease refcount
    #     for i in range(self.hitlist.size()):
    #         Py_XDECREF(<PyObject*>self.hitlist[i])
    #     self.hitlist.clear()

    # cdef void purge(self):
    #     cdef size_t i
    #     # We must cast to PyObject* to decrease refcount
    #     cdef Profile* hitlist = self.hitlist.data()
    #     for i in range(self.hitlist.size()):
    #         Py_XDECREF(<PyObject*>(hitlist[i]))
    #     self.hitlist.clear()
    
    @property
    def hitlist(self):
        cdef list result = []
        cdef size_t i
        cdef size_t size = self.hitlist.size()
        for i in range(size):
            result.append(<Gate>self.hitlist[i].target)
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
            if self.isready():
                self.burn()
        else:
            # otherwise, recalculate our output
            self.process()

    # cdef void bypass(self):
    #     cdef Profile* profile
    #     cdef size_t i
    #     cdef int size = self.hitlist.size()
    #     cdef Profile* hitlist = self.hitlist.data()
    #     cdef Gate target
    #     for i in range(size):
    #         target = <Gate>hitlist[i].target
    #         if update(hitlist[i],self.output):
    #             target.propagate()

    # protect against weird loops by resetting counts
    cdef void sync(self):
        cdef int* book = self.book
        book[:]=[0,0,0,0]
        for source in self.sources:
            if source!=Nothing:
                book[source.output]+=1

    # handles error states and spreads the error
    cdef void burn(self):
        cdef Gate gate
        cdef deque[void*] q
        cdef Profile* profile
        cdef size_t i
        cdef size_t size
        cdef Profile* hitlist 
        cdef Gate target
        q.push_back(<void*>self)
        # keep propagating until everything settles
        while q.size():
            gate = <Gate>q.front()
            q.pop_front()
            hitlist = gate.hitlist.data()
            size = gate.hitlist.size()
            gate.output = ERROR
            for i in range(size):
                profile = &hitlist[i]
                target=<Gate>profile.target
                profile.output = ERROR
                if i==size-1 or profile.target!=hitlist[i+1].target:
                    target.sync()
                    if target.isready() and target.output!=ERROR:
                        q.push_back(<void*>target)
            q.clear()
    # spread the signal change to all connected gates

    cpdef void propagate(self):
        cdef Gate gate
        cdef Gate target
        cdef Profile* profile
        cdef Profile* hitlist
        cdef size_t size
        cdef size_t i
        cdef int* book
        cdef int gate_type
        cdef int realsource
        cdef int high
        cdef int low
        if MODE==FLIPFLOP:
            # notify all targets
            q.push_back(<void*>self)
            # keep propagating until everything settles
            while q.size():
                gate = <Gate>q.front()
                q.pop_front()
                hitlist = gate.hitlist.data()
                size = gate.hitlist.size()
                for i in range(size):
                    profile = &hitlist[i]
                    if gate.output!=profile.output:
                        target=<Gate>profile.target
                        book = target.book
                        book[profile.output]-=1
                        book[gate.output]+=1
                        profile.output = gate.output
                        if i==size-1 or profile.target!=hitlist[i+1].target:
                            gate_type = target.id
                            target.prev_output=target.output
                            high=book[HIGH]
                            low=book[LOW]
                            if high+low==target.inputlimit or high+low+book[UNKNOWN]+book[ERROR]==target.inputlimit:
                                if gate_type==NOT_ID:
                                    target.output=low
                                elif gate_type==AND_ID:
                                    target.output = low==0
                                elif gate_type==NAND_ID:
                                    target.output = low!=0
                                elif gate_type==OR_ID:
                                    target.output = high>0
                                elif gate_type==NOR_ID:
                                    target.output = high==0
                                elif gate_type==XOR_ID:
                                    target.output = high&1
                                elif gate_type==XNOR_ID:
                                    target.output = (high&1)^1
                                elif gate_type==VARIABLE_ID:
                                    target.output=target.value
                                else:
                                    target.output=high
                            if target.prev_output!=target.output:
                                if gate==target: 
                                    q.clear()
                                    gate.burn()
                                    break
                                if profile.index<0: 
                                    q.clear()
                                    gate.burn()
                                    break
                                profile.index*=-1
                                fuse.push_back(profile)
                                q.push_back(<void*>target)
            q.clear()
            clear_fuse()
        elif MODE==SIMULATE:# don't need fuse, the logic itself is loop-proof
            q.push_back(<void*>self)
            # keep propagating until everything settles
            while q.size():
                gate = <Gate>q.front()
                q.pop_front()
                hitlist = gate.hitlist.data()
                size = gate.hitlist.size()
                for i in range(size):
                    profile = &hitlist[i]
                    if gate.output!=profile.output:
                        target=<Gate>profile.target
                        book = target.book
                        book[profile.output]-=1
                        book[gate.output]+=1
                        profile.output = gate.output
                        if i==size-1 or profile.target!=hitlist[i+1].target:
                            gate_type = target.id
                            target.prev_output=target.output
                            high=book[HIGH]
                            low=book[LOW]
                            if high+low==target.inputlimit:
                                if gate_type==NOT_ID:
                                    target.output=low
                                elif gate_type==AND_ID:
                                    target.output = low==0
                                elif gate_type==NAND_ID:
                                    target.output = low!=0
                                elif gate_type==OR_ID:
                                    target.output = high>0
                                elif gate_type==NOR_ID:
                                    target.output = high==0
                                elif gate_type==XOR_ID:
                                    target.output = high&1
                                elif gate_type==XNOR_ID:
                                    target.output = (high&1)^1
                                elif gate_type==VARIABLE_ID:
                                    target.output=target.value
                                else:
                                    target.output=high
                            if target.prev_output!=target.output:
                                q.push_back(<void*>target)
            q.clear()
        else:
            pass

    # remove a connection at a specific index
    cpdef void disconnect(self,int index):
        cdef Gate source = self.sources[index]
        remove(source.hitlist, self, index)
        # recalculate everything
        source.process()
        source.propagate()
        self.process()
        self.propagate()

   
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
            if source != Nothing:
                src = <Gate>source
                remove(src.hitlist, self, index)
                self.sources[index] = source
        
        # recalculate targets
        for i in range(self.hitlist.size()):
            target = <Gate>hitlist[i].target
            if target != self:
                target.process()
                target.propagate()

        self.output = UNKNOWN
        self.book[:] = [0, 0, 0, 0]

    cdef void reveal(self):
        # reconnect to sources (rebuild this gate's inputs)
        cdef int loc
        cdef Profile* profile
        cdef Profile* hitlist = self.hitlist.data()
        cdef Gate src
        for i, source in enumerate(self.sources):
            if source != Nothing:
                src = <Gate>source
                add(src.hitlist, self, i, src.output)
        self.process()
        
        # reconnect to targets (this gate's outputs)
        for i in range(self.hitlist.size()):
            reveal(hitlist[i], self)
        
        self.propagate()

    cpdef bint setlimits(self,int size):
        cdef int i
        cdef int n

        if size>self.inputlimit:
            for _ in range(size-self.inputlimit):
                self.sources.append(Nothing)
            self.inputlimit=size
            return True
        elif size<self.inputlimit:
            for i in range(size, self.inputlimit):
                if self.sources[i] != Nothing:
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
            "source": [source.code for source in self.sources],
        }
        return dictionary

    cpdef dict copy_data(self, set cluster):
        dictionary = {
            "name": self.name,
            "custom_name": "", # Do not copy custom name for gates
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source != Nothing and source in cluster else Nothing.code for source in self.sources],
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
    def __init__(self):
        Gate.__init__(self)
        self.value = 0
        self.inputlimit = 1
        self.id = VARIABLE_ID
        self.sources = [Nothing]
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
        cdef Profile* profile
        cdef Profile* hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            profile = &hitlist[i]
            profile.output=UNKNOWN
    
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
                target.propagate()

    cdef void reveal(self):
        # connect to targets
        cdef Profile* hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            reveal(hitlist[i], self)
        self.propagate()

cdef class Probe(Gate):
    def __init__(self):
        Gate.__init__(self)
        self.inputlimit = 1
        self.id=PROBE_ID
        self.sources = [Nothing]

    cpdef bint setlimits(self,int size):
        return False

    cdef bint isready(self):
        if MODE==DESIGN:
            return False
        elif self.sources[0]!=Nothing:
            return True
        else:
            return False
    cpdef dict copy_data(self, set cluster):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name, 
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source != Nothing and source in cluster else Nothing.code for source in self.sources],
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
        if MODE != DESIGN and self.sources[0] != Nothing:
            self.output = self.sources[0].output
        else:
            self.output = UNKNOWN

cdef class InputPin(Probe):
    def __init__(self):
        Probe.__init__(self)

cdef class OutputPin(Probe):
    def __init__(self):
        Probe.__init__(self)


cdef class NOT(Gate):
    """NOT gate - inverts the input"""
    
    def __init__(self):
        Gate.__init__(self)
        self.inputlimit = 1
        self.sources = [Nothing]
        self.id = NOT_ID
    cdef void process(self):
        self.prev_output = self.output
        cdef int* book = self.book

        if MODE != DESIGN and (book[LOW] or book[HIGH]):
            self.output = book[LOW]
        else:
            self.output = UNKNOWN


cdef class AND(Gate):
    """AND gate - outputs 1 only if all inputs are 1"""
    
    def __init__(self):
        Gate.__init__(self)
        self.id = AND_ID
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
    
    def __init__(self):
        Gate.__init__(self)
        self.id = NAND_ID
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
    
    def __init__(self):
        Gate.__init__(self)
        self.id = OR_ID
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
    
    def __init__(self):
        Gate.__init__(self)
        self.id = NOR_ID    
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
    
    def __init__(self):
        Gate.__init__(self)
        self.id = XOR_ID    
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
    
    def __init__(self):
        Gate.__init__(self)
        self.id = XNOR_ID       
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


