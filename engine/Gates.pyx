# distutils: language = c++
from __future__ import annotations
from collections import deque
from libcpp.vector cimport vector
from libcpp.deque cimport deque
from libcpp.unordered_set cimport unordered_set
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, FLIPFLOP,get_MODE

cpdef run(list varlist):
    cdef Profile profile
    cdef Variable variable
    
    for variable in varlist:
        variable.process()

    for variable in varlist:
        for profile in variable.hitlist:
            if profile.target.output==ERROR:
                update(profile,variable.output)
                profile.target.sync()
                profile.target.process()
                profile.target.propagate()
            elif update(profile,variable.output):
                profile.target.propagate()

from libc.stdlib cimport malloc, free

# You might need to import Variable and Gate depending on your setup
# from LogicComponents import Variable, Gate 

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

cpdef listdel(lst, index):
    if lst:
        lst[index] = lst[-1]
        lst.pop()

cpdef hitlist_del(list hitlist, int index):
    if hitlist:
        hitlist[index] = hitlist[-1]
        hitlist.pop()

cpdef int locate(Gate target, Gate agent):
    cdef int i
    cdef Profile profile
    for i, profile in enumerate(agent.hitlist):
        if profile.target == target:
            return i
    return -1
cdef class Empty:
    def __init__(self):
        self.code = ('X', 'X')
    def __repr__(self):
        return 'Empty'

    def __str__(self):
        return 'Empty'

Nothing = Empty()


cpdef add(Profile profile, int pin_index):
    profile.index.push_back(pin_index)
    profile.target.book[profile.output] += 1


cpdef bint remove(Profile profile, int pin_index):
    cdef Gate target = profile.target
    target.sources[pin_index] = Nothing
    # Find the position of this index in our index list, then remove it
    cdef size_t i = 0
    while i < profile.index.size():
        if profile.index[i] == pin_index:
            profile.index[i] = profile.index.back()
            profile.index.pop_back()
            break
        i += 1

    target.book[profile.output] -= 1
    if profile.index.empty():
        return True
    else:
        return False


cpdef hide(Profile profile):
    cdef Gate target = profile.target
    target.book[profile.output] -= profile.index.size()
    for index in profile.index:
        target.sources[index] = Nothing
    profile.output = UNKNOWN


cpdef reveal(Profile profile,Gate source):
    cdef Gate target = profile.target
    target.book[UNKNOWN] += profile.index.size()
    for index in profile.index:
        target.sources[index] = source


cpdef bint update(Profile profile, int new_output):
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
    target.book[profile.output] -= count
    target.book[new_output] += count
    
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


cpdef bint burn(Profile profile):
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

    def __repr__(self):
        return f"{self.target} {self.index} {self.output}"
    
    def __str__(self):
        return f"{self.target} {self.index} {self.output}"

