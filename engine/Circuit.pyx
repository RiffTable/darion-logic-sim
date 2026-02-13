# distutils: language = c++
import json
from Gates cimport Gate, Variable, run, table
from Gates import Nothing
from Const cimport TOTAL,DESIGN,SIMULATE,FLIPFLOP,ERROR,UNKNOWN,HIGH,LOW,IC_ID,MODE,set_MODE,VARIABLE_ID
from IC cimport IC
from Store cimport get


cdef class Circuit:
    # the main circuit board that holds everything together
    # it knows about all gates, connections, and states

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
            target.propagate()
            
    # switches a variable on or off
    cpdef void toggle(self, Variable target,int value):
        target.toggle(value)
        if target.prev_output != target.output:
            target.propagate()

    # identify target/source
    cpdef void disconnect(self, Gate target,int index):
        target.disconnect(index)

    # removes a component from view (soft delete)
    cpdef void hideComponent(self, object gate):
        if gate.id!=IC_ID:
            (<Gate>gate).hide()
        else:
            gate.hide()
        
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
        if gate.id!=IC_ID:
            (<Gate>gate).reveal()
        else:
            gate.reveal()
        
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
        return table(self.canvas, self.varlist)

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
                    ch = [f"[{i}]:{c}" for i, c in enumerate(comp.sources) if str(c) != 'Empty']
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = f"val:{comp.sources}"

                # Book counts
                book = f"[{comp.book[0]},{comp.book[1]},{comp.book[2]},{comp.book[3]}]"

                # Targets (outputs to) - using hitlist with Profile objects
                tgt = [f"{profile.target} ({profile.index})" for profile in comp.hitlist]
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
                        targets = [f"{profile.target} ({profile.index})" for profile in pin.hitlist]
                        print(f"    {pin.name}: out={pin.getoutput()}, to={', '.join(targets) if targets else 'None'}")

                # Output pins
                if ic.outputs:
                    print("  OUTPUT PINS:")
                    for pin in ic.outputs:
                        ch = [f"{c}" for c in pin.sources if str(c) != 'Empty'] if isinstance(pin.sources, list) else []
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
        pseudo[('X', 'X')] = Nothing
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
        pseudo[('X', 'X')] = Nothing
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
            elif gate !=Nothing:
                gate.clone(gate_dict, pseudo)
        return new_items

    # runs the simulation
    cpdef void simulate(self, int Mod):
        if MODE != DESIGN:
            self.reset()
        set_MODE(Mod)
        run(self.varlist)

    cpdef void reset(self):
        set_MODE(DESIGN)
        for i in self.canvas:
            if i.id!=IC_ID:
                (<Gate>i).reset()
            else:
                (<IC>i).reset()
