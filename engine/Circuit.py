
import orjson
import os
from Gates import Gate, Variable, Profile, hide_profile, reveal_profile
from Const import *
import Const
from IC import IC
from Store import get

# ─── Circuit ──────────────────────────────────────────────────────

class Circuit:
    """The main circuit board."""
    __slots__ = [
        'objlist', 'copydata',
        'counter', 'queue',
        'eval_count'
    ]

    def __init__(self):
        set_MODE(DESIGN)
        self.objlist: list[list] = [[] for _ in range(TOTAL)]
        self.copydata: list = []
        self.counter: int = 0
        self.queue: list = [[None] * LIMIT, [None] * LIMIT]  # double buffer: fixed [2][LIMIT]
        self.eval_count = 0

    def set_UI_MODE(self, mode):
        global UI_MODE
        UI_MODE = mode

    def __repr__(self):
        return 'Circuit'

    def getcomponent(self, choice: int):
        """Create and register a new component."""
        gt = get(choice)
        if gt:
            self.counter += 1
            rank = len(self.objlist[choice])
            self.objlist[choice].append(gt)
            gt.code = (choice, rank)
            name = gt.__class__.__name__
            if Const.DEBUG:
                if gt.id == VARIABLE_ID:
                    gt.codename = chr(ord('A') + (rank) % 26) + str((rank + 1) // 26)
                else:
                    gt.codename = gt.codename + '-' + str(len(self.objlist[choice]))
            if gt.id == VARIABLE_ID:
                gt.output = LOW if get_MODE() != DESIGN else UNKNOWN
        return gt

    def getobj(self, code: tuple):
        return self.objlist[code[0]][code[1]]

    def delobj(self, gate:Gate):
        if gate.id == IC_ID:
            self.counter -= gate.counter
        self.counter -= 1
        self.objlist[gate.code[0]][gate.code[1]]=None

    def renewobj(self,gate:Gate):
        if gate.id == IC_ID:
            self.counter += gate.counter
        self.counter += 1
        self.objlist[gate.code[0]][gate.code[1]]=gate

    def get_components(self) -> list:
        return [gate for sublist in self.objlist for gate in sublist if gate is not None]

    def get_variables(self) -> list:
        return [gate for gate in self.objlist[VARIABLE_ID] if gate is not None]

    def get_ics(self) -> list:
        return [gate for gate in self.objlist[IC_ID] if gate is not None]

    def listComponent(self):
        for i, gate in enumerate(self.get_components()):
            print(f'{i}. {gate}')

    def listVar(self):
        for i, gate in enumerate(self.get_variables()):
            print(f'{i}. {gate}')

    def setlimits(self, gate: Gate, size: int) -> bool:
        return gate.setlimits(size)

    def connect(self, target: Gate, source: Gate, index: int):
        """Connect source -> target at pin index."""
        prev = target.output
        target.connect(source, index)
        if prev != target.output:
            self.propagate(target)

    def toggle(self, target: Variable, value: int):
        """Switch a variable on/off."""
        if value != target.output:
            target.value = value
            target.output = value if get_MODE() == SIMULATE else UNKNOWN
            self.propagate(target)

    def disconnect(self, target: Gate, index: int):
        """Disconnect at pin index."""
        prev = target.output
        target.disconnect(index)
        if prev != target.output:
            self.propagate(target)

    def hide(self, gatelist: list):
        """Soft delete — disconnect and remove from view."""
        for gate in gatelist:
            if gate.id == IC_ID:
                gate.hide()
            else:
                gate.hide()
            self.delobj(gate)

        for gate in gatelist:
            if gate.id == IC_ID:
                for pin in gate.outputs:
                    self.turnoff(pin)
            else:
                self.turnoff(gate)


    def reveal(self, gatelist: list):
        """Bring a hidden component back."""
        for gate in reversed(gatelist):
            if gate.id == IC_ID:
                gate.reveal()
            else:
                gate.reveal()
            self.renewobj(gate)

        for gate in reversed(gatelist):
            if gate.id == IC_ID:
                for pin in gate.outputs:
                    self.propagate(pin)
            else:
                self.propagate(gate)

    def output(self, gate: Gate):
        print(f'{gate} output is {gate.getoutput()}')

    def truthTable(self) -> str:
        """Generate a truth table."""
        variables = self.get_variables()
        if not variables:
            return ''

        gate_list = []
        for item in self.get_components():
            gate_type = item.id
            if gate_type == VARIABLE_ID:
                continue
            elif gate_type != IC_ID:
                gate_list.append(item)
            else:
                for pin in item.outputs:
                    gate_list.append(pin)

        n = len(variables)
        rows_count = 1 << n

        var_names = [v.codename for v in variables]
        gate_names = [v.codename for v in gate_list]
        all_names = var_names + gate_names

        col_width = max((len(name) for name in all_names), default=4) + 2

        header_parts = [name.center(col_width) for name in all_names]
        header = " | ".join(header_parts)
        separator = "─" * len(header)

        Table = [separator + '\n', header + '\n', separator + '\n']

        for i in range(rows_count):
            inputs = []
            for j in range(n):
                var = variables[j]
                bit = 1 if (i & (1 << (n - j - 1))) else 0
                if bit != var.output:
                    var.output = bit
                    self.propagate(var)
                inputs.append(str(bit))

            output_vals = [str(gate.getoutput()) for gate in gate_list]
            row_data = inputs + output_vals
            row_parts = [val.center(col_width) for val in row_data]
            row = " | ".join(row_parts)
            Table.append(row + '\n')

        self.simulate(SIMULATE)
        Table.append(separator + '\n')
        return "".join(Table)

    def diagnose(self):
        """Print a detailed report."""
        print("=" * 90)
        print(" " * 35 + "CIRCUIT DIAGNOSIS")
        print("=" * 90)

        gates = [c for c in self.get_components() if c.id != IC_ID]
        if gates:
            columns = [
                ("Component", 14),
                ("Sources", 28),
                ("Book[L,H,E,U]", 15),
                ("Targets", 25),
                ("Out", 6),
            ]
            total_width = sum(w for _, w in columns)
            fmt = "".join(f"{{:<{w}}}" for _, w in columns)

            print("\n" + fmt.format(*[n for n, _ in columns]))
            print("-" * total_width)

            for comp in gates:
                if isinstance(comp.sources, list):
                    ch = [f"[{i}]:{c}" for i, c in enumerate(comp.sources) if c is not None]
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = f"val:{comp.sources}"

                book = f"[{comp.book[0]},{comp.book[1]},{comp.book[2]},{comp.book[3]}]"

                tgt = [f"{p.target} " for p in comp.hitlist]
                tgt_str = ", ".join(tgt) if tgt else "None"

                ch_str = ch_str[:26] + ".." if len(ch_str) > 28 else ch_str
                tgt_str = tgt_str[:23] + ".." if len(tgt_str) > 25 else tgt_str

                print(fmt.format(str(comp), ch_str, book, tgt_str, str(comp.getoutput())))

            print("-" * total_width)

        ics = [c for c in self.objlist[IC_ID] if c is not None]
        if ics:
            print("\n" + "=" * 90)
            print(" " * 40 + "IC STATUS")
            print("=" * 90)
            for ic in ics:
                print(f"\n  IC: {repr(ic)} (Code: {ic.code})")
                print("  " + "-" * 50)

                if ic.inputs:
                    print("  INPUT PINS:")
                    for pin in ic.inputs:
                        ch = [f"{c}" for c in pin.sources if c is not None] if isinstance(pin.sources, list) else [f"val:{pin.sources}"]
                        targets = [f"{p.target} " for p in pin.hitlist]
                        print(f"    {repr(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}, to={', '.join(targets) if targets else 'None'}")

                if ic.outputs:
                    print("  OUTPUT PINS:")
                    for pin in ic.outputs:
                        ch = [f"{c}" for c in pin.sources if c is not None] if isinstance(pin.sources, list) else [f"val:{pin.sources}"]
                        targets = [f"{p.target} " for p in pin.hitlist]
                        print(f"    {repr(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}, to={', '.join(targets) if targets else 'None'}")

        print("\n" + "=" * 90)

    def writetojson(self, location: str):
        circuit = [gate.full_data() for gate in self.get_components()]
        with open(location, 'wb') as file:
            file.write(orjson.dumps(circuit))

    def decode(self, code) -> tuple:
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))
    def generate(self, circuit):
        pseudo = {}
        pseudo[('X', 'X')] = None
        for i in circuit:
            code = self.decode(i[CODE])
            gate = self.getcomponent(code[0])
            if gate.id == IC_ID:
                gate.custom_name = i[CUSTOM_NAME]
                gate.map = i[MAP]
                gate.tag = i[TAG]
                gate.description = i[DESCRIPTION]
                gate.load_components(i, pseudo)
            pseudo[code] = gate
        if get_MODE()!=DESIGN:
            self.simulate(SIMULATE)

        for gate_dict in circuit:
            code = self.decode(gate_dict[CODE])
            gate = pseudo[code]
            if gate.id == IC_ID:
                gate.clone(pseudo)
                self.counter += gate.counter
            else:
                gate.clone(gate_dict, pseudo)

    def readfromjson(self, location: str):
        with open(location, 'rb') as file:
            circuit = orjson.loads(file.read())
        if isinstance(circuit, dict):
            return
        self.generate(circuit)
        if get_MODE()!=DESIGN:
            self.simulate(SIMULATE)

    def transfer_info(self,gate:Gate, id:int):
        if id>=IC_ID or id<0:
            return
        real_source=[source for source in gate.sources if source is not None ]
        length=len(real_source)
        if not real_source or (length==1 and id!=VARIABLE_ID) or (length>1 and id<VARIABLE_ID):
            if gate.sources[0] is None:
                self.objlist[gate.code[0]][gate.code[1]]=None
                gate.id = id
                gate.code=(id,len(self.objlist[id]))
                self.objlist[id].append(gate)
                gate.process()
                self.propagate(gate)
    def build_ic(self):
        my_ic=self.getcomponent(IC_ID)
        queue=[]
        index=0
        size=0
        outputs=[i for i in self.objlist[OUTPUT_PIN_ID] if i is not None]
        inputs=[i for i in self.objlist[INPUT_PIN_ID] if i is not None]
        for gate in outputs+inputs:
            gate.scheduled=True
            queue.append(gate)
        size=len(queue)
        index=len(outputs)
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
        pins=len(inputs)+len(outputs)
        for input_pin in inputs:
            my_ic.addgate(input_pin)
        for output_pin in outputs:
            my_ic.addgate(output_pin)
        for index in range(pins,size):
            gate = queue[index]
            if gate.id >= INPUT_PIN_ID:
                continue
            my_ic.addgate(gate)
        my_ic.counter = size
        self.counter += size
        return self.objlist[IC_ID].pop()

    def ic_pin_change(self):
        for var in self.objlist[VARIABLE_ID]:
            if var is not None:
                var.code=(INPUT_PIN_ID,len(self.objlist[INPUT_PIN_ID]))
                var.id=INPUT_PIN_ID
                self.objlist[INPUT_PIN_ID].append(var)
        self.objlist[VARIABLE_ID].clear()
        for probe in self.objlist[PROBE_ID]:
            if probe is not None:
                probe.code=(OUTPUT_PIN_ID,len(self.objlist[OUTPUT_PIN_ID]))
                probe.id=OUTPUT_PIN_ID
                self.objlist[OUTPUT_PIN_ID].append(probe)
        self.objlist[PROBE_ID].clear()

    def reorder(self,gate:Gate|IC,index:int):
        lst=self.objlist[gate.id]
        if index<0 or index>=len(lst):
            return
        old=lst[index]
        lst[index]=gate
        lst[gate.code[1]]=old
        if old:old.code,gate.code=gate.code,old.code
        else:gate.code=(gate.code[0],index)

    def save_as_ic(self, location: str, ic_name: str = "IC", tag: str = "", description: str = "",components=None):
        '''sandboxing if components are given'''
        if components:
            crct=Circuit()
            crct.copydata = []
            cluster = []
            for i in components:
                i.load_to_cluster(cluster)
            for i in components:
                crct.copydata.append(i.partial_data())
            for i in cluster:
                i.scheduled=False
            crct.paste()
            crct.save_as_ic(location, ic_name, tag, description)
            return

        if len(self.objlist[VARIABLE_ID]) or len(self.objlist[PROBE_ID]):
            self.ic_pin_change()
        for gate in self.objlist[INPUT_PIN_ID]:
            if gate and gate.sources[0] is not None:
                raise ValueError('Input Pin has extra sources')
        for gate in self.objlist[OUTPUT_PIN_ID]:
            if gate and gate.hitlist:
                raise ValueError('Output Pin has extra targets')


        my_ic=self.build_ic()
        my_ic.custom_name = ic_name
        my_ic.tag = tag
        my_ic.description = description
        with open(location, 'wb') as file:
            file.write(orjson.dumps(my_ic.partial_data()))        
        self.clearcircuit() 

    

    def get_ic(self, location: str):
        with open(location, 'rb') as file:
             crct= orjson.loads(file.read())
        if isinstance(crct[COMPONENTS], list):
            return crct
        else:
            print('Cannot Convert to IC')
            return None
    
    def load_ic(self, crct: list):
        myIC = self.getcomponent(IC_ID)
        myIC.configure(crct)
        self.counter += myIC.counter
        return myIC

    def getIC(self, location: str):
        """Convenience alias: load a saved IC from file and return it."""
        crct = self.get_ic(location)
        if crct is None:
            return None
        return self.load_ic(crct)

    def rank_reset(self):
        for i in range(TOTAL):
            while self.objlist[i] and self.objlist[i][-1] is None:
                self.objlist[i].pop()

    def clearcircuit(self):
        for i in range(TOTAL):
            self.objlist[i].clear()
        self.counter = 0

    def copy(self, components: list):
        if not components:
            return
        self.copydata = []
        cluster = []
        for i in components:
            i.load_to_cluster(cluster)
        for i in components:
            self.copydata.append(i.partial_data())
        for i in cluster:
            i.scheduled=False

    def paste(self):
        circuit = self.copydata
        pseudo = {}
        pseudo[('X', 'X')] = None
        new_items = []
        for i in circuit:
            code = self.decode(i[CODE])
            gate = self.getcomponent(code[0])
            new_items.append(gate)
            if gate.id == IC_ID:
                gate.custom_name = i[CUSTOM_NAME]
                gate.map = i[MAP]
                gate.tag = i[TAG]
                gate.description = i[DESCRIPTION]
                gate.load_components(i, pseudo)
            pseudo[code] = gate

        for gate_dict in circuit:
            code = self.decode(gate_dict[CODE])
            gate = pseudo[code]
            if gate.id == IC_ID:
                gate.implement(pseudo)
                self.counter += gate.counter
            elif gate:
                gate.clone(gate_dict, pseudo)
        if get_MODE()!=DESIGN:
            self.simulate(SIMULATE)
        return new_items

    def simulate(self, Mode: int):
        """Run the simulation."""
        set_MODE(Mode)
        for variable in self.objlist[VARIABLE_ID]:
            if variable is not None:
                variable.output = variable.value
                self.propagate(variable)

    def reset(self):
        """Reset to design mode."""
        set_MODE(DESIGN)
        for i in self.get_components():
            if i.id != IC_ID:
                i.reset()
            else:
                i.reset()

    def turnoff(self, gate: Gate):
        """Set all targets to UNKNOWN and propagate."""
        for profile in gate.hitlist:
            target = profile.target
            if target is not gate:
                target.output = UNKNOWN
                self.propagate(target)

    def burn(self, read_buf: list, read_end: int, write_buf: list):
        """Error propagation — flood-fill ERROR through the graph."""
        write_end: int = 0
        while read_end > 0:
            for i in range(read_end):
                gate = read_buf[i]
                gate.scheduled = False
                gate.output = ERROR
                for profile in gate.hitlist:
                    if profile.output != ERROR:
                        target = profile.target
                        if target.inputlimit != 1:
                            target.book[profile.output] -= 1
                            target.book[ERROR] += 1
                        if target.output != ERROR:
                            write_buf[write_end] = target
                            write_end += 1
                        profile.output = ERROR
            if UI_MODE:
                for i in range(read_end):
                    gate = read_buf[i]
                    for listener in gate.listener:
                        listener(gate.output)
            read_buf, write_buf = write_buf, read_buf
            read_end, write_end = write_end, 0

    def propagate(self, origin: Gate):
        """Double-buffer, fixed-size queue — mirrors reactor's queue[2][LIMIT] pattern."""
        read_buf: list = self.queue[0]
        write_buf: list = self.queue[1]
        read_buf[0] = origin
        read_end: int = 1
        write_end: int = 0
        counter: int = 0
        if origin.output == ERROR:
            self.burn(read_buf, read_end, write_buf)
            return

        while read_end > 0:
            if counter > self.counter:
                self.burn(read_buf, read_end, write_buf)
                return
            counter += 1

            for i in range(read_end):
                gate = read_buf[i]
                gate.scheduled = False
                new_output = gate.output
                for profile in gate.hitlist:
                    self.eval_count += 1
                    profile_output = profile.output
                    if profile_output != new_output:
                        target = profile.target
                        gate_type = target.id
                        limit = target.inputlimit

                        if limit == 1:
                            if gate_type == NOT_ID and new_output != UNKNOWN:
                                target_output = new_output ^ 1
                            else:
                                target_output = new_output
                        else:
                            book = target.book
                            book[profile_output] -= 1
                            book[new_output] += 1
                            high = book[HIGH]
                            low = book[LOW]
                            realsource = high + low
                            if realsource == limit or (realsource and realsource + book[UNKNOWN] + book[ERROR] == limit):
                                if gate_type <= NAND_ID:
                                    target_output = int(low == 0)
                                elif gate_type <= NOR_ID:
                                    target_output = int(high > 0)
                                else:
                                    target_output = high & 1
                                target_output ^= (gate_type & 1)
                            else:
                                target_output = UNKNOWN

                        if target_output != target.output:
                            target.output = target_output
                            if not target.scheduled:
                                target.scheduled = True
                                write_buf[write_end] = target
                                write_end += 1

                        profile.output = new_output

            if UI_MODE:
                for i in range(read_end):
                    gate = read_buf[i]
                    for listener in gate.listener:
                        listener(gate.output)
            read_buf, write_buf = write_buf, read_buf
            read_end, write_end = write_end, 0

