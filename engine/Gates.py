# Pure Python version of Gates.pyx with type annotations
from __future__ import annotations
from typing import Any
from .Const import HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, FLIPFLOP, get_MODE, AND_ID, OR_ID, NAND_ID, NOR_ID, XOR_ID, XNOR_ID, PROBE_ID, INPUT_PIN_ID, OUTPUT_PIN_ID, IC_ID, VARIABLE_ID, NOT_ID

def locate(target: Gate, agent: Gate):
    for i, j in enumerate(agent.hitlist):
        if j.target == target:
            return i
    return -1

def listdel(lst: list[Any], index: int):
    if lst:
        lst[index] = lst[-1]
        lst.pop()

def hitlist_del(hitlist: list[Profile], index: int):
    if hitlist:
        hitlist[index] = hitlist[-1]
        hitlist.pop()

def add(profile: Profile, pin_index: int):
    profile.index.append(pin_index)
    profile.target.book[profile.output] += 1

def remove(profile: Profile, pin_index: int) -> bool:
    target: Gate = profile.target
    target.sources[pin_index] = None
    # Find the position of this index in our index list, then remove it
    i: int = 0
    while i < len(profile.index):
        if profile.index[i] == pin_index:
            profile.index[i] = profile.index[-1]
            profile.index.pop()
            break
        i += 1

    target.book[profile.output] -= 1
    if not profile.index:
        return True
    else:
        return False

def hide(profile: Profile):
    target: Gate = profile.target
    target.book[profile.output] -= len(profile.index)
    for index in profile.index:
        target.sources[index] = None
    profile.output = UNKNOWN

def reveal(profile: Profile, source: Gate):
    target: Gate = profile.target
    target.book[UNKNOWN] += len(profile.index)
    for index in profile.index:
        target.sources[index] = source

class Profile:
    __slots__ = ['target', 'index', 'output']
    def __init__(self, target: Gate, index: int, output: int):
        self.target: Gate = target
        self.index: list[int] = []  # Using Python list instead of C++ vector
        target.book[output] += 1
        self.index.append(index)
        self.output: int = output

    def __repr__(self) -> str:
        return f"{self.target} {self.index} {self.output}"
    
    def __str__(self) -> str:
        return f"{self.target} {self.index} {self.output}"

