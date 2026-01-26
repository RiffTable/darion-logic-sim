from __future__ import annotations
from collections import deque
from Const import Const



class Empty:
    # placeholder for when nothing is connected
    def __init__(self):
        self.code = ('X', 'X')
        self.parents={}
    def __repr__(self):
        return 'Empty'

    def __str__(self):
        return 'Empty'


Nothing = Empty()


class Gate:
    __slots__ = ['children', 'parents', 'inputlimit', 'book', 'output', 'prev_output', 'code', 'name', 'custom_name']
    # the blueprint for all logical gates
    # it handles inputs, outputs, and processing logic

    def __init__(self):
        # who feeds into this gate? (inputs)
        self.children: list[Gate] = [Nothing, Nothing]
        # who does this gate feed into? (outputs)
        self.parents: dict[Gate, list[set, int]] = {}
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
    
    # checks if we have enough inputs to function
    def turnon(self):
        return self.book[Const.HIGH] + self.book[Const.LOW] + self.book[Const.ERROR] >= self.inputlimit
    
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
            realchild = self.book[Const.HIGH] + self.book[Const.LOW] + self.book[Const.ERROR]
            if Const.MODE == Const.SIMULATE:
                # in simulation, we need all inputs connected
                return realchild == self.inputlimit
            else:
                # in flipflop mode, we're a bit more lenient
                return realchild and realchild+self.book[Const.UNKNOWN] == self.inputlimit

    # connect a child gate (input) to this gate
    def connect(self, child: Gate, index: int):
        # update our input counts
        self.book[child.output] += 1
        
        # let the child know we are listening to it
        if self not in child.parents:
            child.parents[self] = [set(), child.output]
        child.parents[self][0].add(index)
        
        # actually plug it in
        self.children[index] = child
        
        # if something is wrong with the input, react
        if child.output==Const.ERROR:
            if self.isready():
                self.burn()
        else:
            # otherwise, recalculate our output
            self.process()

    # called when an input changes
    def update(self, parent: Gate,infolist: list[set|int]):
        if self.output==infolist[1]:
            # if nothing changed, relax
            return False
            
        # update the parent's records
        count=len(infolist[0])
        parent.book[infolist[1]] -= count
        parent.book[self.output] += count
        
        if self.output==Const.ERROR:
            # error propagation
            if self.isready():
                self.output=Const.ERROR
        else:
            # let the parent recalculate
            parent.process()
            
        # update what the parent thinks our output is
        infolist[1]=self.output
        return parent.prev_output != parent.output

    # protect against weird loops by resetting counts
    def sync(self):
        self.book=[0,0,0,0]
        for child in self.children:
            self.book[child.output]+=1

    # handles error states and spreads the error
    def burn(self):
        queue: deque[Gate] = deque()
        queue.append(self)
        while len(queue):
            gate = queue.popleft()
            gate.prev_output = gate.output
            # mark as error
            gate.output = Const.ERROR 
            for parent,infolist in gate.parents.items():
                parent.sync()
                # update parent's knowledge
                infolist[1]=Const.ERROR 
                if parent.isready() and parent.output != Const.ERROR:
                    queue.append(parent)

    # spread the signal change to all connected gates
    def propagate(self):
        if Const.MODE==Const.FLIPFLOP:
            fuse = {}
            queue: deque[Gate] = deque()
            # notify all parents
            for parent,infolist in self.parents.items():
                if self.update(parent,infolist):
                    fuse[(self, parent)] = (self.output, parent.output)
                    queue.append(parent)
            # keep propagating until everything settles
            while queue:
                gate = queue.popleft()
                for parent,infolist in gate.parents.items():
                    if gate.update(parent,infolist):
                        key = (gate, parent)
                        # check for loops or inconsistencies
                        if gate==parent: 
                            gate.burn()
                            return
                        if key in fuse and fuse[key] != (gate.output, parent.output): 
                            gate.burn()
                            return
                        fuse[(gate, parent)] = (gate.output, parent.output) 
                        queue.append(parent)
        elif Const.MODE==Const.SIMULATE:# don't need fuse, the logic itself is loop-proof
            queue: deque[Gate] = deque()            
            # notify all parents
            for parent,infolist in self.parents.items():
                if self.update(parent,infolist):
                    queue.append(parent)                            
            # keep propagating until everything settles
            while queue:
                gate = queue.popleft()
                for parent,infolist in gate.parents.items():
                    if gate.update(parent,infolist):
                        queue.append(parent)
        else:
            pass

    # remove a connection at a specific index
    def disconnect(self, index: int):
        child = self.children[index]
        self.book[child.output] -= 1 
        self.children[index] = Nothing 
        child.parents[self][0].discard(index) 
        
        # if no more connections to this parent, remove it from list
        if len(child.parents[self][0]) == 0:
            child.parents.pop(self)

        # recalculate everything
        child.process()
        child.propagate()
        self.process()
        self.propagate()

    def reset(self):
        self.output = Const.UNKNOWN
        self.book = [0, 0, 0, sum(self.book)]
        self.prev_output = Const.UNKNOWN
        for infolist in self.parents.values():
            infolist[1]=Const.UNKNOWN

    def hide(self):
        # disconnect from parent
        for parent, infolist in self.parents.items():
            for i in infolist[0]:
                parent.children[i] = Nothing
                parent.book[infolist[1]] -= 1
        # disconnect from child
        for child in self.children:
            if child != Nothing:
                child.parents.pop(self)

        for parent in self.parents.keys():
            if parent!=self:
                parent.process()
                parent.propagate()

    def reveal(self):
        # connect to parents
        if self.output==Const.ERROR:
            for parent, infolist in self.parents.items():
                for i in infolist[0]:
                    parent.children[i]=self
            self.burn()
        else:
            for parent, infolist in self.parents.items():
                for i in infolist[0]:
                    parent.children[i]=self
                    parent.book[infolist[1]]+=1
                    parent.process()

            for parent in self.parents.keys():
                if parent!=self:
                    parent.propagate()

        # connect to children
        for index, child in enumerate(self.children):
            if self not in child.parents:
                child.parents[self] = [set(), child.output]
            child.parents[self][0].add(index)

    def setlimits(self):
        pass

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
            "child": [child.code for child in self.children],
            "parent": [[parent.code, list(infolist[0]), Const.UNKNOWN] for parent, infolist in self.parents.items()],
            "book": [0,0,0,sum(self.book)],
        }
        return dictionary

    def copy_data(self, cluster):
        dictionary = {
            "name": self.name,
            "custom_name": "", # Do not copy custom name for gates
            "code": self.code,
            "parent": [[parent.code, list(infolist[0]), Const.UNKNOWN] for parent, infolist in self.parents.items() if parent in cluster],
            "book": [0,0,0,sum(self.book)],
            }
        return dictionary

    def decode(self, code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def clone(self, dictionary, pseudo):
        self.custom_name = dictionary["custom_name"]
        for i in dictionary["parent"]:
            parent = pseudo[self.decode(i[0])]
            self.parents[parent] = [set(i[1]), i[2]]
        self.children = list(pseudo[self.decode(child)] for child in dictionary["child"])
        self.book = dictionary["book"]

    def load_to_cluster(self, cluster: set):
        cluster.add(self)

    def implement(self, dictionary, pseudo):
        self.custom_name = dictionary["custom_name"]
        for i in dictionary["parent"]:
            parent = pseudo[self.decode(i[0])]
            self.parents[parent] = [set(i[1]), i[2]]
        # connect and propagate to parent
        for parent, [index_set, output] in self.parents.items():
            for i in index_set:
                parent.connect(self,i)


class Variable(Gate):
    # this can be both an input or output(bulb)
    __slots__ = ()  
    
    def __init__(self):
        super().__init__()
        self.children = 0
        self.inputlimit = 1

    def connect(self, child, index):
        pass

    def toggle(self, child: int):
        if isinstance(child, int):
            self.children = child
            self.process()

    def reset(self):
        self.output = Const.UNKNOWN
        self.prev_output = Const.UNKNOWN
        for infolist in self.parents.values():
            infolist[1]=Const.UNKNOWN

    def isready(self):
        if Const.MODE==Const.DESIGN:
            return False
        else:
            return True
    
    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.children
        else:
            self.output = Const.UNKNOWN

    def json_data(self):

        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "child": self.children,
            "parent": [[parent.code, list(infolist[0]), Const.UNKNOWN] for parent, infolist in self.parents.items()],
        }
        return dictionary

    def clone(self, dictionary, pseudo):
        self.custom_name = dictionary["custom_name"]
        for i in dictionary["parent"]:
            parent = pseudo[self.decode(i[0])]
            self.parents[parent] = [set(i[1]), i[2]]
        self.children = dictionary["child"]

    def hide(self):
        # disconnect from parent
        for parent, infolist in self.parents.items():
            for i in infolist[0]:
                parent.children[i] = Nothing
                parent.book[infolist[1]] -= 1

        for parent in self.parents.keys():
            if parent!=self:
                parent.process()
                parent.propagate()

    def reveal(self):
        # connect to parents
        for parent, infolist in self.parents.items():
            for i in infolist[0]:
                parent.children[i]=self
                parent.book[infolist[1]]+=1
                parent.process()

        for parent in self.parents.keys():
            if parent!=self:
                parent.propagate()

class Probe(Gate):
    # this can be both an input or output(bulb)
    __slots__=()
    def __init__(self):
        super().__init__()
        self.inputlimit = 1
        self.children = [Nothing]

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
        self.children=[Nothing]

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
