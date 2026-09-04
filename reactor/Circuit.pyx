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
from libc.stdint cimport uint8_t,int8_t
from libcpp.unordered_map cimport unordered_map
from libcpp.vector cimport vector
from libcpp.deque cimport deque
from libcpp.algorithm cimport sort  
import time

try:
    from editor.tools.timing_tracer import tracer as _tracer
except ImportError:
    import sys as _sys, os as _os
    _sys.path.insert(0, _os.path.join(_os.getcwd(), "editor", "tools"))
    from timing_tracer import tracer as _tracer  # type: ignore

cdef class Circuit:
    def __cinit__(self):
        self.hidden = 0 # the oscillation breaking system
        self.eval_count = 0 # just a metric for evaluating speed
        self.gate_infolist.reserve(500_000)# the cpp_gate list consisting of every single gate's info in c++
        self.gate_verse = [] # the gate list in python
        self.runner = None        # asyncio.Task for FLIPFLOP drain loop
        self.Global_Clock = 0
        cdef unsigned int g_delay[12]
        cdef unsigned int fi_delay[12]
        cdef unsigned int fo_delay[12]
        
        g_delay[:] =  [1, 0, 1, 0, 0, 1, 0, 1, 0, 0, 0, 0]
        fi_delay[:] = [1, 1, 1, 1, 2, 2, 0, 0, 0, 0, 0, 0]
        fo_delay[:] = [1, 1, 1, 1, 1, 1, 0, 1, 0, 0, 0, 0]
        
        for i in range(12):
            self.Global_delay[i] = g_delay[i]
            self.FanIn_delay[i] = fi_delay[i]
            self.FanOut_delay[i] = fo_delay[i]
        # time_queue is a C++ deque[int] — default-constructed, no explicit init needed
    def __init__(self):
        # lookup table for objects by code
        set_MODE(DESIGN)
        self.recording = False
        self.clocks_enabled = False
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
    def set_mode(self, int mode):
        set_MODE(mode)
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
                gate.id = -gate.id - 1
        else:
            gate = <Gate>obj
            gate_info[gate.location].type = -gate_info[gate.location].type -1 
            self.hidden += 1
            gate.id = -gate.id - 1
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
                gate.id = -gate.id - 1
                self.hidden-=1
        else:
            gate = <Gate>obj
            gate_info[gate.location].type = -gate_info[gate.location].type -1 
            gate.id = -gate.id - 1
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
        self.visual_queue.push_back(source)
        target.connect(source, index)
        if prev != info.output:
            self.propagate(target.location)

    cpdef void toggle(self, int target, int value):
        '''Toggle a variable's value and output, then propagate'''
        cdef CPP_Gate* info = &self.gate_infolist[target]
        if info.flags & FLAG_SCHEDULED:
            return
        if value != info.output:
            info.flags |= FLAG_MARK
            info.flags = (info.flags&~FLAG_VALUE)|value
            info.output = value if MODE != DESIGN else UNKNOWN
            if MODE!=COMPILE:
                self.propagate(target)
            else:
                self.sweep(target)

    cpdef void enable_all_clocks(self, bint enable=True):
        self.clocks_enabled = enable
        cdef CPP_Gate* gate_info
        cdef Gate gate
        if enable:
            for gate in self.objlist[VARIABLE_ID]:
                if gate is not None:
                    gate_info = &self.gate_infolist[gate.location]
                    if gate_info.inputlimit == 0 and not (gate_info.flags & FLAG_SCHEDULED):
                        gate_info.flags |= FLAG_SCHEDULED
                        self.time_queue.push(Task(gate.location, self.Global_Clock + gate.delay_book[PRIMARY], gate.location))
            if self.runner is None or self.runner.done():
                self.runner = asyncio.create_task(self.task_manager())
        else:
            for gate in self.objlist[VARIABLE_ID]:
                if gate is not None:
                    gate_info = &self.gate_infolist[gate.location]
                    if gate_info.inputlimit == 0:
                        gate_info.flags &= ~FLAG_SCHEDULED

    cpdef double batch_toggle(self, list batch, int batch_size=0):
        '''toggles multiple variables and sweeps exactly once for performance'''
        cdef int target, value
        cdef tuple pair
        cdef CPP_Gate* info
        cdef int origin = self.gate_infolist.size()
        cdef vector[int] targets
        cdef vector[uint8_t] values
        cdef int i, j, n
        cdef double start, end
        
        n = len(batch)
        if batch_size <= 0:
            batch_size = n
            
        targets.reserve(n)
        values.reserve(n)
        for pair in batch:
            targets.push_back(pair[0])
            values.push_back(pair[1])
            
        start = time.perf_counter_ns()
        
        if MODE != COMPILE:
            for i in range(0, n):
                target = targets[i]
                value = values[i]
                info = &self.gate_infolist[target]
                if value != info.output:
                    info.flags = (info.flags & ~FLAG_VALUE) | value
                    info.output = value if MODE != DESIGN else UNKNOWN
                    self.propagate(target)
        else:
            for i in range(0, n, batch_size):
                origin = self.gate_infolist.size()
                for j in range(batch_size):
                    if i + j >= n:
                        break
                    target = targets[i+j]
                    value = values[i+j]
                    info = &self.gate_infolist[target]
                    if value != info.output:
                        info.flags|=FLAG_MARK
                        info.flags = (info.flags & ~FLAG_VALUE) | value
                        info.output = value if MODE != DESIGN else UNKNOWN
                        if origin > target:
                            origin = target
                self.sweep(origin)
                
        end = time.perf_counter_ns()
        return (end - start) / 1000000.0

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
                    if self.gate_infolist[pin.location].output != UNKNOWN:
                        self.propagate(pin.location)
            else:
                if self.gate_infolist[(<Gate>gate).location].output != UNKNOWN:
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
        
    cpdef str truthTable(self, list variables=None, list outputs=None):
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
        
        if outputs is None:
            # Filter gatelist
            for item in self.objlist[OUTPUT_PIN_ID]:
                if item is not None:
                    gate_list.append(item)
        else:
            gate_list = outputs


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

    def diagnose(self) -> str:
        '''Diagnose the circuit'''
        cdef Gate comp
        cdef CPP_Gate* info
        cdef Profile* profile
        cdef Profile* end
        cdef list ics
        cdef list out = []
        out.append("=" * 90)
        out.append(" " * 35 + "CIRCUIT DIAGNOSIS")
        out.append("=" * 90)

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

            out.append("\n" + fmt.format(*[n for n, _ in columns]))
            out.append("-" * total_width)

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
                out.append(row_fmt.format(name_colored, ch_str, book, tgt_str, comp.getoutput()))

            out.append("-" * total_width)

        ics = [c for c in self.objlist[IC_ID] if c is not None]
        if ics:
            out.append("\n" + "=" * 90)
            out.append(" " * 40 + "IC STATUS")
            out.append("=" * 90)
            for ic in ics:
                out.append(f"\n  IC: {repr(ic)} (Code: {ic.code})")
                out.append("  " + "-" * 50)

                if ic.inputs:
                    out.append("  INPUT PINS:")
                    for pin in ic.inputs:
                        ch = [repr(<Gate>PyList_GET_ITEM(self.gate_verse, c)) for c in pin._sources if c != -1] if isinstance(pin._sources, list) else [f"val:{pin._sources}"]
                        out.append(f"    {str(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}")

                if ic.outputs:
                    out.append("  OUTPUT PINS:")
                    for pin in ic.outputs:
                        ch = [repr(<Gate>PyList_GET_ITEM(self.gate_verse, c)) for c in pin._sources if c != -1] if isinstance(pin._sources, list) else [f"val:{pin._sources}"]
                        out.append(f"    {str(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}")

        out.append("\n" + "=" * 90)
        cdef str result = "\n".join(out)
        print(result)
        return result

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

    # cpdef void optimize(self):

    #     if self.gate_infolist.empty():
    #         return
            
    #     self.copydata.clear()
    #     cdef int i=0, pos=0, n, source
    #     cdef vector[int] hash_map, source_ptr, hidden, visited, stack, serial
    #     cdef Profile* profile
    #     cdef Profile* end
    #     cdef CPP_Gate* info
    #     cdef vector[CPP_Gate] new_gate_infolist
    #     cdef CPP_Gate* gate_infolist = self.gate_infolist.data()
    #     cdef Gate gate
        
    #     n = self.gate_infolist.size()
    #     visited.resize(n, 0)
    #     hash_map.resize(n, 0)
    #     source_ptr.resize(n, 0) # tally the source to find the next source as a replacement of recursion 
    #     serial.resize(n, 0)   # this helps to serially store data mostly for hitlist, if i only use hashmap it gets destroyed at big circuits. 
        
    #     cdef int active_gates = n

    #     for i in range(n):
    #         info = &gate_infolist[i]
    #         if info.type < 0:
    #             active_gates -= 1
    #             hidden.push_back(i)
    #             continue
                
    #         if info.hitlist.empty() and not visited[i]:
    #             stack.push_back(i)
    #             visited[i] = 1 # Mark root visited instantly to prevent loopback
                
    #             while not stack.empty():
    #                 node = stack.back()
    #                 info = &gate_infolist[node]
    #                 gate = <Gate>PyList_GET_ITEM(self.gate_verse, node)
                    
    #                 if source_ptr[node] == info.inputlimit:
    #                     stack.pop_back()
    #                     hash_map[node] = pos
    #                     serial[pos] = node  # Log sequential evaluation order
    #                     pos += 1
    #                 else:
    #                     source = gate._sources[source_ptr[node]]
    #                     if source > -1 and not visited[source]:
    #                         stack.push_back(source)
    #                         visited[source] = 1
    #                     source_ptr[node] += 1
                        
    #     # ---------------------------------------------------------
    #     # PASS 2: Catch Floating Leftovers
    #     # ---------------------------------------------------------
    #     for i in range(n):
    #         info = &gate_infolist[i]
    #         if info.type < 0 or visited[i]:
    #             continue
                
    #         stack.push_back(i)
    #         visited[i] = 1
            
    #         while not stack.empty():
    #             node = stack.back()
    #             info = &gate_infolist[node]
    #             gate = <Gate>PyList_GET_ITEM(self.gate_verse, node)
                
    #             if source_ptr[node] == info.inputlimit:
    #                 stack.pop_back()
    #                 hash_map[node] = pos
    #                 serial[pos] = node
    #                 pos += 1
    #             else:
    #                 source = gate._sources[source_ptr[node]]
    #                 if source > -1 and not visited[source]:
    #                     stack.push_back(source)
    #                     visited[source] = 1
    #                 source_ptr[node] += 1

    #     # ---------------------------------------------------------
    #     # PASS 3: Append Hidden Gates
    #     # ---------------------------------------------------------
    #     for i in hidden:
    #         hash_map[i] = pos
    #         serial[pos] = i
    #         pos += 1
            
    #     if pos != n:
    #         print('Error Occured')
    #         return
            
    #     # ---------------------------------------------------------
    #     # PASS 4: Contiguous Heap Allocation Mapping
    #     # ---------------------------------------------------------
    #     new_gate_infolist.resize(n)
    #     cdef int old_pos
        
    #     for i in range(n):
    #         old_pos = serial[i]
    #         # Triggers C++ copy assignment in perfect topological order.
    #         # Forces the memory allocator to place hitlist arrays physically adjacent.
    #         new_gate_infolist[i] = gate_infolist[old_pos]
            
    #         profile = new_gate_infolist[i].hitlist.data()
    #         end = profile + new_gate_infolist[i].hitlist.size()
            
    #         while profile < end:
    #             # Update the target location using hash map
    #             profile.target = hash_map[profile.target]
    #             profile += 1
                
    #         if new_gate_infolist[i].hitlist.size() > 3:
    #             sort(new_gate_infolist[i].hitlist.begin(), new_gate_infolist[i].hitlist.end())
                
    #     self.gate_infolist.swap(new_gate_infolist)
        
    #     # ---------------------------------------------------------
    #     # PASS 5: Python Gate Verse Syncing
    #     # ---------------------------------------------------------
    #     cdef list new_gate_verse = [None for _ in range(n)]
    #     cdef list sources
    #     cdef int new_pos
        
    #     for i in range(n):
    #         gate = <Gate>PyList_GET_ITEM(self.gate_verse, i)
    #         new_pos = hash_map[i]
    #         gate.location = new_pos
    #         sources = gate._sources
            
    #         for index in range(len(sources)):
    #             if sources[index] != -1:
    #                 # Update the source location
    #                 sources[index] = hash_map[sources[index]]
                    
    #         new_gate_verse[new_pos] = gate
            
    #     self.gate_verse[:] = new_gate_verse

    cpdef void optimize(self):
        '''Optimize the circuit using topological sort so prefetcher never has to look back. 
        Also pushes back hidden gates with mutated info type'''
        if self.gate_infolist.empty():
            return
        self.copydata.clear()
        cdef int i=0,j=0,n
        cdef vector[int] hash_map,in_degree,hidden,serial
        cdef Profile* profile, *end
        cdef int degree=0,index=0,active_gates=0
        cdef CPP_Gate* info
        cdef vector[CPP_Gate] new_gate_infolist
        cdef CPP_Gate* gate_infolist=self.gate_infolist.data()
        cdef deque[int] backup,queue
        n=self.gate_infolist.size()
        serial.resize(n)
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
                backup.push_back(index)
        cdef int node
        while not backup.empty():
            node=backup.front()
            backup.pop_front()
            queue.push_back(node)
            while not queue.empty():
                node=queue.front()
                queue.pop_front()
                info=&gate_infolist[node]
                hash_map[node]=j
                serial[j]=node
                j+=1
                profile=info.hitlist.data()
                end=profile+info.hitlist.size()
                while profile<end:
                    '''if the target's dependencies are already in to the list push it to the list now'''
                    if in_degree[profile.target]>0:
                        in_degree[profile.target]-=1
                        if in_degree[profile.target]==0:
                            queue.push_back(profile.target)
                    profile+=1
                    
        for index in range(n):
            if in_degree[index]>0:
                backup.push_back(index)
        while not backup.empty():
            node=backup.front()
            backup.pop_front()
            if in_degree[node]>=1:
                queue.push_back(node)
                in_degree[node]=0
                while not queue.empty():
                    node=queue.front()
                    queue.pop_front()
                    info=&gate_infolist[node]
                    hash_map[node]=j
                    serial[j]=node
                    j+=1
                    profile=info.hitlist.data()
                    end=profile+info.hitlist.size()
                    while profile<end:
                        '''if the target's dependencies are already in to the list push it to the list now'''
                        if in_degree[profile.target]>0:
                            in_degree[profile.target]-=1
                            if in_degree[profile.target]==0:
                                queue.push_back(profile.target)
                        profile+=1

        
        # i is location of each hidden gate, it will be pushed to the end of queue
        for i in hidden:
            hash_map[i]=j
            serial[j]=i    # FIX: was 'node' (last active gate) — must be 'i' (this hidden gate's old index)
            j+=1
        # create new info_list
        new_gate_infolist.resize(n)
        for i in range(n):
            new_gate_infolist[i]=gate_infolist[serial[i]]
            profile=new_gate_infolist[i].hitlist.data()
            end=profile+new_gate_infolist[i].hitlist.size()
            while profile<end:
                '''update the target location'''
                profile.target=hash_map[profile.target]
                profile+=1
            if new_gate_infolist[i].hitlist.size()>3:
                sort(new_gate_infolist[i].hitlist.begin(), new_gate_infolist[i].hitlist.end())
                
        self.gate_infolist.swap(new_gate_infolist)
        cdef list new_gate_verse = []
        cdef Gate gate
        cdef list sources
        for i in range(n):
            gate=<Gate>PyList_GET_ITEM(self.gate_verse, serial[i])
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

    cpdef IC build_ic(self, dict pin_orientations=None):
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
            gate_infolist[gate.location].flags |= FLAG_MARK
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
                    if not (gate_infolist[target.location].flags & FLAG_MARK):
                        gate_infolist[target.location].flags |= FLAG_MARK
                        queue.append(target)
                        size += 1
                    profile += 1
            else:
                while profile != end:
                    target = <Gate>PyList_GET_ITEM(gate_verse, profile.target)
                    if not (gate_infolist[target.location].flags & FLAG_MARK):
                        gate_infolist[target.location].flags |= FLAG_MARK
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
        
        if pin_orientations:
            my_ic.pin_orientations = [
                [pin_orientations.get(pin.location, 0) for pin in my_ic.inputs],
                [pin_orientations.get(pin.location, 0) for pin in my_ic.outputs],
            ]
            
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

    cpdef void save_as_ic(self, str location, str ic_name, str tag, str description, list components=None, dict pin_orientations=None):
        '''save the circuit as an ic
        if components is not empty, it means the user wants to convert selected items to ic
        '''
        cdef Circuit crct
        cdef CPP_Gate* info
        cdef IC my_ic
        cdef Gate gate
        if components:
            '''sandboxing for converting selected items to ic
            create a circuit
            load everything 
            and convert to ic
            '''
            crct = Circuit()
            crct.copy(components)
            crct.paste()
            crct.save_as_ic(location, ic_name, tag, description, None, pin_orientations)
            return
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
        my_ic = self.build_ic(pin_orientations)
        my_ic.custom_name = ic_name
        my_ic.tag = tag
        my_ic.description = description
        with open(location, 'wb') as file:
            file.write(orjson.dumps(my_ic.partial_data()))
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
        self.recording = False
        _tracer.clear()

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
            self.gate_infolist[i].flags &= ~FLAG_MARK

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
        self.visual_queue_clear()
        self.eval_count = 0
        if self.runner is not None and not self.runner.done():
            self.runner.cancel()
        self.runner=None
        if Mod==COMPILE:
            for variable in self.objlist[VARIABLE_ID]:
                if variable is not None:
                    info = &self.gate_infolist[variable.location]
                    info.output = bool(info.flags & FLAG_VALUE)
                    info.flags |= FLAG_MARK
            self.sweep(0)
        else:
            for variable in self.objlist[VARIABLE_ID]:
                if variable is not None:
                    # set output of variable to its value
                    # run the propagation from variable
                    info = &self.gate_infolist[variable.location]
                    info.output = info.flags & FLAG_VALUE
                    self.propagate(variable.location)

    cpdef void custom_simulate(self, list varlist):
        '''simulate the circuit'''
        cdef CPP_Gate* info
        for variable in varlist:
            # set output of variable to its value
            # run the propagation from variable
            info = &self.gate_infolist[variable]
            info.output = (info.flags & FLAG_VALUE)
            self.propagate(variable)

    cpdef void reset(self):
        '''reset the circuit's items to unknown value'''
        cdef Gate g
        set_MODE(DESIGN)
        self.eval_count=0
        cdef priority_queue[Task, vector[Task], greater[Task]] empty_pq
        self.time_queue.swap(empty_pq)
        cdef priority_queue[unsigned int, vector[unsigned int], greater[unsigned int]] empty_tl
        self.time_limit.swap(empty_tl)
        if self.runner is not None and not self.runner.done():
            self.runner.cancel()
        self.runner = None
        self.recording = False
        _tracer.clear()
        for i in self.get_components():
            if i.id != IC_ID:
                g = <Gate>i
                g.reset()
            else:
                (<IC>i).reset()

    cdef void complete_task(self, Task task) nogil:
        '''Process one task called from the async drain loop on the main thread.'''
        self.Global_Clock = task.time   
        cdef int origin = task.gate_loc
        cdef Profile* profile
        cdef Profile* end
        cdef Py_ssize_t realsource, high, low, limit, gate_type
        cdef Py_ssize_t new_output, profile_output, target_output
        cdef unsigned int next_time
        cdef CPP_Gate* self_info
        cdef CPP_Gate* target_info
        cdef uint8_t* book
        cdef CPP_Gate* gate_infolist = self.gate_infolist.data()
        self_info = &gate_infolist[origin]
        
        if self_info.type != VARIABLE_ID:
            if task.time < self_info.target_time:
                return
            if self.recording and self_info.type == PROBE_ID:
                with gil:
                    _tracer.record(<Gate>PyList_GET_ITEM(self.gate_verse, origin), self.Global_Clock)
        else:
            if not (self_info.flags & FLAG_SCHEDULED):
                return
            if self_info.inputlimit == 0:
                self_info.flags ^= FLAG_VALUE
                self_info.output = (self_info.flags & FLAG_VALUE)
                if self.recording:
                    with gil:
                        _tracer.record(<Gate>PyList_GET_ITEM(self.gate_verse, origin), self.Global_Clock)
        if not (self_info.flags & FLAG_UPDATE):
            self.visual_queue.push_back(origin)
            self_info.flags |= FLAG_UPDATE
        new_output = self_info.output
        profile = self_info.hitlist.data()
        end = profile + self_info.hitlist.size()
        while profile != end:
            while profile!=end and profile.output==new_output:
                profile+=1
            if profile ==end:break
            profile_output = profile.output
            target_info = &gate_infolist[profile.target]
            gate_type = target_info.type
            if gate_type>=NOT_ID:target_output=new_output^((gate_type==NOT_ID) &(new_output!=UNKNOWN))
            else:
                book = target_info.book
                book[profile_output] -= 1
                book[new_output] += 1
                high = book[HIGH]
                low  = book[LOW]
                if (new_output==UNKNOWN) or  target_info.invalid:target_output=UNKNOWN
                elif gate_type<OR_ID: target_output= (low==0)^(gate_type&1)
                elif gate_type <XOR_ID: target_output= (high>0)^(gate_type&1)
                else: target_output= (high&1)^(gate_type&1)
            if target_output != target_info.output:
                target_info.output = target_output
                target_info.target_time = self.Global_Clock + self.Global_delay[target_info.type] + (self.FanIn_delay[target_info.type] * limit) + (self.FanOut_delay[target_info.type] * target_info.hitlist.size())
                self.time_queue.push(Task(profile.target, target_info.target_time, profile.target))
            profile.output = new_output
            profile += 1

        if self_info.inputlimit == 0:
            with gil:
                next_time = self.Global_Clock + (<Gate>PyList_GET_ITEM(self.gate_verse, origin)).delay_book[self_info.output]
            self_info.target_time = next_time
            self.time_queue.push(Task(origin, next_time, origin))
            self.time_limit.push(next_time + (self.FanOut_delay[self_info.type] * self_info.hitlist.size()))

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
        cdef uint8_t *book
        cdef CPP_Gate* gate_infolist = self.gate_infolist.data()
        self_info = &gate_infolist[origin]
            
        read_queue[0] = origin
        if not (self_info.flags & FLAG_UPDATE):
            self_info.flags |= FLAG_UPDATE
            self.visual_queue.push_back(origin)
            
        cdef Py_ssize_t wave_limit=self.gate_infolist.size()-self.hidden
        while end_point > 0:
            if unlikely(wave_limit<0):
                self.eval_count += eval
                for i in range(end_point):
                    self_info = &gate_infolist[read_queue[i]]
                    self_info.flags &= ~FLAG_MARK
                    # self_info.flags |= FLAG_SCHEDULED
                    self_info.target_time = self.Global_Clock + self.Global_delay[self_info.type] + (self.FanIn_delay[self_info.type] * self_info.inputlimit) + (self.FanOut_delay[self_info.type] * self_info.hitlist.size())
                    self.time_queue.push(Task(read_queue[i], self_info.target_time, read_queue[i]))
                with gil:
                    if self.runner is None or self.runner.done():
                        self.runner=asyncio.create_task(self.task_manager())
                    return
            wave_limit -= 1
            for index in range(end_point):
                self_info = &gate_infolist[read_queue[index]]
                self_info.flags &= ~FLAG_MARK
                if not (self_info.flags & FLAG_UPDATE):
                    self.visual_queue.push_back(read_queue[index])   # target changed — mark dirty
                    self_info.flags |= FLAG_UPDATE
                new_output = self_info.output
                profile = self_info.hitlist.data()
                end = profile + self_info.hitlist.size()
                eval += self_info.hitlist.size()
                while profile != end:
                    while profile!=end and profile.output==new_output:
                        profile+=1
                    if profile ==end:break
                    profile_output = profile.output
                    target_info = &gate_infolist[profile.target]
                    gate_type = target_info.type
                    if gate_type>=NOT_ID:target_output=new_output^((gate_type==NOT_ID) &(new_output!=UNKNOWN))
                    else:
                        book = target_info.book
                        book[profile_output] -= 1
                        book[new_output] += 1
                        high = book[HIGH]
                        low  = book[LOW]
                        if (new_output==UNKNOWN) or  target_info.invalid:target_output=UNKNOWN
                        elif gate_type<OR_ID: target_output= (low==0)^(gate_type&1)
                        elif gate_type <XOR_ID: target_output= (high>0)^(gate_type&1)
                        else: target_output= (high&1)^(gate_type&1)
                    write_queue[size] = profile.target
                    size += ( ((target_info.flags & FLAG_MARK)==0 )& (target_output!=target_info.output))
                    target_info.flags |= FLAG_MARK * (target_output!=target_info.output)
                    target_info.output = target_output
                    profile.output = new_output
                    profile += 1
            # size is actually the growing size of write_queue
            end_point, size = size, 0
            # buffer switching, read->write and write->read
            read_queue, write_queue = write_queue, read_queue
        self.eval_count += eval

    cdef void batch_propagate(self,Py_ssize_t end_point) nogil:
        '''propagate the output of a gate to its targets'''
        cdef Profile* profile
        cdef Profile* end
        cdef int gate_loc
        cdef Py_ssize_t realsource, high, low,limit,gate_type
        cdef Py_ssize_t new_output, profile_output, target_output
        cdef Py_ssize_t index = 0, size = 0
        cdef Py_ssize_t eval = 0
        cdef int* read_queue = self.queue[0]
        cdef int* write_queue = self.queue[1]
        cdef CPP_Gate* self_info
        cdef CPP_Gate* target_info
        cdef uint8_t *book
        cdef CPP_Gate* gate_infolist = self.gate_infolist.data()            
        cdef Py_ssize_t wave_limit=self.gate_infolist.size()-self.hidden
        while end_point > 0:
            if unlikely(wave_limit<0):
                self.eval_count += eval
                for i in range(end_point):
                    self_info = &gate_infolist[read_queue[i]]
                    self_info.flags &= ~FLAG_MARK
                    self_info.target_time = self.Global_Clock + self.Global_delay[self_info.type] + (self.FanIn_delay[self_info.type] * self_info.inputlimit) + (self.FanOut_delay[self_info.type] * self_info.hitlist.size())
                    self.time_queue.push(Task(read_queue[i], self_info.target_time, read_queue[i]))
                with gil:
                    if self.runner is None or self.runner.done():
                        self.runner=asyncio.create_task(self.task_manager())
                    return
            wave_limit -= 1
            for index in range(end_point):
                self_info = &gate_infolist[read_queue[index]]
                self_info.flags &= ~FLAG_MARK
                if not (self_info.flags & FLAG_UPDATE):
                    self.visual_queue.push_back(read_queue[index])   # target changed — mark dirty
                    self_info.flags |= FLAG_UPDATE
                new_output = self_info.output
                profile = self_info.hitlist.data()
                end = profile + self_info.hitlist.size()
                eval += self_info.hitlist.size()
                while profile != end:
                    while profile!=end and profile.output==new_output:
                        profile+=1
                    if profile ==end:break
                    profile_output = profile.output
                    target_info = &gate_infolist[profile.target]
                    gate_type = target_info.type
                    if gate_type>=NOT_ID:target_output=new_output^((gate_type==NOT_ID) &(new_output!=UNKNOWN))
                    else:
                        book = target_info.book
                        book[profile_output] -= 1
                        book[new_output] += 1
                        high = book[HIGH]
                        low  = book[LOW]
                        if (new_output==UNKNOWN) or  target_info.invalid:target_output=UNKNOWN
                        elif gate_type<OR_ID: target_output= (low==0)^(gate_type&1)
                        elif gate_type <XOR_ID: target_output= (high>0)^(gate_type&1)
                        else: target_output= (high&1)^(gate_type&1)
                    write_queue[size] = profile.target
                    size += ( ((target_info.flags & FLAG_MARK)==0 )& (target_output!=target_info.output))
                    target_info.flags |= FLAG_MARK * (target_output!=target_info.output)
                    target_info.output = target_output
                    profile.output = new_output
                    profile += 1
            # size is actually the growing size of write_queue
            end_point, size = size, 0
            # buffer switching, read->write and write->read
            read_queue, write_queue = write_queue, read_queue
        self.eval_count += eval

    cdef void sweep(self, int origin) nogil:
        '''propagate the output of a gate to its targets'''
        cdef Profile* profile
        cdef Profile* end
        cdef Py_ssize_t realsource, high, low,limit,gate_type
        cdef Py_ssize_t new_output, profile_output, target_output
        cdef Py_ssize_t index = 0,end_point = 0, size = self.gate_infolist.size()
        cdef Py_ssize_t eval = 0
        cdef CPP_Gate* self_info
        cdef CPP_Gate* target_info
        cdef uint8_t *book
        cdef CPP_Gate* gate_infolist = self.gate_infolist.data()
        self_info = &gate_infolist[origin]
        for index in range(origin,size):
            self_info = &gate_infolist[index]
            if self_info.type < 0:
                break                
            if self_info.flags& FLAG_MARK:
                self_info.flags &= ~FLAG_MARK   
                new_output = self_info.output
                if not (self_info.flags & FLAG_UPDATE):
                    self.visual_queue.push_back(index)   # target changed — mark dirty
                    self_info.flags |= FLAG_UPDATE
                profile = self_info.hitlist.data()
                end = profile + self_info.hitlist.size()
                eval += self_info.hitlist.size()

                while profile != end:
                    while profile!=end and profile.output==new_output:
                        profile+=1
                    if profile ==end:break
                    profile_output = profile.output
                    target_info = &gate_infolist[profile.target]
                    gate_type = target_info.type
                    if gate_type>=NOT_ID:target_output=new_output^((gate_type==NOT_ID) &(new_output!=UNKNOWN))
                    else:
                        book = target_info.book
                        book[profile_output] -= 1
                        book[new_output] += 1
                        high = book[HIGH]
                        low  = book[LOW]                        
                        if new_output==UNKNOWN or target_info.invalid:target_output=UNKNOWN
                        elif gate_type<OR_ID: target_output= (low==0)^(gate_type&1)
                        elif gate_type <XOR_ID: target_output= (high>0)^(gate_type&1)
                        else: target_output= (high&1)^(gate_type&1)

                    self.queue[0][end_point] = profile.target
                    end_point += ( ((target_info.flags & FLAG_MARK)==0 )& (target_output!=target_info.output) & (profile.target<=index))
                    target_info.flags |= FLAG_MARK * (target_output!=target_info.output)
                    target_info.output = target_output
                    profile.output = new_output
                    profile += 1
        # size is actually the growing size of write_queue
        self.eval_count += eval
        if end_point:
            self.batch_propagate(end_point)

    cpdef list geometry(self):
        '''
        Extracts the raw memory jump distance for every single connection in the circuit.
        Used for geometry profiling and cache-miss analysis.
        '''
        self.optimize()
        cdef int n = self.gate_infolist.size()
        cdef int i, j, target, jump
        cdef list jumps = []
        
        # Pre-allocate list size to avoid Python heap fragmentation
        cdef int total_edges = 0
        for i in range(n):
            total_edges += self.gate_infolist[i].hitlist.size()
            
        jumps = [0] * total_edges
        cdef int edge_idx = 0
        
        for i in range(n):
            for j in range(self.gate_infolist[i].hitlist.size()):
                target = self.gate_infolist[i].hitlist[j].target
                jump = abs(target - i)
                jumps[edge_idx] = jump
                edge_idx += 1
                
        return jumps
    async def task_manager(self):
        cdef int size, i
        cdef Task task
        cdef unsigned int limit_time
        while not self.time_queue.empty():
            with nogil:
                size = self.time_queue.size()
                for i in range(size):
                    # Drain all oscillator tasks sitting at the head of the queue
                    # (mirrors engine's inner while-inputlimit==0 loop)
                    while (not self.time_queue.empty() and self.gate_infolist[self.time_queue.top().gate_loc].inputlimit == 0):
                        with gil: await asyncio.sleep(DELAY)
                        task = self.time_queue.top()
                        self.time_queue.pop()
                        self.Global_Clock = task.time
                        self.complete_task(task)
                        # Drain combinational descendants that settle within this
                        # half-period (time < next oscillator tick)
                        if not self.time_limit.empty():
                            limit_time = self.time_limit.top()
                            while (not self.time_queue.empty() and self.time_queue.top().time < limit_time):
                                task = self.time_queue.top()
                                self.time_queue.pop()
                                self.complete_task(task)
                            self.time_limit.pop()
                    # Fire one non-oscillator task for this slot
                    if not self.time_queue.empty():
                        task = self.time_queue.top()
                        self.time_queue.pop()
                        self.complete_task(task)
                    else:
                        break
            await asyncio.sleep(DELAY)

    # ── Visual-queue helpers (called from the UI layer) ──────────────────
    cpdef bint visual_queue_empty(self):
        '''Return True when there are no pending dirty gate locations.'''
        return self.visual_queue.empty()

    cpdef void visual_queue_clear(self):
        '''Return True when there are no pending dirty gate locations.'''

        cdef int loc 
        while not self.visual_queue.empty():
            loc = self.visual_queue.front()
            self.gate_infolist[loc].flags &= ~FLAG_UPDATE
            self.visual_queue.pop_front()


    cpdef int pop_visual_queue(self):
        '''Pop and return the next dirty gate location.'''
        cdef int loc = self.visual_queue.front()
        self.gate_infolist[loc].flags &= ~FLAG_UPDATE
        self.visual_queue.pop_front()
        return loc

    cpdef int visual_queue_size(self):
        '''Return the number of pending dirty gate locations.'''
        return self.visual_queue.size()
