# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
# cython: nonecheck=False
import orjson
from Gates cimport Gate, Variable, Profile,vector
from Const cimport *
from IC cimport IC
from Store cimport get,decode
from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM

cdef class Circuit:
    def __cinit__(self):
        self.counter=0
        self.eval_count = 0
    def __init__(self):
        # lookup table for objects by code
        set_MODE(DESIGN)
        self.objlist = [
            [] for i in range(TOTAL)]
        self.copydata = []

    def __repr__(self):
        return 'Circuit'

    cpdef object getcomponent(self,int choice):
        gt = get(choice)
        if gt:
            self.counter+=1
            rank = len(self.objlist[choice])
            self.objlist[choice].append(gt)
            gt.code = (choice, rank)
            if DEBUG:
                if gt.id==VARIABLE_ID:
                    gt.codename = chr(ord('A')+(rank) % 26)+str((rank+1)//26)
                else:
                    gt.codename = gt.codename+'-'+str(len(self.objlist[choice]))
            if gt.id == VARIABLE_ID:
                gt.output = LOW if MODE != DESIGN else UNKNOWN
        return gt

    cpdef object getobj(self, tuple code):
        return self.objlist[code[0]][code[1]]

    cpdef void delobj(self, object gate):
        if gate.id == IC_ID:
            self.counter -= gate.counter
        self.counter -= 1
        self.objlist[gate.code[0]][gate.code[1]]=None

    cpdef void renewobj(self,object gate):
        if gate.id == IC_ID:
            self.counter += gate.counter
        self.counter += 1
        self.objlist[gate.code[0]][gate.code[1]]=gate

    cpdef list get_components(self):
        return [gate for sublist in self.objlist for gate in sublist if gate is not None]

    cpdef list get_variables(self):
        return [gate for gate in self.objlist[VARIABLE_ID] if gate is not None]

    cpdef list get_ics(self):
        return [gate for gate in self.objlist[IC_ID] if gate is not None]

    cpdef void listComponent(self):
        cdef int i=0
        for i,gate in enumerate(self.get_components()):
            print(f'{i}. {gate}')

    cpdef void listVar(self):
        cdef int i=0
        for i,gate in enumerate(self.get_variables()):
            print(f'{i}. {gate}')

    cpdef bint setlimits(self,Gate gate,int size):
        return gate.setlimits(size)

    cpdef void connect(self, Gate target, Gate source,int index):
        cdef int prev=target.output
        target.connect(source,index)
        if prev != target.output:
            self.propagate(target)

            
    cpdef void toggle(self, Gate target,int value):
        if value != target.output:
            target.value=value
            target.output=value if MODE==SIMULATE else UNKNOWN
            self.propagate(target)

    cpdef void disconnect(self, Gate target,int index):
        cdef int prev=target.output
        target.disconnect(index)
        if prev != target.output:
            self.propagate(target)

    cpdef void hide(self, list gatelist):
        cdef Gate pin
        cdef IC ic
        for gate in gatelist:
            if gate.id==IC_ID:
                ic=<IC>gate
                ic.hide()
            else:
                pin=<Gate>gate
                pin.hide()
            self.delobj(gate)

        for gate in gatelist:
            if gate.id==IC_ID:
                ic=<IC>gate
                for pin in ic.outputs:
                    self.turnoff(pin)
            else:
                self.turnoff(gate)

    cpdef void reveal(self, list gatelist):
        cdef Gate pin
        cdef IC ic
        for gate in reversed(gatelist):
            if gate.id==IC_ID:
                ic=<IC>gate
                ic.reveal()
            else:
                pin=<Gate>gate
                pin.reveal()
            self.renewobj(gate)

        for gate in reversed(gatelist):
            if gate.id==IC_ID:
                ic=<IC>gate 
                for pin in ic.outputs:
                    self.propagate(pin)
            else:
                self.propagate(gate)

    # Result
    cpdef void output(self, Gate gate):
        print(f'{gate} output is {gate.getoutput()}')

    cpdef str truthTable(self):
        cdef list variables = self.get_variables()
        if len(variables) == 0 or len(variables)>16 or MODE==DESIGN:
            return 
        cdef list gate_list = []
        cdef list var_names, gate_names, inputs, output_vals, all_names, row_data, header_parts
        cdef list Table = []
        cdef str row, header, separator
        cdef int col_width, bit
        cdef Py_ssize_t i, j, n, k
        cdef int gate_type
        # Filter gatelist
        for item in self.get_components():
            # Use simple type checking or isinstance depending on your import availability
            gate_type = item.id
            if gate_type == VARIABLE_ID: 
                continue
            elif gate_type != IC_ID:
                gate_list.append(item)
            else:
                # Assuming item is an IC
                for pin in item.outputs:
                    gate_list.append(pin)

        n = len(variables)
        # 1 << n is bitwise for 2^n
        cdef int rows_count = 1 << n
        cdef Gate var
        # Collect decoded variable codenames
        var_names = [v.codename for v in variables]
        gate_names = [v.codename for v in gate_list]
        all_names = var_names + gate_names

        if len(all_names) > 0:
            col_width = max([len(name) for name in all_names]) + 2
        else:
            col_width = 4

        header_parts = [name.center(col_width) for name in all_names]
        header = " | ".join(header_parts)
        separator = "─" * len(header)

        Table.append(separator + '\n')
        Table.append(header + '\n')
        Table.append(separator + '\n')

        for i in range(rows_count):
            inputs = []
            for j in range(n):
                # Retrieve variable
                var = variables[j]
                
                # Calculate bit
                bit = 1 if (i & (1 << (n - j - 1))) else 0
                if bit!=var.output:
                    var.output=bit
                    self.propagate(var)
                inputs.append(str(bit))                
            # Calculate outputs
            output_vals = [str(gate.getoutput()) for gate in gate_list]
            
            row_data = inputs + output_vals
            row_parts = [val.center(col_width) for val in row_data]
            
            row = " | ".join(row_parts)
            Table.append(row + '\n')
        self.simulate(SIMULATE)
        Table.append(separator + '\n')
        
        return "".join(Table)

    def diagnose(self):
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
                if isinstance(comp.sources, list):
                    ch = [f"[{i}]:{c}" for i, c in enumerate(comp.sources) if c is not None]
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = f"val:{comp.sources}"

                # Book counts
                book = f"[{comp.book[0]},{comp.book[1]},{comp.book[2]},{comp.book[3]}]"

                # Targets (outputs to) - using hitlist with Profile objects
                tgt = [f"{target} " for target in comp.hitlist]
                tgt_str = ", ".join(tgt) if tgt else "None"

                # Truncate long strings
                ch_str = ch_str[:26] + ".." if len(ch_str) > 28 else ch_str
                tgt_str = tgt_str[:23] + ".." if len(tgt_str) > 25 else tgt_str

                print(fmt.format(str(comp), ch_str, book, tgt_str, str(comp.getoutput())))

            print("-" * total_width)

        cdef list ics = [c for c in self.objlist[IC_ID] if c is not None]
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
                        ch = [f"{c}" for c in pin.sources if c is not None] if isinstance(pin.sources, list) else [f"val:{pin.sources}"]
                        targets = [f"{target} " for target in pin.hitlist]
                        print(f"    {repr(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}, to={', '.join(targets) if targets else 'None'}")

                if ic.outputs:
                    print("  OUTPUT PINS:")
                    for pin in ic.outputs:
                        ch = [f"{c}" for c in pin.sources if c is not None] if isinstance(pin.sources, list) else [f"val:{pin.sources}"]
                        targets = [f"{target} " for target in pin.hitlist]
                        print(f"    {repr(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}, to={', '.join(targets) if targets else 'None'}")

        print("\n" + "=" * 90)

    cpdef void writetojson(self, str location):
        cdef list circuit = []
        for gate in self.get_components():
            circuit.append(gate.full_data())
        with open(location, 'wb') as file:
            file.write(orjson.dumps(circuit))

    cpdef void generate(self,list circuit):
        cdef dict pseudo = {}
        pseudo[('X', 'X')] = None
        cdef object obj
        cdef Gate gate
        cdef IC ic
        for i in circuit:  # load to pseudo
            code = decode(i[CODE])
            obj = self.getcomponent(code[0])
            if obj.id == IC_ID:
                ic = <IC>obj
                ic.custom_name = i[CUSTOM_NAME]
                ic.map = i[MAP]
                ic.load_components(i, pseudo)
            elif obj.id == VARIABLE_ID:
                gate = <Gate>obj
                gate.output=UNKNOWN
            pseudo[code] = obj
        for i in circuit:  # connect components or build the circuit
            code = decode(i[CODE])
            obj = pseudo[code]
            if obj.id==IC_ID:
                ic = <IC>obj
                ic.implement(pseudo)
                self.counter+=ic.counter
            else:
                gate = <Gate>obj
                gate.clone(i, pseudo)

    cpdef void readfromjson(self, str location):
        cdef list circuit
        with open(location, 'rb') as file:
            circuit = orjson.loads(file.read())
        if isinstance(circuit,dict):
            return
        self.generate(circuit)
        if MODE!=DESIGN:
            self.simulate(SIMULATE)

    cpdef IC build_ic(self):
        cdef Gate gate, target
        cdef Profile* profile
        cdef Profile* end
        cdef IC my_ic = self.getcomponent(IC_ID)
        cdef list queue = []
        cdef list outputs = [i for i in self.objlist[OUTPUT_PIN_ID] if i is not None]
        cdef list inputs = [i for i in self.objlist[INPUT_PIN_ID] if i is not None]
        for gate in outputs + inputs:
            gate.scheduled = True
            queue.append(gate)
        cdef Py_ssize_t size = len(queue)
        cdef Py_ssize_t index = len(outputs)
        while index < size:
            gate = queue[index]
            if gate.id == INPUT_PIN_ID and gate.sources[0] is not None:
                profile = gate.hitlist.data()
                end = profile + gate.hitlist.size()
                while profile != end:
                    target = <Gate>profile.target
                    target.sources[profile.index] = gate.sources[0]
                    profile += 1
            elif gate.id == OUTPUT_PIN_ID and not gate.hitlist.empty():
                profile = gate.hitlist.data()
                end = profile + gate.hitlist.size()
                while profile != end:
                    target = <Gate>profile.target
                    target.sources[profile.index] = gate.sources[0]
                    profile += 1
            profile = gate.hitlist.data()
            end = profile + gate.hitlist.size()
            while profile != end:
                target = <Gate>profile.target
                if not target.scheduled:
                    target.scheduled = True
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
        for var in self.objlist[VARIABLE_ID]:
            if var is not None:
                var.code = (INPUT_PIN_ID, len(self.objlist[INPUT_PIN_ID]))
                var.id = INPUT_PIN_ID
                self.objlist[INPUT_PIN_ID].append(var)
        self.objlist[VARIABLE_ID].clear()

        for probe in self.objlist[PROBE_ID]:
            if probe is not None:
                probe.code = (OUTPUT_PIN_ID, len(self.objlist[OUTPUT_PIN_ID]))
                probe.id = OUTPUT_PIN_ID
                self.objlist[OUTPUT_PIN_ID].append(probe)
        self.objlist[PROBE_ID].clear()

    cpdef void transfer_info(self, Gate gate, int id):
        if id >= IC_ID or id < 0:
            return
        cdef list real_source = [source for source in gate.sources if source is not None]
        cdef int length = len(real_source)
        if not real_source or (length == 1 and id != VARIABLE_ID) or (length > 1 and id < VARIABLE_ID):
            if gate.sources[0] is None:
                self.objlist[gate.code[0]][gate.code[1]] = None
                gate.id = id
                gate.code = (id, len(self.objlist[id]))
                self.objlist[id].append(gate)

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

    cpdef void save_as_ic(self, str location, str ic_name):
        if len(self.objlist[VARIABLE_ID]) or len(self.objlist[PROBE_ID]):
            self.ic_pin_change()
        for gate in self.objlist[INPUT_PIN_ID]:
            if gate and (<Gate>gate).sources[0] is not None:
                raise ValueError('Input Pin has extra sources')
        for gate in self.objlist[OUTPUT_PIN_ID]:
            if gate and (<Gate>gate).hitlist.size() > 0:
                raise ValueError('Output Pin has extra targets')
        cdef list cluster=None

        cdef IC my_ic = self.build_ic()
        my_ic.custom_name = ic_name
        # my_ic.tag = tag
        # my_ic.description = description
        with open(location, 'wb') as file:
            file.write(orjson.dumps(my_ic.partial_data()))
        self.clearcircuit()


    cpdef object get_ic(self, str location):
        with open(location, 'rb') as file:
             crct= orjson.loads(file.read())
        if isinstance(crct[COMPONENTS], list):
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
            while self.objlist[i] and self.objlist[i][len(self.objlist[i])-1] is None:
                self.objlist[i].pop()

    cpdef void clearcircuit(self):
        for i in range(TOTAL):
            self.objlist[i].clear()
        self.counter = 0

    cpdef void copy(self, list components):
        if len(components) == 0:
            return
        self.copydata = []
        cluster: list = []
        for i in components:
            i.load_to_cluster(cluster)
        for i in components:
            self.copydata.append(i.partial_data())
        for i in cluster:
            i.scheduled=False

    cpdef list paste(self):
        cdef list circuit=self.copydata
        cdef dict pseudo = {}
        pseudo[('X', 'X')] = None
        cdef list new_items = []
        cdef tuple code
        cdef object gate
        for i in circuit:  # load to pseudo
            code = i[CODE]
            gate = self.getcomponent(code[0])
            new_items.append(gate)
            if gate.id==IC_ID:
                gate.custom_name=i[CUSTOM_NAME]
                gate.map = i[MAP]
                gate.load_components(i, pseudo)
            elif gate.id==VARIABLE_ID:
                gate.output=UNKNOWN
            pseudo[code] = gate

        for gate_info in circuit:  # connect components or build the circuit
            code = gate_info[CODE]
            gate = pseudo[code]
            if gate.id==IC_ID:
                (<IC>gate).implement(pseudo)
                self.counter+=(<IC>gate).counter
            elif gate:
                gate.clone(gate_info, pseudo)

        if MODE!=DESIGN:
            self.simulate(SIMULATE)
        return new_items

    cpdef void simulate(self, int Mod):
        set_MODE(Mod)
        cdef Gate variable
        for variable in self.objlist[VARIABLE_ID]:
            if variable is not None:
                variable.output=variable.value
                self.propagate(variable)

    cpdef void reset(self):
        set_MODE(DESIGN)
        for i in self.get_components():
            if i.id!=IC_ID:
                (<Gate>i).reset()
            else:
                (<IC>i).reset()

    cdef inline void turnoff(self,Gate gate):
        cdef Profile* profile = gate.hitlist.data()
        cdef Profile* end = profile+gate.hitlist.size()
        cdef Gate target
        while profile!=end:
            target = <Gate>profile.target
            if <void*>target != <void*>gate:
                target.output = UNKNOWN
                self.propagate(target)
            profile+=1

    cdef void burn(self,Py_ssize_t index,Py_ssize_t size,void** read_queue,void** write_queue):
        cdef Gate gate,target
        cdef Profile* profile
        cdef Profile* end
        cdef unsigned long long eval=0
        # keep propagating until everything settles
        cdef Py_ssize_t end_point=size
        size=0
        while index<end_point:
            while index<end_point:
                gate = <Gate>read_queue[index]
                gate.scheduled=False
                profile = gate.hitlist.data()
                end = profile+gate.hitlist.size()
                gate.output = ERROR
                while profile!=end:
                    eval+=1
                    if profile.output!=ERROR:
                        target=<Gate>profile.target
                        if target.inputlimit!=1:
                            target.book[profile.output]-=1
                            target.book[ERROR]+=1
                        if target.output!=ERROR:
                                write_queue[size]=<void*>target
                                size+=1
                        profile.output = ERROR
                    profile+=1
                index+=1
            index=0
            end_point=size
            size=0
            read_queue,write_queue=write_queue,read_queue
        self.eval_count+=eval
        
    cdef void propagate(self,Gate origin):
        cdef Gate gate=origin,target
        cdef Profile* profile
        cdef Profile* end
        cdef Py_ssize_t realsource, high, low,gate_type,limit
        cdef Py_ssize_t new_output, profile_output,target_output
        cdef Py_ssize_t index=0,end_point=1,size=0
        cdef unsigned long long counter=0
        cdef unsigned long long eval=0
        cdef void** read_queue=self.queue[0]
        cdef void** write_queue=self.queue[1]
        read_queue[0]=<void*>origin
        if unlikely(origin.output==ERROR):
            self.burn(index,end_point,read_queue,write_queue)
            return
        while end_point>0:
            if unlikely(counter>self.counter):
                self.eval_count+=eval
                self.burn(index,end_point,read_queue,write_queue)
                return

            counter+=1
            for index in range(end_point):
                gate = <Gate>read_queue[index]
                gate.scheduled=False
                new_output=gate.output
                profile = gate.hitlist.data()
                end = profile+gate.hitlist.size()
                while profile!=end:
                    # input(f'Source {gate.codename} {profile.output} {new_output}')
                    eval+=1
                    profile_output = profile.output
                    if profile_output!=new_output:
                        target=<Gate>profile.target
                        gate_type = target.id
                        limit = target.inputlimit
                        # input(f'Updating {target.codename} {target.output}')
                        if limit==1:
                            if new_output>=ERROR:
                                target_output=new_output
                            else:
                                target_output=new_output^(gate_type==NOT_ID)
                        else:
                            target.book[profile_output]-=1
                            target.book[new_output]+=1
                            high=target.book[HIGH]
                            low=target.book[LOW]
                            realsource = high+low
                            if likely(realsource==limit) or unlikely(realsource and realsource+target.book[UNKNOWN]+target.book[ERROR]==limit):
                                if gate_type<OR_ID:target_output = (low==0)^(gate_type&1)
                                elif gate_type<XOR_ID:target_output = (high>0)^(gate_type&1)
                                else:target_output = (high&1)^(gate_type&1)
                            else: target_output = UNKNOWN
                        if target_output!=target.output:
                            target.output = target_output
                            if not target.scheduled:
                                target.scheduled=True
                                write_queue[size]=<void*>target
                                size+=1

                        profile.output = new_output
                    profile+=1
            end_point,size = size,0
            read_queue,write_queue=write_queue,read_queue
        self.eval_count+=eval