cdef class Gate:
    # the blueprint for all logical gates
    # it handles inputs, outputs, and processing logic

    def __init__(self):
        # who feeds into this gate? (inputs)
        self.sources: list = [Nothing, Nothing]
        # who does this gate feed into? (outputs)
        self.hitlist:list= []
        # how many inputs do we need?
        self.inputlimit = 2
        # keeps track of what kind of inputs we have (high, low, etc)
        self.book[:]= [0, 0, 0, 0]
        
        # current and previous state
        self.output = UNKNOWN
        self.prev_output = UNKNOWN
        
        # identity details
        self.code = ()
        self.name = ''
        self.custom_name = ''

    # calculates the output based on inputs
    cpdef process(self):
        pass
       
    cpdef rename(self,str name):
        self.name = name

    def __repr__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.name if self.custom_name == '' else self.custom_name

    # checks if the gate is ready to calculate an output
    cpdef bint isready(self):
        cdef int realsource
        if get_MODE() == DESIGN:
            # if we are designing, nothing works yet
            return False
        else:
            realsource = self.book[HIGH]+self.book[LOW]+self.book[ERROR]
            if get_MODE() == SIMULATE:
                # in simulation, we need all inputs connected
                return realsource == self.inputlimit
            else:
                # in flipflop mode, we're a bit more lenient
                return realsource and realsource+self.book[UNKNOWN] == self.inputlimit

    # connect a source gate (input) to this gate
    cpdef connect(self, Gate source, int index):
        cdef int loc = locate(self, source)
        cdef Profile profile
        if loc != -1:
            profile = source.hitlist[loc]
            add(profile, index)
        else:
            profile = Profile(self, index, source.output)
            source.hitlist.append(profile)
        # actually plug it in
        self.sources[index] = source
        
        # if something is wrong with the input, react
        if source.output==ERROR:
            if self.isready():
                self.burn()
        else:
            # otherwise, recalculate our output
            self.process()

    cpdef bypass(self):
        cdef Profile profile
        for profile in self.hitlist:
            if update(profile,self.output):
                profile.target.propagate()

    # protect against weird loops by resetting counts
    cpdef sync(self):
        self.book[:]=[0,0,0,0]
        for source in self.sources:
            if source!=Nothing:
                self.book[source.output]+=1

    # handles error states and spreads the error
    cpdef burn(self):
        cdef Gate gate
        cdef deque[void*] q
        cdef Profile profile
        q.push_back(<void*>self)
        while q.size():
            gate = <Gate>q.front()
            q.pop_front()
            gate.prev_output = gate.output
            # mark as error
            gate.output = ERROR 
            # mark as error
            gate.output = ERROR 
            for profile in gate.hitlist:
                # update target's knowledge
                if burn(profile) and profile.target.isready():
                    q.push_back(<void*>profile.target)

    # spread the signal change to all connected gates
    cpdef propagate(self):
        cdef Gate gate
        cdef Gate target
        cdef deque[void*] q
        cdef Profile profile
        cdef unordered_set[void*] fuse
        if get_MODE()==FLIPFLOP:
            # notify all targets
            q.push_back(<void*>self)
            # keep propagating until everything settles
            while q.size():
                gate = <Gate>q.front()
                q.pop_front()
                for profile in gate.hitlist:
                    target=<Gate>profile.target
                    if update(profile,gate.output):
                        # check for loops or inconsistencies
                        if gate==target: 
                            gate.burn()
                            return
                        if fuse.count(<void*>profile): 
                            gate.burn()
                            return
                        fuse.insert(<void*>profile)
                        q.push_back(<void*>target)
        elif get_MODE()==SIMULATE:# don't need fuse, the logic itself is loop-proof
            q.push_back(<void*>self)                       
            # keep propagating until everything settles
            while q.size():
                gate = <Gate>q.front()
                q.pop_front()
                for profile in gate.hitlist:
                    target=<Gate>profile.target
                    if update(profile,gate.output):
                        q.push_back(<void*>target)

        else:
            pass

    # remove a connection at a specific index
    cpdef disconnect(self,int index):
        cdef Gate source = self.sources[index]
        cdef int loc = locate(self, source)
        cdef Profile profile
        if loc != -1:
            profile = source.hitlist[loc]
            remove(profile, index)
            if profile.index.empty():
                hitlist_del(source.hitlist, loc)
        
        # recalculate everything
        source.process()
        source.propagate()
        self.process()
        self.propagate()

    cpdef reset(self):
        self.output = UNKNOWN
        cdef int i
        cdef int n
        i=0
        n=len(self.book)
        cdef Profile profile
        cdef int sums=0
        while i<n:
            sums+=self.book[i]
            i+=1
        self.book[:]=[0, 0, 0, sums]
        self.prev_output = UNKNOWN
        
        for profile in self.hitlist:
            profile.output=UNKNOWN

    cpdef hide(self):
        # disconnect from targets (this gate's outputs)
        cdef Profile profile
        cdef Gate target
        cdef int loc
        cdef int index
        for profile in self.hitlist:
            hide(profile)
        
        # disconnect from sources (this gate's inputs)
        for index, source in enumerate(self.sources):
            if source != Nothing:
                loc = locate(self, source)
                if loc != -1:
                    profile = source.hitlist[loc]
                    remove(profile, index)
                    self.sources[index]=source
                    if profile.index.empty():
                        hitlist_del(source.hitlist, loc)
        
        # recalculate targets
        for profile in self.hitlist:
            target = profile.target
            if target != self:
                target.process()
                target.propagate()

        self.prev_output = UNKNOWN
        self.output = UNKNOWN
        self.book[:] = [0, 0, 0, 0]

    cpdef reveal(self):
        # reconnect to sources (rebuild this gate's inputs)
        cdef int loc
        cdef Profile profile
        for i, source in enumerate(self.sources):
            if source != Nothing:
                # Re-register with the source's hitlist
                loc = locate(self, source)
                if loc != -1:
                    # Profile already exists, just add the index
                    add(source.hitlist[loc], i)
                else:
                    # Create new profile
                    source.hitlist.append(Profile(self, i, source.output))
        self.process()
        
        # reconnect to targets (this gate's outputs)
        for profile in self.hitlist:
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

    cpdef json_data(self):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code for source in self.sources],
        }
        return dictionary

    cpdef copy_data(self, set cluster):
        dictionary = {
            "name": self.name,
            "custom_name": "", # Do not copy custom name for gates
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source != Nothing and source in cluster else Nothing.code for source in self.sources],
            }
        return dictionary

    cpdef decode(self,list code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    cpdef clone(self, dict dictionary,dict pseudo):
        self.custom_name = dictionary["custom_name"]
        self.setlimits(dictionary["inputlimit"])
        for index,source in enumerate(dictionary["source"]):
            if source[0]!='X':
                self.connect(pseudo[self.decode(source)],index)

    cpdef load_to_cluster(self,set cluster):
        cluster.add(self)




cdef class Variable(Gate):
    def __init__(self):
        Gate.__init__(self)
        self.sources = 0
        self.inputlimit = 1
    cpdef bint setlimits(self,int size):
        return False
    cpdef connect(self, Gate source, int index):
        pass
    cpdef disconnect(self, int index):
        pass
    cpdef toggle(self, int source):
        self.sources = source
        self.process()

    cpdef reset(self):
        self.output = UNKNOWN
        self.prev_output = UNKNOWN
        cdef Profile profile
        for profile in self.hitlist:
            profile.output=UNKNOWN

    cpdef bint isready(self):
        if get_MODE()==DESIGN:
            return False
        else:
            return True
    
    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.sources
        else:
            self.output = UNKNOWN

    cpdef json_data(self):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "source": self.sources,
        }
        return dictionary

    cpdef clone(self,dict dictionary, dict pseudo):
        self.custom_name = dictionary["custom_name"]
        self.sources = dictionary["source"]

    cpdef copy_data(self,set cluster):
        dictionary = {
            "name": self.name,
            "custom_name": "", # Do not copy custom name for gates
            "code": self.code,
            "source": self.sources,
            }
        return dictionary

    cpdef hide(self):
        # disconnect from target
        cdef Profile profile
        cdef Gate target
        for hits in self.hitlist:
            hide(hits)

        for profile in self.hitlist:
            target = profile.target
            if target != self:
                target.process()
                target.propagate()

    cpdef reveal(self):
        # connect to targets
        for profile in self.hitlist:
            reveal(profile, self)

        self.propagate()

