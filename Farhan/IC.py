from __future__ import annotations
from Gates import Gate, InputPin, OutputPin, Nothing


class IC:
    # Integrated Circuit: a custom chip made of other gates
    # It acts like a black box with inputs and outputs
    __slots__=['inputs','internal','outputs','name','custom_name','code','map']
    
    def __init__(self):
        self.inputs: list[InputPin] = []
        self.internal: list[Gate|IC] = []
        self.outputs: list[OutputPin] = []

        self.name = 'IC'
        self.custom_name = ''
        self.code = ''

        self.map = {}

    def __repr__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.name if self.custom_name == '' else self.custom_name

    # helps created parts inside the IC
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

    def addgate(self, source: Gate | OutputPin | InputPin):

        if isinstance(source, InputPin):
            rank = len(self.inputs)
            self.inputs.append(source)
            source.name = 'in-'+str(len(self.inputs))
        elif isinstance(source, OutputPin):
            rank = len(self.outputs)
            self.outputs.append(source)
            source.name = 'out-'+str(len(self.outputs))
        else:
            rank = len(self.internal)
            self.internal.append(source)
            source.name = source.__class__.__name__+'-'+str(len(self.internal))
        source.code = (source.code[0], rank, self.code)

    # sets up the IC from a saved plan
    def configure(self, dictionary):
        pseudo = {}
        pseudo[('X', 'X')] = Nothing
        self.custom_name=dictionary["custom_name"]
        self.map = dictionary["map"]
        self.load_components(dictionary, pseudo)
        self.clone(pseudo)

    def decode(self, code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    # brings the components to life based on the plan
    def load_components(self, dictionary, pseudo):
        # generate all the necessary components
        for code in dictionary["components"]:
            gate = self.getcomponent(code[0])
            pseudo[self.decode(code)] = gate

    # prepares data to be saved to file
    def json_data(self):
        dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
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
            "custom_name": self.custom_name,
            "code": self.code,
            "components": [gate.code for gate in self.internal+self.inputs+self.outputs],
            "map": []
        }
        for i in self.internal+self.inputs+self.outputs:
            dictionary["map"].append(i.copy_data(cluster))
        return dictionary

    # builds the connections based on the map
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

    # disconnects internal logic (used when deleting)
    def hide(self):
        for pin in self.outputs:
            for target, infolist in pin.targets.items():
                for i in infolist[0]:
                    target.sources[i]=Nothing
                    target.book[infolist[1]]-=1
                    target.process()
            for target, infolist in pin.targets.items():
                target.propagate()
        for pin in self.inputs:
            for source in pin.sources:
                source.targets.pop(pin)

    # reconnects internal logic
    def reveal(self):
        for pin in self.outputs:
            for target, infolist in pin.targets.items():
                for i in infolist[0]:
                    target.sources[i]=pin
                    target.book[infolist[1]]+=1
                    target.process()

            for target, infolist in pin.targets.items():
                target.propagate()
        for pin in self.inputs:
            for index, source in enumerate(pin.sources):
                if pin not in source.targets:
                    source.targets[pin] = [set(), source.output]
                source.targets[pin][0].add(index)

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
                targets = [str(p) for p in pin.targets.keys()]
                print(f"    {pin.name}: out={pin.getoutput()}, to={', '.join(targets) if targets else 'None'}")

        # Show internal components
        if self.internal:
            print("  INTERNAL:")
            for comp in self.internal:
                if isinstance(comp, IC):
                    comp.info()
                else:
                    # Sources (list with indices)
                    if isinstance(comp.sources, list):
                        ch = [f"[{i}]:{c}" for i, c in enumerate(comp.sources) if str(c) != 'Empty']
                        ch_str = ", ".join(ch) if ch else "None"
                    else:
                        ch_str = f"val:{comp.sources}"
                    # Targets
                    tgt = [str(p) for p in comp.targets.keys()]
                    tgt_str = ", ".join(tgt) if tgt else "None"
                    print(f"    {comp.name}: out={comp.getoutput()}, sources={ch_str}, targets={tgt_str}")

        # Show outputs
        if self.outputs:
            print("  OUTPUTS:")
            for pin in self.outputs:
                if isinstance(pin.sources, list):
                    ch = [f"{c}" for c in pin.sources if str(c) != 'Empty']
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = "None"
                print(f"    {pin.name}: out={pin.getoutput()}, from={ch_str}")

        print("  " + "-" * 40)

