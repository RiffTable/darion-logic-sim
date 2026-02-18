import json
from collections import deque
from Gates import Gate, Variable, Profile, hide, reveal
from Const import TOTAL, DESIGN, SIMULATE, FLIPFLOP, get_MODE, set_MODE, ERROR, UNKNOWN, HIGH, LOW, IC_ID, AND_ID, NAND_ID, OR_ID, NOR_ID, XOR_ID, XNOR_ID, NOT_ID, VARIABLE_ID, INPUT_PIN_ID, OUTPUT_PIN_ID, PROBE_ID
from IC import IC
from Store import get

def clear_fuse(fuse: set):
    fuse.clear()

def sync(gate: Gate):
    # reset book based on sources
    gate.book[:] = [0, 0, 0, 0]
    for source in gate.sources:
        if source:
            gate.book[source.output] += 1

def turnoff(gate: Gate, queue: deque, fuse: set):
    for profile in gate.hitlist:
        target = profile.target
        if target != gate:
            target.prev_output = target.output
            target.output = UNKNOWN
            propagate(target, queue, fuse)

def burn(origin: Gate, queue: deque):
    queue.append(origin)
    while queue:
        gate = queue.popleft()
        gate.prev_output = gate.output
        gate.output = ERROR
        for profile in gate.hitlist:
            target = profile.target    
            profile.output = ERROR
            sync(target)
            if target.output != ERROR:
                queue.append(target)

def propagate(origin: Gate, queue: deque, fuse: set):
    gate: Gate
    target: Gate
    
    if get_MODE() == SIMULATE:
        queue.append(origin)
        while queue:
            gate = queue.popleft()
            if gate.listener:
                for listener in gate.listener:
                    listener(gate.output)
            
            for profile in gate.hitlist:
                if gate.output != profile.output:
                    target = profile.target
                    # Update book
                    count = len(profile.index)
                    target.book[profile.output] -= count
                    target.book[gate.output] += count
                    profile.output = gate.output
                    
                    target.prev_output = target.output
                    target.process()
                    if target.prev_output != target.output:
                        queue.append(target)

    elif get_MODE() == FLIPFLOP:
        if origin.output == ERROR:
            burn(origin, queue)
            return
        queue.append(origin)
        while queue:
            gate = queue.popleft()
            if gate.listener:
                for listener in gate.listener:
                    listener(gate.output)

            for profile in gate.hitlist:
                if gate.output != profile.output:
                    target = profile.target
                    # Update book
                    count = len(profile.index)
                    target.book[profile.output] -= count
                    target.book[gate.output] += count
                    profile.output = gate.output
                    
                    target.prev_output = target.output
                    target.process()
                    
                    if target.prev_output != target.output:
                        # loop detection
                        # Reactor checks: if <void*>gate==profile.target or profile.index<0 (fused)
                        # Engine check:
                        if gate == target:
                            queue.clear()
                            burn(gate, queue)
                            clear_fuse(fuse)
                            return
                        if profile in fuse:
                                queue.clear()
                                burn(gate, queue)
                                clear_fuse(fuse)
                                return
                        
                        fuse.add(profile)
                        queue.append(target)
        clear_fuse(fuse)

