import json
from Gates import Gate, Signal, Variable
from Const import Const
from IC import IC
from Store import Components


class Circuit:

    def __init__(self):
        self.objlist: dict[int, list[Gate | Signal | IC]] = {
            i: [] for i in range(0, 13)}  # holds the objects with code name
        self.canvas: list[Gate | Signal | IC] = []  # displays the components
        self.varlist: list[Variable] = []  # holds variables with 0/1 input
        self.iclist: list[IC] = []
        self.sign_0 = Signal(Const.LOW)
        self.sign_1 = Signal(Const.HIGH)
        self.objlist[0] = [self.sign_0, self.sign_1]
        self.copydata = []

    def __repr__(self):
        return 'Circuit'

    def getcomponent(self, choice) -> Gate | Signal | IC:
        gt = Components.get(choice)
        if gt:
            rank = len(self.objlist[choice])
            self.objlist[choice].append(gt)
            gt.code = (choice, rank)
            name = gt.__class__.__name__
            if name == 'Variable':
                gt.name = chr(ord('A')+(rank) % 26)+str((rank+1)//26)
                gt.children[Const.LOW].add(self.sign_0)
            else:
                gt.name = name+'-'+str(len(self.objlist[choice]))

            if isinstance(gt, Variable):
                self.varlist.append(gt)
            if isinstance(gt, IC):
                self.iclist.append(gt)
            self.canvas.append(gt)
        return gt

    def getobj(self, code) -> Gate | Signal:
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

    # connects parent to it's child/inputs
    def connect(self, parent: Gate, child: Gate | Signal):
        parent.connect(child)
        if parent.prev_output != parent.output:
            parent.propagate()

    def passive_connect(self, parent, child, child_output: str):
        parent_obj = self.getobj(parent)
        child_obj = self.getobj(child)
        parent_obj.children[child_output].add(child_obj)
        if child[0] != 0:
            child_obj.parents.add(parent_obj)

    # identify parent/child
    def disconnect(self, parent: Gate, child: Gate):
        if parent in child.parents:
            parent.disconnect(child)

    # deletes component
    def hideComponent(self, gate: Gate | IC):
        gate.hide()
        if gate in self.varlist:
            self.varlist.remove(gate)
        self.canvas.remove(gate)

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

    # Result
    def output(self, gate: Gate):
        print(f'{gate} output is {gate.getoutput()}')

    # Truth Table
    def truthTable(self):
        if len(self.varlist) == 0:
            return

        gate_list = [
            i for i in self.canvas if i not in self.varlist and not isinstance(i, IC)]
        n = len(self.varlist)
        rows = 1 << n
        # Collect decoded variable names and the output gate name
        var_names = [v.name for v in self.varlist]
        output_name = [v.name for v in gate_list]

        # Determine column widths for nice alignment
        col_width = max(len(name) for name in var_names + output_name) + 2
        header = " | ".join(name.center(col_width)
                            for name in var_names + output_name)
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
                self.connect(var, self.sign_1 if bit else self.sign_0)
                inputs.append("1" if bit else "0")
            output = [gate.getoutput() for gate in gate_list]
            row = " | ".join(val.center(col_width) for val in inputs + output)
            Table += row+'\n'
        Table += separator+'\n'
        return Table

    def diagnose(self):
        print("--- Component Diagnosis ---")

        # Define columns dynamically (easy to add/remove in the future)
        columns = [
            ("Component", 12),
            ("Input-0", 22),
            ("Input-1", 22),
            ('Error', 22),
            ("Parents (Outputs to)", 25),
            ("State", 10)
        ]

        # Calculate total width for separator line
        total_width = sum(width for _, width in columns)

        # Header row
        header_format = "".join(f"{{:<{width}}}" for _, width in columns)
        header_names = [name for name, _ in columns]
        print(header_format.format(*header_names))
        print("-" * total_width)

        # Data rows
        row_format = header_format  # Same alignment and widths

        for component in self.canvas:
            if isinstance(component, IC):
                continue
            # Inputs (children)
            input_0 = []
            input_1 = []
            Error = []
            for i in component.children[Const.LOW]:
                input_0.append(i.name)
            for i in component.children[Const.HIGH]:
                input_1.append(i.name)
            for i in component.children[Const.ERROR]:
                Error.append(i.name)
            children_0 = ", ".join(sorted(input_0)) if input_0 else "None"
            children_1 = ", ".join(sorted(input_1)) if input_1 else "None"
            children_neg = ", ".join(sorted(Error)) if Error else "None"

            # Outputs (parents)
            parents = []
            for i in component.parents:
                parents.append(i.name)
            parents = ", ".join(sorted(parents)) if parents else "None"

            # State
            state = component.getoutput()

            print(row_format.format(str(component), children_0,
                  children_1, children_neg, parents, state))

        print("-" * total_width)

    def writetojson(self, location):
        circuit = []
        for gate in self.canvas:
            circuit.append(gate.json_data())
        with open(location, 'w') as file:
            json.dump(circuit, file, indent=4)

    def decode(self, code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def readfromjson(self, location):
        with open(location, 'r') as file:
            circuit = json.load(file)
        pseudo = {}
        pseudo[(0, 0)] = self.sign_0
        pseudo[(0, 1)] = self.sign_1
        for i in circuit:  # load to pseudo
            code = self.decode(i["code"])
            gate = self.getcomponent(code[0])
            if isinstance(gate, IC):
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

    def save_as_ic(self, location):
        if self.varlist:
            print('Delete Variables First')
            return
        lst = [i for i in self.canvas]
        myIC = self.getcomponent(12)
        for component in lst:
            myIC.addgate(component)
        with open(location, 'w') as file:
            json.dump(myIC.json_data(), file, indent=4)

    def getIC(self, location):
        myIC = self.getcomponent(12)
        with open(location, 'r') as file:
            crct = json.load(file)
            if isinstance(crct, dict) and "map" in crct:
                myIC.configure(crct)
            else:
                print('Cannot Convert to IC')
                return

    def rank_reset(self):
        for key in self.objlist.values():
            while key and key[-1] == None:
                key.pop()

    def clearcircuit(self):
        for i, _ in enumerate(self.objlist):
            self.objlist[i] = []
        self.varlist = []
        self.canvas = []

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
            json.dump(self.copydata, file, indent=4)
        self.copydata = [i.code for i in components]

    def paste(self):
        with open('clipboard.json', 'r') as file:
            circuit = json.load(file)
        pseudo = {}
        pseudo[(0, 0)] = self.sign_0
        pseudo[(0, 1)] = self.sign_1
        new_items = []
        for i in circuit:  # load to pseudo
            code = self.decode(i["code"])
            gate = self.getcomponent(code[0])
            new_items.append(gate.code)
            if isinstance(gate, IC):
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

    def simulate(self, Mode):
        Const.MODE = Mode
        for i in self.varlist:
            i.process()
        for i in self.varlist:
            for parent in i.parents:
                parent.connect(i)
                if parent.output != Const.UNKNOWN:
                    parent.propagate()

    def reset(self):
        Const.MODE = Const.DESIGN
        for i in self.canvas:
            i.reset()
