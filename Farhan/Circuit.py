import json
from Gates import Gate, Variable, Nothing
from Const import Const, GateType
from IC import IC
from Store import Components


class Circuit:
    # the main circuit board that holds everything together
    # it knows about all gates, connections, and states
    __slots__ = ['objlist', 'canvas', 'varlist', 'iclist', 'copydata']
    def __init__(self):
        # lookup table for objects by code
        self.objlist: list[list[Gate | IC]] = [
            [] for i in range(GateType.TOTAL)]  # holds the objects with code name
        # list of everything visible on the board
        self.canvas: list[Gate | IC] = []  # displays the components
        # special list for input/output variables (0/1 switches)
        self.varlist: list[Variable] = []  # holds variables with 0/1 input
        # distinct list for Integrated Circuits
        self.iclist: list[IC] = []

        # clipboard for copy/paste
        self.copydata = []

    def __repr__(self):
        return 'Circuit'

    # creates and adds a new component to the circuit
    def getcomponent(self, choice) -> Gate | IC:
        gt = Components.get(choice)
        if gt:
            rank = len(self.objlist[choice])
            self.objlist[choice].append(gt)
            gt.code = (choice, rank)
            name = gt.__class__.__name__
            
            # give it a nice name like A1, B2 or AND-1
            if name == 'Variable':
                gt.name = chr(ord('A')+(rank) % 26)+str((rank+1)//26)
            else:
                gt.name = name+'-'+str(len(self.objlist[choice]))

            if isinstance(gt, Variable):
                self.varlist.append(gt)
            if isinstance(gt, IC):
                self.iclist.append(gt)
            self.canvas.append(gt)
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
            target.propagate()
            
    # switches a variable on or off
    def toggle(self, target: Variable,value):
        target.toggle(value)
        if target.prev_output != target.output:
            target.propagate()

    # identify target/source
    def disconnect(self, target: Gate, index):
        target.disconnect(index)

    # removes a component from view (soft delete)
    def hideComponent(self, gate: Gate | IC):
        gate.hide()
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
        gate.reveal()
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

        gate_list = [
            i for i in self.canvas if i not in self.varlist and not isinstance(i, IC)]
        
        ic_outputs = []
        for i in self.canvas:
            if isinstance(i, IC):
                for pin in i.outputs:
                    ic_outputs.append((i, pin))

        n = len(self.varlist)
        rows = 1 << n
        # Collect decoded variable names and the output gate name
        var_names = [v.name for v in self.varlist]
        gate_names = [v.name for v in gate_list]
        ic_names = [f"{ic}:{pin.name}" for ic, pin in ic_outputs]
        output_names = gate_names + ic_names

        # Determine column widths for nice alignment
        col_width = max(len(name) for name in var_names + output_names) + 2
        header = " | ".join(name.center(col_width)
                            for name in var_names + output_names)
        separator = "─" * len(header)

        # Print table header
        Table = "\nTruth Table\n"
        # add seperater header and seperator in Table
        Table += separator+'\n'
        Table += header+'\n'
        Table += separator+'\n'
        for i in range(rows):
            inputs = []
            for j in range(n):
                var = self.varlist[j]
                bit = 1 if (i & (1 << (n - j - 1))) else 0
                self.toggle(var, bit)
                inputs.append("1" if bit else "0")
            
            output_vals = [gate.getoutput() for gate in gate_list]
            output_vals += [pin.getoutput() for _, pin in ic_outputs]
            
            row = " | ".join(val.center(col_width) for val in inputs + output_vals)
            Table += row+'\n'
        Table += separator+'\n'
        return Table

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
                    ch = [f"[{i}]:{c}" for i, c in enumerate(comp.sources) if str(c) != 'Empty']
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = f"val:{comp.sources}"

                # Book counts
                book = f"[{comp.book[0]},{comp.book[1]},{comp.book[2]},{comp.book[3]}]"

                # Targets (outputs to)
                tgt = [f"{p} ({list(v[0])})" for p, v in comp.targets.items()]
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
                        targets = [f"{p} ({list(v[0])})" for p, v in pin.targets.items()]
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
        pseudo[('X', 'X')] = Nothing
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
        myIC = self.getcomponent(GateType.IC)
        myIC.name = ic_name
        myIC.custom_name = ic_name  # Ensure it has a custom name
        for component in lst:
            myIC.addgate(component)
        with open(location, 'w') as file:
            json.dump(myIC.json_data(), file)

    def getIC(self, location):
        myIC = self.getcomponent(GateType.IC)
        with open(location, 'r') as file:
            crct = json.load(file)
            if isinstance(crct, dict) and "map" in crct:
                myIC.configure(crct)
            else:
                print('Cannot Convert to IC')
                return

    def rank_reset(self):
        for i in range(GateType.TOTAL):
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
        pseudo[('X', 'X')] = Nothing
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
            else:
                gate.implement(gate_dict, pseudo)
        return new_items

    # runs the simulation
    def simulate(self, Mode):
        if Const.MODE!= Const.DESIGN:
            self.reset()
        Const.MODE = Mode
        for i in self.varlist:
            i.process()
        for i in self.varlist:
            for target,infolist in i.targets.items():
                if target.output==Const.ERROR:
                    i.update(target,infolist)
                    target.sync()
                    target.process()
                    target.propagate()
                elif i.update(target,infolist):
                    target.propagate()


    def reset(self):
        Const.MODE = Const.DESIGN
        for i in self.canvas:
            i.reset()
