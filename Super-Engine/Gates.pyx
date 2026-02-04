from __future__ import annotations
from collections import deque
import Const

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
    cdef public tuple code
    cdef public dict targets
    def __init__(self):
        self.code = ('X', 'X')
        self.targets={}
    def __repr__(self):
        return 'Empty'

    def __str__(self):
        return 'Empty'

Nothing = Empty()
cdef class Gate
cdef class Probe

cdef class Profile:
    cdef public Gate source
    cdef public Gate target
    cdef public set index
    cdef public int weight
    cdef public int output
    def __init__(self, Gate source, Gate target, int index, int output):
        self.source:Gate=source
        self.target:Gate=target
        target.book[output] += 1
        self.index:set[int]={index}
        self.weight:int=1
        self.output:int=output

    def __repr__(self):
        return f"{self.target} {self.index} {self.weight} {self.output}"
    
    def __str__(self):
        return f"{self.target} {self.index} {self.weight} {self.output}"
    
    cpdef add(self, int index):
        self.index.add(index)
        self.target.book[self.output] += 1
        self.weight+=1
    
    cpdef remove(self, int index):
        target=self.target
        target.sources[index] = Nothing
        # Find the position of this index in our index list, then remove it
        self.index.discard(index)
        target.book[self.output] -= 1
        self.weight-=1
        if self.weight==0:
            return True
        else:
            return False

    cpdef hide(self):
        target=self.target
        target.book[self.output] -= self.weight
        for index in self.index:
            target.sources[index] = Nothing
        self.output=Const.UNKNOWN

    cpdef reveal(self):
        target=self.target
        target.book[Const.UNKNOWN] += self.weight
        for index in self.index:
            target.sources[index] = self.source
        
    cpdef bint update(self):
        new_output=self.source.output
        if self.output==new_output:
            # if nothing changed, relax
            return False
        target=self.target
        if isinstance(target,Probe):
            self.output=new_output
            target.output=self.output
            target.bypass()
            return False
        # update the target's records
        count=self.weight
        target.book[self.output] -= count
        target.book[new_output] += count
        
        if new_output==Const.ERROR:
            # error propagation
            if target.isready():
                target.output=Const.ERROR
        else:
            # let the target recalculate
            target.process()
            
        # update what the target thinks our output is
        self.output=new_output
        return target.prev_output != target.output

    cpdef burn(self):
        target=self.target
        target.sync()
        self.output=Const.ERROR
        return target.output!=Const.ERROR

