# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
from libcpp.vector cimport vector
from libcpp.deque cimport deque
from libcpp.unordered_set cimport unordered_set
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, FLIPFLOP, MODE
from cpython.ref cimport Py_XINCREF, Py_XDECREF, PyObject

cdef deque[void*] q
cdef vector[void*] fuse

cpdef run(list varlist):
    cdef Profile profile
    cdef Variable variable
    cdef size_t i
    cdef size_t n
    cdef void** hitlist
    cdef Gate target
    for variable in varlist:
        variable.process()

    for variable in varlist:
        n=variable.hitlist.size()
        hitlist = variable.hitlist.data()
        for i in range(n):
            profile = <Profile>hitlist[i]
            target = profile.target
            if target.output==ERROR:
                update(profile,variable.output)
                target.sync()
                target.process()
                target.propagate()
            elif update(profile,variable.output):
                target.propagate()
cdef void clear_fuse():
    cdef Profile profile
    cdef size_t i
    cdef size_t size = fuse.size()
    cdef void** data = fuse.data()
    for i in range(size):
        profile = <Profile>data[i]
        profile.red_flag = False
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



cdef hitlist_del(vector[void*]& hitlist, int index):
    cdef size_t n=hitlist.size()
    if n==1:
        Py_XDECREF(<PyObject*>hitlist.back())
        hitlist.pop_back()
    elif n>1:
        Py_XDECREF(<PyObject*>hitlist[index])
        hitlist[index] = hitlist.back()
        hitlist.pop_back()



cdef int locate(Gate target, vector[void*]& agent_hitlist):
    cdef size_t i
    cdef Profile profile
    for i in range(agent_hitlist.size()):
        profile = <Profile>agent_hitlist[i]
        if <void*>profile.target == <void*>target:
            return i
    return -1

cdef class Empty:
    def __init__(self):
        self.code = ('X', 'X')
        self.output = UNKNOWN
    def __repr__(self):
        return 'Empty'

    def __str__(self):
        return 'Empty'

Nothing = Empty()

cdef  create(vector[void*]& hitlist, Gate target, int pin_index,int output):
    cdef Profile profile = Profile(target, pin_index, output)
    Py_XINCREF(<PyObject*>profile)
    hitlist.push_back(<void*>profile)
    return profile

cdef  add(Profile profile, int pin_index):
    profile.index.push_back(pin_index)
    profile.target.book[profile.output] += 1


cdef  remove(Profile profile, int pin_index):
    cdef Gate target = profile.target
    target.sources[pin_index] = Nothing
    # Find the position of this index in our index list, then remove it
    cdef size_t i = 0
    cdef size_t n = profile.index.size()
    for i in range(n):
        if profile.index[i] == pin_index:
            profile.index[i] = profile.index.back()
            profile.index.pop_back()
            break

    target.book[profile.output] -= 1

cdef  hide(Profile profile):
    cdef Gate target = profile.target
    target.book[profile.output] -= profile.index.size()
    for index in profile.index:
        target.sources[index] = Nothing
    profile.output = UNKNOWN


cdef  reveal(Profile profile,Gate source):
    cdef Gate target = profile.target
    target.book[UNKNOWN] += profile.index.size()
    for index in profile.index:
        target.sources[index] = source


cdef  bint update(Profile profile, int new_output):
    cdef Gate target
    cdef int count
    if profile.output == new_output:
        # if nothing changed, relax
        return False
    target = profile.target
    if isinstance(target, Probe):
        profile.output = new_output
        target.output = profile.output
        target.bypass()
        return False
    # update the target's records
    count = profile.index.size()
    cdef int* book = target.book
    book[profile.output] -= count
    book[new_output] += count

    if new_output == ERROR:
        # error propagation
        if target.isready():
            target.output = ERROR
    else:
        # let the target recalculate
        target.process()
    # update what the target thinks our output is
    profile.output = new_output
    return target.prev_output != target.output


