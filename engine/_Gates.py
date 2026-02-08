# Pure Python version of Gates.pyx with type annotations
from __future__ import annotations
from collections import deque
from typing import Any
import Const


def listdel(lst: list[Any], index: int):
    if lst:
        lst[index] = lst[-1]
        lst.pop()


def hitlist_del(hitlist: list[Profile], index: int, targets_dict: dict[Gate, int]):
    if hitlist:
        last_idx: int = len(hitlist) - 1
        if index != last_idx:
            last_target: Gate = hitlist[-1].target
            hitlist[index] = hitlist[-1]
            targets_dict[last_target] = index
        hitlist.pop()


class Empty:
    def __init__(self):
        self.code: tuple[str, str] = ('X', 'X')
        self.targets: dict[Gate, int] = {}

    def __repr__(self) -> str:
        return 'Empty'

    def __str__(self) -> str:
        return 'Empty'


Nothing: Empty = Empty()


def add(profile: Profile, pin_index: int):
    profile.index.append(pin_index)
    profile.target.book[profile.output] += 1


def remove(profile: Profile, pin_index: int) -> bool:
    target: Gate = profile.target
    target.sources[pin_index] = Nothing
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
        target.sources[index] = Nothing
    profile.output = Const.UNKNOWN


def reveal(profile: Profile):
    target: Gate = profile.target
    target.book[Const.UNKNOWN] += len(profile.index)
    for index in profile.index:
        target.sources[index] = profile.source


def update(profile: Profile) -> bool:
    new_output: int = profile.source.output
    if profile.output == new_output:
        # if nothing changed, relax
        return False
    target: Gate = profile.target
    if isinstance(target, Probe):
        profile.output = new_output
        target.output = profile.output
        target.bypass()
        return False
    # update the target's records
    count: int = len(profile.index)
    target.book[profile.output] -= count
    target.book[new_output] += count
    
    if new_output == Const.ERROR:
        # error propagation
        if target.isready():
            target.output = Const.ERROR
    else:
        # let the target recalculate
        target.process()
        
    # update what the target thinks our output is
    profile.output = new_output
    return target.prev_output != target.output


def burn(profile: Profile) -> bool:
    target: Gate = profile.target
    target.sync()
    profile.output = Const.ERROR
    return target.output != Const.ERROR