class Gate:
    """The blueprint for all logical gates.
    It handles inputs, outputs, and processing logic."""
    __slots__ = ['sources', 'listener', 'hitlist', 'inputlimit', 'book', 'output', 
                 'prev_output', 'code', 'name', 'custom_name', 'id']
    def __init__(self):
        # who feeds into this gate? (inputs)
        self.sources: list[Gate | None] = [None, None]

        self.listener = []
        # who does this gate feed into? (outputs)
        self.hitlist: list[Profile] = []
        # how many inputs do we need?
        self.inputlimit: int = 2
        # keeps track of what kind of inputs we have (high, low, etc)
        self.book: list[int] = [0, 0, 0, 0]
        
        # current and previous state
        self.output: int = UNKNOWN
        self.prev_output: int = UNKNOWN
        
        # identity details
        self.code: tuple = ()
        self.name: str = ''
        self.custom_name: str = ''
        self.id = -1
        
    def updateUI(self):
        if self.listener:
            for listener in self.listener:
                listener(self.output)
    def process(self):
        """Calculates the output based on inputs."""
        pass
       
    def rename(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self) -> str:
        return self.name if self.custom_name == '' else self.custom_name

    def isready(self) -> bool:
        """Checks if the gate is ready to calculate an output."""
        if get_MODE() == DESIGN:
            # if we are designing, nothing works yet
            return False
        else:
            if get_MODE() == SIMULATE:
                # in simulation, we need all inputs connected and valid (no ERROR, no UNKNOWN)
                return self.book[HIGH] + self.book[LOW] == self.inputlimit
            else:
                # in flipflop mode, we're a bit more lenient
                realsource: int = self.book[HIGH] + self.book[LOW]
                return bool(realsource and realsource + self.book[UNKNOWN] + self.book[ERROR] == self.inputlimit)

    def connect(self, source: Gate, index: int):
        """Connect a source gate (input) to this gate."""
        loc: int = -1        
        if len(self.sources) < len(source.hitlist):
            if source in self.sources:
                loc = locate(self, source)
        else:
            loc = locate(self, source)
        if loc != -1:
            profile = self.hitlist[loc]
            add(profile, index)
        else:
            profile = Profile(self, index, source.output)
            source.hitlist.append(profile)
        # actually plug it in
        self.sources[index] = source
        
        # if something is wrong with the input, react
        if source.output == ERROR:
            self.output = ERROR
        else:
            # otherwise, recalculate our output
            self.process()

    def disconnect(self, index: int):
        """Remove a connection at a specific index."""
        source: Gate = self.sources[index]  # type: ignore
        if source is None:
            return
        loc: int = locate(self, source)
        if loc != -1:
            profile = source.hitlist[loc]
            remove(profile, index)
            if not profile.index:
                hitlist_del(source.hitlist, loc)
        
        # recalculate everything
        self.process()

    def reset(self):
        self.output = UNKNOWN
        sums: int = 0
        for i in self.book:
            sums += i
        self.book[:] = [0, 0, 0, sums]
        self.prev_output = UNKNOWN
        for profile in self.hitlist:
            profile.output = UNKNOWN

    def hide(self):
        # disconnect from targets (this gate's outputs)
        for profile in self.hitlist:
            hide(profile)
        
        # disconnect from sources (this gate's inputs)
        for index, source in enumerate(self.sources):
            if source:
                loc: int = locate(self, source)
                if loc != -1:
                    profile = source.hitlist[loc]
                    remove(profile, index)
                    self.sources[index] = source
                    if not profile.index:
                        hitlist_del(source.hitlist, loc)
        
        self.book[:] = [0, 0, 0, 0]

    def reveal(self):
        # reconnect to sources (rebuild this gate's inputs)
        for index, source in enumerate(self.sources):
            if source:
                # Re-register with the source's hitlist
                loc: int = locate(self, source)
                if loc != -1:
                    # Profile already exists, just add the index
                    add(source.hitlist[loc], index)
                else:
                    # Create new profile
                    source.hitlist.append(Profile(self, index, source.output))
        
        self.process()
        
        # reconnect to targets (this gate's outputs)
        for profile in self.hitlist:
            reveal(profile, self)

    def setlimits(self, size: int) -> bool:
        if size > self.inputlimit:
            for i in range(self.inputlimit, size):
                self.sources.append(None)
            self.inputlimit = size
            return True
        elif size < self.inputlimit:
            for i in range(size, self.inputlimit):
                if self.sources[i]:
                    return False
            self.sources = self.sources[:size]
            self.inputlimit = size
            return True
        return False

    def getoutput(self) -> str:
        if self.output == ERROR:
            return '1/0'
        if self.output == UNKNOWN:
            return 'X'
        return 'T' if self.output == HIGH else 'F'

    def json_data(self) -> dict[str, Any]:
        dictionary: dict[str, Any] = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source else ('X', 'X') for source in self.sources],
        }
        return dictionary

    def copy_data(self, cluster: set[Gate]) -> dict[str, Any]:
        dictionary: dict[str, Any] = {
            "name": self.name,
            "custom_name": "",  # Do not copy custom name for gates
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source and source in cluster else ('X', 'X') for source in self.sources],
        }
        return dictionary

    def decode(self, code: list[Any]) -> tuple[Any, ...]:
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def clone(self, dictionary: dict[str, Any], pseudo: dict[tuple[Any, ...], Gate]):
        self.custom_name = dictionary["custom_name"]
        self.setlimits(dictionary["inputlimit"])
        for index, source in enumerate(dictionary["source"]):
            if source[0] != 'X':
                self.connect(pseudo[self.decode(source)], index)

    def load_to_cluster(self, cluster: set[Gate]):
        cluster.add(self)


