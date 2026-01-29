from __future__ import annotations
from collections import deque
from Const import Const



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


class Gate:
    __slots__ = ['sources', 'targets', 'inputlimit', 'book', 'output', 'prev_output', 'code', 'name', 'custom_name']
    # the blueprint for all logical gates
    # it handles inputs, outputs, and processing logic

    def __init__(self):
        # who feeds into this gate? (inputs)
        self.sources: list[Gate] = [Nothing, Nothing]
        # who does this gate feed into? (outputs)
        self.targets: dict[Gate, list[set, int]] = {}
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
        # update our input counts
        self.book[source.output] += 1
        
        # let the source know we are listening to it
        if self not in source.targets:
            source.targets[self] = [set(), source.output]
        source.targets[self][0].add(index)
        
        # actually plug it in
        self.sources[index] = source
        
        # if something is wrong with the input, react
        if source.output==Const.ERROR:
            if self.isready():
                self.burn()
        else:
            # otherwise, recalculate our output
            self.process()

    # called when an input changes
    def update(self, target: Gate,infolist: list[set|int]):
        if self.output==infolist[1]:
            # if nothing changed, relax
            return False
        if isinstance(target,Probe):
            infolist[1]=self.output
            target.output=self.output
            target.bypass()
            return False
        # update the target's records
        count=len(infolist[0])
        target.book[infolist[1]] -= count
        target.book[self.output] += count
        
        if self.output==Const.ERROR:
            # error propagation
            if target.isready():
                target.output=Const.ERROR
        else:
            # let the target recalculate
            target.process()
            
        # update what the target thinks our output is
        infolist[1]=self.output
        return target.prev_output != target.output
    
    def bypass(self):
        for target,infolist in self.targets.items():
            if self.update(target,infolist):
                target.propagate()  

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
            for target,infolist in gate.targets.items():
                target.sync()
                # update target's knowledge
                infolist[1]=Const.ERROR 
                if target.isready() and target.output != Const.ERROR:
                    queue.append(target)

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
                for target,infolist in gate.targets.items():
                    if gate.update(target,infolist):
                        # check for loops or inconsistencies
                        if gate==target: 
                            gate.burn()
                            return
                        if id(infolist) in fuse: 
                            gate.burn()
                            return
                        fuse.add(id(infolist))
                        queue.append(target)
        elif Const.MODE==Const.SIMULATE:# don't need fuse, the logic itself is loop-proof
            queue: deque[Gate] = deque()            
            queue.append(self)                       
            # keep propagating until everything settles
            while queue:
                gate = queue.popleft()
                for target,infolist in gate.targets.items():
                    if gate.update(target,infolist):
                        queue.append(target)
        else:
            pass

    # remove a connection at a specific index
    def disconnect(self, index: int):
        source = self.sources[index]
        self.book[source.output] -= 1 
        self.sources[index] = Nothing 
        source.targets[self][0].discard(index) 
        
        # if no more connections to this target, remove it from list
        if len(source.targets[self][0]) == 0:
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
        for infolist in self.targets.values():
            infolist[1]=Const.UNKNOWN

    def hide(self):
        # disconnect from target
        for target, infolist in self.targets.items():
            for i in infolist[0]:
                target.sources[i] = Nothing
                target.book[infolist[1]] -= 1
        # disconnect from source
        for source in self.sources:
            if source != Nothing and self in source.targets:
                source.targets.pop(self)

        for target in self.targets.keys():
            if target!=self:
                target.process()
                target.propagate()

    def reveal(self):
        # connect to targets
        if self.output==Const.ERROR:
            for target, infolist in self.targets.items():
                for i in infolist[0]:
                    target.sources[i]=self
            self.burn()
        else:
            for target, infolist in self.targets.items():
                for i in infolist[0]:
                    target.sources[i]=self
                    target.book[infolist[1]]+=1
                    target.process()

            for target in self.targets.keys():
                if target!=self:
                    target.propagate()

        # connect to sources
        for index, source in enumerate(self.sources):
            if source==Nothing:
                continue
            if self not in source.targets:
                source.targets[self] = [set(), source.output]
            source.targets[self][0].add(index)

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
            "target": [[target.code, list(infolist[0]), Const.UNKNOWN] for target, infolist in self.targets.items()],
            "book": [0,0,0,sum(self.book)],
        }
        return dictionary

    def copy_data(self, cluster):
        dictionary = {
            "name": self.name,
            "custom_name": "", # Do not copy custom name for gates
            "code": self.code,
            "inputlimit": self.inputlimit,
            "target": [[target.code, list(infolist[0]), Const.UNKNOWN] for target, infolist in self.targets.items() if target in cluster],
            "book": [0,0,0,sum(self.book)],
            }
        return dictionary

    def decode(self, code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def clone(self, dictionary, pseudo):
        self.custom_name = dictionary["custom_name"]
        self.inputlimit = dictionary["inputlimit"]
        for i in dictionary["target"]:
            target = pseudo[self.decode(i[0])]
            self.targets[target] = [set(i[1]), i[2]]
        self.sources = list(pseudo[self.decode(source)] for source in dictionary["source"])
        self.book = dictionary["book"]

    def load_to_cluster(self, cluster: set):
        cluster.add(self)

    def implement(self, dictionary, pseudo):
        self.custom_name = dictionary["custom_name"]
        self.inputlimit = dictionary["inputlimit"]
        self.sources = list(Nothing for _ in range(self.inputlimit))
        for i in dictionary["target"]:
            target = pseudo[self.decode(i[0])]
            self.targets[target] = [set(i[1]), i[2]]
        # connect and propagate to target
        for target, [index_set, output] in self.targets.items():
            for i in index_set:
                target.connect(self,i)


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
        for infolist in self.targets.values():
            infolist[1]=Const.UNKNOWN

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
            "inputlimit": self.inputlimit,
            "code": self.code,
            "source": self.sources,
            "target": [[target.code, list(infolist[0]), Const.UNKNOWN] for target, infolist in self.targets.items()],
        }
        return dictionary

    def clone(self, dictionary, pseudo):
        self.custom_name = dictionary["custom_name"]
        for i in dictionary["target"]:
            target = pseudo[self.decode(i[0])]
            self.targets[target] = [set(i[1]), i[2]]
        self.sources = dictionary["source"]

    def copy_data(self, cluster):
        dictionary = {
            "name": self.name,
            "custom_name": "", # Do not copy custom name for gates
            "code": self.code,
            "inputlimit": self.inputlimit,
            "target": [[target.code, list(infolist[0]), Const.UNKNOWN] for target, infolist in self.targets.items() if target in cluster],
            "book": [0,0,0,0],
            }
        return dictionary

    def implement(self, dictionary, pseudo):
        self.custom_name = dictionary["custom_name"]
        self.sources = 0
        for i in dictionary["target"]:
            target = pseudo[self.decode(i[0])]
            self.targets[target] = [set(i[1]), i[2]]
        # connect and propagate to target
        for target, [index_set, output] in self.targets.items():
            for i in index_set:
                target.connect(self,i)
                
        


    def hide(self):
        # disconnect from target
        for target, infolist in self.targets.items():
            for i in infolist[0]:
                target.sources[i] = Nothing
                target.book[infolist[1]] -= 1

        for target in self.targets.keys():
            if target!=self:
                target.process()
                target.propagate()

    def reveal(self):
        # connect to targets
        for target, infolist in self.targets.items():
            for i in infolist[0]:
                target.sources[i]=self
                target.book[infolist[1]]+=1
                target.process()

        for target in self.targets.keys():
            if target!=self:
                target.propagate()

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
        elif self.sources!=Nothing:
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
