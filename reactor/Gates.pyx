# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
# cython: nonecheck=False
from Gates cimport vector
from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM
from Const cimport *
from libc.string cimport memmove
from Store cimport decode
from libc.stdint cimport uint16_t

# ---------------------------------------------------------------------------
# Inline helpers that operate purely on CPP_Gate data (DOD)
# ---------------------------------------------------------------------------

cdef inline void pop(vector[Profile]& hitlist, int target, int pin_index):
    cdef Profile* profile = hitlist.data()
    cdef Profile* end = profile + hitlist.size()
    while profile < end:
        if profile.target == target and profile.index == pin_index:
            profile[0] = (end-1)[0]
            hitlist.pop_back()
            break
        profile += 1

cdef inline void hide(Profile& profile):
    # profile.target is an index into gate_infolist; caller adjusts book via CPP_Gate
    profile.output = UNKNOWN

cdef inline void reveal(Profile& profile, Gate source, vector[CPP_Gate]& gate_infolist):
    cdef CPP_Gate* target_info = &gate_infolist[profile.target]
    target_info.book[UNKNOWN] += 1
    cdef Gate target_gate = <Gate>target_info.gate
    target_gate.sources[profile.index] = source

# ---------------------------------------------------------------------------
# Gate class
# ---------------------------------------------------------------------------

