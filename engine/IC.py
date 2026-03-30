
from __future__ import annotations
from Gates import Gate, Profile, pop, hide_profile, reveal_profile
from Const import IC_ID, INPUT_PIN_ID, OUTPUT_PIN_ID, NAME, CUSTOM_NAME, CODE, COMPONENTS, MAP, INPUTLIMIT, SOURCES, TAG, DESCRIPTION

class IC:
    """Integrated Circuit: a custom chip made of other gates."""
    __slots__ = [
        'inputs', 'internal', 'outputs',
        'codename', 'custom_name', 'code', 'map',
        'id', 'counter', 'tag', 'description',
    ]

    def __init__(self,id:int,name:str):
        self.id: int = IC_ID
        self.counter: int = 0
        self.inputs: list[In] = []
        self.internal: list = []
        self.outputs: list[Out] = []
        self.codename: str = 'IC'
        self.custom_name: str = ''
        self.code: tuple = ()
        self.map: list = []
        self.tag=''
        self.description=''

    def __repr__(self):
        return self.custom_name+'-'+self.codename

    def __str__(self):
        return self.custom_name+'-'+self.codename

    def getcomponent(self, choice: int):
        """Create a sub-component inside this IC."""
        from Store import get
        gt = get(choice)
        if gt:
            self.counter += 1
            if gt.id == INPUT_PIN_ID:
                rank = len(self.inputs)
                self.inputs.append(gt)
                gt.codename = 'in-' + str(len(self.inputs))
            elif gt.id == OUTPUT_PIN_ID:
                rank = len(self.outputs)
                self.outputs.append(gt)
                gt.codename = 'out-' + str(len(self.outputs))
            else:
                rank = len(self.internal)
                self.internal.append(gt)
                gt.codename = gt.codename+ '-' + str(len(self.internal))
            gt.code = (choice, rank, self.code)
        return gt

    def addgate(self, source):
        """Add an existing gate into this IC."""
        if source.id == INPUT_PIN_ID:
            rank = len(self.inputs)
            self.inputs.append(source)
            source.codename = 'in-' + str(len(self.inputs))
        elif source.id == OUTPUT_PIN_ID:
            rank = len(self.outputs)
            self.outputs.append(source)
            source.codename = 'out-' + str(len(self.outputs))
        else:
            rank = len(self.internal)
            self.internal.append(source)
            source.codename = source.codename+ '-' + str(len(self.internal))
        source.code = (source.code[0], rank, self.code)

    def configure(self, dictionary: list):
        """Set up the IC from a saved plan."""
        pseudo = {}
        pseudo[('X', 'X')] = None
        self.custom_name = dictionary[CUSTOM_NAME]
        self.map = dictionary[MAP]
        self.tag=dictionary[TAG]
        self.description=dictionary[DESCRIPTION]
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

   

    def full_data(self) -> list:
        dictionary = [            
            self.custom_name,
            self.code,
            [],
            [],
            self.tag,
            self.description
        ]
        for i in self.inputs+self.outputs+self.internal:
            dictionary[COMPONENTS].append(i.code)
            dictionary[MAP].append(i.full_data())
        return dictionary

    def partial_data(self):
        dictionary=[
            self.custom_name,
            self.code,
            [],
            [],
            self.tag,
            self.description
        ]
        for i in self.inputs+self.outputs+self.internal:
            dictionary[COMPONENTS].append(i.code)
            dictionary[MAP].append(i.partial_data())
        return dictionary

    def clone(self, pseudo: dict):
        """Wire up all sub-components."""
        for i in self.map:
            code = self.decode(i[CODE])
            gate = pseudo[code]
            gate.clone(i, pseudo)

    def load_to_cluster(self, cluster: list):
        for i in self.inputs+self.outputs+self.internal:
            cluster.append(i)
            i.mark=True   

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
        print(f"\n  IC: {self.codename} (Code: {self.code})")
        print("  " + "-" * 40)

        if self.inputs:
            print("  INPUTS:")
            for pin in self.inputs:
                targets = [str(p.target) for p in pin.hitlist]
                print(f"    {pin.codename}: out={pin.getoutput()}, to={', '.join(targets) if targets else 'None'}")

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
                    print(f"    {comp.codename}: out={comp.getoutput()}, sources={ch_str}, targets={tgt_str}")

        if self.outputs:
            print("  OUTPUTS:")
            for pin in self.outputs:
                if isinstance(pin.sources, list):
                    ch = [f"{c}" for c in pin.sources if c is not None]
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = "None"
                print(f"    {pin.codename}: out={pin.getoutput()}, from={ch_str}")

        print("  " + "-" * 40)
