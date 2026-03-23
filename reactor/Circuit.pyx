# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
# cython: nonecheck=False
import orjson
from Gates cimport Gate, Variable, Profile, vector, CPP_Gate
from Const cimport *
from IC cimport IC
from Store cimport get, decode
from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM
from libc.stdint cimport uint16_t
from libcpp.unordered_map cimport unordered_map

cdef class Circuit:
    def __cinit__(self):
        self.counter = 0
        self.eval_count = 0
        self.gate_infolist.reserve(500_000)
        self.gate_verse = []
    def __init__(self):
        # lookup table for objects by code
        set_MODE(DESIGN)
        self.objlist = [
            [] for i in range(TOTAL)]
        self.copydata = []

    def __repr__(self):
        return 'Circuit'
    @property
    def infolist_size(self):
        return self.gate_infolist.size()
    cpdef object getcomponent(self, int choice):
        gt = get(choice, self.gate_infolist, self.gate_verse)
        if gt:
            self.counter += 1
            rank = len(self.objlist[choice])
            self.objlist[choice].append(gt)
            gt.code = (choice, rank)
            if DEBUG:
                if gt.id == VARIABLE_ID:
                    gt.codename = chr(ord('A') + (rank) % 26) + str((rank + 1) // 26)
                else:
                    gt.codename = gt.codename + '-' + str(len(self.objlist[choice]))
            if gt.id == VARIABLE_ID:
                self.gate_infolist[(<Gate>gt).location].output = UNKNOWN if MODE==DESIGN else LOW
        return gt

    cpdef object getobj(self, tuple code):
        return self.objlist[code[0]][code[1]]

    cpdef void delobj(self, object obj):
        cdef CPP_Gate* gate_info=self.gate_infolist.data()
        cdef Gate gate
        cdef IC ic
        if obj.id == IC_ID:
            ic = <IC>obj
            self.counter += ic.counter
            for gate in ic.outputs+ic.inputs+ic.internal:
                gate_info[gate.location].type = -gate_info[gate.location].type -1
        else:
            gate = <Gate>obj
            gate_info[gate.location].type = -gate_info[gate.location].type -1 
        self.counter -= 1
        self.objlist[obj.code[0]][obj.code[1]] = None

    cpdef void renewobj(self, object obj):
        cdef CPP_Gate* gate_info=self.gate_infolist.data()
        cdef Gate gate
        cdef IC ic
        if obj.id == IC_ID:
            ic = <IC>obj
            self.counter += ic.counter
            for gate in ic.outputs+ic.inputs+ic.internal:
                gate_info[gate.location].type = -gate_info[gate.location].type -1
        else:
            gate = <Gate>obj
            gate_info[gate.location].type = -gate_info[gate.location].type -1 
        self.counter += 1
        self.objlist[obj.code[0]][obj.code[1]] = obj


    cpdef list get_components(self):
        return [gate for sublist in self.objlist for gate in sublist if gate is not None]

    cpdef list get_variables(self):
        return [gate for gate in self.objlist[VARIABLE_ID] if gate is not None]

    cpdef list get_ics(self):
        return [gate for gate in self.objlist[IC_ID] if gate is not None]

    cpdef void listComponent(self):
        cdef int i = 0
        for i, gate in enumerate(self.get_components()):
            print(f'{i}. {gate}')

    cpdef void listVar(self):
        cdef int i = 0
        for i, gate in enumerate(self.get_variables()):
            print(f'{i}. {gate}')

    cpdef bint setlimits(self, Gate gate, int size):
        return gate.setlimits(size)

    cpdef void connect(self, Gate target, int source, int index):
        cdef CPP_Gate* info = &self.gate_infolist[target.location]
        cdef int prev = info.output
        target.connect(source, index)
        if prev != info.output:
            self.propagate(target.location)

    cpdef void toggle(self, int target, int value):
        cdef CPP_Gate* info = &self.gate_infolist[target]
        if value != info.output:
            info.value = value
            info.output = value if MODE == SIMULATE else UNKNOWN
            self.propagate(target)

    cpdef void disconnect(self, Gate target, int index):
        cdef CPP_Gate* info = &self.gate_infolist[target.location]
        cdef int prev = info.output
        target.disconnect(index)
        if prev != info.output:
            self.propagate(target.location)

    cpdef void hide(self, list gatelist):
        cdef Gate pin
        cdef IC ic
        for gate in gatelist:
            if gate.id == IC_ID:
                ic = <IC>gate
                ic.hide()
            else:
                pin = <Gate>gate
                pin.hide()
            self.delobj(gate)

        for gate in gatelist:
            if gate.id == IC_ID:
                ic = <IC>gate
                for pin in ic.outputs:
                    self.turnoff(pin)
            else:
                self.turnoff(gate)

    cpdef void reveal(self, list gatelist):
        cdef Gate pin
        cdef IC ic
        for gate in reversed(gatelist):
            self.renewobj(gate)
            if gate.id == IC_ID:
                ic = <IC>gate
                ic.reveal()
            else:
                pin = <Gate>gate
                pin.reveal()

        for gate in reversed(gatelist):
            if gate.id == IC_ID:
                ic = <IC>gate
                for pin in ic.outputs:
                    self.propagate(pin.location)
            else:
                self.propagate((<Gate>gate).location)

    # Result
    cpdef void output(self, Gate gate):
        print(f'{gate} output is {gate.getoutput()}')
        
    cdef bytearray table(self,vector[int] &var,vector[int] &gate):
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        cdef int var_size=var.size()
        cdef int gate_size=gate.size()
        cdef int row=1<<var_size,col=var_size+gate_size
        cdef bytearray matrix=bytearray(row*col)
        cdef unsigned char[:] view=matrix
        cdef int i,j,k,bit
        cdef int gray = 0
        cdef int prev_gray = 0
        cdef int mask, changed_bit, offset

        for i in range(row):
            prev_gray = gray
            gray = i ^ (i >> 1)

            if i != 0:
                mask = prev_gray ^ gray

                if mask == 1: changed_bit = 0
                elif mask == 2: changed_bit = 1
                elif mask == 4: changed_bit = 2
                elif mask == 8: changed_bit = 3
                elif mask == 16: changed_bit = 4
                elif mask == 32: changed_bit = 5
                elif mask == 64: changed_bit = 6
                elif mask == 128: changed_bit = 7
                elif mask == 256: changed_bit = 8
                elif mask == 512: changed_bit = 9
                elif mask == 1024: changed_bit = 10
                elif mask == 2048: changed_bit = 11
                elif mask == 4096: changed_bit = 12
                elif mask == 8192: changed_bit = 13
                elif mask == 16384: changed_bit = 14
                elif mask == 32768: changed_bit = 15
                else: changed_bit = 0

                j = (var_size - 1) - changed_bit
                bit = 1 if (gray & mask) else 0
                gate_infolist[var[j]].output = bit
                self.propagate(var[j])
            else:
                for j in range(var_size):
                    if gate_infolist[var[j]].output != 0:
                        gate_infolist[var[j]].output = 0
                        self.propagate(var[j])

            # Fast C-level list creation instead of .append()
            offset=col*gray
            for k in range(var_size):
                view[offset+k] = gate_infolist[var[k]].output
            for k in range(gate_size):
                view[offset+var_size+k] = gate_infolist[gate[k]].output
        return matrix
        
    cpdef str truthTable(self, list variables, list outputs):
        if variables is None:
            variables = self.get_variables()
        if len(variables) == 0 or len(variables) > 16 or MODE == DESIGN:
            return ""
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        cdef list gate_list = []
        cdef list var_names, gate_names, all_names, header_parts, final_table_lines, row_parts
        cdef str header, separator
        cdef int col_width, bit, gate_type
        cdef Py_ssize_t i, j, k, n
        cdef list IN_MAP, OUT_MAP
        cdef list v_states, g_states
        cdef Gate var, gate,pin
        cdef IC ic
        cdef object item
        
        # Filter gatelist
        if outputs is not None:
            gate_list = outputs
        else:
            for item in self.get_components():
                gate_type = item.id
                if gate_type == VARIABLE_ID:
                    continue
                elif gate_type != IC_ID:
                    gate_list.append(item)
                else:
                    ic = <IC>item
                    for pin in ic.outputs:
                        gate_list.append(pin)

        n = len(variables)
        cdef int rows_count = 1 << n

        cdef CPP_Gate* var_info
        var_names = [str(v) for v in variables]
        gate_names = [str(v) for v in gate_list]
        all_names = var_names + gate_names
        cdef vector[int] var_vector
        cdef vector[int] gate_vector
        for gate in variables:
            var_vector.push_back((<Gate>gate).location)
        for gate in gate_list:
            gate_vector.push_back((<Gate>gate).location)
        cdef bytearray raw_rows = self.table(var_vector, gate_vector)
        if len(all_names) > 0:
            col_width = max([len(name) for name in all_names]) + 2
        else:
            col_width = 4

        # Pre-compute formatting maps
        IN_MAP = [
            "0".center(col_width),
            "1".center(col_width)
        ]
        OUT_MAP = [
            "F".center(col_width),
            "T".center(col_width),
            "E".center(col_width),
            "X".center(col_width)
        ]

        header_parts = [name.center(col_width) for name in all_names]
        header = " | ".join(header_parts)
        separator = "─" * len(header)

        self.simulate(SIMULATE)

        # --- STRING JOINING PHASE ---
        final_table_lines = [separator, header, separator]
        cdef int total=len(variables)+len(gate_list)

        for i in range(rows_count):
            row_parts = [IN_MAP[raw_rows[i*total+j]] for j in range(n)]
            row_parts.extend([OUT_MAP[raw_rows[i*total+n+j]] for j in range(len(gate_list))])
            final_table_lines.append(" | ".join(row_parts))

        final_table_lines.append(separator)
        final_table_lines.append("")

        return "\n".join(final_table_lines)

    def diagnose(self):
        cdef Gate comp
        cdef CPP_Gate* info
        cdef Profile* profile
        cdef Profile* end
        cdef list ics
        print("=" * 90)
        print(" " * 35 + "CIRCUIT DIAGNOSIS")
        print("=" * 90)

        gates = [c for c in self.get_components() if c.id != IC_ID]
        if gates:
            columns = [
                ("Component", 14),
                ("Sources", 28),
                ("Book[L,H,E,U]", 15),
                ("Targets", 25),
                ("Out", 6)
            ]
            total_width = sum(w for _, w in columns)
            fmt = "".join(f"{{:<{w}}}" for _, w in columns)

            print("\n" + fmt.format(*[n for n, _ in columns]))
            print("-" * total_width)

            for comp in gates:
                info = &self.gate_infolist[comp.location]
                if isinstance(comp.sources, list):
                    ch = [f"[{i}]:{c}" for i, c in enumerate(comp.sources) if c != -1]
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = f"val:{comp.sources}"

                book = f"[{info.book[0]},{info.book[1]},{info.book[2]},{info.book[3]}]"

                # Targets from info.hitlist
                tgt = []
                profile = info.hitlist.data()
                end = profile + info.hitlist.size()
                while profile < end:
                    tgt.append(str(<Gate>PyList_GET_ITEM(self.gate_verse, profile.target)))
                    profile += 1
                tgt_str = ", ".join(tgt) if tgt else "None"

                ch_str = ch_str[:26] + ".." if len(ch_str) > 28 else ch_str
                tgt_str = tgt_str[:23] + ".." if len(tgt_str) > 25 else tgt_str

                print(fmt.format(str(comp), ch_str, book, tgt_str, str(comp.getoutput())))

            print("-" * total_width)

        ics = [c for c in self.objlist[IC_ID] if c is not None]
        if ics:
            print("\n" + "=" * 90)
            print(" " * 40 + "IC STATUS")
            print("=" * 90)
            for ic in ics:
                print(f"\n  IC: {repr(ic)} (Code: {ic.code})")
                print("  " + "-" * 50)

                if ic.inputs:
                    print("  INPUT PINS:")
                    for pin in ic.inputs:
                        ch = [f"{c}" for c in pin.sources if c != -1] if isinstance(pin.sources, list) else [f"val:{pin.sources}"]
                        print(f"    {repr(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}")

                if ic.outputs:
                    print("  OUTPUT PINS:")
                    for pin in ic.outputs:
                        ch = [f"{c}" for c in pin.sources if c != -1] if isinstance(pin.sources, list) else [f"val:{pin.sources}"]
                        print(f"    {repr(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}")

        print("\n" + "=" * 90)

    cpdef void writetojson(self, str location):
        cdef list circuit = []
        cdef object gate
        for gate in self.get_components():
            circuit.append(gate.full_data())
        with open(location, 'wb') as file:
            file.write(orjson.dumps(circuit))

    cpdef void refresh(self):
        self.optimize()
        cdef int n=self.gate_infolist.size()
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        while n>0 and gate_infolist[n-1].type<0:
            self.gate_verse.pop()
            self.gate_infolist.pop_back()
            n-=1

    cpdef void optimize(self):
        cdef int i=0,j=0,n
        cdef vector[int] queue,hash_map,in_degree,hidden
        cdef Profile* profile, *end
        cdef int degree=0,index=0,active_gates=0
        cdef CPP_Gate* info
        cdef vector[CPP_Gate] new_gate_infolist
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        cdef Gate gate
        with nogil:
            n=self.gate_infolist.size()
            queue.resize(n)
            hash_map.resize(n)
            in_degree.resize(n)
            active_gates=n
            for i in range(n):
                info=&gate_infolist[i]
                if info.type<0:
                    in_degree[i]=-1
                    active_gates-=1
                    hidden.push_back(i)
                    continue
                profile=info.hitlist.data()
                end=profile+info.hitlist.size()
                while profile<end:
                    in_degree[profile.target]+=1
                    profile+=1
            i=0
            for index in range(n):
                if in_degree[index]==0:
                    queue[j]=index
                    j+=1
            while i<j:
                info=&gate_infolist[queue[i]]
                hash_map[queue[i]]=i
                profile=info.hitlist.data()
                end=profile+info.hitlist.size()
                while profile<end:
                    if in_degree[profile.target]>0:
                        in_degree[profile.target]-=1
                        if in_degree[profile.target]==0:
                            queue[j]=profile.target
                            j+=1
                    profile+=1
                i+=1
            if j<active_gates:
                for index in range(n):
                    if in_degree[index]>0:
                        queue[j]=index
                        in_degree[index]=0
                        j+=1
                        while i<j:
                            info=&gate_infolist[queue[i]]
                            hash_map[queue[i]]=i
                            profile=info.hitlist.data()
                            end=profile+info.hitlist.size()
                            while profile<end:
                                if in_degree[profile.target]>0:
                                    in_degree[profile.target]-=1
                                    if in_degree[profile.target]==0:
                                        queue[j]=profile.target
                                        j+=1
                                profile+=1
                            i+=1
            # i is location of each hidden gate, it will be pushed to the end of queue
            for i in hidden:
                queue[j]=i
                hash_map[i]=j
                j+=1
            # create new info_list
            new_gate_infolist.resize(n)
            for i in range(n):
                new_gate_infolist[i]=gate_infolist[queue[i]]
                profile=new_gate_infolist[i].hitlist.data()
                end=profile+new_gate_infolist[i].hitlist.size()
                while profile<end:
                    profile.target=hash_map[profile.target]
                    profile+=1
            self.gate_infolist.swap(new_gate_infolist)
        cdef list new_gate_verse = []
        for i in range(n):
            gate=<Gate>PyList_GET_ITEM(self.gate_verse, queue[i])
            gate.location=i
            for index in range(len(gate._sources)):
                if gate._sources[index] != -1:
                    gate._sources[index] = hash_map[gate._sources[index]]
            new_gate_verse.append(gate)
        self.gate_verse[:] = new_gate_verse

    cpdef void generate(self, list circuit):
        cdef unordered_map[int,int] pseudo
        pseudo[-1] = -1
        cdef object obj
        cdef Gate gate
        cdef IC ic
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        cdef list info
        cdef list ic_list=[]
        for info in circuit:  # load to pseudo
            if info[ID] == IC_ID:
                ic = <IC>self.getcomponent(info[ID])
                ic.custom_name = info[CUSTOM_NAME]
                ic.map = info[MAP]
                ic.load_components(info, pseudo)
                ic_list.append(ic)
            else:
                gate = <Gate>self.getcomponent(info[ID])
                if gate.id == VARIABLE_ID:
                    gate_infolist[gate.location].output = UNKNOWN
                pseudo[info[LOCATION]] = gate.location
        for info in circuit:  # connect components
            if info[ID] != IC_ID:
                gate = <Gate>PyList_GET_ITEM(self.gate_verse, pseudo[info[LOCATION]])
                gate.clone(info, pseudo)
        for ic in ic_list:
            ic.implement(pseudo)
            self.counter += ic.counter

    cpdef void readfromjson(self, str location):
        cdef list circuit
        with open(location, 'rb') as file:
            circuit = orjson.loads(file.read())
            self.generate(circuit)
        if MODE != DESIGN:
            self.simulate(SIMULATE)

    cpdef IC build_ic(self):
        cdef Gate gate, target
        cdef Profile* profile
        cdef Profile* end
        cdef CPP_Gate* info
        cdef IC my_ic = self.getcomponent(IC_ID)
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        cdef list queue = []
        cdef list outputs = [i for i in self.objlist[OUTPUT_PIN_ID] if i is not None]
        cdef list inputs = [i for i in self.objlist[INPUT_PIN_ID] if i is not None]
        for gate in outputs + inputs:
            gate_infolist[gate.location].scheduled = True
            queue.append(gate)
        cdef Py_ssize_t size = len(queue)
        cdef Py_ssize_t index = len(outputs)
        cdef list gate_verse = self.gate_verse
        while index < size:
            gate = queue[index]
            info = &gate_infolist[gate.location]
            if gate.id == INPUT_PIN_ID and gate._sources[0] != -1:
                profile = info.hitlist.data()
                end = profile + info.hitlist.size()
                while profile != end:
                    target = <Gate>PyList_GET_ITEM(gate_verse, profile.target)
                    target._sources[profile.index] = gate._sources[0]
                    profile += 1
            elif gate.id == OUTPUT_PIN_ID and not info.hitlist.empty():
                profile = info.hitlist.data()
                end = profile + info.hitlist.size()
                while profile != end:
                    target = <Gate>PyList_GET_ITEM(gate_verse, profile.target)
                    target._sources[profile.index] = gate._sources[0]
                    profile += 1
            profile = info.hitlist.data()
            end = profile + info.hitlist.size()
            while profile != end:
                target = <Gate>PyList_GET_ITEM(gate_verse, profile.target)
                if not gate_infolist[target.location].scheduled:
                    gate_infolist[target.location].scheduled = True
                    queue.append(target)
                    size += 1
                profile += 1
            index += 1
        cdef int pins = len(inputs) + len(outputs)
        for input_pin in inputs:
            my_ic.addgate(input_pin)
        for output_pin in outputs:
            my_ic.addgate(output_pin)
        for index in range(pins, size):
            gate = queue[index]
            if gate.id >= INPUT_PIN_ID:
                continue
            my_ic.addgate(gate)
        return my_ic

    cpdef void ic_pin_change(self):
        cdef Gate var, probe
        cdef CPP_Gate* info
        for var in self.objlist[VARIABLE_ID]:
            if var is not None:
                info = &self.gate_infolist[var.location]
                var.code = (INPUT_PIN_ID, len(self.objlist[INPUT_PIN_ID]))
                var.id = INPUT_PIN_ID
                info.type = INPUT_PIN_ID
                self.objlist[INPUT_PIN_ID].append(var)
        self.objlist[VARIABLE_ID].clear()

        for probe in self.objlist[PROBE_ID]:
            if probe is not None:
                info = &self.gate_infolist[probe.location]
                probe.code = (OUTPUT_PIN_ID, len(self.objlist[OUTPUT_PIN_ID]))
                probe.id = OUTPUT_PIN_ID
                info.type = OUTPUT_PIN_ID
                self.objlist[OUTPUT_PIN_ID].append(probe)
        self.objlist[PROBE_ID].clear()

    cpdef void transfer_info(self, Gate gate, int id):
        cdef CPP_Gate* info
        cdef list real_source
        cdef int length
        if id >= IC_ID or id < 0:
            return
        real_source = [source for source in gate._sources if source != -1]
        length = len(real_source)
        if not real_source or (length == 1 and id != VARIABLE_ID) or (length > 1 and id < VARIABLE_ID):
            if gate._sources[0] == -1:
                self.objlist[gate.code[0]][gate.code[1]] = None
                gate.id = id
                gate.code = (id, len(self.objlist[id]))
                self.objlist[id].append(gate)
                # Update CPP_Gate type as well
                info = &self.gate_infolist[gate.location]
                info.type = id
                gate.process()
                self.propagate(gate.location)

    cpdef void reorder(self, object gate, int index):
        cdef list lst = self.objlist[(<Gate>gate).id]
        if index < 0 or index >= len(lst):
            return
        cdef object old = lst[index]
        lst[index] = gate
        lst[gate.code[1]] = old
        if old is not None:
            old.code, gate.code = gate.code, old.code
        else:
            gate.code = (gate.code[0], index)

    cpdef void save_as_ic(self, str location, str ic_name, str tag, str description, list components):
        cdef Circuit crct
        cdef CPP_Gate* info
        cdef IC my_ic
        if components:
            crct = Circuit()
            crct.copy(components)
            crct.paste()
            crct.save_as_ic(location, ic_name, tag, description, None)
            return
        if len(self.objlist[VARIABLE_ID]) or len(self.objlist[PROBE_ID]):
            self.ic_pin_change()
        for gate in self.objlist[INPUT_PIN_ID]:
            if gate and (<Gate>gate)._sources[0] != -1:
                raise ValueError('Input Pin has extra sources')
        for gate in self.objlist[OUTPUT_PIN_ID]:
            if gate:
                info = &self.gate_infolist[(<Gate>gate).location]
                if info.hitlist.size() > 0:
                    raise ValueError('Output Pin has extra targets')

        my_ic = self.build_ic()
        my_ic.custom_name = ic_name
        my_ic.tag = tag
        my_ic.description = description
        with open(location, 'wb') as file:
            file.write(orjson.dumps(my_ic.partial_data()))
        self.clearcircuit()

    cpdef object get_ic(self, str location):
        with open(location, 'rb') as file:
            crct = orjson.loads(file.read())
        if isinstance(crct[LOCATION], list):
            return crct
        else:
            print('Cannot Convert to IC')
            return None

    cpdef IC load_ic(self, list crct):
        cdef IC myIC = self.getcomponent(IC_ID)
        myIC.configure(crct)
        self.counter += myIC.counter
        return myIC

    cpdef IC getIC(self, location):
        cdef list crct = self.get_ic(location)
        if crct is None:
            return None
        return self.load_ic(crct)

    cpdef void rank_reset(self):
        for i in range(TOTAL):
            while self.objlist[i] and self.objlist[i][len(self.objlist[i]) - 1] is None:
                self.objlist[i].pop()

    cpdef void clearcircuit(self):
        self.gate_infolist.clear()
        self.gate_verse.clear()
        for i in range(TOTAL):
            self.objlist[i].clear()
        self.counter = 0

    cpdef void copy(self, list components):
        cdef Gate gate
        cdef object item
        cdef list cluster
        if len(components) == 0:
            return
        self.copydata = []
        cluster = []
        for item in components:
            item.load_to_cluster(cluster)
        for item in components:
            if item.id != IC_ID:
                gate = <Gate>item
                self.copydata.append(gate.partial_data())
            else:
                self.copydata.append(item.partial_data())
        for gate in cluster:
            self.gate_infolist[gate.location].scheduled = False

    cpdef list paste(self):
        cdef list circuit
        cdef unordered_map[int,int] pseudo
        cdef list new_items=[]
        cdef tuple code
        cdef Gate g
        circuit = self.copydata
        pseudo[-1] = -1
        new_items = []
        cdef Gate gate
        cdef IC ic
        cdef list info,gate_info
        cdef list ic_list=[]
        for info in circuit:  # load to pseudo
            if info[ID] == IC_ID:
                ic = <IC>self.getcomponent(info[ID])
                ic.custom_name = info[CUSTOM_NAME]
                ic.map = info[MAP]
                ic.load_components(info, pseudo)
                ic_list.append(ic)
                new_items.append(ic)
            else:
                gate = <Gate>self.getcomponent(info[ID])
                if gate.id == VARIABLE_ID:
                    gate.output = UNKNOWN
                pseudo[info[LOCATION]] = gate.location
                new_items.append(gate)

        for gate_info in circuit:  # connect components
            if gate_info[ID] != IC_ID:
                gate = <Gate>PyList_GET_ITEM(self.gate_verse, pseudo[gate_info[LOCATION]])
                gate.clone(gate_info, pseudo)
        for ic in ic_list:
            ic.implement(pseudo)
            self.counter += ic.counter

        if MODE != DESIGN:
            self.simulate(SIMULATE)
        return new_items

    cpdef void simulate(self, int Mod):
        cdef Gate variable
        cdef CPP_Gate* info
        set_MODE(Mod)
        for variable in self.objlist[VARIABLE_ID]:
            if variable is not None:
                info = &self.gate_infolist[variable.location]
                info.output = info.value
                self.propagate(variable.location)

    cpdef void reset(self):
        cdef Gate g
        set_MODE(DESIGN)
        for i in self.get_components():
            if i.id != IC_ID:
                g = <Gate>i
                g.reset()
            else:
                (<IC>i).reset()

    cdef inline void turnoff(self, int gate) nogil:
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        cdef Profile* profile = gate_infolist[gate].hitlist.data()
        cdef Profile* end = profile + gate_infolist[gate].hitlist.size()
        cdef int self_idx = gate
        while profile != end:
            if profile.target != self_idx:
                gate_infolist[profile.target].output = UNKNOWN
                self.propagate(profile.target)
            profile += 1

    cdef void burn(self, Py_ssize_t index, Py_ssize_t size, int* read_queue, int* write_queue) nogil:
        cdef Profile* profile
        cdef Profile* end
        cdef unsigned long long eval = 0
        cdef Py_ssize_t end_point = size
        cdef int gidx, tidx
        cdef CPP_Gate* info
        cdef CPP_Gate* target_info
        cdef CPP_Gate* gate_infolist = self.gate_infolist.data()
        size = 0
        while index < end_point:
            while index < end_point:
                info = &gate_infolist[read_queue[index]]
                info.scheduled = False
                profile = info.hitlist.data()
                end = profile + info.hitlist.size()
                info.output = ERROR
                while profile != end:
                    eval += 1
                    if profile.output != ERROR:
                        target_info = &self.gate_infolist[profile.target]
                        if target_info.inputlimit != 1:
                            target_info.book[profile.output] -= 1
                            target_info.book[ERROR] += 1
                        if target_info.output != ERROR:
                            write_queue[size] = profile.target
                            size += 1
                        target_info.output = ERROR
                        profile.output = ERROR
                    profile += 1
                index += 1
            index = 0
            end_point = size
            size = 0
            read_queue, write_queue = write_queue, read_queue
        self.eval_count += eval

    cdef void propagate(self, int origin) nogil:
        cdef Profile* profile
        cdef Profile* end
        cdef Py_ssize_t realsource, high, low, gate_type, limit
        cdef Py_ssize_t new_output, profile_output, target_output
        cdef Py_ssize_t index = 0, end_point = 1, size = 0
        cdef unsigned long long counter = 0
        cdef unsigned long long eval = 0
        cdef int* read_queue = self.queue[0]
        cdef int* write_queue = self.queue[1]
        cdef CPP_Gate* self_info
        cdef CPP_Gate* target_info
        cdef uint16_t *book
        cdef CPP_Gate* gate_infolist = self.gate_infolist.data()
        read_queue[0] = origin
        if unlikely(gate_infolist[origin].output == ERROR):
            self.burn(index, end_point, read_queue, write_queue)
            return

        while end_point > 0:
            if unlikely(counter > self.counter):
                self.eval_count += eval
                self.burn(index, end_point, read_queue, write_queue)
                return

            counter += 1
            for index in range(end_point):
                self_info = &gate_infolist[read_queue[index]]
                self_info.scheduled = False
                new_output = self_info.output
                profile = self_info.hitlist.data()
                end = profile + self_info.hitlist.size()
                while profile != end:
                    eval += 1
                    profile_output = profile.output
                    if profile_output != new_output:
                        target_info = &gate_infolist[profile.target]
                        gate_type = target_info.type
                        limit = target_info.inputlimit
                        if gate_type >= NOT_ID:
                            if new_output >= ERROR:
                                target_output = new_output
                            else:
                                target_output = new_output ^ (gate_type == NOT_ID)
                        else:
                            book = target_info.book
                            book[profile_output] -= 1
                            book[new_output] += 1
                            high = book[HIGH]
                            low  = book[LOW]
                            realsource = high + low
                            if likely(realsource == limit) or unlikely(realsource and realsource + book[UNKNOWN] + book[ERROR] == limit):
                                if gate_type < OR_ID:    target_output = (low == 0) ^ (gate_type & 1)
                                elif gate_type < XOR_ID: target_output = (high > 0) ^ (gate_type & 1)
                                else:                    target_output = (high & 1) ^ (gate_type & 1)
                            else:
                                target_output = UNKNOWN
                        if target_output != target_info.output:
                            target_info.output = target_output
                            if not target_info.scheduled:
                                target_info.scheduled = True
                                write_queue[size] = profile.target
                                size += 1

                        profile.output = new_output
                    profile += 1
            end_point, size = size, 0
            read_queue, write_queue = write_queue, read_queue
        self.eval_count += eval