cdef class Gate:
    cdef public object sources
    cdef public dict targets
    cdef public list hitlist
    cdef public int inputlimit
    cdef public int[4] book
    cdef public int output
    cdef public int prev_output
    cdef public tuple code
    cdef public str name
    cdef public str custom_name
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
        self.output = Const.UNKNOWN
        self.prev_output = Const.UNKNOWN
        
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
        if Const.MODE == Const.DESIGN:
            # if we are designing, nothing works yet
            return False
        else:
            realsource = self.book[Const.HIGH]+self.book[Const.LOW]+self.book[Const.ERROR]
            if Const.MODE == Const.SIMULATE:
                # in simulation, we need all inputs connected
                return realsource == self.inputlimit
            else:
                # in flipflop mode, we're a bit more lenient
                return realsource and realsource+self.book[Const.UNKNOWN] == self.inputlimit

    # connect a source gate (input) to this gate
    cpdef connect(self, Gate source, int index):
        if self in source.targets:
            loc=source.targets[self]
            self.hitlist[loc].add(index)
        else:
            source.hitlist.append(Profile(source,self,index,source.output))
            source.targets[self]=len(source.hitlist)-1            
        # actually plug it in
        self.sources[index] = source
        
        # if something is wrong with the input, react
        if source.output==Const.ERROR:
            if self.isready():
                self.burn()
        else:
            # otherwise, recalculate our output
            self.process()

    cpdef bypass(self):
        for profile in self.hitlist:
            if profile.update():
                profile.target.propagate()  

    # protect against weird loops by resetting counts
    cpdef sync(self):
        self.book[:]=[0,0,0,0]
        for source in self.sources:
            if source!=Nothing:
                self.book[source.output]+=1

    # handles error states and spreads the error
    cpdef burn(self):
        queue: deque[Gate] = deque()
        queue.append(self)
        while len(queue):
            gate = queue.popleft()
            gate.prev_output = gate.output
            # mark as error
            gate.output = Const.ERROR 
            for profile in gate.hitlist:
                # update target's knowledge
                if profile.burn() and profile.target.isready():
                    queue.append(profile.target)

    # spread the signal change to all connected gates
    cpdef propagate(self):
        if Const.MODE==Const.FLIPFLOP:
            fuse = set()
            queue: deque[Gate] = deque()
            # notify all targets
            queue.append(self)
            # keep propagating until everything settles
            while queue:
                gate = queue.popleft()
                for profile in gate.hitlist:
                    target=profile.target
                    if profile.update():
                        # check for loops or inconsistencies
                        if gate==target: 
                            gate.burn()
                            return
                        if profile in fuse: 
                            gate.burn()
                            return
                        fuse.add(profile)
                        queue.append(target)

        elif Const.MODE==Const.SIMULATE:# don't need fuse, the logic itself is loop-proof
            queue: deque[Gate] = deque()            
            queue.append(self)                       
            # keep propagating until everything settles
            while queue:
                gate = queue.popleft()
                for profile in gate.hitlist:
                    target=profile.target
                    if profile.update():
                        queue.append(target)

        else:
            pass

    # remove a connection at a specific index
    cpdef disconnect(self,int index):
        cdef Gate source = self.sources[index]
        cdef int loc=source.targets[self]
        cdef Profile profile=source.hitlist[loc]
        if profile.remove(index):
            hitlist_del(source.hitlist, loc, source.targets)
            source.targets.pop(self)
        
        # recalculate everything
        source.process()
        source.propagate()
        self.process()
        self.propagate()

    cpdef reset(self):
        self.output = Const.UNKNOWN
        cdef int sums
        sums=0
        for i in self.book:
            sums+=i
        self.book[:]=[0, 0, 0, sums]
        self.prev_output = Const.UNKNOWN
        for profile in self.hitlist:
            profile.output=Const.UNKNOWN

    cpdef hide(self):
        # disconnect from targets (this gate's outputs)
        for profile in self.hitlist:
            profile.hide()
        
        # disconnect from sources (this gate's inputs)
        for source in self.sources:
            if source != Nothing and self in source.targets:
                loc = source.targets.pop(self)
                hitlist_del(source.hitlist, loc, source.targets)
        
        # recalculate targets
        for target in self.targets.keys():
            if target != self:
                target.process()
                target.propagate()

        self.prev_output = Const.UNKNOWN
        self.output = Const.UNKNOWN
        self.book[:] = [0, 0, 0, 0]

    cpdef reveal(self):
        # reconnect to sources (rebuild this gate's inputs)
        for index, source in enumerate(self.sources):
            if source != Nothing:
                # Re-register with the source's hitlist
                if self in source.targets:
                    # Profile already exists, just add the index
                    loc = source.targets[self]
                    source.hitlist[loc].add(index)
                else:
                    # Create new profile
                    source.hitlist.append(Profile(source, self, index, source.output))
                    source.targets[self] = len(source.hitlist) - 1
        
        self.process()
        
        # reconnect to targets (this gate's outputs)
        for profile in self.hitlist:
            profile.reveal()
        
        self.propagate()

    cpdef bint setlimits(self,int size):
        if size>self.inputlimit:
            for i in range(self.inputlimit,size):
                self.sources.append(Nothing)
            self.inputlimit=size
            return True
        elif size<self.inputlimit:
            for i in range(size,self.inputlimit):
                if self.sources[i] != Nothing:
                    return False
            self.sources = self.sources[:size]
            self.inputlimit=size
            return True
        return False

    cpdef str getoutput(self):
        if self.output == Const.ERROR:
            return '1/0'
        if self.output == Const.UNKNOWN:
            return 'X'
        return 'T' if self.output == Const.HIGH else 'F'

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
        self.output = Const.UNKNOWN
        self.prev_output = Const.UNKNOWN
        for profile in self.hitlist:
            profile.output=Const.UNKNOWN

    cpdef bint isready(self):
        if Const.MODE==Const.DESIGN:
            return False
        else:
            return True
    
    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.sources
        else:
            self.output = Const.UNKNOWN

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
            hits.hide()

        for target in self.targets.keys():
            if target!=self:
                target.process()
                target.propagate()

    cpdef reveal(self):
        # connect to targets
        for profile in self.hitlist:
            profile.reveal()

        self.propagate()

cdef class Probe(Gate):
    def __init__(self):
        Gate.__init__(self)
        self.inputlimit = 1
        self.sources = [Nothing]

    cpdef bint setlimits(self,int size):
        return False

    cpdef bint isready(self):
        if Const.MODE==Const.DESIGN:
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
            self.output = Const.UNKNOWN




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
            self.output = self.book[Const.LOW]
        else:
            self.output = Const.UNKNOWN

cdef class AND(Gate):
    """AND gate - outputs 1 only if all inputs are 1"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[Const.LOW] else 1
        else:
            self.output = Const.UNKNOWN


cdef class NAND(Gate):
    """NAND gate - NOT AND"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[Const.LOW] else 0
        else:
            self.output = Const.UNKNOWN

cdef class OR(Gate):
    """OR gate - outputs 1 if any input is 1"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[Const.HIGH] else 0
        else:
            self.output = Const.UNKNOWN

cdef class NOR(Gate):
    """NOR gate - NOT OR"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[Const.HIGH] else 1
        else:
            self.output = Const.UNKNOWN

cdef class XOR(Gate):
    """XOR gate - outputs 1 if odd number of inputs are 1"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[Const.HIGH] % 2
        else:
            self.output = Const.UNKNOWN

cdef class XNOR(Gate):
    """XNOR gate - NOT XOR"""
    
    def __init__(self):
        Gate.__init__(self)

    cpdef process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = (self.book[Const.HIGH] % 2) ^ 1
        else:
            self.output = Const.UNKNOWN

