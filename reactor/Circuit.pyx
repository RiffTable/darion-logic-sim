# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=True
# cython: initializedcheck=False
# cython: cdivision=True
import json
from Gates cimport Gate, Variable, Profile
from libcpp.deque cimport deque
from libcpp.vector cimport vector
from Const cimport TOTAL
from Const cimport HIGH, LOW, ERROR, UNKNOWN, DESIGN, SIMULATE, FLIPFLOP, MODE,AND_ID,OR_ID,NOT_ID,XOR_ID,NAND_ID,NOR_ID,XNOR_ID,VARIABLE_ID,PROBE_ID,INPUT_PIN_ID,OUTPUT_PIN_ID,IC_ID,set_MODE
from IC cimport IC
from Store cimport get

cdef inline void clear_fuse(Fuse &fuse):
    cdef Profile* profile
    for profile in fuse:
        profile.index=-profile.index-1
    fuse.clear()

cdef inline void sync(Gate gate):
    cdef int* book = gate.book
    book[:]=[0,0,0,0]
    cdef Gate source
    for source in gate.sources:
        if source:
            book[source.output]+=1

cdef inline void turnoff(Gate gate,Queue &queue,Fuse &fuse):
    cdef Profile* profile = gate.hitlist.data()
    cdef Profile* end = profile+gate.hitlist.size()
    cdef Gate target
    while profile!=end:
        target = <Gate>profile.target
        if <void*>target != <void*>gate:
            target.prev_output=target.output
            target.output = UNKNOWN
            propagate(target,queue,fuse)
        profile+=1

cdef inline void burn(Gate origin, Queue &queue):
    cdef Gate gate
    cdef Profile* profile
    cdef Profile* end 
    cdef Gate target
    queue.push_back(<void*>origin)
    # input(f'burn from {self}\n')
    # keep propagating until everything settles
    while queue.size():
        gate = <Gate>queue.front()
        queue.pop_front()
        profile = gate.hitlist.data()
        end = profile+gate.hitlist.size()
        gate.prev_output=gate.output
        gate.output = ERROR
        while profile!=end:
            target=<Gate>profile.target
            profile.output = ERROR
            if profile==end-1 or profile.target!=(profile+1).target:
                sync(target)
                if target.output!=ERROR:
                    queue.push_back(<void*>target)
            profile+=1