class Profile:
    def __init__(self, source: Gate, target: Gate, index: int, output: int):
        self.source: Gate = source
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

    def __init__(self):
        # who feeds into this gate? (inputs)
        self.sources: list[Gate | Empty] = [Nothing, Nothing]
        # who does this gate feed into? (outputs)
        self.targets: dict[Gate, int] = {}
        self.hitlist: list[Profile] = []
        # how many inputs do we need?
        self.inputlimit: int = 2
        # keeps track of what kind of inputs we have (high, low, etc)
        self.book: list[int] = [0, 0, 0, 0]
        
        # current and previous state
        self.output: int = Const.UNKNOWN
        self.prev_output: int = Const.UNKNOWN
        
        # identity details
        self.code: tuple[Any, ...] = ()
        self.name: str = ''
        self.custom_name: str = ''

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
        if Const.MODE == Const.DESIGN:
            # if we are designing, nothing works yet
            return False
        else:
            realsource: int = self.book[Const.HIGH] + self.book[Const.LOW] + self.book[Const.ERROR]
            if Const.MODE == Const.SIMULATE:
                # in simulation, we need all inputs connected
                return realsource == self.inputlimit
            else:
                # in flipflop mode, we're a bit more lenient
                return bool(realsource and realsource + self.book[Const.UNKNOWN] == self.inputlimit)

    def connect(self, source: Gate, index: int):
        """Connect a source gate (input) to this gate."""
        loc: int
        if self in source.targets:
            loc = source.targets[self]
            add(source.hitlist[loc], index)
        else:
            source.hitlist.append(Profile(source, self, index, source.output))
            source.targets[self] = len(source.hitlist) - 1            
        # actually plug it in
        self.sources[index] = source
        
        # if something is wrong with the input, react
        if source.output == Const.ERROR:
            if self.isready():
                self.burn()
        else:
            # otherwise, recalculate our output
            self.process()

    def bypass(self):
        for profile in self.hitlist:
            if update(profile):
                profile.target.propagate()  

    def sync(self):
        """Protect against weird loops by resetting counts."""
        self.book[:] = [0, 0, 0, 0]
        for source in self.sources:
            if source != Nothing:
                self.book[source.output] += 1

    def burn(self):
        """Handles error states and spreads the error."""
        queue: deque[Gate] = deque()
        queue.append(self)
        while len(queue):
            gate: Gate = queue.popleft()
            gate.prev_output = gate.output
            # mark as error
            gate.output = Const.ERROR 
            for profile in gate.hitlist:
                # update target's knowledge
                if burn(profile) and profile.target.isready():
                    queue.append(profile.target)

    def propagate(self):
        """Spread the signal change to all connected gates."""
        gate: Gate
        target: Gate
        if Const.MODE == Const.FLIPFLOP:
            fuse: set[Profile] = set()
            queue: deque[Gate] = deque()
            # notify all targets
            queue.append(self)
            # keep propagating until everything settles
            while queue:
                gate = queue.popleft()
                for profile in gate.hitlist:
                    target = profile.target
                    if update(profile):
                        # check for loops or inconsistencies
                        if gate == target: 
                            gate.burn()
                            return
                        if profile in fuse: 
                            gate.burn()
                            return
                        fuse.add(profile)
                        queue.append(target)

        elif Const.MODE == Const.SIMULATE:  # don't need fuse, the logic itself is loop-proof
            queue: deque[Gate] = deque()            
            queue.append(self)                       
            # keep propagating until everything settles
            while queue:
                gate = queue.popleft()
                for profile in gate.hitlist:
                    target = profile.target
                    if update(profile):
                        queue.append(target)

        else:
            pass

    def disconnect(self, index: int):
        """Remove a connection at a specific index."""
        source: Gate = self.sources[index]  # type: ignore
        loc: int = source.targets[self]
        profile: Profile = source.hitlist[loc]
        if remove(profile, index):
            hitlist_del(source.hitlist, loc, source.targets)
            source.targets.pop(self)
        
        # recalculate everything
        source.process()
        source.propagate()
        self.process()
        self.propagate()

    def reset(self):
        self.output = Const.UNKNOWN
        sums: int = 0
        for i in self.book:
            sums += i
        self.book[:] = [0, 0, 0, sums]
        self.prev_output = Const.UNKNOWN
        for profile in self.hitlist:
            profile.output = Const.UNKNOWN

    def hide(self):
        # disconnect from targets (this gate's outputs)
        for profile in self.hitlist:
            hide(profile)
        
        # disconnect from sources (this gate's inputs)
        for source in self.sources:
            if source != Nothing and self in source.targets:
                loc: int = source.targets.pop(self)
                hitlist_del(source.hitlist, loc, source.targets)  # type: ignore
        
        # recalculate targets
        for target in self.targets.keys():
            if target != self:
                target.process()
                target.propagate()

        self.prev_output = Const.UNKNOWN
        self.output = Const.UNKNOWN
        self.book[:] = [0, 0, 0, 0]

    def reveal(self):
        # reconnect to sources (rebuild this gate's inputs)
        for index, source in enumerate(self.sources):
            if source != Nothing:
                # Re-register with the source's hitlist
                if self in source.targets:
                    # Profile already exists, just add the index
                    loc: int = source.targets[self]
                    add(source.hitlist[loc], index)
                else:
                    # Create new profile
                    source.hitlist.append(Profile(source, self, index, source.output))  # type: ignore
                    source.targets[self] = len(source.hitlist) - 1
        
        self.process()
        
        # reconnect to targets (this gate's outputs)
        for profile in self.hitlist:
            reveal(profile)
        
        self.propagate()

    def setlimits(self, size: int) -> bool:
        if size > self.inputlimit:
            for i in range(self.inputlimit, size):
                self.sources.append(Nothing)
            self.inputlimit = size
            return True
        elif size < self.inputlimit:
            for i in range(size, self.inputlimit):
                if self.sources[i] != Nothing:
                    return False
            self.sources = self.sources[:size]
            self.inputlimit = size
            return True
        return False

    def getoutput(self) -> str:
        if self.output == Const.ERROR:
            return '1/0'
        if self.output == Const.UNKNOWN:
            return 'X'
        return 'T' if self.output == Const.HIGH else 'F'

    def json_data(self) -> dict[str, Any]:
        dictionary: dict[str, Any] = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code for source in self.sources],
        }
        return dictionary

    def copy_data(self, cluster: set[Gate]) -> dict[str, Any]:
        dictionary: dict[str, Any] = {
            "name": self.name,
            "custom_name": "",  # Do not copy custom name for gates
            "code": self.code,
            "inputlimit": self.inputlimit,
            "source": [source.code if source != Nothing and source in cluster else Nothing.code for source in self.sources],
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
    def __init__(self):
        Gate.__init__(self)
        self.sources: int = 0  # type: ignore
        self.inputlimit: int = 1

    def setlimits(self, size: int) -> bool:
        return False

    def connect(self, source: Gate, index: int):
        pass

    def disconnect(self, index: int):
        pass

    def toggle(self, source: int):
        self.sources = source  # type: ignore
        self.process()

    def reset(self):
        self.output = Const.UNKNOWN
        self.prev_output = Const.UNKNOWN
        for profile in self.hitlist:
            profile.output = Const.UNKNOWN

    def isready(self) -> bool:
        if Const.MODE == Const.DESIGN:
            return False
        else:
            return True
    
    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.sources  # type: ignore
        else:
            self.output = Const.UNKNOWN

    def json_data(self) -> dict[str, Any]:
        dictionary: dict[str, Any] = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "source": self.sources,
        }
        return dictionary

    def clone(self, dictionary: dict[str, Any], pseudo: dict[tuple[Any, ...], Gate]):
        self.custom_name = dictionary["custom_name"]
        self.sources = dictionary["source"]  # type: ignore

    def copy_data(self, cluster: set[Gate]) -> dict[str, Any]:
        dictionary: dict[str, Any] = {
            "name": self.name,
            "custom_name": "",  # Do not copy custom name for gates
            "code": self.code,
            "source": self.sources,
        }
        return dictionary

    def hide(self):
        # disconnect from target
        for hits in self.hitlist:
            hide(hits)

        for target in self.targets.keys():
            if target != self:
                target.process()
                target.propagate()

    def reveal(self):
        # connect to targets
        for profile in self.hitlist:
            reveal(profile)

        self.propagate()