cdef  bint burn(Profile profile):
    cdef Gate target = profile.target
    target.sync()
    profile.output = ERROR
    return target.output != ERROR


cdef class Profile:
    def __init__(self, Gate target, int index, int output):
        self.target = target
        target.book[output] += 1
        self.index.push_back(index)
        self.output = output
        self.red_flag = False

    def __repr__(self):
        return f"{self.target} {self.index} {self.output}"
    
    def __str__(self):
        return f"{self.target} {self.index} {self.output}"

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


    def __repr__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def __dealloc__(self):
        cdef size_t i
        # We must cast to PyObject* to decrease refcount
        for i in range(self.hitlist.size()):
            Py_XDECREF(<PyObject*>self.hitlist[i])
        self.hitlist.clear()

    cdef void purge(self):
        cdef size_t i
        # We must cast to PyObject* to decrease refcount
        cdef void** hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            Py_XDECREF(<PyObject*>(hitlist[i]))
        self.hitlist.clear()
    
    @property
    def hitlist(self):
        cdef list result = []
        cdef size_t i
        cdef void** data = self.hitlist.data()
        cdef size_t size = self.hitlist.size()
        for i in range(size):
            result.append(<Profile>data[i])
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
        cdef int loc = -1        
        cdef Profile profile
        if len(self.sources)<source.hitlist.size():
            if source in self.sources:
                loc = locate(self, (<Gate>source).hitlist)
        else:
            loc = locate(self, (<Gate>source).hitlist)
        if loc != -1:
            profile = <Profile>(<Gate>source).hitlist[loc]
            add(profile, index)
        else:
            profile = create((<Gate>source).hitlist, self, index, source.output)
        # actually plug it in
        self.sources[index] = source
        
        # if something is wrong with the input, react
        if source.output==ERROR:
            if self.isready():
                self.burn()
        else:
            # otherwise, recalculate our output
            self.process()

    cdef void bypass(self):
        cdef Profile profile
        cdef size_t i
        cdef int size = self.hitlist.size()
        cdef void** hitlist = self.hitlist.data()
        for i in range(size):
            profile = <Profile>hitlist[i]
            if update(profile,self.output):
                profile.target.propagate()

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
        cdef Profile profile
        cdef size_t i
        cdef size_t size
        cdef void** hitlist 
        q.push_back(<void*>self)
        while q.size():
            gate = <Gate>q.front()
            q.pop_front()
            gate.prev_output = gate.output
            # mark as error
            gate.output = ERROR 
            # mark as error
            gate.output = ERROR 
            hitlist = gate.hitlist.data()
            size = gate.hitlist.size()
            for i in range(size):
                profile = <Profile>hitlist[i]
                # update target's knowledge
                if burn(profile) and profile.target.isready():
                    q.push_back(<void*>profile.target)
        q.clear()

    # spread the signal change to all connected gates

    cpdef void propagate(self):
        cdef Gate gate
        cdef Gate target
        cdef Profile profile
        cdef void** hitlist
        cdef size_t size
        cdef size_t i
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
                    profile = <Profile>hitlist[i]
                    target=<Gate>profile.target
                    if update(profile,gate.output):
                        # check for loops or inconsistencies
                        if gate==target: 
                            gate.burn()
                            break
                        if profile.red_flag: 
                            gate.burn()
                            break
                        profile.red_flag = True
                        fuse.push_back(<void*>profile)
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
                    profile = <Profile>hitlist[i]
                    target=<Gate>profile.target
                    if update(profile,gate.output):
                        q.push_back(<void*>target)
            q.clear()

        else:
            pass

    # remove a connection at a specific index
    cpdef void disconnect(self,int index):
        cdef Gate source = self.sources[index]
        cdef int loc = locate(self, source.hitlist)
        cdef Profile profile
        if loc != -1:
            profile = <Profile>source.hitlist[loc]
            remove(profile, index)
            if profile.index.empty():
                hitlist_del(source.hitlist, loc)
        
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
        cdef Profile profile
        cdef void** hitlist = self.hitlist.data()
        cdef int sums=0
        for i in range(n):
            sums+=book[i]
        book[:]=[0, 0, 0, sums]
        self.prev_output = UNKNOWN

        for i in range(self.hitlist.size()):
            profile = <Profile>hitlist[i]
            profile.output=UNKNOWN

    cdef void hide(self):
        # disconnect from targets (this gate's outputs)
        cdef Profile profile
        cdef Gate target
        cdef Gate src
        cdef int loc
        cdef int index
        cdef void** hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            profile = <Profile>hitlist[i]
            hide(profile)
        
        # disconnect from sources (this gate's inputs)
        for index, source in enumerate(self.sources):
            if source != Nothing:
                src = <Gate>source
                loc = locate(self, src.hitlist)
                if loc != -1:
                    profile = <Profile>src.hitlist[loc]
                    remove(profile, index)
                    self.sources[index]=source
                    if profile.index.empty():
                        hitlist_del(src.hitlist, loc)
        
        # recalculate targets
        for i in range(self.hitlist.size()):
            profile = <Profile>hitlist[i]
            target = profile.target
            if target != self:
                target.process()
                target.propagate()

        self.output = UNKNOWN
        self.book[:] = [0, 0, 0, 0]

    cdef void reveal(self):
        # reconnect to sources (rebuild this gate's inputs)
        cdef int loc
        cdef Profile profile
        cdef void** hitlist = self.hitlist.data()
        cdef Gate src
        for i, source in enumerate(self.sources):
            if source != Nothing:
                src = <Gate>source
                # Re-register with the source's hitlist
                loc = locate(self, src.hitlist)
                if loc != -1:
                    # Profile already exists, just add the index
                    add(<Profile>src.hitlist[loc], i)
                else:
                    # Create new profile
                    create(src.hitlist, self, i, src.output)
        self.process()
        
        # reconnect to targets (this gate's outputs)
        for i in range(self.hitlist.size()):
            profile = <Profile>hitlist[i]
            reveal(profile, self)
        
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
        self.sources = 0
        self.inputlimit = 1
    cpdef bint setlimits(self,int size):
        return False
    cpdef void connect(self, Gate source, int index):
        pass
    cpdef void disconnect(self, int index):
        pass
    cdef void toggle(self, int source):
        self.sources = source
        self.process()

    cdef void reset(self):
        self.output = UNKNOWN
        self.prev_output = UNKNOWN
        cdef Profile profile
        cdef void** hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            profile = <Profile>hitlist[i]
            profile.output=UNKNOWN
    
    cdef void process(self):
        self.prev_output = self.output
        if MODE != DESIGN:
            self.output = self.sources
        else:
            self.output = UNKNOWN

    cpdef dict json_data(self):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "source": self.sources,
        }
        return dictionary

    cpdef void clone(self,dict dictionary, dict pseudo):
        self.custom_name = dictionary["custom_name"]
        self.sources = dictionary["source"]

    cpdef dict copy_data(self,set cluster):
        dictionary = {
            "name": self.name,
            "custom_name": "", # Do not copy custom name for gates
            "code": self.code,
            "source": self.sources,
            }
        return dictionary

    cdef void hide(self):
        # disconnect from target
        cdef Profile profile
        cdef Gate target
        cdef void** hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            profile = <Profile>hitlist[i]
            hide(profile)

        for i in range(self.hitlist.size()):
            profile = <Profile>hitlist[i]
            target = profile.target
            if target != self:
                target.process()
                target.propagate()

    cdef void reveal(self):
        # connect to targets
        cdef Profile profile
        cdef void** hitlist = self.hitlist.data()
        for i in range(self.hitlist.size()):
            profile = <Profile>hitlist[i]
            reveal(profile, self)
        self.propagate()

cdef class Probe(Gate):
    def __init__(self):
        Gate.__init__(self)
        self.inputlimit = 1
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


