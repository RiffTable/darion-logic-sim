
from __future__ import annotations
from Const import *


# ─── Profile ──────────────────────────────────────────────────────
# C++ Profile struct
class Profile:
    __slots__ = ['target', 'index', 'output']

    def __init__(self, target: Gate, index: int, output: int):
        self.target: Gate = target
        self.index: int = index
        self.output: int = output

    def __repr__(self) -> str:
        return f"{self.target}"

    def __str__(self) -> str:
        return f"{self.target}"


def pop(hitlist: list[Profile], target: Gate, pin_index: int):
    """Linear scan, swap-with-last, pop."""
    for i, p in enumerate(hitlist):
        if p.target is target and p.index == pin_index:
            hitlist[i] = hitlist[-1]
            hitlist.pop()
            return
    

def hide_profile(profile: Profile):
    """Disconnect a profile's target from its source."""
    target: Gate = profile.target
    target.book[profile.output] -= 1
    target.sources[profile.index] = None
    profile.output = UNKNOWN


def reveal_profile(profile: Profile, source: Gate):
    """Reconnect a profile's target to its source."""
    target: Gate = profile.target
    target.book[UNKNOWN] += 1
    target.sources[profile.index] = source




class Gate:
    __slots__ = [
        'sources', 'hitlist', 'inputlimit', 'book',
        'output', 'scheduled', 'id', 'code', 'name', 'custom_name',
        'listener',
    ]

    def __init__(self):

        self.sources: list[Gate | None] = [None, None]
        self.hitlist: list[Profile] = []
        self.inputlimit: int = 2
        self.book: list[int] = [0, 0, 0, 0]  # [LOW, HIGH, ERROR, UNKNOWN]
        self.output: int = UNKNOWN
        self.scheduled: bool = False
        self.id: int = -1
        self.code: tuple = ()
        self.name: str = ''
        self.custom_name: str = ''
        self.listener = []

    def __repr__(self) -> str:
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self) -> str:
        return self.name if self.custom_name == '' else self.custom_name

    def update_ui(self):
        for func in self.listener:
            if func is None:
                continue
            func(self.output)

    def process(self):
        """Calculate output from book counts."""
        if get_MODE() == DESIGN:
            self.output = UNKNOWN
        else:
            high = self.book[HIGH]
            low = self.book[LOW]
            realsource = high + low
            if realsource == self.inputlimit or (realsource and realsource + self.book[ERROR] + self.book[UNKNOWN] == self.inputlimit):
                gate_type = self.id
                if gate_type <= NAND_ID:
                    target_output = int(low == 0)
                elif gate_type <= NOR_ID:
                    target_output = int(high > 0)
                else:
                    target_output = high & 1
                target_output ^= (gate_type & 1)
                self.output = target_output
            else:
                self.output = UNKNOWN

    def rename(self, name: str):
        self.custom_name = name



    def connect(self, source: Gate, index: int):
        """Connect source -> self at pin index."""

        source.hitlist.append(Profile(self, index, source.output))
        self.sources[index] = source
        self.book[source.output] += 1

        if source.output == ERROR:
            self.output = ERROR
        else:
            self.process()

    def disconnect(self, index: int):
        """Disconnect pin at index."""
        source: Gate = self.sources[index]
        if source is None:
            return
        pop(source.hitlist, self, index)
        self.sources[index] = None
        self.book[source.output] -= 1
        self.process()

    def reset(self):
        """Reset to UNKNOWN state."""
        self.output = UNKNOWN
        book = self.book
        book[UNKNOWN] += book[LOW] + book[HIGH] + book[ERROR]
        book[LOW] = book[HIGH] = book[ERROR] = 0
        for profile in self.hitlist:
            profile.output = UNKNOWN

    def hide(self):
        """Soft-disconnect from all targets and sources."""
        for profile in self.hitlist:
            hide_profile(profile)

        for i, source in enumerate(self.sources):
            if source is not None:
                pop(source.hitlist, self, i)
        self.output = UNKNOWN
        self.book[:] = [0, 0, 0, 0]

    def reveal(self):
        """Reconnect to sources and targets."""
        for i, source in enumerate(self.sources):
            if source is not None:
                source.hitlist.append(Profile(self, i, source.output))
                self.book[source.output] += 1

        for profile in self.hitlist:
            reveal_profile(profile, self)
        self.process()

    def setlimits(self, size: int) -> bool:
        if size < 2:
            return False
        if size > self.inputlimit:
            for _ in range(size - self.inputlimit):
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

    def json_data(self) -> list:
        return [
            
            self.custom_name,
            self.code,
            self.inputlimit,
            [s.code if s else ('X', 'X') for s in self.sources],
        ]

    def copy_data(self, cluster: set) -> list:
        return [
            
            "",
            self.code,
            self.inputlimit,
            [s.code if s and s in cluster else ('X', 'X') for s in self.sources],
        ]

    def decode(self, code: list) -> tuple:
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def clone(self, dictionary: list, pseudo: dict):
        self.custom_name = dictionary[CUSTOM_NAME]
        self.setlimits(dictionary[INPUTLIMIT])
        for index, source in enumerate(dictionary[SOURCES]):
            if source[0] != 'X':
                self.connect(pseudo[self.decode(source)], index)

    def load_to_cluster(self, cluster: set):
        cluster.add(self)