cdef inline void propagate(Gate origin, Queue &queue,Fuse &fuse):

    cdef Gate gate
    cdef Gate target
    cdef Profile* profile
    cdef Profile* end
    cdef int* book
    cdef int gate_type
    cdef int realsource
    cdef int high
    cdef int low
    cdef int limit
    if MODE==SIMULATE:# don't need fuse, the logic itself is loop-proof
        queue.push_back(<void*>origin)
        # keep propagating until everything settles
        while not queue.empty():
            gate = <Gate>queue.front()
            queue.pop_front()
            profile = gate.hitlist.data()
            end = profile+gate.hitlist.size()
            while profile!=end:
                if gate.output!=profile.output:
                    target=<Gate>profile.target
                    gate_type = target.id
                    limit=target.inputlimit
                    if limit==1:
                        target.prev_output=target.output
                        if gate_type==NOT_ID:
                            if gate.output==UNKNOWN:
                                target.output=UNKNOWN
                            else:
                                target.output=gate.output^1
                        else:
                            target.output=gate.output
                        if target.prev_output!=target.output:
                            queue.push_back(<void*>target)
                    else:                           
                        book = target.book
                        book[profile.output]-=1
                        book[gate.output]+=1
                        if profile==end-1 or profile.target!=(profile+1).target:
                            target.prev_output=target.output
                            high=book[HIGH]
                            low=book[LOW]
                            realsource=book[HIGH]+book[LOW]
                            if realsource==limit:
                                if gate_type==AND_ID:target.output = low==0
                                elif gate_type==NAND_ID:target.output = low!=0
                                elif gate_type==OR_ID:target.output = high>0
                                elif gate_type==NOR_ID:target.output = high==0
                                elif gate_type==XOR_ID:target.output = high&1
                                elif gate_type==XNOR_ID:target.output = (high&1)^1
                            else:target.output=UNKNOWN
                            if target.prev_output!=target.output:
                                queue.push_back(<void*>target)
                    profile.output = gate.output
                profile+=1

    elif MODE==FLIPFLOP:

            # notify all targets
        if origin.output==ERROR:
            burn(origin,queue)
            return
        queue.push_back(<void*>origin)
        # keep propagating until everything settles
        while not queue.empty():
            gate = <Gate>queue.front()
            queue.pop_front()
            profile = gate.hitlist.data()
            end = profile+gate.hitlist.size()
            while profile!=end:
                if gate.output!=profile.output:
                    target=<Gate>profile.target
                    gate_type = target.id
                    limit=target.inputlimit
                    if limit==1:
                        target.prev_output=target.output
                        if gate_type==NOT_ID:
                            if gate.output==UNKNOWN:
                                target.output=UNKNOWN
                            else:
                                target.output=gate.output^1
                        else:
                            target.output=gate.output
                        if target.prev_output!=target.output:
                            queue.push_back(<void*>target)
                    else:                           
                        book = target.book
                        book[profile.output]-=1
                        book[gate.output]+=1
                        profile.output = gate.output
                        if profile==end-1 or profile.target!=(profile+1).target:
                            target.prev_output=target.output
                            high=book[HIGH]
                            low=book[LOW]
                            realsource=book[HIGH]+book[LOW]
                            if realsource==limit or (realsource and realsource+book[UNKNOWN]+book[ERROR]==limit):
                                if gate_type==AND_ID:target.output = low==0
                                elif gate_type==NAND_ID:target.output = low!=0
                                elif gate_type==OR_ID:target.output = high>0
                                elif gate_type==NOR_ID:target.output = high==0
                                elif gate_type==XOR_ID:target.output = high&1
                                elif gate_type==XNOR_ID:target.output = (high&1)^1
                            else:target.output=UNKNOWN
                            if target.prev_output!=target.output:
                                if <void*>gate==profile.target or profile.index<0: 
                                    queue.clear()
                                    burn(gate,queue)
                                    clear_fuse(fuse)
                                    return
                                profile.index=-profile.index-1
                                fuse.push_back(profile)
                                queue.push_back(<void*>target)
                    profile.output = gate.output
                profile+=1
            clear_fuse(fuse)
