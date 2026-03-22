# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
# cython: nonecheck=False
from Gates cimport Gate, Probe, Profile, CPP_Gate, hide, reveal, pop, vector,CPP_Gate,vector
from Store cimport get, decode
from Const cimport *
from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM
cdef class IC:
    def __cinit__(self):
        self.id = IC_ID
        self.counter = 0
    def __init__(self, int id, str name):
        self.inputs = []
        self.internal = []
        self.outputs = []

        self.codename = name
        self.custom_name = ''
        self.code = ()
        self.map = []
        self.tag = ''
        self.description = ''
        self.gate_infolist_ptr=NULL

    def __repr__(self):
        return self.codename if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.codename if self.custom_name == '' else self.custom_name

    cpdef object getcomponent(self, int choice):
        cdef object gt = get(choice, self.gate_infolist_ptr[0],self.gate_verse)
        if gt:
            self.counter += 1
            if gt.id == INPUT_PIN_ID:
                rank = len(self.inputs)
                self.inputs.append(gt)
            elif gt.id == OUTPUT_PIN_ID:
                rank = len(self.outputs)
                self.outputs.append(gt)
            else:
                rank = len(self.internal)
                self.internal.append(gt)
            gt.codename = gt.codename + '-' + str(rank)
            gt.code = (choice, rank, self.code)
        return gt

    cpdef void addgate(self, object source):
        if source.id == INPUT_PIN_ID:
            rank = len(self.inputs)
            self.inputs.append(source)
        elif source.id == OUTPUT_PIN_ID:
            rank = len(self.outputs)
            self.outputs.append(source)
        else:
            rank = len(self.internal)
            self.internal.append(source)
        source.codename = source.codename + '-' + str(rank)
        source.code = (source.code[0], rank, self.code)

    cpdef void configure(self, list dictionary):
        cdef dict pseudo = {}
        pseudo[('X', 'X')] = None
        self.custom_name = dictionary[CUSTOM_NAME]
        self.map = dictionary[MAP]
        if len(dictionary) > TAG:
            self.tag = dictionary[TAG]
        if len(dictionary) > DESCRIPTION:
            self.description = dictionary[DESCRIPTION]
        self.load_components(dictionary, pseudo)
        self.clone(pseudo)

    cpdef void load_components(self, list dictionary, dict pseudo):
        cdef object gate
        cdef list comp_code
        for comp_code in dictionary[MAP]:
            gate = self.getcomponent(comp_code[ID])
            pseudo[comp_code[LOCATION]] = gate

    cpdef void clone(self, dict pseudo):
        cdef Gate gate
        cdef tuple code
        for i in self.map:
            gate = pseudo[i[LOCATION]]
            gate.clone(i, pseudo)

    cpdef void load_to_cluster(self, list cluster):
        cdef Gate i
        for i in self.outputs + self.inputs + self.internal:
            cluster.append(i)
            i.location_ptr[0][i.location].scheduled = True

    cpdef list full_data(self):
        cdef Gate i
        cdef list dictionary = [
            self.custom_name,
            IC_ID,
            [],
            [],
            self.code,
            self.tag,
            self.description,
        ]
        for i in self.inputs + self.outputs + self.internal:
            dictionary[COMPONENTS].append(i.code)
            dictionary[MAP].append(i.full_data())
        return dictionary

    cpdef list partial_data(self):
        cdef Gate i
        cdef list dictionary = [
            self.custom_name,
            IC_ID,
            [],
            [],
            self.code,
            self.tag,
            self.description,
        ]
        for i in self.inputs + self.outputs + self.internal:
            dictionary[COMPONENTS].append(i.code)
            dictionary[MAP].append(i.partial_data())
        return dictionary

    cpdef void implement(self, dict pseudo):
        cdef Gate gate
        cdef tuple code
        for i in self.map:
            gate = pseudo[i[LOCATION]]
            gate.clone(i, pseudo)

    cpdef void hide(self):
        cdef Gate pin_out, pin_in, src
        cdef CPP_Gate* pin_out_info
        cdef CPP_Gate* src_info
        cdef Profile* hitlist
        cdef int index
        cdef size_t i, sz

        # Disconnect outputs from external targets
        cdef CPP_Gate* gate_infolist = self.gate_infolist_ptr[0].data()
        for pin_out in self.outputs:
            pin_out_info = &gate_infolist[pin_out.location]
            hitlist = pin_out_info.hitlist.data()
            sz = pin_out_info.hitlist.size()
            for i in range(sz):
                hide(hitlist[i],gate_infolist, self.gate_verse)

        # Disconnect inputs from external sources
        for pin_in in self.inputs:
            for index, source_loc in enumerate(<list>pin_in._sources):
                if source_loc != -1:
                    src_info = &gate_infolist[source_loc]
                    pop(src_info.hitlist, pin_in.location, index)

    cpdef void reveal(self):
        cdef Gate pin_in, pin_out, source
        cdef CPP_Gate* pin_in_info
        cdef CPP_Gate* pin_out_info
        cdef CPP_Gate* src_info
        cdef Profile* hitlist
        cdef size_t i, sz
        cdef CPP_Gate* gate_infolist = self.gate_infolist_ptr[0].data()
        # Re-register in external source hitlists

        cdef int source_loc
        for pin_in in self.inputs:
            pin_in_info = &gate_infolist[pin_in.location]
            source_loc = pin_in._sources[0]
            if source_loc != -1:
                src_info = &gate_infolist[source_loc]
                src_info.hitlist.emplace_back(pin_in.location, 0, src_info.output)
            pin_in.process()

        # Reconnect output targets via hitlist
        for pin_out in self.outputs:
            pin_out_info = &gate_infolist[pin_out.location]
            hitlist = pin_out_info.hitlist.data()
            sz = pin_out_info.hitlist.size()
            for i in range(sz):
                reveal(hitlist[i], pin_out, self.gate_verse)

    cpdef void reset(self):
        cdef Gate g
        for i in self.inputs + self.internal + self.outputs:
            if i.id != IC_ID:
                g = <Gate>i
                g.reset()
            else:
                (<IC>i).reset()

    cpdef void showinputpins(self):
        for i, gate in enumerate(self.inputs):
            print(f'{i}. {gate}')

    cpdef void showoutputpins(self):
        for i, gate in enumerate(self.outputs):
            print(f'{i}. {gate}')

    cpdef void info(self):
        """Show all IC components in an organized way."""
        cdef Gate pin
        cdef CPP_Gate* pin_info
        cdef Profile* p
        cdef Profile* pend
        cdef list gate_verse = self.gate_verse
        print(f"\n  IC: {self.codename} (Code: {self.code})")
        print("  " + "-" * 40)
        cdef CPP_Gate* gate_infolist = self.gate_infolist_ptr[0].data()
        if self.inputs:
            print("  INPUTS:")
            for pin in self.inputs:
                targets = []
                pin_info = &gate_infolist[pin.location]
                p = pin_info.hitlist.data()
                pend = p + pin_info.hitlist.size()
                while p < pend:
                    targets.append(str(<Gate>PyList_GET_ITEM(gate_verse, p.target)))
                    p += 1
                print(f"    {pin.codename}: out={pin.getoutput()}, to={', '.join(targets) if targets else 'None'}")

        if self.internal:
            print("  INTERNAL:")
            for pin in self.internal:
                if isinstance(pin.sources, list):
                    ch = [f"[{i}]:{c}" for i, c in enumerate(pin.sources) if c != -1]
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = f"val:{pin.sources}"
                tgt = []
                pin_info = &gate_infolist[pin.location]
                p = pin_info.hitlist.data()
                pend = p + pin_info.hitlist.size()
                while p < pend:
                    tgt.append(str(<Gate>PyList_GET_ITEM(gate_verse, p.target)))
                    p += 1
                tgt_str = ", ".join(tgt) if tgt else "None"
                print(f"    {pin.codename}: out={pin.getoutput()}, sources={ch_str}, targets={tgt_str}")

        if self.outputs:
            print("  OUTPUTS:")
            for pin in self.outputs:
                if isinstance(pin.sources, list):
                    ch = [f"{c}" for c in pin.sources if c != -1]
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = "None"
                print(f"    {pin.codename}: out={pin.getoutput()}, from={ch_str}")

        print("  " + "-" * 40)
