# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
import orjson
from Gates cimport Gate, Variable, Profile
from libcpp.vector cimport vector
from Const cimport *
from IC cimport IC
from Store cimport get
from cpython.list cimport PyList_GET_SIZE, PyList_GET_ITEM

cdef inline void turnoff(Gate gate,Queue &queue,int wave_limit,unsigned long long* eval_ptr):
    cdef Profile* profile = gate.hitlist.data()
    cdef Profile* end = profile+gate.hitlist.size()
    cdef Gate target
    while profile!=end:
        target = <Gate>profile.target
        if <void*>target != <void*>gate:
            target.output = UNKNOWN
            propagate(target,queue,wave_limit,eval_ptr)
        profile+=1

cdef void burn(Queue &queue,int index):
    cdef Gate gate,target
    cdef Profile* profile
    cdef Profile* end
    cdef Py_ssize_t size=queue.size()
    cdef int* book
    # keep propagating until everything settles
    while index<size:
        while index<size:
            gate = <Gate>queue[index]
            gate.scheduled=False
            profile = gate.hitlist.data()
            end = profile+gate.hitlist.size()
            gate.output = ERROR
            while profile!=end:
                if profile.output!=ERROR:
                    target=<Gate>profile.target
                    if target.inputlimit!=1:
                        target.book[profile.output]-=1
                        target.book[ERROR]+=1
                    if target.output!=ERROR:
                        queue.push_back(<void*>target)
                    profile.output = ERROR
                profile+=1
            index+=1
        size = queue.size()
    queue.clear()

cdef void propagate(Gate origin,Queue &queue,int wave_limit,unsigned long long* eval_ptr):
    cdef Gate gate=origin,target
    cdef Profile* profile
    cdef Profile* end
    cdef int* book
    cdef int gate_type, realsource, high, low, limit
    cdef int old_output, new_output, profile_output,target_output
    cdef Py_ssize_t index=0,size=1
    cdef int counter=0
    if unlikely(origin.output==ERROR):
        burn(queue,index)
        return
    queue.push_back(<void*>origin)
    while index<size:
        if unlikely(counter>wave_limit):
            burn(queue,index)
            return
        counter+=1
        while index<size:
            gate = <Gate>queue[index]
            gate.scheduled=False
            new_output=gate.output
            profile = gate.hitlist.data()
            end = profile+gate.hitlist.size()
            while profile!=end:
                if eval_ptr is not NULL:
                    eval_ptr[0]+=1
                profile_output = profile.output
                if profile_output!=new_output:
                    target=<Gate>profile.target
                    gate_type = target.id
                    limit = target.inputlimit
                    if limit==1:
                        if gate_type==NOT_ID and new_output!=UNKNOWN:
                            target_output=new_output^1
                        else:
                            target_output=new_output
                    else:
                        book = target.book
                        book[profile_output]-=1
                        book[new_output]+=1
                        high=book[HIGH]
                        low=book[LOW]
                        realsource = high+low
                        if likely(realsource==limit) or unlikely(realsource and realsource+book[UNKNOWN]+book[ERROR]==limit):
                            if gate_type<OR_ID:target_output = (low==0)^(gate_type&1)
                            elif gate_type<XOR_ID:target_output = (high>0)^(gate_type&1)
                            else:target_output = (high&1)^(gate_type&1)
                        else: target_output = UNKNOWN
                    if target_output!=target.output:
                        target.output = target_output
                        if not target.scheduled:
                            target.scheduled=True
                            queue.push_back(<void*>target)
                    profile.output = new_output
                profile+=1
            index+=1
        size = queue.size()
    queue.clear()

