from __future__ import annotations
from collections import deque
import Const

def listdel(lst, index):
    if lst:
        lst[index] = lst[-1]
        lst.pop()

def hitlist_del(hitlist, index, targets_dict):
    if hitlist:
        last_idx = len(hitlist) - 1
        if index != last_idx:
            last_target=hitlist[-1].target
            hitlist[index]=hitlist[-1]
            targets_dict[last_target]=index
        hitlist.pop()

class Empty:
    # placeholder for when nothing is connected
    def __init__(self):
        self.code = ('X', 'X')
        self.targets={}
    def __repr__(self):
        return 'Empty'

    def __str__(self):
        return 'Empty'


Nothing = Empty()

class Profile:
    __slots__ = ['source','target', 'index','weight','output']
    def __init__(self,source,target,index,output):
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
    
    def add(self,index):
        self.index.add(index)
        self.target.book[self.output] += 1
        self.weight+=1
    
    def remove(self,index):
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

    def hide(self):
        target=self.target
        target.book[self.output] -= self.weight
        for index in self.index:
            target.sources[index] = Nothing
        self.output=Const.UNKNOWN

    def reveal(self):
        target=self.target
        target.book[Const.UNKNOWN] += self.weight
        for index in self.index:
            target.sources[index] = self.source
        
    def update(self):
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
        target_book=target.book
        target_book[self.output] -= count
        target_book[new_output] += count
        
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

    def burn(self):
        target=self.target
        target.sync()
        self.output=Const.ERROR
        return target.output!=Const.ERROR


class Gate:
    __slots__ = ['sources', 'targets','hitlist', 'inputlimit', 'book', 'output', 'prev_output', 'code', 'name', 'custom_name']
    # the blueprint for all logical gates
    # it handles inputs, outputs, and processing logic

    def __init__(self):
        # who feeds into this gate? (inputs)
        self.sources: list[Gate] = [Nothing, Nothing]
        # who does this gate feed into? (outputs)
        self.targets: dict[Gate, int] = {}
        self.hitlist:list[Profile]=[]
        # how many inputs do we need?
        self.inputlimit = 2
        # keeps track of what kind of inputs we have (high, low, etc)
        self.book: list[int] = [0, 0, 0, 0]
        
        # current and previous state
        self.output = Const.UNKNOWN
        self.prev_output = Const.UNKNOWN
        
        # identity details
        self.code = ''
        self.name = ''
        self.custom_name = ''

    # calculates the output based on inputs
    def process(self):
        pass
       
    def rename(self, name):
        self.name = name

    def __repr__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.name if self.custom_name == '' else self.custom_name

    # checks if the gate is ready to calculate an output
    def isready(self):
        if Const.MODE == Const.DESIGN:
            # if we are designing, nothing works yet
            return False
        else:
            realsource = sum(self.book[:3])
            if Const.MODE == Const.SIMULATE:
                # in simulation, we need all inputs connected
                return realsource == self.inputlimit
            else:
                # in flipflop mode, we're a bit more lenient
                return realsource and realsource+self.book[Const.UNKNOWN] == self.inputlimit

    # connect a source gate (input) to this gate
    def connect(self, source: Gate, index: int):

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

    def bypass(self):
        for profile in self.hitlist:
            if profile.update():
                profile.target.propagate()  

    # protect against weird loops by resetting counts
    def sync(self):
        self.book=[0,0,0,0]
        for source in self.sources:
            if source!=Nothing:
                self.book[source.output]+=1

    # handles error states and spreads the error
    def burn(self):
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
    def propagate(self):
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
                        if id(profile) in fuse: 
                            gate.burn()
                            return
                        fuse.add(id(profile))
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
    def disconnect(self, index: int):
        source = self.sources[index]
        loc=source.targets[self]
        profile=source.hitlist[loc]
        if profile.remove(index):
            hitlist_del(source.hitlist, loc, source.targets)
            source.targets.pop(self)
        
        # recalculate everything
        source.process()
        source.propagate()
        self.process()
        self.propagate()

    def reset(self):
        self.output = Const.UNKNOWN
        self.book = [0, 0, 0, sum(self.book)]
        self.prev_output = Const.UNKNOWN
        for profile in self.hitlist:
            profile.output=Const.UNKNOWN

    def hide(self):
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
        self.book = [0, 0, 0, 0]

    def reveal(self):
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

    def setlimits(self,size):
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

    def getoutput(self):
        if self.output == Const.ERROR:
            return '1/0'
        if self.output == Const.UNKNOWN:
            return 'X'
        return 'T' if self.output == Const.HIGH else 'F'

    def json_data(self):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code for source in self.sources],
        }
        return dictionary

    def copy_data(self, cluster):
        dictionary = {
            "name": self.name,
            "custom_name": "", # Do not copy custom name for gates
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source != Nothing and source in cluster else Nothing.code for source in self.sources],
            }
        return dictionary

    def decode(self, code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def clone(self, dictionary, pseudo):
        self.custom_name = dictionary["custom_name"]
        self.setlimits(dictionary["inputlimit"])
        for index,source in enumerate(dictionary["source"]):
            if source[0]!='X':
                self.connect(pseudo[self.decode(source)],index)

    def load_to_cluster(self, cluster: set):
        cluster.add(self)




class Variable(Gate):
    # this can be both an input or output(bulb)
    __slots__ = ()  
    
    def __init__(self):
        super().__init__()
        self.sources = 0
        self.inputlimit = 1
    def setlimits(self,size):
        return False
    def connect(self, source, index):
        pass

    def toggle(self, source: int):
        if isinstance(source, int):
            self.sources = source
            self.process()

    def reset(self):
        self.output = Const.UNKNOWN
        self.prev_output = Const.UNKNOWN
        for profile in self.hitlist:
            profile.output=Const.UNKNOWN

    def isready(self):
        if Const.MODE==Const.DESIGN:
            return False
        else:
            return True
    
    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.sources
        else:
            self.output = Const.UNKNOWN

    def json_data(self):

        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "source": self.sources,
        }
        return dictionary

    def clone(self, dictionary, pseudo):
        self.custom_name = dictionary["custom_name"]
        self.sources = dictionary["source"]

    def copy_data(self, cluster):
        dictionary = {
            "name": self.name,
            "custom_name": "", # Do not copy custom name for gates
            "code": self.code,
            "source": self.sources,
            }
        return dictionary

    def hide(self):
        # disconnect from target
        for hits in self.hitlist:
            hits.hide()

        for target in self.targets.keys():
            if target!=self:
                target.process()
                target.propagate()

    def reveal(self):
        # connect to targets
        for profile in self.hitlist:
            profile.reveal()

        self.propagate()

