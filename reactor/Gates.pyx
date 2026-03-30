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
from libcpp.unordered_map cimport unordered_map

cdef inline void pop(vector[Profile]& hitlist,CPP_Gate* gate_infolist, int target, int pin_index):
    '''Remove a specific entry from a hitlist by target gate and pin index'''
    cdef Profile* profile = hitlist.data()
    cdef Profile* end = profile + hitlist.size()
    while profile < end:
        if profile.target == target and profile.index == pin_index:
            if gate_infolist[target].type < VARIABLE_ID:
                gate_infolist[target].book[profile.output] -= 1
            profile[0] = (end-1)[0] # swap and pop
            hitlist.pop_back()
            break
        profile += 1

cdef inline void hide(Profile& profile, CPP_Gate* gate_infolist, list gate_verse):
    '''Sever one outgoing connection and zero out the target's source slot'''
    cdef CPP_Gate* target_info = &gate_infolist[profile.target]
    if target_info.type < VARIABLE_ID:
        target_info.book[profile.output] -= 1
    profile.output = UNKNOWN
    cdef Gate target_gate = <Gate>gate_verse[profile.target]
    target_gate._sources[profile.index] = -1

cdef inline void reveal(Profile& profile, Gate source, list gate_verse):
    '''Restore one outgoing connection and re-register the source in the target's book'''
    cdef CPP_Gate* gate_infolist=source.location_ptr[0].data()
    cdef CPP_Gate* target_info = &gate_infolist[profile.target]
    if target_info.type < VARIABLE_ID:
        target_info.book[UNKNOWN] += 1
    cdef Gate target_gate = <Gate>gate_verse[profile.target]
    target_gate._sources[profile.index] = source.location


