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


cdef inline void pop(vector[Profile]& hitlist, int target, int pin_index):
    cdef Profile* profile = hitlist.data()
    cdef Profile* end = profile + hitlist.size()
    while profile < end:
        if profile.target == target and profile.index == pin_index:
            profile[0] = (end-1)[0]
            hitlist.pop_back()
            break
        profile += 1

cdef inline void hide(Profile& profile, CPP_Gate* gate_infolist):
    cdef CPP_Gate* target_info = &gate_infolist[profile.target]
    target_info.book[profile.output] -= 1
    profile.output = UNKNOWN
    cdef Gate target_gate = <Gate>target_info.gate
    target_gate.sources[profile.index] = None

cdef inline void reveal(Profile& profile, Gate source):
    cdef CPP_Gate* gate_infolist=source.info_ptr[0].data()
    cdef CPP_Gate* target_info = &gate_infolist[profile.target]
    target_info.book[UNKNOWN] += 1
    cdef Gate target_gate = <Gate>target_info.gate
    target_gate.sources[profile.index] = source


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
        cdef list targets = []
        cdef CPP_Gate* base = self.info_ptr[0].data()
        cdef CPP_Gate* info=base+self.info
        cdef Profile* profile = info.hitlist.data()
        cdef Profile* end = profile + info.hitlist.size()
        while profile < end:
            targets.append(<Gate>(base[profile.target].gate))
            profile += 1
        return targets

    @property
    def book(self):
        return self.info_ptr[0][self.info].book

    @property
    def inputlimit(self):
        return self.info_ptr[0][self.info].inputlimit
    @property 
    def scheduled(self):
        return self.info_ptr[0][self.info].scheduled
    @property
    def output(self):
        return self.info_ptr[0][self.info].output

    @property
    def value(self):
        return self.info_ptr[0][self.info].value
    @output.setter
    def output(self, int val):
        self.info_ptr[0][self.info].output = val
    @value.setter
    def value(self, int val):
        self.info_ptr[0][self.info].value = val

    cdef void process(self):
        cdef CPP_Gate* gate_infolist=self.info_ptr[0].data()
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
                info.output = info.value
            else:
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

    cdef void connect(self, Gate source, int index):
        cdef CPP_Gate* self_info = &self.info_ptr[0][self.info]
        if self_info.type == VARIABLE_ID or self.sources[index] is not None:
            return
        cdef CPP_Gate* src_info = &source.info_ptr[0][source.info]
        src_info.hitlist.emplace_back(self.info, index, src_info.output)
        self.sources[index] = source
        self_info.book[src_info.output] += 1
        self.process()

    cdef void disconnect(self, int index):
        cdef CPP_Gate* self_info = &self.info_ptr[0][self.info]
        if self_info.type == VARIABLE_ID or self.sources[index] is None:
            return
        cdef Gate source = self.sources[index]
        cdef CPP_Gate* src_info = &source.info_ptr[0][source.info]
        pop(src_info.hitlist, self.info, index)
        self.sources[index] = None
        self_info.book[src_info.output] -= 1
        self_info.output = UNKNOWN

    cdef void reset(self):
        cdef CPP_Gate* info = &self.info_ptr[0][self.info]
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
        cdef Py_ssize_t i
        cdef CPP_Gate* target_info
        cdef Gate target_gate
        cdef list sources
        cdef Gate source
        cdef CPP_Gate* src_info
        cdef uint16_t* book
        cdef Py_ssize_t n
        cdef Profile* hitlist
        cdef CPP_Gate* gate_infolist=self.info_ptr[0].data()
        cdef CPP_Gate* info = &gate_infolist[self.info]
        n = info.hitlist.size()
        hitlist = info.hitlist.data()
        for i in range(n):
            hide(hitlist[i], gate_infolist)

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

    cdef void reveal(self):
        cdef list sources = self.sources
        cdef Py_ssize_t i
        cdef Py_ssize_t n = len(sources)
        cdef Gate source
        cdef CPP_Gate* src_info
        cdef CPP_Gate* gate_infolist=self.info_ptr[0].data()
        cdef CPP_Gate* info = &gate_infolist[self.info]
        if info.type != VARIABLE_ID:
            for i in range(n):
                source = <Gate>PyList_GET_ITEM(sources, i)
                if source is not None:
                    src_info = &gate_infolist[source.info]
                    src_info.hitlist.emplace_back(self.info, i, src_info.output)
                    info.book[src_info.output] += 1

        n = info.hitlist.size()
        cdef Profile* hitlist = info.hitlist.data()
        for i in range(n):
            reveal(hitlist[i], self)

        self.process()

    cpdef bint setlimits(self, int size):
        cdef CPP_Gate* info = &self.info_ptr[0][self.info]
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
        cdef int output=self.info_ptr[0][self.info].output
        if output == HIGH: return 'T'
        elif output == LOW: return 'F'
        elif output == ERROR: return 'T/F'
        else: return 'X'
        
    cpdef list full_data(self):
        cdef CPP_Gate* info = &self.info_ptr[0][self.info]
        cdef Gate source
        cdef list dictionary = [
            self.custom_name,
            self.code,
            info.inputlimit,
            info.value if info.type == VARIABLE_ID else [source.code if source else ('X', 'X') for source in self.sources],
            ]
        return dictionary

    cpdef list partial_data(self):
        cdef CPP_Gate* gate_infolist=self.info_ptr[0].data()
        cdef CPP_Gate* info = &gate_infolist[self.info]
        cdef Gate source
        cdef list dictionary = [
            self.custom_name,
            self.code,
            info.inputlimit,
            info.value if info.type == VARIABLE_ID else [source.code if source and gate_infolist[source.info].scheduled else ('X', 'X') for source in self.sources],
            ]
        return dictionary

    cdef void clone(self, list dictionary, dict pseudo):
        self.custom_name = dictionary[CUSTOM_NAME]
        cdef CPP_Gate* info = &self.info_ptr[0][self.info]
        if info.type == VARIABLE_ID:
            info.value = dictionary[VALUE]
        else:
            self.setlimits(dictionary[INPUTLIMIT])
            for index, source in enumerate(dictionary[SOURCES]):
                if source[0] != 'X':
                    self.connect(pseudo[decode(source)], index)

    cpdef void load_to_cluster(self, list cluster):
        cluster.append(self)
        self.info_ptr[0][self.info].scheduled = True

cdef class Variable(Gate):
    pass

cdef class Probe(Gate):
    pass

cdef class NOT(Gate):
    pass
