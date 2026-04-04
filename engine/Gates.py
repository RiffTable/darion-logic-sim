
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
            if target.id<VARIABLE_ID:
                target.book[p.output]-=1
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
        'output', 'scheduled', 'mark', 'id', 'code', 'codename', 'custom_name',
        'value', 'location','update'
    ]

    def __init__(self,id:int,name:str):
        self.id=id
        self.codename=name
        self.hitlist: list[Profile] = []
        if id>=VARIABLE_ID:
            self.inputlimit=1
            self.sources=[None]
        else:
            self.inputlimit=2
            self.sources: list[Gate | None] = [None, None]
        self.book: list[int] = [0, 0, 0]  # [LOW, HIGH, UNKNOWN]
        self.output: int = UNKNOWN
        self.value=0
        self.scheduled: bool = False
        self.mark: bool = False
        self.code: tuple = ()
        self.custom_name: str = ''
        self.location: int = -1   # flat index assigned by Circuit at registration
        self.update: bool = False

    def __repr__(self) -> str:
        return self.codename if self.custom_name == '' else self.custom_name

    def __str__(self) -> str:
        name = self.codename if self.custom_name == '' else self.custom_name
        if self.output == LOW:     return f'\033[94m{name}\033[0m'
        elif self.output == HIGH:  return f'\033[92m{name}\033[0m'
        else:                      return f'\033[97m{name}\033[0m'

    def register(self):
        pass

    def process(self):
        """Calculate output from book counts."""
        if get_MODE() == DESIGN:
            self.output = UNKNOWN
        else:
            if self.id==VARIABLE_ID:
                self.output=self.value
            limit=self.inputlimit
            id=self.id
            if limit == 1:
                if id==VARIABLE_ID:
                    self.output=self.value
                else:
                    source=self.sources[0]
                    if source is None:
                        self.output=UNKNOWN
                    elif source.output==UNKNOWN:
                        self.output=UNKNOWN
                    else:
                        self.output=source.output^(id==NOT_ID)
            else:
                book = self.book
                high = book[HIGH]
                low = book[LOW]
                realsource = high + low
                if realsource == limit or (realsource and realsource + book[UNKNOWN]  == limit):
                    if id <= NAND_ID:
                        self.output = int(low == 0)
                    elif id <= NOR_ID:
                        self.output = int(high > 0)
                    else:
                        self.output = high & 1
                    self.output ^= (id & 1)
                else:
                    self.output = UNKNOWN

    def rename(self, name: str):
        self.custom_name = name



    def connect(self, source: Gate, index: int):
        """Connect source -> self at pin index."""
        if self.id==VARIABLE_ID or self.sources[index] is not None:
            return
        source.hitlist.append(Profile(self, index, source.output))
        self.sources[index] = source
        self.book[source.output] += 1
        self.process()

    def disconnect(self, index: int):
        """Disconnect pin at index."""
        if self.id==VARIABLE_ID or self.sources[index] is None:
            return
        source: Gate = self.sources[index]
        pop(source.hitlist, self, index)
        self.sources[index] = None
        self.output=UNKNOWN

    def reset(self):
        """Reset to UNKNOWN state."""
        if self.id<VARIABLE_ID:
            book = self.book
            book[UNKNOWN] += book[LOW] + book[HIGH] 
            book[LOW] = book[HIGH] = 0
        self.output = UNKNOWN        
        for profile in self.hitlist:
            profile.output = UNKNOWN
        self.scheduled = False

    def hide(self):
        """Soft-disconnect from all targets and sources."""
        for profile in self.hitlist:
            hide_profile(profile)
        if self.id!=VARIABLE_ID:
            for i, source in enumerate(self.sources):
                if source is not None:
                    pop(source.hitlist, self, i)
        self.output = UNKNOWN
        if self.id<VARIABLE_ID:
            self.book[:]=[0,0,0]

    def reveal(self):
        """Reconnect to sources and targets."""
        if self.id!=VARIABLE_ID:
            for i, source in enumerate(self.sources):
                if source is not None:
                    source.hitlist.append(Profile(self, i, source.output))
                    self.book[source.output] += 1

        for profile in self.hitlist:
            reveal_profile(profile, self)
        self.process()

    def setlimits(self, size: int) -> bool:
        if size < 2 or self.id>=VARIABLE_ID:
            return False
        if size > self.inputlimit:
            for _ in range(size - self.inputlimit):
                self.sources.append(None)
            self.inputlimit = size
            self.process()
            return True
        elif size < self.inputlimit:
            for i in range(size, self.inputlimit):
                if self.sources[i]:
                    return False
            self.sources = self.sources[:size]
            self.inputlimit = size
            self.process()
            return True
        return False

    def getoutput(self) -> str:
        if self.output == UNKNOWN:
            return 'X'
        return 'T' if self.output == HIGH else 'F'

    def full_data(self) -> list:
        return [
            self.custom_name,
            self.code,
            self.inputlimit,
            self.value if self.id==VARIABLE_ID else [s.code if s else ('X', 'X') for s in self.sources],
        ]

    def partial_data(self) -> list:
        return [
            self.custom_name,
            self.code,
            self.inputlimit,
            self.value if self.id==VARIABLE_ID else [s.code if s and s.mark else ('X', 'X') for s in self.sources],
        ]

    def decode(self, code: list) -> tuple:
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def clone(self, dictionary: list, pseudo: dict):
        self.custom_name = dictionary[CUSTOM_NAME]
        if self.id==VARIABLE_ID:
            self.value = dictionary[VALUE]
        else:
            self.setlimits(dictionary[INPUTLIMIT])
            for index, source in enumerate(dictionary[SOURCES]):
                if source[0] != 'X':
                    self.connect(pseudo[self.decode(source)], index)

    def load_to_cluster(self, cluster: list):
        cluster.append(self)
        self.mark=True

class Variable(Gate):
    pass


class Probe(Gate):
    pass


class NOT(Gate):
    """NOT gate — inverts the input."""
    pass

