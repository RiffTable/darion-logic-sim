# distutils: language = c++
from __future__ import annotations
from collections import deque
from libcpp.vector cimport vector
from libcpp.deque cimport deque
from libcpp.unordered_set cimport unordered_set
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, FLIPFLOP,get_MODE

cpdef listdel(lst, index):
    if lst:
        lst[index] = lst[-1]
        lst.pop()

cpdef hitlist_del(list hitlist,int index, dict targets_dict):
    if hitlist:
        last_idx = len(hitlist) - 1
        if index != last_idx:
            last_target=hitlist[-1].target
            hitlist[index]=hitlist[-1]
            targets_dict[last_target]=index
        hitlist.pop()
cdef class Empty:
    def __init__(self):
        self.code = ('X', 'X')
        self.targets={}
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


cpdef reveal(Profile profile):
    cdef Gate target = profile.target
    target.book[UNKNOWN] += profile.index.size()
    for index in profile.index:
        target.sources[index] = profile.source


cpdef bint update(Profile profile):
    cdef int new_output = profile.source.output
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
    def __init__(self, Gate source, Gate target, int index, int output):
        self.source = source
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
        self.targets: dict = {}
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
        cdef int loc
        if self in source.targets:
            loc=source.targets[self]
            add(source.hitlist[loc], index)
        else:
            source.hitlist.append(Profile(source,self,index,source.output))
            source.targets[self]=len(source.hitlist)-1            
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
        cdef int i=0
        cdef int n=len(self.hitlist)
        while i<n:
            profile=<Profile>self.hitlist[i]
            if update(profile):
                profile.target.propagate()  
            i+=1

    # protect against weird loops by resetting counts
    cpdef sync(self):
        self.book[:]=[0,0,0,0]
        cdef int i=0
        cdef int n=len(self.sources)
        while i<n:
            source=self.sources[i]
            if source!=Nothing:
                self.book[source.output]+=1
            i+=1

    # handles error states and spreads the error
    cpdef burn(self):
        cdef Gate gate
        cdef deque[void*] q
        cdef int i
        cdef int n
        q.push_back(<void*>self)
        while q.size():
            gate = <Gate>q.front()
            q.pop_front()
            gate.prev_output = gate.output
            # mark as error
            gate.output = ERROR 
            i=0
            n=len(gate.hitlist)
            while i<n:
                profile=<Profile>gate.hitlist[i]
                # update target's knowledge
                if burn(profile) and profile.target.isready():
                    q.push_back(<void*>profile.target)
                i+=1

    # spread the signal change to all connected gates
    cpdef propagate(self):
        cdef Gate gate
        cdef Gate target
        cdef deque[void*] q
        cdef Profile profile
        cdef unordered_set[void*] fuse
        cdef int i
        cdef int n
        if get_MODE()==FLIPFLOP:
            # notify all targets
            q.push_back(<void*>self)
            # keep propagating until everything settles
            while q.size():
                gate = <Gate>q.front()
                q.pop_front()
                i=0
                n=len(gate.hitlist)
                while i<n:
                    profile=<Profile>gate.hitlist[i]
                    target=<Gate>profile.target
                    if update(profile):
                        # check for loops or inconsistencies
                        if gate==target: 
                            gate.burn()
                            return
                        if fuse.count(<void*>profile): 
                            gate.burn()
                            return
                        fuse.insert(<void*>profile)
                        q.push_back(<void*>target)
                    i+=1
        elif get_MODE()==SIMULATE:# don't need fuse, the logic itself is loop-proof
            q.push_back(<void*>self)                       
            # keep propagating until everything settles
            while q.size():
                gate = <Gate>q.front()
                q.pop_front()
                i=0
                n=len(gate.hitlist)
                while i<n:
                    profile=<Profile>gate.hitlist[i]
                    target=<Gate>profile.target
                    if update(profile):
                        q.push_back(<void*>target)
                    i+=1

        else:
            pass

    # remove a connection at a specific index
    cpdef disconnect(self,int index):
        cdef Gate source = self.sources[index]
        cdef int loc=source.targets[self]
        cdef Profile profile=source.hitlist[loc]
        if remove(profile, index):
            hitlist_del(source.hitlist, loc, source.targets)
            source.targets.pop(self)
        
        # recalculate everything
        source.process()
        source.propagate()
        self.process()
        self.propagate()

    cpdef reset(self):
        self.output = UNKNOWN
        cdef int i
        cdef int n
        sums=0
        i=0
        n=len(self.book)
        while i<n:
            sums+=self.book[i]
            i+=1
        self.book[:]=[0, 0, 0, sums]
        self.prev_output = UNKNOWN
        i=0
        n=len(self.hitlist)
        while i<n:
            profile=<Profile>self.hitlist[i]
            profile.output=UNKNOWN
            i+=1

    cpdef hide(self):
        # disconnect from targets (this gate's outputs)
        cdef int i
        cdef int n
        i=0
        n=len(self.hitlist)
        while i<n:
            profile=<Profile>self.hitlist[i]
            hide(profile)
            i+=1
        
        # disconnect from sources (this gate's inputs)
        i=0
        n=len(self.sources)
        while i<n:
            source=self.sources[i]
            if source != Nothing and self in source.targets:
                loc = source.targets.pop(self)
                hitlist_del(source.hitlist, loc, source.targets)
            i+=1
        
        # recalculate targets
        for target in self.targets.keys():
            if target != self:
                target.process()
                target.propagate()

        self.prev_output = UNKNOWN
        self.output = UNKNOWN
        self.book[:] = [0, 0, 0, 0]

    cpdef reveal(self):
        # reconnect to sources (rebuild this gate's inputs)
        cdef int i
        cdef int n
        i=0
        n=len(self.sources)
        while i<n:
            source=self.sources[i]
            if source != Nothing:
                # Re-register with the source's hitlist
                if self in source.targets:
                    # Profile already exists, just add the index
                    loc = source.targets[self]
                    source.hitlist[loc].add(i)
                else:
                    # Create new profile
                    source.hitlist.append(Profile(source, self, i, source.output))
                    source.targets[self] = len(source.hitlist) - 1
            i+=1
        self.process()
        
        # reconnect to targets (this gate's outputs)
        i=0
        n=len(self.hitlist)
        while i<n:
            profile=<Profile>self.hitlist[i]
            reveal(profile)
            i+=1
        
        self.propagate()

    cpdef bint setlimits(self,int size):
        cdef int i
        cdef int n

        if size>self.inputlimit:
            i=0
            n=size-self.inputlimit
            while i<n:
                self.sources.append(Nothing)
                i+=1
            self.inputlimit=size
            return True
        elif size<self.inputlimit:
            i=size
            n=self.inputlimit
            while i<n:
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
        cdef int i=0
        cdef int n=len(self.hitlist)
        while i<n:
            self.hitlist[i].output=UNKNOWN
            i+=1

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
        for hits in self.hitlist:
            hide(hits)

        for target in self.targets.keys():
            if target!=self:
                target.process()
                target.propagate()

    cpdef reveal(self):
        # connect to targets
        for profile in self.hitlist:
            reveal(profile)

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

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.sources[0].output
        else:
            self.output = UNKNOWN

cdef class InputPin(Probe):
    def __init__(self):
        Probe.__init__(self)
        self.inputlimit = 1

    cpdef copy_data(self, set cluster):
        d = super().copy_data(cluster)
        d["custom_name"] = self.custom_name
        return d

cdef class OutputPin(Probe):
    def __init__(self):
        Probe.__init__(self)
        self.inputlimit = 1

    cpdef copy_data(self,set cluster):
        d = super().copy_data(cluster)
        d["custom_name"] = self.custom_name
        return d 

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

