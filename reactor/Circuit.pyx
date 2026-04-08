# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
# cython: nonecheck=False
import orjson
import asyncio
from libcpp.deque cimport deque
from Gates cimport Gate, Variable, Profile, Task, vector, CPP_Gate
from Const cimport *
from IC cimport IC
from Store cimport get, decode
from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM
from libc.stdint cimport uint16_t,int8_t
from libcpp.unordered_map cimport unordered_map
from libcpp.vector cimport vector
import time
cdef class Circuit:
    def __cinit__(self):
        self.hidden = 0 # the oscillation breaking system
        self.eval_count = 0 # just a metric for evaluating speed
        self.gate_infolist.reserve(500_000)# the cpp_gate list consisting of every single gate's info in c++
        self.gate_verse = [] # the gate list in python
        self.runner = None        # asyncio.Task for FLIPFLOP drain loop
        self.Global_Clock = 0
        cdef unsigned int delay_init[12]
        delay_init[:] = [2, 0, 3, 1, 4, 5, 0, 0, 0, 0, 0, 0]
        for i in range(12):
            self.Global_delay[i] = delay_init[i]
        # time_queue is a C++ deque[int] — default-constructed, no explicit init needed
    def __init__(self):
        # lookup table for objects by code
        set_MODE(DESIGN)
        self.objlist = [
            [] for i in range(TOTAL)] # list of visible gates and ics, stored according to it's type
        self.copydata = []

    def __repr__(self):
        return 'Circuit'
    def __dealloc__(self):
        pass  # asyncio task is cancelled automatically when the event loop closes
    @property
    def infolist_size(self):
        return self.gate_infolist.size()

    cpdef object getcomponent(self, int choice):
        '''Get object from store, put it in objlist and update its code and codename'''
        gt = get(choice, self.gate_infolist, self.gate_verse) 
        if gt:
            rank = len(self.objlist[choice])
            self.objlist[choice].append(gt)
            gt.code = (choice, rank)
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
        '''Delete object from objlist and mutate info id for removal'''
        cdef CPP_Gate* gate_info=self.gate_infolist.data()
        cdef Gate gate
        cdef IC ic
        if obj.id == IC_ID:
            ic = <IC>obj
            for gate in ic.outputs+ic.inputs+ic.internal:
                gate_info[gate.location].type = -gate_info[gate.location].type -1
                self.hidden+=1
        else:
            gate = <Gate>obj
            gate_info[gate.location].type = -gate_info[gate.location].type -1 
            self.hidden += 1
        self.objlist[obj.code[0]][obj.code[1]] = None

    cpdef void renewobj(self, object obj):
        '''Renew object in objlist and revert info id'''
        cdef CPP_Gate* gate_info=self.gate_infolist.data()
        cdef Gate gate
        cdef IC ic
        if obj.id == IC_ID:
            ic = <IC>obj
            
            for gate in ic.outputs+ic.inputs+ic.internal:
                gate_info[gate.location].type = -gate_info[gate.location].type -1
                self.hidden-=1
        else:
            gate = <Gate>obj
            gate_info[gate.location].type = -gate_info[gate.location].type -1 
            self.hidden -= 1
        self.objlist[obj.code[0]][obj.code[1]] = obj


    cpdef list get_components(self):
        '''Get all components in the circuit'''
        return [gate for sublist in self.objlist for gate in sublist if gate is not None]

    cpdef list get_variables(self):
        '''Get all variables in the circuit'''
        return [gate for gate in self.objlist[VARIABLE_ID] if gate is not None]

    cpdef list get_ics(self):
        '''Get all ICs in the circuit'''
        return [gate for gate in self.objlist[IC_ID] if gate is not None]

    cpdef void listComponent(self):
        '''List all components in the circuit'''
        cdef int i = 0
        for i, gate in enumerate(self.get_components()):
            print(f'{i}. {gate}')

    cpdef void listVar(self):
        '''List all variables in the circuit'''
        cdef int i = 0
        for i, gate in enumerate(self.get_variables()):
            print(f'{i}. {gate}')

    cpdef bint setlimits(self, Gate gate, int size):
        '''Set the input-size of a gate'''
        cdef CPP_Gate* info = &self.gate_infolist[gate.location]
        cdef int prev = info.output
        if gate.setlimits(size):
            if prev != info.output:
                self.propagate(gate.location)
            return True
        return False

    cpdef void connect(self, Gate target, int source, int index):
        '''Connect a gate to another gate'''
        cdef CPP_Gate* info = &self.gate_infolist[target.location]
        cdef int prev = info.output
        target.connect(source, index)
        if prev != info.output:
            self.propagate(target.location)

    cpdef void toggle(self, int target, int value):
        '''toggles a variable's value'''
        cdef CPP_Gate* info = &self.gate_infolist[target]
        if value != info.output:
            info.value = value
            info.output = value if MODE != DESIGN else UNKNOWN
            self.propagate(target)

    cpdef void disconnect(self, Gate target, int index):
        '''Disconnect a gate from another gate'''
        cdef CPP_Gate* info = &self.gate_infolist[target.location]
        cdef int prev = info.output
        target.disconnect(index)
        if prev != info.output:
            self.propagate(target.location)

    cpdef void hide(self, list gatelist):
        '''Hide a list of gates'''
        cdef Gate pin
        cdef IC ic
        for gate in gatelist:
            if gate.id == IC_ID:
                ic = <IC>gate
                ic.hide()
            else:
                pin = <Gate>gate
                pin.hide()
            '''make the gates invisible/ready for removal'''
            self.delobj(gate)

        for gate in gatelist:
            '''Turn off the outputs of the gates/ propagates unknown values'''
            if gate.id == IC_ID:
                ic = <IC>gate
                for pin in ic.outputs:
                    self.propagate(pin.location)
            else:
                self.propagate((<Gate>gate).location)

    cpdef void reveal(self, list gatelist):
        '''Reveal a list of gates'''
        cdef Gate pin
        cdef IC ic
        for gate in reversed(gatelist):
            '''Renew the gates first. reverse order is cruical for proper retrieval'''
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
        '''Output the value of a gate'''
        print(f'{gate} output is {gate.getoutput()}')
        
    cdef bytearray table(self,vector[int] &var,vector[int] &gate):
        '''Generate a truth table for the circuit'''
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        cdef int var_size=var.size()
        cdef int gate_size=gate.size()
        cdef int row=1<<var_size,col=var_size+gate_size
        cdef bytearray matrix=bytearray(row*col)
        cdef unsigned char[:] view=matrix # just store pointer to matrix
        cdef int i,j,k,bit
        cdef int gray = 0
        cdef int prev_gray = 0
        cdef int mask, changed_bit, offset

        for i in range(row):
            '''use gray-code as gray-codes ensure only one change of variable per row'''
            prev_gray = gray
            gray = i ^ (i >> 1)

            if i != 0:
                '''find the changed bit'''
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
        # repr() = plain name (no ANSI) for col_width math and file-safe output.
        # str() = colored name, used only for the printed header cells.
        var_reprs  = [repr(v) for v in variables]
        gate_reprs = [repr(v) for v in gate_list]
        all_reprs  = var_reprs + gate_reprs
        cdef vector[int] var_vector
        cdef vector[int] gate_vector
        for gate in variables:
            var_vector.push_back((<Gate>gate).location)
        for gate in gate_list:
            gate_vector.push_back((<Gate>gate).location)
        cdef bytearray raw_rows = self.table(var_vector, gate_vector)
        if len(all_reprs) > 0:
            col_width = max([len(name) for name in all_reprs]) + 2
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
            "X".center(col_width)
        ]

        # Header: colored names padded based on plain-name length.
        var_colored  = [str(v) for v in variables]
        gate_colored = [str(v) for v in gate_list]
        all_colored  = var_colored + gate_colored
        header_parts = [
            colored.center(col_width + len(colored) - len(plain))
            for colored, plain in zip(all_colored, all_reprs)
        ]
        header    = " | ".join(header_parts)
        separator = "─" * (col_width * len(all_reprs) + 3 * (len(all_reprs) - 1))
        self.visual_queue_clear()
        cdef int mode=MODE
        self.reset()
        self.simulate(mode)

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
        '''Diagnose the circuit'''
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
                ("Book[L,H,U]", 15),
                ("Targets", 25),
                ("Out", 6)
            ]
            total_width = sum(w for _, w in columns)
            fmt = "".join(f"{{:<{w}}}" for _, w in columns)

            print("\n" + fmt.format(*[n for n, _ in columns]))
            print("-" * total_width)

            for comp in gates:
                info = &self.gate_infolist[comp.location]
                # repr() for source/target names keeps column widths intact.
                if isinstance(comp._sources, list):
                    ch = [f"[{i}]:{repr(<Gate>PyList_GET_ITEM(self.gate_verse, c))}" for i, c in enumerate(comp._sources) if c != -1]
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = f"val:{comp._sources}"

                book = f"[{info.book[0]},{info.book[1]},{info.book[2]}]"

                # Targets from info.hitlist — repr() only, no colors in auxiliary columns.
                tgt = []
                profile = info.hitlist.data()
                end = profile + info.hitlist.size()
                while profile < end:
                    tgt.append(repr(<Gate>PyList_GET_ITEM(self.gate_verse, profile.target)))
                    profile += 1
                tgt_str = ", ".join(tgt) if tgt else "None"

                ch_str  = ch_str[:26]  + ".." if len(ch_str)  > 28 else ch_str
                tgt_str = tgt_str[:23] + ".." if len(tgt_str) > 25 else tgt_str

                # Color only the component name; widen its column by the ANSI byte overhead.
                name_plain   = repr(comp)
                name_colored = str(comp)
                extra = len(name_colored) - len(name_plain)
                comp_col_w = columns[0][1] + extra
                row_fmt = f"{{:<{comp_col_w}}}" + "".join(f"{{:<{w}}}" for _, w in columns[1:])
                print(row_fmt.format(name_colored, ch_str, book, tgt_str, comp.getoutput()))

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
                        ch = [repr(<Gate>PyList_GET_ITEM(self.gate_verse, c)) for c in pin._sources if c != -1] if isinstance(pin._sources, list) else [f"val:{pin._sources}"]
                        print(f"    {str(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}")

                if ic.outputs:
                    print("  OUTPUT PINS:")
                    for pin in ic.outputs:
                        ch = [repr(<Gate>PyList_GET_ITEM(self.gate_verse, c)) for c in pin._sources if c != -1] if isinstance(pin._sources, list) else [f"val:{pin._sources}"]
                        print(f"    {str(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}")

        print("\n" + "=" * 90)

    cpdef void writetojson(self, str location):
        '''Write the circuit's entire info to a json file'''
        cdef list circuit = []
        cdef object gate
        for gate in self.get_components():
            circuit.append(gate.full_data())
        with open(location, 'wb') as file:
            file.write(orjson.dumps(circuit))

    cpdef void refresh(self):
        '''purge unused gates from end of the gate list'''
        self.optimize() # puts hidden gates to the end
        cdef int n=self.gate_infolist.size()
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        while n>0 and gate_infolist[n-1].type<0:
            self.gate_verse.pop()
            self.gate_infolist.pop_back()
            n-=1

    cpdef void optimize(self):
        '''Optimize the circuit using topological sort so prefetcher never has to look back. 
        Also pushes back hidden gates with mutated info type'''
        self.copydata.clear()
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
                    '''count of how many gates point to the target gate'''
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
                    '''if the target's dependencies are already in to the list push it to the list now'''
                    if in_degree[profile.target]>0:
                        in_degree[profile.target]-=1
                        if in_degree[profile.target]==0:
                            queue[j]=profile.target
                            j+=1
                    profile+=1
                i+=1
            if j<active_gates:
                '''if there are still gates with in_degree>0, it means there are cycles, they will now be resolved one by one'''
                for index in range(n):
                    if in_degree[index]>0:
                        queue[j]=index
                        in_degree[index]=0
                        j+=1
                        while i<j:
                            '''resolving one gate can resolve other gates in the chain'''
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
                    '''update the target location'''
                    profile.target=hash_map[profile.target]
                    profile+=1
            self.gate_infolist.swap(new_gate_infolist)
        cdef list new_gate_verse = []
        cdef list sources
        for i in range(n):
            gate=<Gate>PyList_GET_ITEM(self.gate_verse, queue[i])
            gate.location=i
            sources = gate._sources
            for index in range(len(sources)):
                if sources[index] != -1:
                    '''update the source location'''
                    sources[index] = hash_map[sources[index]]
            new_gate_verse.append(gate)
        self.gate_verse[:] = new_gate_verse

    cpdef void generate(self, list circuit):
        '''generate the circuit from the list of info'''
        cdef unordered_map[int,int] pseudo # store the location of each gate in the gate_verse vs. their location in the json/list of info
        pseudo.reserve(PyList_GET_SIZE(circuit))
        pseudo[-1] = -1
        cdef list varlist=[]
        cdef object obj
        cdef Gate gate
        cdef IC ic
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        cdef list info
        cdef list ic_list=[]
        '''first pass: load all the gates to pseudo and set up the ic_list'''
        for info in circuit:  # load to pseudo
            if info[ID] == IC_ID:
                ic = <IC>self.getcomponent(info[ID])
                ic.custom_name = info[CUSTOM_NAME]
                ic.map = info[MAP]
                ic.load_components(info, pseudo)
                ic_list.append(ic) # a seperate list of ics to be resolved and implemented later
            else:
                gate = <Gate>self.getcomponent(info[ID])
                if gate.id == VARIABLE_ID:
                    gate_infolist[gate.location].output = UNKNOWN
                    varlist.append(gate.location)
                pseudo[info[LOCATION]] = gate.location
        '''second pass: connect all the gates'''
        for info in circuit:  # connect components
            if info[ID] != IC_ID:
                gate = <Gate>PyList_GET_ITEM(self.gate_verse, pseudo[info[LOCATION]])
                gate.clone(info, pseudo)
        '''third pass: implement all the ics'''
        for ic in ic_list:
            ic.implement(pseudo)
        if MODE != DESIGN:
            self.custom_simulate(varlist)

    cpdef void readfromjson(self, str location):
        '''read the circuit from a json file'''
        cdef list circuit
        with open(location, 'rb') as file:
            circuit = orjson.loads(file.read())
        if len(circuit) == DESCRIPTION and isinstance(circuit[DESCRIPTION],str):
            return
        self.generate(circuit)

    cpdef IC build_ic(self):
        '''build an ic from the current circuit'''
        cdef Gate gate, target
        cdef Profile* profile
        cdef Profile* end
        cdef CPP_Gate* info
        cdef IC my_ic = self.getcomponent(IC_ID)
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        cdef list queue = []
        # distribute input and output pins
        cdef list outputs = [i for i in self.objlist[OUTPUT_PIN_ID] if i is not None]
        cdef list inputs = [i for i in self.objlist[INPUT_PIN_ID] if i is not None]
        for gate in outputs + inputs:
            gate_infolist[gate.location].mark = True
            queue.append(gate)
        cdef Py_ssize_t size = len(queue)
        cdef Py_ssize_t index = len(outputs)
        cdef list gate_verse = self.gate_verse
        while index < size:
            gate = queue[index]
            info = &gate_infolist[gate.location]
            profile = info.hitlist.data()
            end = profile + info.hitlist.size()
            '''if the gate is an input pin with a source or an output pin with a hitlist, connect it to the next gates. these are 
            pins of internal ics that will be removed, so no more nested ics'''
            if (info.type == INPUT_PIN_ID and gate._sources[0] != -1) or (info.type == OUTPUT_PIN_ID and not info.hitlist.empty()):
                while profile != end:
                    target = <Gate>PyList_GET_ITEM(gate_verse, profile.target)
                    target._sources[profile.index] = gate._sources[0]
                    if not gate_infolist[target.location].mark:
                        gate_infolist[target.location].mark = True
                        queue.append(target)
                        size += 1
                    profile += 1
            else:
                while profile != end:
                    target = <Gate>PyList_GET_ITEM(gate_verse, profile.target)
                    if not gate_infolist[target.location].mark:
                        gate_infolist[target.location].mark = True
                        queue.append(target)
                        size += 1
                    profile += 1
            index += 1
        # load pins to ic
        cdef int pins = len(inputs) + len(outputs)
        for input_pin in inputs:
            my_ic.addgate(input_pin)
        for output_pin in outputs:
            my_ic.addgate(output_pin)
        # load internal gates to ic
        for index in range(pins, size):
            gate = queue[index]
            if gate.id >= INPUT_PIN_ID:
                continue
            my_ic.addgate(gate)
        return my_ic

    cpdef void ic_pin_change(self):
        # convert variables to inputpin and probes to outputpin
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
        '''check for transferability'''
        if not real_source or (length == 1 and id != VARIABLE_ID) or (length > 1 and id < VARIABLE_ID):
            if gate._sources[0] == -1:
                self.objlist[gate.code[0]][gate.code[1]] = None # remove from old list
                gate.id = id # set new id
                gate.code = (id, len(self.objlist[id])) # update code
                self.objlist[id].append(gate) # add to new list
                # Update CPP_Gate type as well
                info = &self.gate_infolist[gate.location] # update cpp_gate
                info.type = id
                gate.process() # process the gate
                self.propagate(gate.location) # propagate the changes

    cpdef void reorder(self, object gate, int index):
        # shift the position of same types of gates in objlist
        # basically a code and position change
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

    cpdef void save_as_ic(self, str location, str ic_name, str tag, str description):
        '''save the circuit as an ic
        if components is not empty, it means the user wants to convert selected items to ic
        '''
        cdef Circuit crct
        cdef CPP_Gate* info
        cdef IC my_ic
        cdef Gate gate
        # if components:
        #     '''sandboxing for converting selected items to ic
        #     create a circuit
        #     load everything 
        #     and convert to ic
        #     '''
        #     crct = Circuit()
        #     crct.copy(components)
        #     crct.paste()
        #     crct.save_as_ic(location, ic_name, tag, description, None)
        #     return
        if len(self.objlist[VARIABLE_ID]) or len(self.objlist[PROBE_ID]):
            self.ic_pin_change()
        for gate in self.objlist[INPUT_PIN_ID]:
            if gate and gate._sources[0] != -1:
                raise ValueError('Input Pin has extra sources')
        for gate in self.objlist[OUTPUT_PIN_ID]:
            if gate:
                info = &self.gate_infolist[gate.location]
                if info.hitlist.size() > 0:
                    raise ValueError('Output Pin has extra targets')
        '''build ic and save'''
        my_ic = self.build_ic()
        my_ic.custom_name = ic_name
        my_ic.tag = tag
        my_ic.description = description
        with open(location, 'wb') as file:
            file.write(orjson.dumps(my_ic.full_data()))
        '''ic building process corrupts gates so i need to clear and rebuild'''
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
        '''load ic to circuit'''
        cdef IC myIC = self.getcomponent(IC_ID)
        myIC.configure(crct)
        return myIC

    cpdef IC getIC(self, location):
        '''get ic from file and load it'''
        cdef list crct = self.get_ic(location)
        if crct is None:
            return None
        return self.load_ic(crct)

    cpdef void rank_reset(self):
        '''reset rank of all gates'''
        for i in range(TOTAL):
            while self.objlist[i] and self.objlist[i][len(self.objlist[i]) - 1] is None:
                self.objlist[i].pop()

    cpdef void clearcircuit(self):
        '''clear circuit/ purge every item of circuit'''
        self.gate_infolist.clear()
        self.gate_verse.clear()
        for i in range(TOTAL):
            self.objlist[i].clear()
        self.hidden = 0

    cpdef void copy(self, list components):
        '''copy components to self.copydata'''
        cdef object item
        cdef list cluster
        cdef int i
        if len(components) == 0:
            return
        self.copydata = []
        cluster = []
        # mark all gates in cluster as scheduled
        for item in components:
            item.load_to_cluster(cluster)
        # copy all components
        for item in components:
            if item.id != IC_ID:
                self.copydata.append(<Gate>item.partial_data())
            else:
                self.copydata.append(<IC>item.partial_data())
        # unmark all gates in cluster as scheduled
        for i in cluster:
            self.gate_infolist[i].mark = False

    cpdef list paste(self):
        '''paste components from copydata to circuit.
        same as the generation but has to pass a list of gates'''
        cdef list circuit
        cdef unordered_map[int,int] pseudo
        cdef list new_items=[]
        cdef list varlist=[]
        cdef tuple code
        cdef Gate g
        circuit = self.copydata
        pseudo.reserve(PyList_GET_SIZE(circuit))
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
                    varlist.append(gate.location)
                pseudo[info[LOCATION]] = gate.location
                new_items.append(gate)

        for gate_info in circuit:  # connect components
            if gate_info[ID] != IC_ID:
                gate = <Gate>PyList_GET_ITEM(self.gate_verse, pseudo[gate_info[LOCATION]])
                gate.clone(gate_info, pseudo)
        for ic in ic_list:
            ic.implement(pseudo)

        if MODE != DESIGN:
            self.custom_simulate(varlist)
        return new_items

    cpdef void simulate(self, int Mod):
        '''simulate the circuit'''
        cdef Gate variable
        cdef CPP_Gate* info
        set_MODE(Mod)
        if self.runner is not None and not self.runner.done():
            self.runner.cancel()
        self.runner=None
        for variable in self.objlist[VARIABLE_ID]:
            if variable is not None:
                # set output of variable to its value
                # run the propagation from variable
                info = &self.gate_infolist[variable.location]
                info.output = info.value
                self.propagate(variable.location)

    cpdef void custom_simulate(self, list varlist):
        '''simulate the circuit'''
        cdef CPP_Gate* info
        for variable in varlist:
            # set output of variable to its value
            # run the propagation from variable
            info = &self.gate_infolist[variable]
            info.output = info.value
            self.propagate(variable)

    cpdef void reset(self):
        '''reset the circuit's items to unknown value'''
        cdef Gate g
        set_MODE(DESIGN)
        self.eval_count=0
        cdef priority_queue[Task, vector[Task], greater[Task]] empty_pq
        self.time_queue.swap(empty_pq)
        if self.runner is not None and not self.runner.done():
            self.runner.cancel()
        for i in self.get_components():
            if i.id != IC_ID:
                g = <Gate>i
                g.reset()
            else:
                (<IC>i).reset()

    cdef void update_gate(self, Task task) nogil:
        '''Process one task called from the async drain loop on the main thread.'''
        if task.time > self.Global_Clock:
            self.Global_Clock = task.time
            
        cdef int origin = task.gate_loc
        cdef Profile* profile
        cdef Profile* end
        cdef Py_ssize_t realsource, high, low, limit, gate_type
        cdef Py_ssize_t new_output, profile_output, target_output
        cdef CPP_Gate* self_info
        cdef CPP_Gate* target_info
        cdef uint16_t* book
        cdef CPP_Gate* gate_infolist = self.gate_infolist.data()
        self_info = &gate_infolist[origin]
        if not self_info.update:
            self.visual_queue.push_back(origin) 
            self_info.update = True
        self_info.scheduled = False
        new_output = self_info.output
        profile = self_info.hitlist.data()
        end = profile + self_info.hitlist.size()
        while profile != end:
            self.eval_count += 1
            profile_output = profile.output
            if profile_output != new_output:
                target_info = &gate_infolist[profile.target]
                gate_type = target_info.type
                limit = target_info.inputlimit
                if gate_type >= NOT_ID:
                    if new_output != UNKNOWN:
                        target_output = new_output ^ (gate_type == NOT_ID)
                    else:
                        target_output = UNKNOWN
                else:
                    # update target
                    book = target_info.book
                    book[profile_output] -= 1
                    book[new_output] += 1
                    
                    if new_output != UNKNOWN:
                        high = book[HIGH]
                        low  = book[LOW]
                        realsource = high + low
                        if likely(realsource == limit) or unlikely(realsource and realsource + book[UNKNOWN] == limit):
                            if gate_type < OR_ID:    target_output = (low == 0) ^ (gate_type & 1)
                            elif gate_type < XOR_ID: target_output = (high > 0) ^ (gate_type & 1)
                            else:                    target_output = (high & 1) ^ (gate_type & 1)
                        else:
                            target_output = UNKNOWN
                    else:
                        target_output = UNKNOWN
                if target_output != target_info.output:
                    target_info.output = target_output
                    if not target_info.update:
                        self.visual_queue.push_back(profile.target)   # target changed — mark dirty
                        target_info.update = True
                    if not target_info.scheduled:
                        target_info.scheduled = True
                        self.time_queue.push(Task(profile.target, self.Global_Clock + self.Global_delay[target_info.type] + limit, profile.target))
                profile.output = new_output
            profile += 1

        if self_info.inputlimit == 0:
            self_info.value ^= 1
            self_info.output = self_info.value
            self.time_queue.push(Task(origin, self.Global_Clock + self_info.book[self_info.output], origin))
            self_info.scheduled = True
    cdef void propagate(self, int origin) nogil:
        '''propagate the output of a gate to its targets'''
        cdef Profile* profile
        cdef Profile* end
        cdef int gate_loc
        cdef Py_ssize_t realsource, high, low,limit,gate_type
        cdef Py_ssize_t new_output, profile_output, target_output
        cdef Py_ssize_t index = 0, end_point = 1, size = 0
        cdef Py_ssize_t eval = 0
        cdef int* read_queue = self.queue[0]
        cdef int* write_queue = self.queue[1]
        cdef CPP_Gate* self_info
        cdef CPP_Gate* target_info
        cdef uint16_t *book
        cdef CPP_Gate* gate_infolist = self.gate_infolist.data()
        self_info = &gate_infolist[origin]

        if MODE == FLIPFLOP:
            if not self_info.scheduled:
                if self_info.inputlimit == 0:
                    self.time_queue.push(Task(origin, self.Global_Clock + self_info.book[PRIMARY], origin))
                else:
                    self.time_queue.push(Task(origin, self.Global_Clock + self.Global_delay[self_info.type] + self_info.inputlimit, origin))
                self_info.scheduled = True
            else:
                if self_info.inputlimit == 0:
                    self_info.scheduled = False  # Allows resetting of clock
            with gil:
                if self.runner is None or self.runner.done():
                    self.runner = asyncio.create_task(self.oscillate())
            return
            
        read_queue[0] = origin
        if not self_info.update:
            self_info.update = True
            self.visual_queue.push_back(origin)
            
        cdef Py_ssize_t wave_limit=self.gate_infolist.size()-self.hidden
        while end_point > 0:
            if unlikely(wave_limit<0):
                self.eval_count += eval
                for i in range(end_point):
                    self_info = &gate_infolist[read_queue[i]]
                    self_info.mark=False
                    self_info.scheduled=True
                    self.time_queue.push(Task(read_queue[i], self.Global_Clock, read_queue[i]))
                with gil:
                    if self.runner is None or self.runner.done():
                        self.runner=asyncio.create_task(self.oscillate())
                    return
            wave_limit -= 1
            for index in range(end_point):
                self_info = &gate_infolist[read_queue[index]]
                self_info.mark = False
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
                            if new_output != UNKNOWN:
                                target_output = new_output ^ (gate_type == NOT_ID)
                            else:
                                target_output = UNKNOWN
                        else:
                            # update target
                            book = target_info.book
                            book[profile_output] -= 1
                            book[new_output] += 1
                           
                            if new_output != UNKNOWN:
                                high = book[HIGH]
                                low  = book[LOW]
                                realsource = high + low
                                if likely(realsource == limit) or unlikely(realsource and realsource + book[UNKNOWN] == limit):
                                    if gate_type < OR_ID:    target_output = (low == 0) ^ (gate_type & 1)
                                    elif gate_type < XOR_ID: target_output = (high > 0) ^ (gate_type & 1)
                                    else:                    target_output = (high & 1) ^ (gate_type & 1)
                                else:
                                    target_output = UNKNOWN
                            else:
                                target_output = UNKNOWN
                        if target_output != target_info.output:
                            target_info.output = target_output
                            if not target_info.update:
                                self.visual_queue.push_back(profile.target)   # target changed — mark dirty
                                target_info.update = True
                            if not target_info.mark:
                                target_info.mark = True
                                write_queue[size] = profile.target
                                size += 1
                        profile.output = new_output
                    profile += 1
            # size is actually the growing size of write_queue
            end_point, size = size, 0
            # buffer switching, read->write and write->read
            read_queue, write_queue = write_queue, read_queue
        self.eval_count += eval

    async def oscillate(self):
        cdef int size
        cdef Task task
        
        while not self.time_queue.empty():
            with nogil:
                size = self.time_queue.size()
                while size:
                    size -= 1
                    task = self.time_queue.top()
                    self.time_queue.pop()
                    self.update_gate(task)
            await asyncio.sleep(0.075)

    # ── Visual-queue helpers (called from the UI layer) ──────────────────
    cpdef bint visual_queue_empty(self):
        '''Return True when there are no pending dirty gate locations.'''
        return self.visual_queue.empty()

    cpdef void visual_queue_clear(self):
        '''Return True when there are no pending dirty gate locations.'''

        cdef int loc 
        while not self.visual_queue.empty():
            loc = self.visual_queue.front()
            self.gate_infolist[loc].update = False
            self.visual_queue.pop_front()


    cpdef int pop_visual_queue(self):
        '''Pop and return the next dirty gate location.'''
        cdef int loc = self.visual_queue.front()
        self.gate_infolist[loc].update = False
        self.visual_queue.pop_front()
        return loc

    cpdef int visual_queue_size(self):
        '''Return the number of pending dirty gate locations.'''
        return self.visual_queue.size()
