
from __future__ import annotations
from Gates import Gate, InputPin, OutputPin, Profile, pop, hide_profile, reveal_profile
from Const import IC_ID, INPUT_PIN_ID, OUTPUT_PIN_ID, NAME, CUSTOM_NAME, CODE, COMPONENTS, MAP, INPUTLIMIT, SOURCES
from collections import deque

class IC:
    """Integrated Circuit: a custom chip made of other gates."""
    __slots__ = [
        'inputs', 'internal', 'outputs',
        'name', 'custom_name', 'code', 'map',
        'id', 'counter',
    ]

    def __init__(self):
        self.id: int = IC_ID
        self.counter: int = 0
        self.inputs: list[InputPin] = []
        self.internal: list = []
        self.outputs: list[OutputPin] = []
        self.name: str = 'IC'
        self.custom_name: str = ''
        self.code: tuple = ()
        self.map: list = []

    def __repr__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def getcomponent(self, choice: int):
        """Create a sub-component inside this IC."""
        from Store import get
        gt = get(choice)
        if gt:
            self.counter += 1
            if gt.id == INPUT_PIN_ID:
                rank = len(self.inputs)
                self.inputs.append(gt)
                gt.name = 'in-' + str(len(self.inputs))
            elif gt.id == OUTPUT_PIN_ID:
                rank = len(self.outputs)
                self.outputs.append(gt)
                gt.name = 'out-' + str(len(self.outputs))
            else:
                rank = len(self.internal)
                self.internal.append(gt)
                gt.name = gt.__class__.__name__ + '-' + str(len(self.internal))
            gt.code = (choice, rank, self.code)
        return gt

    def addgate(self, source):
        """Add an existing gate into this IC."""
        if source.id == INPUT_PIN_ID:
            rank = len(self.inputs)
            self.inputs.append(source)
            source.name = 'in-' + str(len(self.inputs))
        elif source.id == OUTPUT_PIN_ID:
            rank = len(self.outputs)
            self.outputs.append(source)
            source.name = 'out-' + str(len(self.outputs))
        else:
            rank = len(self.internal)
            self.internal.append(source)
            source.name = source.__class__.__name__ + '-' + str(len(self.internal))
        source.code = (source.code[0], rank, self.code)

    def configure(self, dictionary: list):
        """Set up the IC from a saved plan."""
        pseudo = {}
        pseudo[('X', 'X')] = None
        self.custom_name = dictionary[CUSTOM_NAME]
        self.map = dictionary[MAP]
        self.load_components(dictionary, pseudo)
        self.clone(pseudo)

    def decode(self, code: list) -> tuple:
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def load_components(self, dictionary: list, pseudo: dict):
        """Instantiate components from the plan."""
        for comp_code in dictionary[COMPONENTS]:
            gate = self.getcomponent(comp_code[0])
            pseudo[self.decode(comp_code)] = gate

    def create_data(self):
        dictionary = [            
            self.custom_name,
            self.code,
            [],
            [],
        ]
        queue=[]
        index=0
        size=0
        for gate in self.outputs+self.inputs:
            gate.scheduled=True
            queue.append(gate)
        size=len(queue)
        index=len(self.outputs)
        while index<size:
            gate = queue[index]
            if gate.id == INPUT_PIN_ID and gate.sources[0] is not None:
                for profile in gate.hitlist:
                    target = profile.target
                    target.sources[profile.index] = gate.sources[0]
            elif gate.id==OUTPUT_PIN_ID and gate.hitlist:
                for profile in gate.hitlist:
                    target = profile.target
                    target.sources[profile.index] = gate.sources[0]
            for profile in gate.hitlist:
                target = profile.target
                if not target.scheduled:
                    target.scheduled = True
                    queue.append(target)
                    size+=1
            index+=1
        pins=len(self.inputs)+len(self.outputs)
        for index in range(pins):
            gate = queue[index]
            dictionary[COMPONENTS].append(gate.code)
            dictionary[MAP].append(gate.json_data())
        for index in range(pins,size):
            gate = queue[index]
            if gate.id >= INPUT_PIN_ID:
                continue
            dictionary[COMPONENTS].append(gate.code)
            dictionary[MAP].append(gate.json_data())
        return dictionary

    def json_data(self) -> list:
        dictionary = [            
            self.custom_name,
            self.code,
            [i.code for i in self.outputs+self.inputs+self.internal],
            [i.json_data() for i in self.outputs+self.inputs+self.internal],
        ]
        return dictionary

    def clone(self, pseudo: dict):
        """Wire up all sub-components."""
        for i in self.map:
            code = self.decode(i[CODE])
            gate = pseudo[code]
            gate.clone(i, pseudo)

    def load_to_cluster(self, cluster: set):
        cluster.add(self.outputs+self.inputs+self.internal)

    def copy_data(self, cluster: set) -> list:
        dictionary = [            
            self.custom_name,
            self.code,
            [i.code for i in self.outputs+self.inputs+self.internal],
            [i.copy_data(cluster) for i in self.outputs+self.inputs+self.internal],
        ]
        return dictionary
        

    def implement(self, pseudo: dict):
        """Build connections from the map (paste path)."""
        for i in self.map:
            code = self.decode(i[CODE])
            gate = pseudo[code]
            gate.clone(i, pseudo)

    def hide(self):
        """Disconnect output pins from targets, input pins from sources."""
        for pin_out in self.outputs:
            for profile in pin_out.hitlist:
                hide_profile(profile)

        for pin_in in self.inputs:
            for index, source in enumerate(pin_in.sources):
                if source is not None:
                    pop(source.hitlist, pin_in, index)

    def reveal(self):
        """Reconnect input/output pins."""
        for pin_in in self.inputs:
            source = pin_in.sources[0]
            if source is not None:
                source.hitlist.append(Profile(pin_in, 0, source.output))
            pin_in.process()

        for pin_out in self.outputs:
            for profile in pin_out.hitlist:
                reveal_profile(profile, pin_out)

    def reset(self):
        for i in self.inputs + self.internal + self.outputs:
            if i.id != IC_ID:
                i.reset()
            else:
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

        if self.inputs:
            print("  INPUTS:")
            for pin in self.inputs:
                targets = [str(p.target) for p in pin.hitlist]
                print(f"    {pin.name}: out={pin.getoutput()}, to={', '.join(targets) if targets else 'None'}")

        if self.internal:
            print("  INTERNAL:")
            for comp in self.internal:
                if comp.id == IC_ID:
                    comp.info()
                else:
                    if isinstance(comp.sources, list):
                        ch = [f"[{i}]:{c}" for i, c in enumerate(comp.sources) if c is not None]
                        ch_str = ", ".join(ch) if ch else "None"
                    else:
                        ch_str = f"val:{comp.sources}"
                    tgt = [str(p.target) for p in comp.hitlist]
                    tgt_str = ", ".join(tgt) if tgt else "None"
                    print(f"    {comp.name}: out={comp.getoutput()}, sources={ch_str}, targets={tgt_str}")

        if self.outputs:
            print("  OUTPUTS:")
            for pin in self.outputs:
                if isinstance(pin.sources, list):
                    ch = [f"{c}" for c in pin.sources if c is not None]
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = "None"
                print(f"    {pin.name}: out={pin.getoutput()}, from={ch_str}")

        print("  " + "-" * 40)