class Variable(Gate):
    __slots__ = ['value']

    def __init__(self):
        super().__init__()
        self.id = VARIABLE_ID
        self.value: int = 0
        self.inputlimit = 1
        self.output = UNKNOWN if get_MODE() == DESIGN else self.value
        self.sources = [None]

    def setlimits(self, size: int) -> bool:
        return False

    def connect(self, source: Gate, index: int):
        pass

    def disconnect(self, index: int):
        pass

    def process(self):
        if get_MODE() == DESIGN:
            self.output = UNKNOWN
        else:
            self.output = self.value

    def reset(self):
        self.output = UNKNOWN
        for profile in self.hitlist:
            profile.output = UNKNOWN

    def json_data(self) -> list:
        return [
            
            self.custom_name,
            self.code,
            self.inputlimit,
            self.value,
        ]

    def clone(self, dictionary: list, pseudo: dict):
        self.custom_name = dictionary[CUSTOM_NAME]
        self.value = dictionary[VALUE]

    def copy_data(self, cluster: set) -> list:
        return [
            
            "",
            self.code,
            self.inputlimit,
            self.value,
        ]

    def hide(self):
        for profile in self.hitlist:
            hide_profile(profile)

    def reveal(self):
        for profile in self.hitlist:
            reveal_profile(profile, self)




class Probe(Gate):
    def __init__(self):
        super().__init__()
        self.id = PROBE_ID
        self.inputlimit = 1
        self.sources = [None]

    def setlimits(self, size: int) -> bool:
        return False



    def process(self):
        if get_MODE() == DESIGN:
            self.output = UNKNOWN
        elif self.sources[0] is not None:
            self.output = self.sources[0].output
        else:
            self.output = UNKNOWN

    def connect(self, source: Gate, index: int):
        source.hitlist.append(Profile(self, index, source.output))
        self.sources[index] = source
        self.output = source.output

    def disconnect(self, index: int):
        source = self.sources[index]
        if source is None:
            return
        pop(source.hitlist, self, index)
        self.sources[index] = None
        self.output = UNKNOWN

    def reset(self):
        self.output = UNKNOWN
        for profile in self.hitlist:
            profile.output = UNKNOWN

    def hide(self):
        for profile in self.hitlist:
            hide_profile(profile)
        for i, source in enumerate(self.sources):
            if source is not None:
                pop(source.hitlist, self, i)
        self.output = UNKNOWN

    def reveal(self):
        source = self.sources[0]
        if source is not None:
            source.hitlist.append(Profile(self, 0, source.output))
            self.output = source.output
        for profile in self.hitlist:
            reveal_profile(profile, self)

    def copy_data(self, cluster: set) -> list:
        return [
            
            self.custom_name,
            self.code,
            self.inputlimit,
            [s.code if s and s in cluster else ('X', 'X') for s in self.sources],
        ]

    def clone(self, dictionary: list, pseudo: dict):
        self.custom_name = dictionary[CUSTOM_NAME]
        self.setlimits(dictionary[INPUTLIMIT])
        for index, source in enumerate(dictionary[SOURCES]):
            if source[0] != 'X':
                self.connect(pseudo[self.decode(source)], index)


class InputPin(Probe):
    def __init__(self):
        super().__init__()
        self.id = INPUT_PIN_ID


class OutputPin(Probe):
    def __init__(self):
        super().__init__()
        self.id = OUTPUT_PIN_ID




class NOT(Gate):
    """NOT gate — inverts the input."""

    def __init__(self):
        super().__init__()
        self.id = NOT_ID
        self.inputlimit = 1
        self.sources = [None]

    def process(self):
        if get_MODE() == DESIGN:
            self.output = UNKNOWN
        elif self.sources[0] is not None:
            output = self.sources[0].output
            if output == UNKNOWN:
                self.output = UNKNOWN
            else:
                self.output = output ^ 1
        else:
            self.output = UNKNOWN

    def connect(self, source: Gate, index: int):
        source.hitlist.append(Profile(self, index, source.output))
        self.sources[index] = source
        if source.output >= ERROR:
            self.output = source.output
        else:
            self.output = source.output ^ 1

    def disconnect(self, index: int):
        source = self.sources[index]
        if source is None:
            return
        pop(source.hitlist, self, index)
        self.sources[index] = None
        self.output = UNKNOWN

    def reset(self):
        self.output = UNKNOWN
        for profile in self.hitlist:
            profile.output = UNKNOWN

    def hide(self):
        for profile in self.hitlist:
            hide_profile(profile)
        source = self.sources[0]
        if source is not None:
            pop(source.hitlist, self, 0)
        self.output = UNKNOWN

    def reveal(self):
        source = self.sources[0]
        if source is not None:
            source.hitlist.append(Profile(self, 0, source.output))
            if source.output >= ERROR:
                self.output = source.output
            else:
                self.output = source.output ^ 1
        for profile in self.hitlist:
            reveal_profile(profile, self)




class AND(Gate):
    """AND gate — outputs 1 only if all inputs are 1"""
    def __init__(self):
        super().__init__()
        self.id = AND_ID

class NAND(Gate):
    """NAND gate — NOT AND"""
    def __init__(self):
        super().__init__()
        self.id = NAND_ID

class OR(Gate):
    """OR gate — outputs 1 if any input is 1"""
    def __init__(self):
        super().__init__()
        self.id = OR_ID

class NOR(Gate):
    """NOR gate — NOT OR"""
    def __init__(self):
        super().__init__()
        self.id = NOR_ID

class XOR(Gate):
    """XOR gate — outputs 1 if odd number of inputs are 1"""
    def __init__(self):
        super().__init__()
        self.id = XOR_ID

class XNOR(Gate):
    """XNOR gate — NOT XOR"""
    def __init__(self):
        super().__init__()
        self.id = XNOR_ID