cdef class Gate:
    def __init__(self, int id, str name):
        self.codename = name
        self.location = -1
        self.id = id
        if id >= VARIABLE_ID:
            self._sources = [-1]
        else:
            self._sources = [-1, -1]
        self.code = ()
        self.custom_name = ''

    def __repr__(self):
        return self.codename if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.codename if self.custom_name == '' else self.custom_name
    def __int__(self):
        return self.location

    @property
    def hitlist(self):
        '''All gates this gate currently drives'''
        cdef list targets = []
        cdef CPP_Gate* base = self.location_ptr[0].data()
        cdef CPP_Gate* info=base+self.location
        cdef Profile* profile = info.hitlist.data()
        cdef Profile* end = profile + info.hitlist.size()
        cdef list gate_verse = self.gate_verse
        while profile < end:
            targets.append(<Gate>(PyList_GET_ITEM(gate_verse, profile.target)))
            profile += 1
        return targets

    @property
    def book(self):
        '''Input tally: counts of LOW, HIGH, ERROR, and UNKNOWN sources'''
        return self.location_ptr[0][self.location].book

    @property
    def inputlimit(self):
        '''How many inputs this gate accepts'''
        return self.location_ptr[0][self.location].inputlimit
    @property 
    def scheduled(self):
        '''Whether this gate is already queued for propagation this tick'''
        return self.location_ptr[0][self.location].scheduled
    @property
    def output(self):
        '''Current output value of this gate'''
        return self.location_ptr[0][self.location].output

    @property
    def value(self):
        '''Stored toggle value, only meaningful for variables'''
        return self.location_ptr[0][self.location].value
    
    @property
    def sources(self):
        '''The gate objects wired into each input slot, or None for empty slots'''
        cdef list source_list=[]
        cdef int i
        for i in self._sources:
            if i != -1:
                source_list.append(self.gate_verse[i])
            else:
                source_list.append(None)
        return source_list
    @output.setter
    def output(self, int val):
        self.location_ptr[0][self.location].output = val
    @value.setter
    def value(self, int val):
        self.location_ptr[0][self.location].value = val

    cdef void process(self):
        '''Recompute this gate's output from its current inputs and type
        a slower yet safer method of updating output'''
        cdef CPP_Gate* gate_infolist=self.location_ptr[0].data()
        cdef CPP_Gate* info = &gate_infolist[self.location]
        cdef CPP_Gate* src_info
        cdef uint16_t* book
        cdef int gate_type = info.type
        cdef int limit = info.inputlimit
        cdef int high, low, realsource
        cdef int source_loc # Changed from Gate source to int source_loc

        if MODE == DESIGN:
            info.output = UNKNOWN
            return

        if gate_type >= VARIABLE_ID:
            if gate_type == VARIABLE_ID:
                info.output = info.value
            else:
                source_loc = self._sources[0]
                if source_loc == -1:
                    info.output = UNKNOWN
                else:
                    src_info = &gate_infolist[source_loc]
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
                else:                      info.output = (high & 1) ^ (gate_type & 1)
            else:
                info.output = UNKNOWN

    cpdef void rename(self, str name):
        '''Give the gate a display name'''
        self.custom_name = name

    cpdef void deregister(self):
        '''Remove the gate from the global list and mark its slot as deleted'''
        self.all_gates[self.location] = None
        self.location_ptr[0][self.location].type = -1

    cdef void connect(self, int source, int index):
        '''Wire a source gate into this gate's input slot at index'''
        cdef CPP_Gate* gate_infolist=self.location_ptr[0].data()
        cdef CPP_Gate* self_info = &gate_infolist[self.location]
        if self_info.type == VARIABLE_ID or self._sources[index] != -1:
            return
        cdef CPP_Gate* src_info = &gate_infolist[source]
        src_info.hitlist.emplace_back(self.location, index, src_info.output)
        self._sources[index] = source
        if self.id<VARIABLE_ID:
            self_info.book[src_info.output] += 1
        self.process()

    cdef void disconnect(self, int index):
        '''Remove whatever is wired into input slot at index and clear the output'''
        cdef CPP_Gate* gate_infolist=self.location_ptr[0].data()
        cdef CPP_Gate* self_info = &gate_infolist[self.location]
        if self_info.type == VARIABLE_ID or self._sources[index] == -1:
            return
        cdef int src_loc = self._sources[index]
        cdef CPP_Gate* src_info = &gate_infolist[src_loc]
        pop(src_info.hitlist, gate_infolist, self.location, index)
        self._sources[index] = -1
        self_info.output = UNKNOWN

    cdef void reset(self):
        '''Move all counted inputs back to unknown and set output to unknown'''
        cdef CPP_Gate* info = &self.location_ptr[0][self.location]
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

    cdef void hide(self):
        '''Detach this gate from the live graph without removing it from the lists'''
        cdef Py_ssize_t i
        cdef CPP_Gate* target_info
        cdef Gate target_gate
        cdef list sources
        cdef int source_loc
        cdef CPP_Gate* src_info
        cdef uint16_t* book
        cdef Py_ssize_t n
        cdef Profile* hitlist
        cdef CPP_Gate* gate_infolist=self.location_ptr[0].data()
        cdef CPP_Gate* info = &gate_infolist[self.location]
        n = info.hitlist.size()
        hitlist = info.hitlist.data()
        for i in range(n):
            hide(hitlist[i], gate_infolist, self.gate_verse)

        sources = self._sources
        if info.type != VARIABLE_ID:
            n = len(sources)
            for i in range(n):
                source_loc = sources[i]
                if source_loc != -1:
                    src_info = &gate_infolist[source_loc]
                    pop(src_info.hitlist,gate_infolist, self.location, i)

        # 3. Zero out own state
        info.output = UNKNOWN
        if info.type < VARIABLE_ID:
            book = info.book
            book[0] = book[1] = book[2] = book[3] = 0

    cdef void reveal(self):
        '''Re-attach this gate to the live graph and recompute its output'''
        cdef list sources = self._sources
        cdef Py_ssize_t i
        cdef Py_ssize_t n = len(sources)
        cdef int source_loc
        cdef CPP_Gate* src_info
        cdef CPP_Gate* gate_infolist=self.location_ptr[0].data()
        cdef CPP_Gate* info = &gate_infolist[self.location]
        if info.type != VARIABLE_ID:
            for i in range(n):
                source_loc = sources[i]
                if source_loc != -1:
                    src_info = &gate_infolist[source_loc]
                    src_info.hitlist.emplace_back(self.location, i, src_info.output)
                    info.book[src_info.output] += 1

        n = info.hitlist.size()
        cdef Profile* hitlist = info.hitlist.data()
        for i in range(n):
            reveal(hitlist[i], self, self.gate_verse)

        self.process()

    cpdef bint setlimits(self, int size):
        '''Resize the input list; returns False if slots are in use and can't be trimmed'''
        cdef CPP_Gate* info = &self.location_ptr[0][self.location]
        cdef int i
        cdef int current
        if size < 2 or info.type >= VARIABLE_ID:
            return False
        current = info.inputlimit

        if size > current:
            for _ in range(size - current):
                self._sources.append(-1)
            info.inputlimit = size
            self.process()
            return True
        elif size < current:
            for i in range(size, current):
                if self._sources[i] != -1:
                    return False
            self._sources = self._sources[:size]
            info.inputlimit = size
            self.process()
            return True
        return False

    cpdef str getoutput(self):
        '''Return the output as a human-readable character: T, F, E, or X'''
        cdef int output=self.location_ptr[0][self.location].output
        if output == HIGH: return 'T'
        elif output == LOW: return 'F'
        elif output == ERROR: return 'E'
        else: return 'X'
        
    cpdef list full_data(self):
        '''Serialise the gate with full connection info, used for saving the circuit'''
        cdef CPP_Gate* info = &self.location_ptr[0][self.location]
        cdef list dictionary = [
            self.custom_name,
            self.id,
            self.location,
            info.inputlimit,
            info.value if info.type == VARIABLE_ID else list(self._sources),
            ]
        return dictionary

    cpdef list partial_data(self):
        '''Serialise the gate with only the in-cluster connections, for copy/paste and IC export'''
        cdef CPP_Gate* gate_infolist=self.location_ptr[0].data()
        cdef CPP_Gate* info = &gate_infolist[self.location]
        cdef list dictionary = [
            self.custom_name,
            self.id,
            self.location,
            info.inputlimit,
            info.value if info.type == VARIABLE_ID else [src_loc if src_loc != -1 and gate_infolist[src_loc].scheduled else -1 for src_loc in self._sources],
            ]
        return dictionary

    cdef void clone(self, list dictionary, unordered_map[int,int]& pseudo):
        '''Restore gate state from serialised data, remapping source locations via pseudo'''
        self.custom_name = dictionary[CUSTOM_NAME]
        cdef CPP_Gate* info = &self.location_ptr[0][self.location]
        if info.type == VARIABLE_ID:
            info.value = dictionary[VALUE]
        else:
            self.setlimits(dictionary[INPUTLIMIT])
            for index, source in enumerate(dictionary[SOURCES]):
                if source != -1:
                    self.connect(pseudo[source], index)

    cpdef void load_to_cluster(self, list cluster):
        '''Mark this gate as scheduled and add it to the copy cluster'''
        cluster.append(self)
        self.location_ptr[0][self.location].scheduled = True

cdef class Variable(Gate):
    pass

cdef class Probe(Gate):
    pass

cdef class NOT(Gate):
    pass
