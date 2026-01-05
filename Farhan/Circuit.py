from Gates import *


class Circuit:
    def __init__(self):
        self.objlist = {}  # holds the objects with code name
        self.complist = []  # displays the components
        self.varlist = []  # holds variables with 0/1 input
        self.circuit_breaker = {}  # checks for loops while connecting
        self.gatelist = ["NOT", "AND", "NAND", "OR", "NOR", "XOR", "XNOR"]
        self.objlist["00"] = self.sign_0 = Signal(self, 0)
        self.objlist["01"] = self.sign_1 = Signal(self, 1)
        self.copydata = []
        self.gateobjects = {
            "1": NOT,
            "2": AND,
            "3": NAND,
            "4": OR,
            "5": NOR,
            "6": XOR,
            "7": XNOR,
            "8": Variable,
        }

    def __repr__(self):
        return "Circuit"

    def getobj(self, code):
        return self.objlist[code]

    # show component
    def listComponent(self):
        for i in range(len(self.complist)):
            print(f"{i}. {self.complist[i]}")

    # show variables
    def listVar(self):
        for i in range(len(self.varlist)):
            print(f"{i}. {self.varlist[i]}")

    # name suggests it
    def getcomponent(self, i, code):
        if i not in self.gateobjects:
            return
        gt = self.gateobjects[i](self)
        if i == "8":
            self.varlist.append(gt)
        if code != "":
            gt.override(code)
        gt.name = self.decode(gt.code)
        self.objlist[gt.code] = gt
        self.complist.append(gt)
        self.circuit_breaker[gt] = -1
        return gt

    def decode(self, code):
        gate = int(code[0])
        if gate == 8:
            order = int(code[1:])
            return chr(ord("A") + order % 26) + str(order // 26)
        elif gate == 0:
            return code[1:]
        else:
            gate -= 1
            return self.gatelist[gate] + "-" + code[1:]

    # connects parent to it's child/inputs
    def switch(self, var: Variable, value: str):
        if var.output == value:
            return
        var.children[var.output].clear()
        var.children[int(value)].add(self.sign_1 if value == "1" else self.sign_0)
        var.process()
        self.update(var)

    def connect(self, gate: Gate, child: Gate):
        val = child.output
        if (
            child in gate.children[val]
        ):  # no need to reconnect if connected to it's correct value
            return

        if isinstance(gate, NOT):
            for exclude_child in gate.children[gate.output]:
                exclude_child.parents.discard(gate)
                gate.children[exclude_child.output].discard(exclude_child)

        if child in gate.children[child.prev_output]:
            gate.children[child.prev_output].discard(child)
        gate.children[val].add(child)

        # connect children to it as their parent
        if gate not in child.parents:
            child.parents.add(gate)
        gate.process()
        self.update(gate)  # renew output

    def passive_connect(self, parent, child, child_output):
        parent_obj = self.getobj(parent)
        child_obj = self.getobj(child)
        parent_obj.children[child_output].add(child_obj)
        if child[0] != "0":
            child_obj.parents.add(parent_obj)

    # disconnects parent & child
    def disconnect_gates(self, parent: Gate, child: Gate):

        parent.children[child.output].discard(child)
        child.parents.discard(parent)

        child.process()
        self.update(child)
        parent.process()  # modify output after removing child
        self.update(parent)

    # identify parent/child
    def disconnect(self, gate1: Gate, gate2: Gate):

        # check for parenthood and delete with function
        if gate1 in gate2.parents:
            self.disconnect_gates(gate1, gate2)
        elif gate2 in gate1.parents:
            self.disconnect_gates(gate2, gate1)

    # deletes component
    def deleteComponent(self, gate: Gate):

        for (
            parent
        ) in gate.parents:  # disconnect from parents and they will modify their output
            parent.children[gate.output].discard(gate)
        for child in gate.children[0]:  # disconnect from children
            child.parents.discard(gate)
        for child in gate.children[1]:
            child.parents.discard(gate)
        for child in gate.children[-1]:
            child.parents.discard(gate)
        if isinstance(gate, Variable):
            self.varlist.remove(gate)
        for (
            parent
        ) in gate.parents:  # disconnect from parents and they will modify their output
            parent.process()
            self.update(parent)

    def renewComponent(self, gate: Gate):
        if gate.output == -1:
            self.poison(gate)
        else:
            for (
                parent
            ) in (
                gate.parents
            ):  # disconnect from parents and they will modify their output
                self.connect(parent, gate)
        for child in gate.children[0]:  # disconnect from children
            child.parents.add(gate)
        for child in gate.children[1]:
            child.parents.add(gate)
        if isinstance(gate, Variable):
            self.varlist.append(gate)

    # if my output changes i will update my parents
    # circuit breaker breaks if a gate seen more than twice in a single operation
    def update(self, gate: Gate):
        prev = gate.prev_output
        out = gate.output
        if self.circuit_breaker[gate] == -1:
            self.circuit_breaker[gate] = out
            # i removed parity check here so if i get errors it's because of this
            if prev != out:
                for parent in gate.parents:
                    self.connect(parent, gate)
                    if parent.output == -1:
                        break
            self.circuit_breaker[gate] = -1
        elif self.circuit_breaker[gate] == out:
            return
        else:
            # print('Loop Detected')
            gate.prev_output = gate.output
            self.poison(gate)

    # use queue here***********
    def poison(self, gate: Gate):
        gate.output = -1
        for parent in gate.parents:
            parent.children[-1].add(gate)
            parent.children[0].discard(gate)
            parent.children[1].discard(gate)
            if parent.output != -1:
                self.poison(parent)

    # Result
    def output(self, gate: Gate):
        print(f"{gate} output is {gate.getoutput()}")

    # Truth Table
    def truthTable(self):
        if len(self.varlist) == 0:
            return

        gate_list = [i for i in self.complist if i not in self.varlist]
        n = len(self.varlist)
        rows = 1 << n
        # Collect decoded variable names and the output gate name
        var_names = [v.name for v in self.varlist]
        output_name = [v.name for v in gate_list]

        # Determine column widths for nice alignment
        col_width = max(len(name) for name in var_names + output_name) + 2
        header = " | ".join(name.center(col_width) for name in var_names + output_name)
        separator = "─" * len(header)

        # Print table header
        Table = "\nTruth Table\n"
        # add seperater header and seperator in Table
        Table += separator + "\n"
        Table += header + "\n"
        Table += separator + "\n"
        for i in range(rows):
            inputs = []
            for j in range(n):
                var = self.varlist[j]
                bit = 1 if (i & (1 << (n - j - 1))) else 0
                self.switch(var, str(bit))
                inputs.append("1" if bit else "0")
            output = [gate.getoutput() for gate in gate_list]
            row = " | ".join(val.center(col_width) for val in inputs + output)
            Table += row + "\n"
        Table += separator + "\n"
        return Table

    # diagnosis: this menu is AI generated and it's not the main part of code just to check errors in CLI mode
    # i modified logic in between commits
    def diagnose(self):
        print("--- Component Diagnosis ---")

        # Define columns dynamically (easy to add/remove in the future)
        columns = [
            ("Component", 12),
            ("Input-0", 22),
            ("Input-1", 22),
            ("Error", 22),
            ("Parents (Outputs to)", 25),
            ("State", 10),
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

        for component in self.complist:

            # Inputs (children)
            input_0 = []
            input_1 = []
            Error = []
            for i in component.children[0]:
                input_0.append(i.name)
            for i in component.children[1]:
                input_1.append(i.name)
            for i in component.children[-1]:
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

            print(
                row_format.format(
                    str(component), children_0, children_1, children_neg, parents, state
                )
            )

        print("-" * total_width)

    def writetofile(self, address):
        # write the component list to file
        f = open(address, "w")

        for i in self.complist:
            f.write(f"{i.code} ")
        f.write("\n")
        for i in self.complist:

            # write self
            f.write(f"{i.code} ")
            # write children
            input_0 = [child.code for child in i.children[0]]
            input_0 = ",".join(input_0)
            if len(input_0):
                f.write(f"{input_0} ")
            else:
                f.write("X ")
            input_1 = [child.code for child in i.children[1]]
            input_1 = ",".join(input_1)
            if len(input_1):
                f.write(f"{input_1} ")
            else:
                f.write("X ")
            input_neg = [child.code for child in i.children[-1]]
            input_neg = ",".join(input_neg)
            if len(input_neg):
                f.write(f"{input_neg} ")
            else:
                f.write("X ")
            # write output
            f.write(str(i.output))
            f.write("\n")
        f.close()

    # read from file
    def readfromfile(self, address):

        f = open(address, "r")
        components = f.readline().split(" ")
        components.pop()
        if len(components) == 0:
            return
        self.objlist["00"] = self.sign_0
        self.objlist["01"] = self.sign_1
        pivot = [0] + [gate.rank for gate in self.gateobjects.values()]
        pseudo = {}
        pseudo["00"] = "00"
        pseudo["01"] = "01"

        # create components
        for component in components:
            old_rank = int(component[1:])
            identity = component[0]
            new_code = identity + str(old_rank + pivot[int(identity)])
            self.getcomponent(identity, new_code)
            if identity == "8":
                self.getobj(component).children[0].clear()
            pseudo[component] = new_code
        connections = f.read().split("\n")
        connections.pop()
        for line in connections:
            line = line.split(" ")
            gate = line[0]
            children_0 = line[1].split(",")
            if "X" not in children_0:
                for child in children_0:
                    self.passive_connect(pseudo[gate], pseudo[child], 0)
            children_1 = line[2].split(",")
            if "X" not in children_1:
                for child in children_1:
                    self.passive_connect(pseudo[gate], pseudo[child], 1)
            children_neg = line[3].split(",")
            if "X" not in children_neg:
                for child in children_neg:
                    self.passive_connect(pseudo[gate], pseudo[child], -1)
            output = line[4]
            self.getobj(gate).output = int(output)
        f.close()

    def rank_reset(self):
        for gates in self.gateobjects.values():
            gates.rank = 0
        for key in self.objlist.keys():
            if key[0] != "0":
                self.gateobjects[key[0]].rank = max(
                    self.gateobjects[key[0]].rank, int(key[1:])
                )

    def clearcircuit(self):
        self.objlist.clear()
        self.circuit_breaker.clear()
        self.varlist.clear()
        self.complist.clear()
        self.rank_reset()

    def copy(self, components):
        if len(components) == 0:
            return
        self.copydata.clear()
        self.copydata.append(",".join(components))
        for component in components:
            obj = self.getobj(component)
            info = component
            info += " "
            children = obj.children[0] | obj.children[1] | obj.children[-1]
            copychild = []
            for child in children:
                if child in components or child[0] == "0":
                    copychild.append(child)
            copychild = ",".join(copychild)
            if len(copychild) == 0:
                copychild = "X"
            info += copychild
            self.copydata.append(info)

    def paste(self):
        pivot = [0] + [gate.rank for gate in self.gateobjects.values()]
        if len(self.copydata) == 0:
            return
        components = self.copydata[0]
        pseudo = {}
        pseudo["00"] = "00"
        pseudo["01"] = "01"
        new_items = []
        for component in components.split(","):
            old_rank = int(component[1:])
            identity = component[0]
            new_code = identity + str(old_rank + pivot[int(identity)])
            self.getcomponent(identity, new_code)
            pseudo[component] = new_code
            new_items.append(new_code)
        connections = [self.copydata[i] for i in range(1, len(self.copydata))]
        for line in connections:
            line = line.split(" ")
            gate = line[0]
            children = line[1].split(",")
            if "X" not in children:
                for child in children:
                    self.connect(pseudo[gate], pseudo[child])
        return new_items
