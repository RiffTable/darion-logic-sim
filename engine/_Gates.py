# Pure Python version of Gates.pyx with type annotations
from __future__ import annotations
from collections import deque
from typing import Any
from Const import HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, FLIPFLOP,get_MODE

def run(varlist: list[Gate]):
    i: int = 0
    n: int = len(varlist)
    while i<n:
        varlist[i].process()
        i+=1
    i=0
    while i<n:
        idx=0
        size=len(varlist[i].hitlist)
        while idx<size:
            profile=varlist[i].hitlist[idx]
            if profile.target.output==ERROR:
                update(profile,varlist[i].output)
                profile.target.sync()
                profile.target.process()
                profile.target.propagate()
            elif update(profile,varlist[i].output):
                profile.target.propagate()
            idx+=1
        i+=1
def locate(target:Gate,agent:Gate):
    for i,j in enumerate(agent.hitlist):
        if j.target==target:
            return i
    return -1

def table(gate_list: list[Gate], varlist: list[Gate]):
    from IC import IC
    gate_list = [i for i in gate_list if i not in varlist and not isinstance(i, IC)]
    ic_outputs= []
    for i in gate_list:
        if isinstance(i, IC):
            for pin in i.outputs:
                ic_outputs.append((i, pin))

    n = len(varlist)
    rows = 1 << n
    # Collect decoded variable names and the output gate name
    var_names = [v.name for v in varlist]
    gate_names = [v.name for v in gate_list]
    ic_names = [f"{ic}:{pin.name}" for ic, pin in ic_outputs]
    output_names = gate_names + ic_names

    # Determine column widths for nice alignment
    col_width = max(len(name) for name in var_names + output_names) + 2
    header = " | ".join(name.center(col_width)
                        for name in var_names + output_names)
    separator = "─" * len(header)

    # Print table header
    Table = "\nTruth Table\n"
    # add seperater header and seperator in Table
    Table += separator+'\n'
    Table += header+'\n'
    Table += separator+'\n'
    for i in range(rows):
        inputs = []
        for j in range(n):
            var = varlist[j]
            bit = 1 if (i & (1 << (n - j - 1))) else 0
            var.toggle(bit)
            if var.prev_output != var.output:
                var.propagate()
            inputs.append("1" if bit else "0")
        
        output_vals = [gate.getoutput() for gate in gate_list]
        output_vals += [pin.getoutput() for _, pin in ic_outputs]
        
        row = " | ".join(val.center(col_width) for val in inputs + output_vals)
        Table += row+'\n'
    Table += separator+'\n'
    return Table
    
def listdel(lst: list[Any], index: int):
    if lst:
        lst[index] = lst[-1]
        lst.pop()


def hitlist_del(hitlist: list[Profile], index: int):
    if hitlist:
        hitlist[index] = hitlist[-1]
        hitlist.pop()


class Empty:
    def __init__(self):
        self.code: tuple[str, str] = ('X', 'X')

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
    profile.output = UNKNOWN


def reveal(profile: Profile,source:Gate):
    target: Gate = profile.target
    target.book[UNKNOWN] += len(profile.index)
    for index in profile.index:
        target.sources[index] = source


def update(profile: Profile,new_output: int) -> bool:
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


def burn(profile: Profile) -> bool:
    target: Gate = profile.target
    target.sync()
    profile.output = ERROR
    return target.output != ERROR