class Probe(Gate):
    # this can be both an input or output(bulb)
    __slots__=()
    def __init__(self):
        super().__init__()
        self.inputlimit = 1
        self.sources = [Nothing]
    def setlimits(self,size):
        return False

    def isready(self):
        if Const.MODE==Const.DESIGN:
            return False
        elif self.sources[0]!=Nothing:
            return True
        else:
            return False

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[Const.HIGH]
        else:
            self.output = Const.UNKNOWN




class InputPin(Probe):
    # this can be both an input or output(bulb)
    __slots__=()
    def __init__(self):
        super().__init__()
        self.inputlimit = 1

    def copy_data(self, cluster):
        d = super().copy_data(cluster)
        d["custom_name"] = self.custom_name
        return d

class OutputPin(Probe):
    # this can be both an input or output(bulb)
    __slots__=()
    def __init__(self):
        super().__init__()
        self.inputlimit = 1

    def copy_data(self, cluster):
        d = super().copy_data(cluster)
        d["custom_name"] = self.custom_name
        return d 

class NOT(Gate):
    __slots__=()
    def __init__(self):
        super().__init__()
        self.inputlimit = 1
        self.sources=[Nothing]

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[Const.LOW]
        else:
            self.output = Const.UNKNOWN

class AND(Gate):
    __slots__=()
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[Const.LOW] else 1
        else:
            self.output = Const.UNKNOWN


class NAND(Gate):
    __slots__=()
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[Const.LOW] else 0
        else:
            self.output = Const.UNKNOWN

class OR(Gate):
    __slots__=()
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[Const.HIGH] else 0
        else:
            self.output = Const.UNKNOWN

class NOR(Gate):
    __slots__=()
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[Const.HIGH] else 1
        else:
            self.output = Const.UNKNOWN

class XOR(Gate):
    __slots__=()
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[Const.HIGH] % 2
        else:
            self.output = Const.UNKNOWN

class XNOR(Gate):
    __slots__=()
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = (self.book[Const.HIGH] % 2) ^ 1
        else:
            self.output = Const.UNKNOWN
