from __future__ import annotations
from Const import Const
from Gates import Gate, InputPin, OutputPin


class IC:
    def __init__(self):
        self.inputs: list[InputPin] = []
        self.internal: list[OutputPin] = []
        self.outputs: list[Gate | IC] = []

        self.name = 'IC'
        self.custom_name = ''
        self.code = ''

        self.map = {}

        self.inputpoint = False
        self.outputpoint = False

    def __repr__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def getcomponent(self, choice):
        from Store import Components
        gt = Components.get(choice)
        if gt:
            if isinstance(gt, InputPin):
                rank = len(self.inputs)
                self.inputs.append(gt)
                gt.name = 'in-'+str(len(self.inputs))
            elif isinstance(gt, OutputPin):
                rank = len(self.outputs)
                self.outputs.append(gt)
                gt.name = 'out-'+str(len(self.outputs))
            else:
                rank = len(self.internal)
                self.internal.append(gt)
                gt.name = gt.__class__.__name__+'-'+str(len(self.internal))
            gt.code = (choice, rank, self.code)
        return gt

    def addgate(self, child: Gate | OutputPin | InputPin):

        if isinstance(child, InputPin):
            rank = len(self.inputs)
            self.inputs.append(child)
            child.name = 'in-'+str(len(self.inputs))
        elif isinstance(child, OutputPin):
            rank = len(self.outputs)
            self.outputs.append(child)
            child.name = 'out-'+str(len(self.outputs))
        else:
            rank = len(self.internal)
            self.internal.append(child)
            child.name = child.__class__.__name__+'-'+str(len(self.internal))
        child.code = (child.code[0], rank, self.code)

    def configure(self, dictionary):
        pseudo = {}
        self.map = dictionary["map"]
        self.load_components(dictionary, pseudo)
        self.clone(pseudo)

    def decode(self, code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def load_components(self, dictionary, pseudo):
        # generate all the necessary components
        for code in dictionary["components"]:
            gate = self.getcomponent(code[0])
            pseudo[self.decode(code)] = gate

    def json_data(self):
        dictionary = {
            "name": self.name,
            "code": self.code,
            "components": [gate.code for gate in self.internal+self.inputs+self.outputs],
            "map": []
        }
        for i in self.internal+self.inputs+self.outputs:
            dictionary["map"].append(i.json_data())
        return dictionary

    def clone(self, pseudo):
        for i in self.map:
            code = self.decode(i["code"])
            gate = pseudo[code]
            if isinstance(gate, IC):
                gate.map = i["map"]
                gate.load_components(i, pseudo)
                gate.clone(pseudo)
            else:
                gate.clone(i, pseudo)

    def load_to_cluster(self, cluster: set):
        for i in self.inputs+self.internal+self.outputs:
            if isinstance(i, IC):
                cluster.add(i)
                i.load_to_cluster(cluster)
            else:
                cluster.add(i)

    def copy_data(self, cluster):
        dictionary = {
            "name": self.name,
            "code": self.code,
            "components": [gate.code for gate in self.internal+self.inputs+self.outputs],
            "map": []
        }
        for i in self.internal+self.inputs+self.outputs:
            dictionary["map"].append(i.copy_data(cluster))
        return dictionary

    def implement(self, pseudo):
        for i in self.map:
            code = self.decode(i["code"])
            gate = pseudo[code]
            if isinstance(gate, IC):
                gate.map = i["map"]
                gate.load_components(i, pseudo)
                gate.implement(pseudo)
            else:
                gate.implement(i, pseudo)

    def hide(self):
        for pin in self.outputs:
            for parent in pin.parents.keys():
                parent.children[pin.output].discard(pin)
            for parent in pin.parents.keys():
                parent.process()
                parent.propagate()
        for pin in self.inputs:
            for i in pin.children.keys():
                for child in pin.children[i]:
                    child.parents.discard(pin)

    def reveal(self):
        for pin in self.outputs:
            for parent in pin.parents:
                parent.connect(pin)
            for parent in pin.parents:
                parent.propagate()
        for pin in self.inputs:
            for i in pin.children.keys():
                for child in pin.children[i]:
                    child.parents.add(pin)

    def reset(self):
        for i in self.inputs+self.internal+self.outputs:
            i.reset()

    def showinputpins(self):
        for i, gate in enumerate(self.inputs):
            print(f'{i}. {gate}')

    def showoutputpins(self):
        for i, gate in enumerate(self.outputs):
            print(f'{i}. {gate}')

    def info(self):
        """Show all IC components in an organized way."""
        print(f"\n  IC: {self.name} (Code: {self.code})")
        print("  " + "-" * 40)

        # Show inputs
        if self.inputs:
            print("  INPUTS:")
            for pin in self.inputs:
                parents = [str(p) for p in pin.parents.keys()]
                print(f"    {pin.name}: out={pin.getoutput()}, to={', '.join(parents) if parents else 'None'}")

        # Show internal components
        if self.internal:
            print("  INTERNAL:")
            for comp in self.internal:
                if isinstance(comp, IC):
                    comp.info()
                else:
                    # Children (list with indices)
                    if isinstance(comp.children, list):
                        ch = [f"[{i}]:{c}" for i, c in enumerate(comp.children) if str(c) != 'Empty']
                        ch_str = ", ".join(ch) if ch else "None"
                    else:
                        ch_str = f"val:{comp.children}"
                    # Parents
                    par = [str(p) for p in comp.parents.keys()]
                    par_str = ", ".join(par) if par else "None"
                    print(f"    {comp.name}: out={comp.getoutput()}, children={ch_str}, parents={par_str}")

        # Show outputs
        if self.outputs:
            print("  OUTPUTS:")
            for pin in self.outputs:
                if isinstance(pin.children, list):
                    ch = [f"{c}" for c in pin.children if str(c) != 'Empty']
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = "None"
                print(f"    {pin.name}: out={pin.getoutput()}, from={ch_str}")

        print("  " + "-" * 40)