class Profile:
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

    def __init__(self):
        # who feeds into this gate? (inputs)
        self.sources: list[Gate | Empty] = [Nothing, Nothing]
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
        if get_MODE() == DESIGN:
            # if we are designing, nothing works yet
            return False
        else:
            realsource: int = self.book[HIGH] + self.book[LOW] + self.book[ERROR]
            if get_MODE() == SIMULATE:
                # in simulation, we need all inputs connected
                return realsource == self.inputlimit
            else:
                # in flipflop mode, we're a bit more lenient
                return bool(realsource and realsource + self.book[UNKNOWN] == self.inputlimit)

    def connect(self, source: Gate, index: int):
        """Connect a source gate (input) to this gate."""
        loc: int = locate(self,source)
        if loc != -1:
            profile=self.hitlist[loc]
            add(profile.index, index)
        else:
            profile=Profile(self, index, source.output)
            source.hitlist.append(profile)
        # actually plug it in
        self.sources[index] = source
        
        # if something is wrong with the input, react
        if source.output == ERROR:
            if self.isready():
                self.burn()
        else:
            # otherwise, recalculate our output
            self.process()

    def bypass(self):
        for profile in self.hitlist:
            if update(profile,self.output):
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
            gate.output = ERROR 
            for profile in gate.hitlist:
                # update target's knowledge
                if burn(profile) and profile.target.isready():
                    queue.append(profile.target)

    def propagate(self):
        """Spread the signal change to all connected gates."""
        gate: Gate
        target: Gate
        if get_MODE() == FLIPFLOP:
            fuse: set[Profile] = set()
            queue: deque[Gate] = deque()
            # notify all targets
            queue.append(self)
            # keep propagating until everything settles
            while queue:
                gate = queue.popleft()
                for profile in gate.hitlist:
                    target = profile.target
                    if update(profile,gate.output):
                        # check for loops or inconsistencies
                        if gate == target: 
                            gate.burn()
                            return
                        if profile in fuse: 
                            gate.burn()
                            return
                        fuse.add(profile)
                        queue.append(target)

        elif get_MODE() == SIMULATE:  # don't need fuse, the logic itself is loop-proof
            queue: deque[Gate] = deque()            
            queue.append(self)                       
            # keep propagating until everything settles
            while queue:
                gate = queue.popleft()
                for profile in gate.hitlist:
                    target = profile.target
                    if update(profile,gate.output):
                        queue.append(target)

        else:
            pass

    def disconnect(self, index: int):
        """Remove a connection at a specific index."""
        source: Gate = self.sources[index]  # type: ignore
        loc: int = locate(self,source)
        if loc != -1:
            profile=source.hitlist[loc]
            remove(profile, index)
            if not profile.index:
                hitlist_del(source.hitlist,loc)
        
        # recalculate everything
        source.process()
        source.propagate()
        self.process()
        self.propagate()

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
        for index,source in enumerate(self.sources):
            if source != Nothing:
                loc: int = locate(self,source)
                if loc != -1:
                    profile=self.hitlist[loc]
                    remove(profile, index)
                    self.sources[index]=source
                    if not profile.index:
                        hitlist_del(source.hitlist, loc)
        
        # recalculate targets
        for profile in self.hitlist:
            target: Gate = profile.target
            if target != self:
                target.process()
                target.propagate()

        self.prev_output = UNKNOWN
        self.output = UNKNOWN
        self.book[:] = [0, 0, 0, 0]

    def reveal(self):
        # reconnect to sources (rebuild this gate's inputs)
        for index, source in enumerate(self.sources):
            if source != Nothing:
                # Re-register with the source's hitlist
                loc: int = locate(self,source)
                if loc != -1:
                    # Profile already exists, just add the index
                    add(source.hitlist[loc], index)
                else:
                    # Create new profile
                    source.hitlist.append(Profile(self, index, source.output))
        
        self.process()
        
        # reconnect to targets (this gate's outputs)
        for profile in self.hitlist:
            reveal(profile,self)
        
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
            self.output = self.sources  # type: ignore
        else:
            self.output = UNKNOWN

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

        for profile in self.hitlist:
            target: Gate = profile.target
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
        if get_MODE() == DESIGN:
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
            self.output = UNKNOWN


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
            self.output = self.book[LOW]
        else:
            self.output = UNKNOWN


class AND(Gate):
    """AND gate - outputs 1 only if all inputs are 1"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[LOW] else 1
        else:
            self.output = UNKNOWN


class NAND(Gate):
    """NAND gate - NOT AND"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[LOW] else 0
        else:
            self.output = UNKNOWN


class OR(Gate):
    """OR gate - outputs 1 if any input is 1"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 1 if self.book[HIGH] else 0
        else:
            self.output = UNKNOWN


class NOR(Gate):
    """NOR gate - NOT OR"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = 0 if self.book[HIGH] else 1
        else:
            self.output = UNKNOWN


class XOR(Gate):
    """XOR gate - outputs 1 if odd number of inputs are 1"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = self.book[HIGH] % 2
        else:
            self.output = UNKNOWN


class XNOR(Gate):
    """XNOR gate - NOT XOR"""
    
    def __init__(self):
        Gate.__init__(self)

    def process(self):
        self.prev_output = self.output
        if self.isready():
            self.output = (self.book[HIGH] % 2) ^ 1
        else:
            self.output = UNKNOWN