class Circuit:
    # the main circuit board that holds everything together
    # it knows about all gates, connections, and states
    __slots__ = ['objlist', 'canvas', 'varlist', 'iclist', 'copydata', 'queue', 'fuse']
    def __init__(self):
        # lookup table for objects by code
        self.objlist: list[list[Gate | IC]] = [
            [] for i in range(TOTAL)]  # holds the objects with code name
        # list of everything visible on the board
        self.canvas: list[Gate | IC] = []  # displays the components
        # special list for input/output variables (0/1 switches)
        self.varlist: list[Variable] = []  # holds variables with 0/1 input
        # distinct list for Integrated Circuits
        self.iclist: list[IC] = []

        # clipboard for copy/paste
        self.copydata = []
        
        self.queue = deque()
        self.fuse = set()

    def __repr__(self):
        return 'Circuit'

    # creates and adds a new component to the circuit
    def getcomponent(self, choice, ui_connect=None) -> Gate | IC:
        gt = get(choice)
        if gt:
            rank = len(self.objlist[choice])
            self.objlist[choice].append(gt)
            gt.code = (choice, rank)
            name = gt.__class__.__name__
            
            # give it a nice name like A1, B2 or AND-1
            if name == 'Variable':
                gt.name = chr(ord('A')+(rank) % 26)+str((rank+1)//26)
            elif name == 'InputPin':
                gt.name = 'IN-' + str(len(self.objlist[choice]))
            elif name == 'OutputPin':
                gt.name = 'OUT-' + str(len(self.objlist[choice]))
            else:
                gt.name = name+'-'+str(len(self.objlist[choice]))

            if isinstance(gt, Variable):
                self.varlist.append(gt)
            if isinstance(gt, IC):
                self.iclist.append(gt)
            self.canvas.append(gt)
        if ui_connect:
            gt.listener.append(ui_connect)
        return gt

    def getobj(self, code) -> Gate:
        return self.objlist[code[0]][code[1]]

    def delobj(self, code):
        self.objlist[code[0]][code[1]] = None

    # show component
    def listComponent(self):
        for i in range(len(self.canvas)):
            print(f'{i}. {self.canvas[i]}')

    # show variables
    def listVar(self):
        for i in range(len(self.varlist)):
            print(f'{i}. {self.varlist[i]}')

    def setlimits(self,gate:Gate,size:int):
        return gate.setlimits(size)

    # connects a target gate to a source (input)
    def connect(self, target: Gate, source: Gate, index):
        target.connect(source,index)
        # if the connection changed something, let everyone know
        if target.prev_output != target.output:
            propagate(target, self.queue, self.fuse)
            
    # switches a variable on or off
    def toggle(self, target: Variable, value):
        target.toggle(value)
        if target.prev_output != target.output:
            propagate(target, self.queue, self.fuse)

    # identify target/source
    def disconnect(self, target: Gate, index):
        target.disconnect(index)
        if target.prev_output != target.output:
            propagate(target, self.queue, self.fuse)

    # removes a component from view (soft delete)
    def hideComponent(self, gate: Gate | IC):
        if isinstance(gate, IC):
            gate.hide()
            for pin in gate.outputs:
                turnoff(pin, self.queue, self.fuse)
        else:
            gate.hide()
            turnoff(gate, self.queue, self.fuse)
        
        if gate in self.varlist:
            self.varlist.remove(gate)
        if gate in self.iclist:
            self.iclist.remove(gate)
        self.canvas.remove(gate)

    # completely wipes a component from existence
    def terminate(self, code):
        gate = self.getobj(code)
        if gate in self.varlist:
            self.varlist.remove(gate)
        if gate in self.iclist:
            self.iclist.remove(gate)
        if gate in self.canvas:
            self.canvas.remove(gate)
        self.delobj(code)

    def renewComponent(self, gate: Gate | IC):
        if isinstance(gate, IC):
            gate.reveal()
            for pin in gate.outputs:
                propagate(pin, self.queue, self.fuse)
        else:
            gate.reveal()
            propagate(gate, self.queue, self.fuse)

        if isinstance(gate, Variable):
            self.varlist.append(gate)
        self.canvas.append(gate)
        if isinstance(gate, IC):
            self.iclist.append(gate)

    # Result
    def output(self, gate: Gate):
        print(f'{gate} output is {gate.getoutput()}')

    # generates a truth table for all possible inputs
    def truthTable(self):
        if len(self.varlist) == 0:
            return
        
        # logic from old table() or reactor truthTable()
        gate_list = []
        for item in self.canvas:
            if isinstance(item, Variable): 
                continue
            elif isinstance(item, IC):
                for pin in item.outputs:
                    gate_list.append(pin)
            else:
                gate_list.append(item)

        n = len(self.varlist)
        rows_count = 1 << n
        var_names = [v.name for v in self.varlist]
        gate_names = [v.name for v in gate_list] # IC pins might need better names?
        all_names = var_names + gate_names

        if len(all_names) > 0:
            col_width = max([len(name) for name in all_names]) + 2
        else:
            col_width = 4

        header_parts = [name.center(col_width) for name in all_names]
        header = " | ".join(header_parts)
        separator = "─" * len(header)
        
        Table = []
        Table.append(separator + '\n')
        Table.append(header + '\n')
        Table.append(separator + '\n')
        
        for i in range(rows_count):
            inputs = []
            for j in range(n):
                var = self.varlist[j]
                bit = 1 if (i & (1 << (n - j - 1))) else 0
                
                var.toggle(bit)
                if var.prev_output != var.output:
                     propagate(var, self.queue, self.fuse)
                
                inputs.append("1" if bit else "0")
            
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
        gates = [c for c in self.canvas if not isinstance(c, IC)]
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
                ic.info()

        print("\n" + "=" * 90)

    def writetojson(self, location):
        circuit = []
        for gate in self.canvas:
            circuit.append(gate.json_data())
        with open(location, 'w') as file:
            json.dump(circuit, file)

    def decode(self, code):
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
            if isinstance(gate, IC):
                gate.custom_name = i["custom_name"]
                gate.map = i["map"]
                gate.load_components(i, pseudo)
            pseudo[code] = gate

        for gate_dict in circuit:  # connect components or build the circuit
            code = self.decode(gate_dict["code"])
            gate = pseudo[code]
            if isinstance(gate, IC):
                gate.clone(pseudo)
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

    def rank_reset(self):
        for i in range(TOTAL):
            while self.objlist[i] and self.objlist[i][-1] == None:
                self.objlist[i].pop()

    def clearcircuit(self):
        for i, _ in enumerate(self.objlist):
            self.objlist[i] = []
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
            if isinstance(gate, IC):
                gate.custom_name=i["custom_name"]
                gate.map = i["map"]
                gate.load_components(i, pseudo)
            pseudo[code] = gate

        for gate_dict in circuit:  # connect components or build the circuit
            code = self.decode(gate_dict["code"])
            gate = pseudo[code]
            if isinstance(gate, IC):
                gate.implement(pseudo)
            elif gate:
                gate.clone(gate_dict, pseudo)
        return new_items

    # runs the simulation
    def simulate(self, Mode):
        if get_MODE() != DESIGN:
            self.reset()
        set_MODE(Mode)
        for variable in self.varlist:
            variable.output=variable.value
            propagate(variable, self.queue, self.fuse)

    def reset(self):
        set_MODE(DESIGN)
        for i in self.canvas:
            i.reset()