cdef class Probe(Gate):
    def __init__(self):
        Gate.__init__(self)
        self.inputlimit = 1
        self.sources = [Nothing]

    cpdef bint setlimits(self,int size):
        return False

    cpdef bint isready(self):
        if get_MODE()==DESIGN:
            return False
        elif self.sources[0]!=Nothing:
            return True
        else:
            return False
    cpdef copy_data(self, set cluster):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name, 
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source != Nothing and source in cluster else Nothing.code for source in self.sources],
            }
        return dictionary

    cpdef clone(self, dict dictionary, dict pseudo):
        self.custom_name = dictionary["custom_name"]
        self.setlimits(dictionary["inputlimit"])
        for index,source in enumerate(dictionary["source"]):
            if source[0]!='X':
                self.connect(pseudo[self.decode(source)],index)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
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

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[LOW]
        else:
            self.output = UNKNOWN

cdef class AND(Gate):
    """AND gate - outputs 1 only if all inputs are 1"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[LOW] else 1
        else:
            self.output = UNKNOWN


cdef class NAND(Gate):
    """NAND gate - NOT AND"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[LOW] else 0
        else:
            self.output = UNKNOWN

cdef class OR(Gate):
    """OR gate - outputs 1 if any input is 1"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[HIGH] else 0
        else:
            self.output = UNKNOWN

cdef class NOR(Gate):
    """NOR gate - NOT OR"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[HIGH] else 1
        else:
            self.output = UNKNOWN

cdef class XOR(Gate):
    """XOR gate - outputs 1 if odd number of inputs are 1"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[HIGH] % 2
        else:
            self.output = UNKNOWN

cdef class XNOR(Gate):
    """XNOR gate - NOT XOR"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = (self.book[HIGH] % 2) ^ 1
        else:
            self.output = UNKNOWN