class Variable(Gate):
    __slots__ = ['value']
    def __init__(self):
        super().__init__()
        self.value: int = 0 
        self.inputlimit: int = 1
        self.sources = [None]
        self.id = VARIABLE_ID

    def setlimits(self, size: int) -> bool:
        return False

    def connect(self, source: Gate, index: int):
        pass

    def disconnect(self, index: int):
        pass

    def toggle(self, source: int):
        self.value = source 
        self.process()

    def reset(self):
        self.output = UNKNOWN
        self.prev_output = UNKNOWN
        for profile in self.hitlist:
            profile.output = UNKNOWN

    def isready(self) -> bool:
        if get_MODE() == DESIGN:
            return False
        else:
            return True
    
    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.value 
        else:
            self.output = UNKNOWN

    def json_data(self) -> dict[str, Any]:
        dictionary: dict[str, Any] = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "value": self.value,
        }
        return dictionary

    def clone(self, dictionary: dict[str, Any], pseudo: dict[tuple[Any, ...], Gate]):
        self.custom_name = dictionary["custom_name"]
        self.value = dictionary["value"]

    def copy_data(self, cluster: set[Gate]) -> dict[str, Any]:
        dictionary: dict[str, Any] = {
            "name": self.name,
            "custom_name": "",  # Do not copy custom name for gates
            "code": self.code,
            "value": self.value,
        }
        return dictionary

    def hide(self):
        # disconnect from target
        for hits in self.hitlist:
            hide(hits)

    def reveal(self):
        # connect to targets
        for profile in self.hitlist:
            reveal(profile, self)


class Probe(Gate):
    __slots__ = []
    def __init__(self):
        super().__init__()
        self.inputlimit: int = 1
        self.sources: list[Gate | None] = [None]
        self.id = PROBE_ID

    def setlimits(self, size: int) -> bool:
        return False

    def isready(self) -> bool:
        if get_MODE() == DESIGN:
            return False
        elif self.sources[0]:
            return True
        else:
            return False

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.sources[0].output
        else:
            self.output = UNKNOWN

    def copy_data(self, cluster: set[Gate]) -> dict[str, Any]:
        dictionary: dict[str, Any] = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source and source in cluster else ('X', 'X') for source in self.sources],
        }
        return dictionary


class InputPin(Probe):
    __slots__ = []
    def __init__(self):
        super().__init__()
        self.inputlimit: int = 1
        self.id = INPUT_PIN_ID

    def copy_data(self, cluster: set[Gate]) -> dict[str, Any]:
        d: dict[str, Any] = super().copy_data(cluster)
        d["custom_name"] = self.custom_name
        return d


class OutputPin(Probe):
    __slots__ = []
    def __init__(self):
        super().__init__()
        self.inputlimit: int = 1
        self.id = OUTPUT_PIN_ID

    def copy_data(self, cluster: set[Gate]) -> dict[str, Any]:
        d: dict[str, Any] = super().copy_data(cluster)
        d["custom_name"] = self.custom_name
        return d


class NOT(Gate):
    __slots__ = []
    """NOT gate - inverts the input"""
    
    def __init__(self):
        super().__init__()
        self.inputlimit: int = 1
        self.sources: list[Gate | None] = [None]
        self.id = NOT_ID

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[LOW]
        else:
            self.output = UNKNOWN


class AND(Gate):
    __slots__ = []
    """AND gate - outputs 1 only if all inputs are 1"""
    
    def __init__(self):
        super().__init__()
        self.id = AND_ID

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[LOW] else 1
        else:
            self.output = UNKNOWN


class NAND(Gate):
    __slots__ = []
    """NAND gate - NOT AND"""
    
    def __init__(self):
        super().__init__()
        self.id = NAND_ID

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[LOW] else 0
        else:
            self.output = UNKNOWN


class OR(Gate):
    __slots__ = []
    """OR gate - outputs 1 if any input is 1"""
    
    def __init__(self):
        super().__init__()
        self.id = OR_ID

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[HIGH] else 0
        else:
            self.output = UNKNOWN


class NOR(Gate):
    __slots__ = []
    """NOR gate - NOT OR"""
    
    def __init__(self):
        super().__init__()
        self.id = NOR_ID

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[HIGH] else 1
        else:
            self.output = UNKNOWN


class XOR(Gate):
    __slots__ = []
    """XOR gate - outputs 1 if odd number of inputs are 1"""
    
    def __init__(self):
        super().__init__()
        self.id = XOR_ID

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[HIGH] % 2
        else:
            self.output = UNKNOWN


class XNOR(Gate):
    __slots__ = []
    """XNOR gate - NOT XOR"""
    
    def __init__(self):
        super().__init__()
        self.id = XNOR_ID

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = (self.book[HIGH] % 2) ^ 1
        else:
            self.output = UNKNOWN
