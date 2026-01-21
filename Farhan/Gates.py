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

    def __repr__(self):
        return 'Empty'

    def __str__(self):
        return 'Empty'


Nothing = Empty()


class Gate:

    def __init__(self):
        # gate's child or inputs
        self.children: list[Gate] = [Empty, Empty]
        self.parents: dict[Gate, set] = {}
        self.book: list[int] = [0, 0, 0, 0]
        # input limit
        self.inputlimit = 2
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
            realchild = self.book[Const.HIGH] + \
                self.book[Const.LOW] + self.book[Const.ERROR]
            if Const.MODE == Const.SIMULATE:
                return realchild == self.inputlimit
        return realchild and realchild+self.children[Const.UNKNOWN] == self.inputlimit

    def connect(self, child: Gate, index: int):
        # book manage
        self.book[child.output] += 1
        # self in parent register
        child.parents[self].add(child)
        # child register
        self.children[index] = child
        # update value
        self.process()

    def update(self, parent: Gate):
        count = len(self.parents[parent])
        parent.book[self.prev_output] -= count
        parent.book[self.output] += count
        # update value
        parent.process()
        return parent.prev_output != parent.output

    def burn(self):
        queue: deque[Gate] = deque()
        queue.append(self)
        while len(queue):
            gate = queue.popleft()
            gate.prev_output = gate.output
            gate.output = -1
            for parent in gate.parents.keys():
                count = len(gate.parents[parent])
                parent.book[gate.prev_output] -= count
                parent.book[gate.output] += count
                if parent.isready() and parent.output != Const.ERROR:
                    queue.append(parent)

    def propagate(self):
        fuse = {}
        queue: deque[Gate] = deque()
        for parent in self.parents.keys():
            if self.update(parent):
                fuse[(self, parent)] = (self.output, parent.output)
                queue.append(parent)
        while queue:
            gate = queue.popleft()
            for parent in gate.parents:
                if gate.update(parent):
                    key = (gate, parent)
                    if key in fuse and fuse[key] != (gate.output, parent.output):
                        gate.burn()
                        return
                    fuse[(gate, parent)] = (gate.output, parent.output)
                    queue.append((gate, parent))

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
        child.parents[self].discard(index)
        if len(child.parents[self]) == 0:
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
        for parent, index in self.parents.items():
            for i in index:
                parent.children[i] = Nothing
        # disconnect from child
        for child in self.children:
            child.parents.pop(self)

        for parent in self.parents.keys():
            parent.process()
            parent.propagate()

    def reveal(self):
        # connect to parents
        if self.output == Const.ERROR:
            self.burn()
        else:
            for parent, index in self.parents.items():
                for i in index:
                    parent.connect(self, i)

        # connect to children
        for index, child in enumerate(self.children):
            child.parents[self].add(index)

        # Propagate Parents
        for parent in self.parents.keys():
            parent.propagate()

    def setlimits(self):
        pass

    # gives output in T or F of off if there isn't enough inputs

    def getoutput(self):
        if self.output == Const.ERROR:
            return '1/0'
        if self.output == Const.UNKNOWN:
            return Const.UNKNOWN
        return 'T' if self.output == Const.HIGH else 'F'

    def json_data(self):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "child": [child.code for child in self.children],
            "parent": {parent.code: list(self.parents[parent]) for parent in self.parents},
        }
        return dictionary

    def copy_data(self, cluster):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "parent": {parent.code: list(index) for parent, index in self.parents.items() if parent in cluster},
            "output": self.output,
        }
        return dictionary

    def decode(self, code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def clone(self, dictionary, pseudo):
        self.custom_name = dictionary["custom_name"]
        for parent_code, index_set in dictionary["parent"].items():
            parent = pseudo[self.decode(parent_code)]
            self.parents[parent] = set(index_set)
        self.children = list(pseudo[self.decode(child)]
                             for child in dictionary["child"])

    def load_to_cluster(self, cluster: set):
        cluster.add(self)

    def implement(self, dictionary, pseudo):
        self.custom_name = dictionary["custom_name"]
        for parent_code, index_set in dictionary["parent"].items():
            parent = pseudo[self.decode(parent_code)]
            self.parents[parent] = set(index_set)
        # connect and propagate to parent
        for parent in self.parents:
            parent.connect(self)


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
        self.output = 'X'
        pass

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
            "parent": [parent.code for parent in self.parents],
        }
        return dictionary


class Probe(Gate):
    # this can be both an input or output(bulb)
    def __init__(self):
        super().__init__()
        self.inputlimit = 1

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = len(self.children[Const.HIGH])
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

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = len(self.children[Const.LOW])
        else:
            self.output = Const.UNKNOWN


class AND(Gate):
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if len(self.children[Const.LOW]) else 1
        else:
            self.output = Const.UNKNOWN


class NAND(Gate):
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if len(self.children[Const.LOW]) else 0
        else:
            self.output = Const.UNKNOWN


class OR(Gate):
    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if len(self.children[Const.HIGH]) else 0
        else:
            self.output = Const.UNKNOWN


class NOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if len(self.children[Const.HIGH]) else 1
        else:
            self.output = Const.UNKNOWN


class XOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = len(self.children[Const.HIGH]) % 2
        else:
            self.output = Const.UNKNOWN


class XNOR(Gate):

    def __init__(self):
        super().__init__()

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = (len(self.children[Const.HIGH]) % 2) ^ 1
        else:
            self.output = Const.UNKNOWN