cdef class Circuit:
    # the main circuit board that holds everything together
    # it knows about all gates, connections, and states
    def __cinit__(self):
        self.fuse.reserve(1000)
    def __init__(self):
        # lookup table for objects by code
        self.objlist = [
            [] for i in range(TOTAL)]  # holds the objects with code name
        # list of everything visible on the board
        self.canvas = []  # displays the components
        # special list for input/output variables (0/1 switches)
        self.varlist = []  # holds variables with 0/1 input
        # distinct list for Integrated Circuits
        self.iclist = []

        # clipboard for copy/paste
        self.copydata = []

    def __repr__(self):
        return 'Circuit'

    # creates and adds a new component to the circuit
    cpdef object getcomponent(self,int choice):
        gt = get(choice)
        if gt:
            rank = len(self.objlist[choice])
            self.objlist[choice].append(gt)
            gt.code = (choice, rank)
            name = gt.__class__.__name__
            
            # give it a nice name like A1, B2 or AND-1
            # give it a nice name like A1, B2 or AND-1
            if name == 'Variable':
                gt.name = chr(ord('A')+(rank) % 26)+str((rank+1)//26)
            elif name == 'InputPin':
                gt.name = 'IN-' + str(len(self.objlist[choice]))
            elif name == 'OutputPin':
                gt.name = 'OUT-' + str(len(self.objlist[choice]))
            else:
                gt.name = name+'-'+str(len(self.objlist[choice]))

            if gt.id==VARIABLE_ID:
                self.varlist.append(gt)
            if gt.id==IC_ID:
                self.iclist.append(gt)
            self.canvas.append(gt)
        return gt

    cpdef object getobj(self, tuple code):
        return self.objlist[code[0]][code[1]]

    cpdef void delobj(self, tuple code):
        self.objlist[code[0]][code[1]] = None

    # show component
    cpdef void listComponent(self):
        cdef int i=0
        for i,gate in enumerate(self.canvas):
            print(f'{i}. {gate}')

    # show variables
    cpdef void listVar(self):
        cdef int i=0
        for i,gate in enumerate(self.varlist):
            print(f'{i}. {gate}')

    cpdef bint setlimits(self,Gate gate,int size):
        return gate.setlimits(size)

    # connects a target gate to a source (input)
    cpdef void connect(self, Gate target, Gate source,int index):
        target.connect(source,index)
        # if the connection changed something, let everyone know
        if target.prev_output != target.output:
            propagate(target,self.queue,self.fuse)
            
    # switches a variable on or off
    cpdef void toggle(self, Variable target,int value):
        target.toggle(value)
        if target.prev_output != target.output and target.output!=ERROR:
            propagate(target,self.queue,self.fuse)

    # identify target/source
    cpdef void disconnect(self, Gate target,int index):
        target.disconnect(index)
        if target.prev_output != target.output:
            propagate(target,self.queue,self.fuse)

    # removes a component from view (soft delete)
    cpdef void hideComponent(self, object gate):
        cdef Gate pin
        if gate.id==IC_ID:
            (<IC>gate).hide()
            for pin in gate.outputs:
                turnoff(pin,self.queue,self.fuse)
        else:
            pin=<Gate>gate
            pin.hide()
            turnoff(pin,self.queue,self.fuse)
        
        if gate in self.varlist:
            self.varlist.remove(gate)
        if gate in self.iclist:
            self.iclist.remove(gate)
        self.canvas.remove(gate)

    # completely wipes a component from existence
    cpdef void terminate(self, code):
        cdef object gate = self.getobj(code)
        if gate in self.varlist:
            self.varlist.remove(gate)
        if gate in self.iclist:
            self.iclist.remove(gate)
        if gate in self.canvas:
            self.canvas.remove(gate)
        self.delobj(code)

    cpdef void renewComponent(self, object gate):
        cdef Gate pin
        if gate.id==IC_ID:
            (<IC>gate).reveal()
            for pin in gate.outputs:
                propagate(pin,self.queue,self.fuse)
        else:
            pin=<Gate>gate
            pin.reveal()
            propagate(pin,self.queue,self.fuse)
        
        if gate.id==VARIABLE_ID:
            self.varlist.append(gate)
        self.canvas.append(gate)
        if gate.id==IC_ID:
            self.iclist.append(gate)

    # Result
    cpdef void output(self, Gate gate):
        print(f'{gate} output is {gate.getoutput()}')

    # generates a truth table for all possible inputs
    cpdef str truthTable(self):
        if len(self.varlist) == 0:
            return
        cdef list gate_list = []
        cdef list var_names, gate_names, inputs, output_vals, all_names, row_data, header_parts
        cdef list Table = []
        cdef str row, header, separator
        cdef int col_width, bit
        cdef Py_ssize_t i, j, n, k
        cdef int gate_type
        cdef list varlist=self.varlist
        # Filter gatelist
        for item in self.canvas:
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

        n = len(varlist)
        # 1 << n is bitwise for 2^n
        cdef int rows_count = 1 << n
        cdef Variable var
        # Collect decoded variable names
        var_names = [v.name for v in varlist]
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
                var = varlist[j]
                
                # Calculate bit
                bit = 1 if (i & (1 << (n - j - 1))) else 0
                
                var.toggle(bit)
                if var.prev_output != var.output:
                    propagate(var,self.queue,self.fuse)
                
                inputs.append("1" if bit else "0")
            
            # Calculate outputs
            output_vals = [str(gate.getoutput()) for gate in gate_list]
            
            row_data = inputs + output_vals
            row_parts = [val.center(col_width) for val in row_data]
            
            row = " | ".join(row_parts)
            Table.append(row + '\n')

        Table.append(separator + '\n')
        
        return "".join(Table)

    # prints a detailed report of everything going on
    def diagnose(self):
        print("=" * 90)
        print(" " * 35 + "CIRCUIT DIAGNOSIS")
        print("=" * 90)

        # Diagnose regular gates
        gates = [c for c in self.canvas if c.id != IC_ID]
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
                # Sources (inputs) - list with indices
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

        # Diagnose ICs
        if self.iclist:
            print("\n" + "=" * 90)
            print(" " * 40 + "IC STATUS")
            print("=" * 90)
            for ic in self.iclist:
                print(f"\n  IC: {ic.name} (Code: {ic.code})")
                print("  " + "-" * 50)

                # Input pins
                if ic.inputs:
                    print("  INPUT PINS:")
                    for pin in ic.inputs:
                        targets = [f"{target} " for target in pin.hitlist]
                        print(f"    {pin.name}: out={pin.getoutput()}, to={', '.join(targets) if targets else 'None'}")

                # Output pins
                if ic.outputs:
                    print("  OUTPUT PINS:")
                    for pin in ic.outputs:
                        ch = [f"{c}" for c in pin.sources if c is not None] if isinstance(pin.sources, list) else []
                        print(f"    {pin.name}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}")

        print("\n" + "=" * 90)

    def writetojson(self, location):
        circuit = []
        for gate in self.canvas:
            circuit.append(gate.json_data())
        with open(location, 'w') as file:
            json.dump(circuit, file)

    cpdef tuple decode(self, code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def readfromjson(self, location):
        with open(location, 'r') as file:
            circuit = json.load(file)
        if isinstance(circuit,dict):
            return
        pseudo = {}
        pseudo[('X', 'X')] = None
        for i in circuit:  # load to pseudo
            code = self.decode(i["code"])
            gate = self.getcomponent(code[0])
            if gate.id == IC_ID:
                gate.custom_name = i["custom_name"]
                gate.map = i["map"]
                gate.load_components(i, pseudo)
            pseudo[code] = gate

        for gate_dict in circuit:  # connect components or build the circuit
            code = self.decode(gate_dict["code"])
            gate = pseudo[code]
            if gate.id == IC_ID:
                (<IC>gate).clone(pseudo)
            else:
                gate.clone(gate_dict, pseudo)

    # packages the current circuit into an IC
    def save_as_ic(self, location, ic_name="IC"):
        if self.varlist:
            print('Delete Variables First')
            return
        lst = [i for i in self.canvas]
        myIC = self.getcomponent(IC_ID)
        myIC.name = ic_name
        myIC.custom_name = ic_name  # Ensure it has a custom name
        for component in lst:
            myIC.addgate(component)
        with open(location, 'w') as file:
            json.dump(myIC.json_data(), file)

    def getIC(self, location):
        myIC = self.getcomponent(IC_ID)
        with open(location, 'r') as file:
            crct = json.load(file)
            if isinstance(crct, dict) and "map" in crct:
                myIC.configure(crct)
                return myIC
            else:
                print('Cannot Convert to IC')
                return None

    cpdef void rank_reset(self):
        for i in range(TOTAL):
            while self.objlist[i] and self.objlist[i][-1] == None:
                self.objlist[i].pop()

    cpdef void clearcircuit(self):
        for i in range(TOTAL):
            self.objlist[i]=[]
        self.varlist = []
        self.canvas = []
        self.iclist = []

    # copies selected components to clipboard
    def copy(self, components: list["Gate"]):
        if len(components) == 0:
            return
        self.copydata = []
        cluster: set["Gate"] = set()
        for i in components:
            i.load_to_cluster(cluster)
        for i in components:
            self.copydata.append(i.copy_data(cluster))
        with open('clipboard.json', 'w') as file:
            json.dump(self.copydata, file)
        self.copydata = [i.code for i in components]

    # pastes components from clipboard
    def paste(self):
        with open('clipboard.json', 'r') as file:
            circuit = json.load(file)
        pseudo = {}
        pseudo[('X', 'X')] = None
        new_items = []
        for i in circuit:  # load to pseudo
            code = self.decode(i["code"])
            gate = self.getcomponent(code[0])
            new_items.append(gate.code)
            if gate.id==IC_ID:
                gate.custom_name=i["custom_name"]
                gate.map = i["map"]
                gate.load_components(i, pseudo)
            pseudo[code] = gate

        for gate_dict in circuit:  # connect components or build the circuit
            code = self.decode(gate_dict["code"])
            gate = pseudo[code]
            if gate.id==IC_ID:
                gate.implement(pseudo)
            elif gate:
                gate.clone(gate_dict, pseudo)
        return new_items

    # runs the simulation
    cpdef void simulate(self, int Mod):
        if MODE != DESIGN:
            self.reset()
        set_MODE(Mod)
        cdef Variable variable
        for variable in self.varlist:
            variable.output=variable.value
            propagate(variable,self.queue,self.fuse)

    cpdef void reset(self):
        set_MODE(DESIGN)
        for i in self.canvas:
            if i.id!=IC_ID:
                (<Gate>i).reset()
            else:
                (<IC>i).reset()