cdef class Circuit:
    def __cinit__(self):
        self.counter=0
        self.queue.reserve(3*1024*1024)
        self.eval_ptr = NULL
        self.eval_count = 0
    def __init__(self):
        # lookup table for objects by code
        set_MODE(DESIGN)
        self.objlist = [
            [] for i in range(TOTAL)]
        self.copydata = []

    def __repr__(self):
        return 'Circuit'
    cpdef void activate_eval(self):
        self.eval_ptr = &self.eval_count
    cpdef void deactivate_eval(self):
        self.eval_ptr = NULL
    cpdef object getcomponent(self,int choice):
        gt = get(choice)
        if gt:
            self.counter+=1
            rank = len(self.objlist[choice])
            self.objlist[choice].append(gt)
            gt.code = (choice, rank)
            name = gt.__class__.__name__
            
            
            if name == 'Variable':
                gt.name = chr(ord('A')+(rank) % 26)+str((rank+1)//26)
            elif name == 'InputPin':
                gt.name = 'IN-' + str(len(self.objlist[choice]))
            elif name == 'OutputPin':
                gt.name = 'OUT-' + str(len(self.objlist[choice]))
            else:
                gt.name = name+'-'+str(len(self.objlist[choice]))

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
            propagate(target,self.queue,self.counter,self.eval_ptr)

            
    cpdef void toggle(self, Variable target,int value):
        if value != target.output:
            target.value=value
            target.output=value if MODE==SIMULATE else UNKNOWN
            propagate(target,self.queue,self.counter,self.eval_ptr)

    cpdef void disconnect(self, Gate target,int index):
        cdef int prev=target.output
        target.disconnect(index)
        if prev != target.output:
            propagate(target,self.queue,self.counter,self.eval_ptr)

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
                    turnoff(pin,self.queue,self.counter,self.eval_ptr)
            else:
                turnoff(gate,self.queue,self.counter,self.eval_ptr)

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
                    propagate(pin,self.queue,self.counter,self.eval_ptr)
            else:
                propagate(gate,self.queue,self.counter,self.eval_ptr)

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
        cdef Variable var
        # Collect decoded variable names
        var_names = [v.name for v in variables]
        gate_names = [v.name for v in gate_list]
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
                    propagate(var,self.queue,self.counter,self.eval_ptr)
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
                print(f"\n  IC: {ic.name} (Code: {ic.code})")
                print("  " + "-" * 50)

                if ic.inputs:
                    print("  INPUT PINS:")
                    for pin in ic.inputs:
                        targets = [f"{target} " for target in pin.hitlist]
                        print(f"    {pin.name}: out={pin.getoutput()}, to={', '.join(targets) if targets else 'None'}")

                if ic.outputs:
                    print("  OUTPUT PINS:")
                    for pin in ic.outputs:
                        ch = [f"{c}" for c in pin.sources if c is not None] if isinstance(pin.sources, list) else []
                        print(f"    {pin.name}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}")

        print("\n" + "=" * 90)

    def writetojson(self, location):
        circuit = []
        for gate in self.get_components():
            circuit.append(gate.json_data())
        with open(location, 'wb') as file:
            file.write(orjson.dumps(circuit))

    cpdef tuple decode(self, code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def readfromjson(self, location):
        with open(location, 'rb') as file:
            circuit = orjson.loads(file.read())
        if isinstance(circuit,dict):
            return
        pseudo = {}
        pseudo[('X', 'X')] = None
        for i in circuit:  # load to pseudo
            code = self.decode(i[CODE])
            gate = self.getcomponent(code[0])
            if gate.id == IC_ID:
                gate.custom_name = i[CUSTOM_NAME]
                gate.map = i[MAP]
                gate.load_components(i, pseudo)
            elif gate.id == VARIABLE_ID:
                gate.output=UNKNOWN
            pseudo[code] = gate

        for gate_info in circuit:  # connect components or build the circuit
            code = self.decode(gate_info[CODE])
            gate = pseudo[code]
            if gate.id == IC_ID:
                (<IC>gate).clone(pseudo,0)
                self.counter+=(<IC>gate).counter
            else:
                gate.clone(gate_info, pseudo)
        if MODE!=DESIGN:
            self.simulate(SIMULATE)

    def save_as_ic(self, location, ic_name="IC"):
        if any(g is not None for g in self.objlist[VARIABLE_ID]):
            print('Delete Variables First')
            return
        lst = self.get_components()
        myIC = self.getcomponent(IC_ID)
        myIC.name = ic_name
        myIC.custom_name = ic_name  # Ensure it has a custom name
        for component in lst:
            myIC.addgate(component)
        with open(location, 'wb') as file:
            file.write(orjson.dumps(myIC.json_data()))
        self.clearcircuit()

    def getIC(self, location):
        myIC = self.getcomponent(IC_ID)
        with open(location, 'rb') as file:
            crct = orjson.loads(file.read())
            if isinstance(crct[COMPONENTS], list):
                myIC.configure(crct)
                self.counter+=myIC.counter
                return myIC
            else:
                print('Cannot Convert to IC')
                return None

    cpdef void rank_reset(self):
        for i in range(TOTAL):
            while self.objlist[i] and self.objlist[i][len(self.objlist[i])-1] is None:
                self.objlist[i].pop()

    cpdef void clearcircuit(self):
        for i in range(TOTAL):
            self.objlist[i].clear()
        self.counter = 0

    def copy(self, components: list):
        if len(components) == 0:
            return
        self.copydata = []
        cluster: set = set()
        for i in components:
            i.load_to_cluster(cluster)
        for i in components:
            self.copydata.append(i.copy_data(cluster))
        with open('clipboard.json', 'wb') as file:
            file.write(orjson.dumps(self.copydata))
        self.copydata = [i.code for i in components]

    def paste(self):
        with open('clipboard.json', 'rb') as file:
            circuit = orjson.loads(file.read())
        pseudo = {}
        pseudo[('X', 'X')] = None
        new_items = []
        for i in circuit:  # load to pseudo
            code = self.decode(i[CODE])
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
            code = self.decode(gate_info[CODE])
            gate = pseudo[code]
            if gate.id==IC_ID:
                gate.implement(pseudo,0)
                self.counter+=(<IC>gate).counter
            elif gate:
                gate.clone(gate_info, pseudo)

        if MODE!=DESIGN:
            self.simulate(SIMULATE)
        return new_items

    cpdef void simulate(self, int Mod):
        set_MODE(Mod)
        cdef Variable variable
        for variable in self.objlist[VARIABLE_ID]:
            if variable is not None:
                variable.output=variable.value
                propagate(variable,self.queue,self.counter,self.eval_ptr)

    cpdef void reset(self):
        set_MODE(DESIGN)
        for i in self.get_components():
            if i.id!=IC_ID:
                (<Gate>i).reset()
            else:
                (<IC>i).reset()
