
import json
from Gates import Gate, Variable, Profile, hide_profile, reveal_profile
from Const import (
    TOTAL, DESIGN, SIMULATE, set_MODE,
    ERROR, UNKNOWN, HIGH, LOW,
    IC_ID, AND_ID, NAND_ID, OR_ID, NOR_ID, XOR_ID, XNOR_ID, NOT_ID,
    VARIABLE_ID, INPUT_PIN_ID, OUTPUT_PIN_ID, PROBE_ID,
)
import Const
from IC import IC
from Store import get

def turnoff(gate: Gate, queue: list, wave_limit: int):
    """Set all targets to UNKNOWN and propagate."""
    for profile in gate.hitlist:
        target = profile.target
        if target is not gate:
            target.output = UNKNOWN
            propagate(target, queue, wave_limit)

def burn(origin: Gate, queue: list):
    """Error propagation — flood-fill ERROR through the graph."""
    index = 0
    size = 1
    queue.append(origin)
    while index < size:
        while index < size:
            gate = queue[index]
            gate.scheduled = False
            gate.output = ERROR
            for profile in gate.hitlist:
                if profile.output != ERROR:
                    target = profile.target
                    if target.inputlimit != 1:
                        target.book[profile.output] -= 1
                        target.book[ERROR] += 1
                    profile.output = ERROR
                    if target.output != ERROR:
                        queue.append(target)
            index += 1
        size = len(queue)
    queue.clear()


def propagate(origin: Gate, queue: list, wave_limit: int):
    """The core reactor propagation loop.
    Single queue, index-based traversal, inline gate evaluation, scheduled flag."""

    if origin.output == ERROR:
        burn(origin, queue)
        return

    queue.append(origin)
    counter = 0
    index = 0
    size = 1

    while index < size:
        if counter > wave_limit:
            queue.clear()
            burn(gate, queue)
            return
        counter += 1

        while index < size:
            gate = queue[index]
            gate.scheduled = False
            new_output = gate.output

            for profile in gate.hitlist:
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
                            queue.append(target)

                    profile.output = new_output

            index += 1
        size = len(queue)
    queue.clear()


# ─── Circuit ──────────────────────────────────────────────────────