cdef class Gate:
    def __init__(self, int id, str name):
        self.id = id
        self.codename = name
        self.info = -1
        if id >= VARIABLE_ID:
            self.sources: list = [None]
        else:
            self.sources: list = [None, None]
        self.code = ()
        self.custom_name = ''

    def __repr__(self):
        return self.codename if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.codename if self.custom_name == '' else self.custom_name

    @property
    def hitlist(self):
        # hitlist is now DOD-only; lives in CPP_Gate inside gate_infolist.
        # Python-side callers should use circuit.diagnose() or ic.info() instead.
        return []

    @property
    def book(self):
        # Removed — book lives in CPP_Gate only.
        raise AttributeError("book is DOD-only; access via gate_infolist")

    @property
    def inputlimit(self):
        raise AttributeError("inputlimit is DOD-only; access via gate_infolist")

    # ------------------------------------------------------------------
    # process: compute new output from CPP_Gate data only
    # ------------------------------------------------------------------
    cdef void process(self, vector[CPP_Gate]& gate_infolist):
        cdef CPP_Gate* info = &gate_infolist[self.info]
        cdef CPP_Gate* src_info
        cdef uint16_t* book
        cdef int gate_type = info.type
        cdef int limit = info.inputlimit
        cdef int high, low, realsource
        cdef Gate source

        if MODE == DESIGN:
            info.output = UNKNOWN
            return

        if gate_type >= VARIABLE_ID:
            if gate_type == VARIABLE_ID:
                info.output = self.value
            else:
                # NOT / INPUT_PIN / OUTPUT_PIN / PROBE — single input
                source = <Gate>PyList_GET_ITEM(self.sources, 0)
                if source is None:
                    info.output = UNKNOWN
                else:
                    src_info = &gate_infolist[source.info]
                    if src_info.output >= ERROR:
                        info.output = src_info.output
                    else:
                        info.output = src_info.output ^ (gate_type == NOT_ID)
        else:
            book = info.book
            high = book[HIGH]
            low  = book[LOW]
            realsource = high + low
            if likely(realsource == limit) or unlikely(realsource and realsource + book[ERROR] + book[UNKNOWN] == limit):
                if gate_type <= NAND_ID:   info.output = (low == 0) ^ (gate_type & 1)
                elif gate_type <= NOR_ID:  info.output = (high > 0) ^ (gate_type & 1)
                else:                       info.output = (high & 1) ^ (gate_type & 1)
            else:
                info.output = UNKNOWN

    cpdef void rename(self, str name):
        self.custom_name = name

    # ------------------------------------------------------------------
    # connect / disconnect — DOD only
    # ------------------------------------------------------------------
    cdef void connect(self, Gate source, int index, vector[CPP_Gate]& gate_infolist):
        cdef CPP_Gate* self_info  = &gate_infolist[self.info]
        if self_info.type == VARIABLE_ID or self.sources[index] is not None:
            return
        cdef CPP_Gate* src_info = &gate_infolist[source.info]
        # Record connection in CPP hitlist
        src_info.hitlist.emplace_back(self.info, index, src_info.output)
        self.sources[index] = source
        # Update book count
        self_info.book[src_info.output] += 1
        self.process(gate_infolist)

    cdef void disconnect(self, int index, vector[CPP_Gate]& gate_infolist):
        cdef CPP_Gate* self_info = &gate_infolist[self.info]
        if self_info.type == VARIABLE_ID or self.sources[index] is None:
            return
        cdef Gate source = self.sources[index]
        cdef CPP_Gate* src_info = &gate_infolist[source.info]
        pop(src_info.hitlist, self.info, index)
        self.sources[index] = None
        self_info.book[src_info.output] -= 1
        self_info.output = UNKNOWN

    # ------------------------------------------------------------------
    # reset
    # ------------------------------------------------------------------
    cdef void reset(self, vector[CPP_Gate]& gate_infolist):
        cdef CPP_Gate* info = &gate_infolist[self.info]
        cdef uint16_t* book
        if info.type < VARIABLE_ID:
            book = info.book
            book[3] += book[0] + book[1] + book[2]
            book[0] = book[1] = book[2] = 0
        info.output = UNKNOWN
        cdef Profile* profile = info.hitlist.data()
        cdef Profile* end = profile + info.hitlist.size()
        while profile < end:
            profile.output = UNKNOWN
            profile += 1

    # ------------------------------------------------------------------
    # hide / reveal — gate-level DOD
    # ------------------------------------------------------------------
    cdef void hide(self, vector[CPP_Gate]& gate_infolist):
        cdef CPP_Gate* info = &gate_infolist[self.info]
        cdef Py_ssize_t i
        cdef CPP_Gate* target_info
        cdef Gate target_gate
        cdef list sources
        cdef Gate source
        cdef CPP_Gate* src_info
        cdef uint16_t* book
        cdef Py_ssize_t n
        cdef Profile* hitlist

        # 1. Disconnect from targets: update each target's book and sources
        n = info.hitlist.size()
        hitlist = info.hitlist.data()
        for i in range(n):
            target_info = &gate_infolist[hitlist[i].target]
            # Decrement the target's book for this gate's output
            target_info.book[hitlist[i].output] -= 1
            target_info.book[UNKNOWN] += 1
            target_gate = <Gate>target_info.gate
            target_gate.sources[hitlist[i].index] = None
            hitlist[i].output = UNKNOWN

        # 2. Disconnect from sources: remove self from each source's hitlist
        sources = self.sources
        if info.type != VARIABLE_ID:
            n = len(sources)
            for i in range(n):
                source = <Gate>PyList_GET_ITEM(sources, i)
                if source is not None:
                    src_info = &gate_infolist[source.info]
                    pop(src_info.hitlist, self.info, i)

        # 3. Zero out own state
        info.output = UNKNOWN
        if info.type < VARIABLE_ID:
            book = info.book
            book[0] = book[1] = book[2] = book[3] = 0

    cdef void reveal(self, vector[CPP_Gate]& gate_infolist):
        cdef CPP_Gate* info = &gate_infolist[self.info]
        cdef list sources = self.sources
        cdef Py_ssize_t i
        cdef Py_ssize_t n = len(sources)
        cdef Gate source
        cdef CPP_Gate* src_info

        # 1. Re-register in each source's hitlist and update our book
        if info.type != VARIABLE_ID:
            for i in range(n):
                source = <Gate>PyList_GET_ITEM(sources, i)
                if source is not None:
                    src_info = &gate_infolist[source.info]
                    src_info.hitlist.emplace_back(self.info, i, src_info.output)
                    info.book[src_info.output] += 1

        # 2. Reconnect to targets in our hitlist (restore their sources pointer + book)
        n = info.hitlist.size()
        cdef Profile* hitlist = info.hitlist.data()
        cdef CPP_Gate* target_info
        cdef Gate target_gate
        for i in range(n):
            target_info = &gate_infolist[hitlist[i].target]
            target_gate = <Gate>target_info.gate
            target_gate.sources[hitlist[i].index] = self
            target_info.book[UNKNOWN] += 1

        self.process(gate_infolist)

    # ------------------------------------------------------------------
    # setlimits — resize sources list and update CPP_Gate.inputlimit
    # ------------------------------------------------------------------
    cdef bint setlimits(self, int size, vector[CPP_Gate]& gate_infolist):
        cdef CPP_Gate* info = &gate_infolist[self.info]
        cdef int i
        cdef int current
        if size < 2 or info.type >= VARIABLE_ID:
            return False
        current = info.inputlimit

        if size > current:
            for _ in range(size - current):
                self.sources.append(None)
            info.inputlimit = size
            return True
        elif size < current:
            for i in range(size, current):
                if self.sources[i]:
                    return False
            self.sources = self.sources[:size]
            info.inputlimit = size
            return True
        return False

    cpdef str getoutput(self):
        return ''

    cdef list full_data(self, vector[CPP_Gate]& gate_infolist):
        cdef CPP_Gate* info = &gate_infolist[self.info]
        cdef Gate source
        cdef list dictionary = [
            self.custom_name,
            self.code,
            info.inputlimit,
            self.value if info.type == VARIABLE_ID else [source.code if source else ('X', 'X') for source in self.sources],
            ]
        return dictionary

    cdef list partial_data(self, vector[CPP_Gate]& gate_infolist):
        cdef CPP_Gate* info = &gate_infolist[self.info]
        cdef Gate source
        cdef list dictionary = [
            self.custom_name,
            self.code,
            info.inputlimit,
            self.value if info.type == VARIABLE_ID else [source.code if source and source.scheduled else ('X', 'X') for source in self.sources],
            ]
        return dictionary

    cdef void clone(self, list dictionary, dict pseudo, vector[CPP_Gate]& gate_infolist):
        cdef CPP_Gate* info = &gate_infolist[self.info]
        self.custom_name = dictionary[CUSTOM_NAME]
        if info.type == VARIABLE_ID:
            self.value = dictionary[VALUE]
        else:
            self.setlimits(dictionary[INPUTLIMIT], gate_infolist)
            for index, source in enumerate(dictionary[SOURCES]):
                if source[0] != 'X':
                    self.connect(pseudo[decode(source)], index, gate_infolist)

    cpdef void load_to_cluster(self, list cluster):
        cluster.append(self)
        self.scheduled = True

cdef class Variable(Gate):
    pass

cdef class Probe(Gate):
    pass

cdef class NOT(Gate):
    pass