class Probe(Gate):
    def __init__(self):
        Gate.__init__(self)
        self.inputlimit: int = 1
        self.sources: list[Gate | Empty] = [Nothing]

    def setlimits(self, size: int) -> bool:
        return False

    def isready(self) -> bool:
        if Const.MODE == Const.DESIGN:
            return False
        elif self.sources[0] != Nothing:
            return True
        else:
            return False

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.sources[0].output
        else:
            self.output = Const.UNKNOWN


class InputPin(Probe):
    def __init__(self):
        Probe.__init__(self)
        self.inputlimit: int = 1

    def copy_data(self, cluster: set[Gate]) -> dict[str, Any]:
        d: dict[str, Any] = super().copy_data(cluster)
        d["custom_name"] = self.custom_name
        return d


class OutputPin(Probe):
    def __init__(self):
        Probe.__init__(self)
        self.inputlimit: int = 1

    def copy_data(self, cluster: set[Gate]) -> dict[str, Any]:
        d: dict[str, Any] = super().copy_data(cluster)
        d["custom_name"] = self.custom_name
        return d


class NOT(Gate):
    """NOT gate - inverts the input"""
    
    def __init__(self):
        Gate.__init__(self)
        self.inputlimit: int = 1
        self.sources: list[Gate | Empty] = [Nothing]

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[Const.LOW]
        else:
            self.output = Const.UNKNOWN


class AND(Gate):
    """AND gate - outputs 1 only if all inputs are 1"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[Const.LOW] else 1
        else:
            self.output = Const.UNKNOWN


class NAND(Gate):
    """NAND gate - NOT AND"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[Const.LOW] else 0
        else:
            self.output = Const.UNKNOWN


class OR(Gate):
    """OR gate - outputs 1 if any input is 1"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[Const.HIGH] else 0
        else:
            self.output = Const.UNKNOWN


class NOR(Gate):
    """NOR gate - NOT OR"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[Const.HIGH] else 1
        else:
            self.output = Const.UNKNOWN


class XOR(Gate):
    """XOR gate - outputs 1 if odd number of inputs are 1"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[Const.HIGH] % 2
        else:
            self.output = Const.UNKNOWN


class XNOR(Gate):
    """XNOR gate - NOT XOR"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = (self.book[Const.HIGH] % 2) ^ 1
        else:
            self.output = Const.UNKNOWN