class Circuit:
    """The main circuit board."""
    __slots__ = [
        'objlist', 'canvas', 'varlist', 'iclist', 'copydata',
        'counter', 'queue',
    ]

    def __init__(self):
        self.objlist: list[list] = [[] for _ in range(TOTAL)]
        self.canvas: list = []
        self.varlist: list[Variable] = []
        self.iclist: list[IC] = []
        self.copydata: list = []
        self.counter: int = 0
        self.queue: list = []

    def __repr__(self):
        return 'Circuit'

    def getcomponent(self, choice: int):
        """Create and register a new component."""
        self.counter += 1
        gt = get(choice)
        if gt:
            rank = len(self.objlist[choice])
            self.objlist[choice].append(gt)
            gt.code = (choice, rank)
            name = gt.__class__.__name__

            if name == 'Variable':
                gt.name = chr(ord('A') + (rank) % 26) + str((rank + 1) // 26)
            elif name == 'InputPin':
                gt.name = 'IN-' + str(len(self.objlist[choice]))
            elif name == 'OutputPin':
                gt.name = 'OUT-' + str(len(self.objlist[choice]))
            else:
                gt.name = name + '-' + str(len(self.objlist[choice]))

            if gt.id == VARIABLE_ID:
                self.varlist.append(gt)
            if gt.id == IC_ID:
                self.iclist.append(gt)
            self.canvas.append(gt)
        return gt

    def getobj(self, code: tuple):
        return self.objlist[code[0]][code[1]]

    def delobj(self, code: tuple):
        self.objlist[code[0]][code[1]] = None

    def listComponent(self):
        for i, gate in enumerate(self.canvas):
            print(f'{i}. {gate}')

    def listVar(self):
        for i, gate in enumerate(self.varlist):
            print(f'{i}. {gate}')

    def setlimits(self, gate: Gate, size: int) -> bool:
        return gate.setlimits(size)

    def connect(self, target: Gate, source: Gate, index: int):
        """Connect source -> target at pin index."""
        prev = target.output
        target.connect(source, index)
        if prev != target.output:
            propagate(target, self.queue, self.counter)

    def toggle(self, target: Variable, value: int):
        """Switch a variable on/off."""
        if value != target.output:
            target.value = value
            target.output = value if Const.MODE == SIMULATE else UNKNOWN
            propagate(target, self.queue, self.counter)

    def disconnect(self, target: Gate, index: int):
        """Disconnect at pin index."""
        prev = target.output
        target.disconnect(index)
        if prev != target.output:
            propagate(target, self.queue, self.counter)

    def hideComponent(self, gate):
        """Soft delete — disconnect and remove from view."""
        if gate.id == IC_ID:
            gate.hide()
            for pin in gate.outputs:
                turnoff(pin, self.queue, self.counter)
            self.counter -= gate.counter
        else:
            gate.hide()
            turnoff(gate, self.queue, self.counter)
        self.counter -= 1

        if gate in self.varlist:
            self.varlist.remove(gate)
        if gate in self.iclist:
            self.iclist.remove(gate)
        self.canvas.remove(gate)

    def terminate(self, code):
        """Hard delete."""
        gate = self.getobj(code)
        if gate.id == VARIABLE_ID:
            self.varlist.remove(gate)
        elif gate.id == IC_ID:
            self.counter -= gate.counter
            self.iclist.remove(gate)
        self.counter -= 1
        self.canvas.remove(gate)
        self.delobj(code)

    def renewComponent(self, gate):
        """Bring a hidden component back."""
        if gate.id == IC_ID:
            gate.reveal()
            self.counter += gate.counter
            for pin in gate.outputs:
                propagate(pin, self.queue, self.counter)
        else:
            gate.reveal()
            propagate(gate, self.queue, self.counter)
        self.counter += 1

        if gate.id == VARIABLE_ID:
            self.varlist.append(gate)
        self.canvas.append(gate)
        if gate.id == IC_ID:
            self.iclist.append(gate)

    def output(self, gate: Gate):
        print(f'{gate} output is {gate.getoutput()}')

    def truthTable(self) -> str:
        """Generate a truth table."""
        if not self.varlist:
            return ''

        gate_list = []
        for item in self.canvas:
            gate_type = item.id
            if gate_type == VARIABLE_ID:
                continue
            elif gate_type != IC_ID:
                gate_list.append(item)
            else:
                for pin in item.outputs:
                    gate_list.append(pin)

        n = len(self.varlist)
        rows_count = 1 << n

        var_names = [v.name for v in self.varlist]
        gate_names = [v.name for v in gate_list]
        all_names = var_names + gate_names

        col_width = max((len(name) for name in all_names), default=4) + 2

        header_parts = [name.center(col_width) for name in all_names]
        header = " | ".join(header_parts)
        separator = "─" * len(header)

        Table = [separator + '\n', header + '\n', separator + '\n']

        for i in range(rows_count):
            inputs = []
            for j in range(n):
                var = self.varlist[j]
                bit = 1 if (i & (1 << (n - j - 1))) else 0
                if bit != var.output:
                    var.output = bit
                    propagate(var, self.queue, self.counter)
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

        gates = [c for c in self.canvas if c.id != IC_ID]
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

        if self.iclist:
            print("\n" + "=" * 90)
            print(" " * 40 + "IC STATUS")
            print("=" * 90)
            for ic in self.iclist:
                print(f"\n  IC: {ic.name} (Code: {ic.code})")
                print("  " + "-" * 50)

                if ic.inputs:
                    print("  INPUT PINS:")
                    for pin in ic.inputs:
                        targets = [f"{p.target} " for p in pin.hitlist]
                        print(f"    {pin.name}: out={pin.getoutput()}, to={', '.join(targets) if targets else 'None'}")

                if ic.outputs:
                    print("  OUTPUT PINS:")
                    for pin in ic.outputs:
                        ch = [f"{c}" for c in pin.sources if c is not None] if isinstance(pin.sources, list) else []
                        print(f"    {pin.name}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}")

        print("\n" + "=" * 90)

    def writetojson(self, location: str):
        circuit = [gate.json_data() for gate in self.canvas]
        with open(location, 'w') as file:
            json.dump(circuit, file)

    def decode(self, code) -> tuple:
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    def readfromjson(self, location: str):
        with open(location, 'r') as file:
            circuit = json.load(file)
        if isinstance(circuit, dict):
            return
        pseudo = {}
        pseudo[('X', 'X')] = None
        for i in circuit:
            code = self.decode(i["code"])
            gate = self.getcomponent(code[0])
            if gate.id == IC_ID:
                gate.custom_name = i["custom_name"]
                gate.map = i["map"]
                gate.load_components(i, pseudo)
            pseudo[code] = gate

        for gate_dict in circuit:
            code = self.decode(gate_dict["code"])
            gate = pseudo[code]
            if gate.id == IC_ID:
                gate.clone(pseudo)
                self.counter += gate.counter
            else:
                gate.clone(gate_dict, pseudo)

    def save_as_ic(self, location: str, ic_name: str = "IC"):
        if self.varlist:
            print('Delete Variables First')
            return
        lst = list(self.canvas)
        myIC = self.getcomponent(IC_ID)
        myIC.name = ic_name
        myIC.custom_name = ic_name
        for component in lst:
            myIC.addgate(component)
        with open(location, 'w') as file:
            json.dump(myIC.json_data(), file)
        self.clearcircuit()
        self.getIC(location)

    def getIC(self, location: str):
        myIC = self.getcomponent(IC_ID)
        with open(location, 'r') as file:
            crct = json.load(file)
            if isinstance(crct, dict) and "map" in crct:
                myIC.configure(crct)
                self.counter += myIC.counter
                return myIC
            else:
                print('Cannot Convert to IC')
                return None

    def rank_reset(self):
        for i in range(TOTAL):
            while self.objlist[i] and self.objlist[i][-1] is None:
                self.objlist[i].pop()

    def clearcircuit(self):
        for i in range(TOTAL):
            self.objlist[i].clear()
        self.varlist.clear()
        self.canvas.clear()
        self.iclist.clear()
        self.counter = 0

    def copy(self, components: list):
        if not components:
            return
        self.copydata = []
        cluster = set()
        for i in components:
            i.load_to_cluster(cluster)
        for i in components:
            self.copydata.append(i.copy_data(cluster))
        with open('clipboard.json', 'w') as file:
            json.dump(self.copydata, file)
        self.copydata = [i.code for i in components]

    def paste(self):
        with open('clipboard.json', 'r') as file:
            circuit = json.load(file)
        pseudo = {}
        pseudo[('X', 'X')] = None
        new_items = []
        for i in circuit:
            code = self.decode(i["code"])
            gate = self.getcomponent(code[0])
            new_items.append(gate.code)
            if gate.id == IC_ID:
                gate.custom_name = i["custom_name"]
                gate.map = i["map"]
                gate.load_components(i, pseudo)
            pseudo[code] = gate

        for gate_dict in circuit:
            code = self.decode(gate_dict["code"])
            gate = pseudo[code]
            if gate.id == IC_ID:
                gate.implement(pseudo)
                self.counter += gate.counter
            elif gate:
                gate.clone(gate_dict, pseudo)
        return new_items

    def simulate(self, Mode: int):
        """Run the simulation."""
        set_MODE(Mode)
        for variable in self.varlist:
            variable.output = variable.value
            propagate(variable, self.queue, self.counter)

    def reset(self):
        """Reset to design mode."""
        set_MODE(DESIGN)
        for i in self.canvas:
            if i.id != IC_ID:
                i.reset()
            else:
                i.reset()
