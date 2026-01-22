from __future__ import annotations
from collections import deque
from Const import Const


class Signal:
    # default signals that exist indepdently
    def __init__(self, value):
        self.parents = set()
        self.output = value
        self.name = str(value)
        self.code = (0, value)

    def __repr__(self):
        return self.name

    def __str__(self):
        return self.name


class Empty:
    def __init__(self):
        self.code = ('X', 'X')
        self.parents={}
    def __repr__(self):
        return 'Empty'

    def __str__(self):
        return 'Empty'


Nothing = Empty()


class Gate:

    def __init__(self):
        # gate's child or inputs
        self.children: list[Gate] = [Nothing, Nothing]
        # self.parents: dict[Gate, tuple[set[int], int]] = {}
        self.parents: dict[Gate, list[set, int]] = {}
        # input limit
        self.inputlimit = 2
        self.book: list[int] = [0, 0, 0, 0]
        # default output
        self.output = Const.UNKNOWN
        self.prev_output = Const.UNKNOWN
        # each gate will have it's own unique id
        self.code = ''
        self.name = ''
        self.custom_name = ''

        self.inputpoint = True
        self.outputpoint = True

    def process():
        pass
    def turnon(self):
        return self.book[Const.HIGH] + self.book[Const.LOW] + self.book[Const.ERROR] >= self.inputlimit
    def rename(self, name):
        self.name = name

    def __repr__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.name if self.custom_name == '' else self.custom_name
    def isready(self):
        if Const.MODE == Const.DESIGN:
            return False
        else:
            realchild = self.book[Const.HIGH] + self.book[Const.LOW] + self.book[Const.ERROR]
            if Const.MODE == Const.SIMULATE:
                return realchild == self.inputlimit
        return realchild and realchild+self.book[Const.UNKNOWN] == self.inputlimit

    def connect(self, child: Gate, index: int):
        # book manage
        self.book[child.output] += 1
        # self in parent register
        if self not in child.parents:
            child.parents[self] = [set(), child.output]
        child.parents[self][0].add(index)
        # child register
        self.children[index] = child
        # update value
        if child.output==Const.ERROR:
            if self.isready():
                self.burn()
        else:
            self.process()

    def update(self, parent: Gate,infolist: list[set|int]):
        if self.output==infolist[1]:
            return False
        count=len(infolist[0])
        parent.book[infolist[1]] -= count
        parent.book[self.output] += count
        # update value
        if self.output==Const.ERROR:
            if self.isready():
                self.output=Const.ERROR
        else:
            parent.process()
        infolist[1]=self.output
        return parent.prev_output != parent.output

    def sync(self):
        self.book=[0,0,0,0]
        for child in self.children:
            self.book[child.output]+=1

    def burn(self):
        queue: deque[Gate] = deque()
        queue.append(self)
        while len(queue):
            gate = queue.popleft()
            gate.prev_output = gate.output
            gate.output = Const.ERROR
            for parent,infolist in gate.parents.items():
                parent.sync()
                infolist[1]=Const.ERROR
                if parent.isready() and parent.output != Const.ERROR:
                    queue.append(parent)


    def propagate(self):
        fuse = {}
        queue: deque[Gate] = deque()
        for parent,infolist in self.parents.items():
            if self.update(parent,infolist):
                fuse[(self, parent)] = (self.output, parent.output)
                queue.append(parent)
        while queue:
            gate = queue.popleft()
            for parent,infolist in gate.parents.items():
                if gate.update(parent,infolist):
                    key = (gate, parent)
                    if gate==parent:
                        gate.burn()
                        return
                    if key in fuse and fuse[key] != (gate.output, parent.output):
                        gate.burn()
                        return
                    fuse[(gate, parent)] = (gate.output, parent.output)
                    queue.append(parent)

            # parent.connect(child)
            # if parent.prev_output != parent.output:
            #     if key not in fuse:
            #         fuse[key] = (parent.output, child.output)
            #         for grandparent in parent.parents:
            #             queue.append((grandparent, parent))
            #     elif fuse[key] != (parent.output, child.output):
            #         child.burn()
            #         return

    def disconnect(self, index: int):
        child = self.children[index]
        self.book[child.output] -= 1
        self.children[index] = Nothing
        child.parents[self][0].discard(index)
        if len(child.parents[self][0]) == 0:
            child.parents.pop(self)

        child.process()  # probably not needed
        child.propagate()
        self.process()
        self.propagate()

    def reset(self):
        self.output = Const.UNKNOWN
        self.book = [0, 0, 0, sum(self.book)]

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

        # Propagate Parents

    def setlimits(self):
        pass

    # gives output in T or F of off if there isn't enough inputs

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
            "custom_name": self.custom_name,
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
        pass
    
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

class Probe(Gate):
    # this can be both an input or output(bulb)
    def __init__(self):
        super().__init__()
        self.inputlimit = 1

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[Const.HIGH]
        else:
            self.output = Const.UNKNOWN

    # def json_data(self):
    #     dictionary={
    #         "name":self.name,
    #         "code":self.code,
    #         "parent":[parent.code for parent in self.parents],
    #         "High":[child.code for child in self.children[Const.HIGH]],
    #         "Low":[child.code for child in self.children[Const.LOW]],
    #         "Error":[child.code for child in self.children[Const.ERROR]],
    #         "output":self.output,
    #         "inputpoint":self.inputpoint,
    #         "outputpoint":self.outputpoint
    #     }
    #     return dictionary


class InputPin(Probe):
    # this can be both an input or output(bulb)
    def __init__(self):
        super().__init__()
        self.inputlimit = 1
        # self.inputpoint=False


class OutputPin(Probe):
    # this can be both an input or output(bulb)
    def __init__(self):
        super().__init__()
        self.inputlimit = 1
        # self.outputpoint=False


class NOT(Gate):
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
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[Const.LOW] else 1
        else:
            self.output = Const.UNKNOWN


class NAND(Gate):
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[Const.LOW] else 0
        else:
            self.output = Const.UNKNOWN


class OR(Gate):
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[Const.HIGH] else 0
        else:
            self.output = Const.UNKNOWN


class NOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[Const.HIGH] else 1
        else:
            self.output = Const.UNKNOWN


class XOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[Const.HIGH] % 2
        else:
            self.output = Const.UNKNOWN


class XNOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = (self.book[Const.HIGH] % 2) ^ 1
        else:
            self.output = Const.UNKNOWN
