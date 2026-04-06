
import orjson
import os
from Gates import Gate, Variable, Profile, hide_profile, reveal_profile
from Const import *
import Const
from IC import IC
from Store import get, reset_loc
from collections import deque
import asyncio
import time
import heapq

Global_delay=[2,0,3,1,4,5,0,0,0,0,0]
# ─── Circuit ──────────────────────────────────────────────────────
class Task:
    __slots__=['gate','time','location']
    def __init__(self,gate:Gate,time:int,location:int):
        self.gate=gate
        self.time=time
        self.location=location
    def __lt__(self,other):
        if self.time==other.time:
            return self.location<other.location
        return self.time<other.time

class Circuit:
    """The main circuit board."""
    __slots__ = [
        'objlist', 'copydata',
        'counter', 'queue',
        'eval_count','time_queue','runner',
        'visual_queue','Global_Clock','oscillation_queue'
    ]

    def __init__(self):
        set_MODE(DESIGN)
        self.objlist: list[list] = [[] for _ in range(TOTAL)]
        self.copydata: list = []
        self.counter: int = 0
        self.queue: list = [[None] * LIMIT, [None] * LIMIT]  # double buffer: fixed [2][LIMIT]
        self.eval_count = 0
        self.time_queue: list[Task] = []
        self.oscillation_queue:deque[Gate]=deque()
        heapq.heapify(self.time_queue)
        self.runner=None
        self.visual_queue: deque[Gate] = deque()  # stores gate locations (ints) for dirty UI updates
        self.Global_Clock=0

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
            if Const.DEBUG:
                if gt.id == VARIABLE_ID:
                    gt.codename = chr(ord('A') + (rank) % 26) + str((rank + 1) // 26)
                else:
                    gt.codename = gt.codename + '-' + str(len(self.objlist[choice]))
            if gt.id == VARIABLE_ID:
                gt.output = LOW if get_MODE() != DESIGN else UNKNOWN
        return gt
    
    def optimize(self):
        pass
    
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
        prev = gate.output
        if gate.setlimits(size):
            if prev != gate.output:
                self.propagate(gate)
            return True
        return False

    def connect(self, target: Gate, source: Gate, index: int):
        """Connect source -> target at pin index."""
        prev = target.output
        target.connect(source, index)
        if prev != target.output:
            self.propagate(target)
    
    def set_timings(self, fps: float, ratio: float):
        Const.VISUALIZE = fps * (1 - ratio)
        Const.OSCILLATE = fps * ratio

    def toggle(self, target: Variable, value: int):
        """Switch a variable on/off."""
        if value != target.output:
            target.value = value
            target.output = value if get_MODE() != DESIGN else UNKNOWN
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
                    self.propagate(pin)
            else:
                self.propagate(gate)


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
                    if pin.output!=UNKNOWN:
                        self.propagate(pin)
            else:
                if gate.output!=UNKNOWN:
                    self.propagate(gate)

    def output(self, gate: Gate):
        print(f'{gate} output is {gate.getoutput()}')
  
    def table(self, variables: list, gate_list: list) -> list:
        """Generate a truth table for the circuit."""
        n = len(variables)
        rows_count = 1 << n
        raw_rows = [None] * rows_count
        gray = 0
        prev_gray = 0

        for i in range(rows_count):
            # Gray Code Sequence
            prev_gray = gray
            gray = i ^ (i >> 1)
            
            if i != 0:
                mask = prev_gray ^ gray
                changed_bit = mask.bit_length() - 1
                j = (n - 1) - changed_bit
                
                var = variables[j]
                bit = 1 if (gray & mask) else 0
                if bit != var.output:
                    var.output = bit
                    self.propagate(var)
            else:
                for j in range(n):
                    var = variables[j]
                    if var.output != 0:
                        var.output = 0
                        self.propagate(var)

            # Fast tuple extraction
            v_states = tuple(var.output for var in variables)
            g_states = tuple(gate.output for gate in gate_list)
            raw_rows[gray] = (v_states, g_states)

        return raw_rows

    def truthTable(self, variables: list = None, outputs: list = None) -> str:
        """Gray Code optimized Truth Table with sorting and string caching."""
      
        if variables is None:
            variables = self.get_variables()
        if not variables:
            return ''

        gate_list = []
        if outputs is not None:
            gate_list = outputs
        else:
            for item in self.get_components():
                gate_type = item.id
                if gate_type == VARIABLE_ID:
                    continue
                elif gate_type != IC_ID:
                    gate_list.append(item)
                else:
                    for pin in item.outputs:
                        gate_list.append(pin)

        raw_rows = self.table(variables, gate_list)

        # repr() gives the plain name (no ANSI codes) — used for width math and file output.
        # str() gives the colored name — used only for the printed header cells.
        var_reprs  = [repr(v) for v in variables]
        gate_reprs = [repr(v) for v in gate_list]
        all_reprs  = var_reprs + gate_reprs

        col_width = max((len(name) for name in all_reprs), default=4) + 2

        IN_MAP = [
            "0".center(col_width),
            "1".center(col_width)
        ]
        OUT_MAP = [
            "F".center(col_width),
            "T".center(col_width),
            "1/0".center(col_width),
            "X".center(col_width)
        ]

        # Header: colored names padded to col_width based on plain-name length.
        var_colored   = [str(v) for v in variables]
        gate_colored  = [str(v) for v in gate_list]
        all_colored   = var_colored + gate_colored
        header_parts  = [
            colored.center(col_width + len(colored) - len(plain))
            for colored, plain in zip(all_colored, all_reprs)
        ]
        header    = " | ".join(header_parts)
        separator = "─" * (col_width * len(all_reprs) + 3 * (len(all_reprs) - 1))
        mode=get_MODE()
        self.reset()
        self.simulate(mode)
        
        final_table_lines = [separator, header, separator]
        for v_states, g_states in raw_rows:
            row_parts = [IN_MAP[v] for v in v_states]
            row_parts.extend(OUT_MAP[g] for g in g_states)
            final_table_lines.append(" | ".join(row_parts))
            
        final_table_lines.append(separator)
        final_table_lines.append("")
        return "\n".join(final_table_lines)

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
                # Sources: repr() keeps column widths intact; no color needed for source names.
                if isinstance(comp.sources, list):
                    ch = [f"[{i}]:{repr(c)}" for i, c in enumerate(comp.sources) if c is not None]
                    ch_str = ", ".join(ch) if ch else "None"
                else:
                    ch_str = f"val:{comp.sources}"

                book = f"[{comp.book[0]},{comp.book[1]},{comp.book[2]}]"

                tgt = [f"{repr(p.target)} " for p in comp.hitlist]
                tgt_str = ", ".join(tgt) if tgt else "None"

                ch_str  = ch_str[:26]  + ".." if len(ch_str)  > 28 else ch_str
                tgt_str = tgt_str[:23] + ".." if len(tgt_str) > 25 else tgt_str

                # The component cell is colored via str(); the ANSI overhead is compensated
                # by widening only that cell so the fixed layout stays correct.
                name_plain  = repr(comp)
                name_colored = str(comp)
                extra = len(name_colored) - len(name_plain)   # bytes added by ANSI codes
                comp_col_w = columns[0][1] + extra
                row_fmt = f"{{:<{comp_col_w}}}" + "".join(f"{{:<{w}}}" for _, w in columns[1:])
                print(row_fmt.format(name_colored, ch_str, book, tgt_str, comp.getoutput()))

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
                        ch = [repr(c) for c in pin.sources if c is not None] if isinstance(pin.sources, list) else [f"val:{pin.sources}"]
                        targets = [repr(p.target) for p in pin.hitlist]
                        print(f"    {str(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}, to={', '.join(targets) if targets else 'None'}")

                if ic.outputs:
                    print("  OUTPUT PINS:")
                    for pin in ic.outputs:
                        ch = [repr(c) for c in pin.sources if c is not None] if isinstance(pin.sources, list) else [f"val:{pin.sources}"]
                        targets = [repr(p.target) for p in pin.hitlist]
                        print(f"    {str(pin)}: out={pin.getoutput()}, from={', '.join(ch) if ch else 'None'}, to={', '.join(targets) if targets else 'None'}")

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
        varlist=[]
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
            if gate.id==VARIABLE_ID:
                gate.output = UNKNOWN
                varlist.append(gate)
            pseudo[code] = gate
        
        for gate_dict in circuit:
            code = self.decode(gate_dict[CODE])
            gate = pseudo[code]
            if gate.id == IC_ID:
                gate.clone(pseudo)
                self.counter += gate.counter
            else:
                gate.clone(gate_dict, pseudo)
        if get_MODE()!=DESIGN:
            self.custom_simulate(varlist)

    def readfromjson(self, location: str):
        with open(location, 'rb') as file:
            circuit = orjson.loads(file.read())
        if isinstance(circuit, dict):
            return
        self.generate(circuit)

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
            gate.mark=True
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
                if not target.mark:
                    target.mark = True
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
            crct.copy(components)
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
            file.write(orjson.dumps(my_ic.full_data()))        
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
        reset_loc()   # reset shared location counter in Store

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
            i.mark=False

    def paste(self):
        circuit = self.copydata
        pseudo = {}
        pseudo[('X', 'X')] = None
        varlist=[]
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
            if gate.id==VARIABLE_ID:
                gate.value = UNKNOWN
                varlist.append(gate)
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
            self.custom_simulate(varlist)
        return new_items

    def simulate(self, Mode: int):
        """Run the simulation."""
        set_MODE(Mode)
        self.visual_queue_clear()
        self.eval_count=0
        if self.runner is not None and not self.runner.done():
            self.runner.cancel()
        self.runner=None
        for variable in self.objlist[VARIABLE_ID]:
            if variable is not None:
                variable.output = variable.value
                self.propagate(variable)

    def custom_simulate(self,gates:list[Gate]):
        for i in gates:
            i.output = i.value
            self.propagate(i)
        
    def reset(self):
        """Reset to design mode."""
        set_MODE(DESIGN)
        self.eval_count=0
        self.time_queue.clear()
        if self.runner is not None and not self.runner.done():
            self.runner.cancel()
        self.runner=None
        for i in self.get_components():
            i.reset()

    async def task_manager(self):
        while self.time_queue:
            n=len(self.time_queue)
            for _ in range(n):
                task = heapq.heappop(self.time_queue)
                self.complete_task(task)
            await asyncio.sleep(0.05)

    def complete_task(self, task: Task):
        if task.time > self.Global_Clock:
            self.Global_Clock = task.time
        gate = task.gate
        if not gate.update:
            self.visual_queue.append(gate)
            gate.update = True
        gate.scheduled = False
        new_output = gate.output
        for profile in gate.hitlist:
            self.eval_count += 1
            profile_output = profile.output
            if profile_output != new_output:
                target = profile.target
                gate_type = target.id
                limit = target.inputlimit

                if gate_type > VARIABLE_ID:
                    target_output = new_output if new_output > HIGH else new_output ^ (gate_type == NOT_ID)
                else:
                    book = target.book
                    book[profile_output] -= 1
                    book[new_output] += 1
                    if new_output > HIGH: target_output = new_output
                    else:
                        high = book[HIGH]
                        low = book[LOW]
                        realsource = high + low
                        if realsource == limit or (realsource and realsource + book[UNKNOWN] == limit):
                            if gate_type <= NAND_ID: target_output = int(low == 0) ^ (gate_type & 1)
                            elif gate_type <= NOR_ID: target_output = int(high > 0) ^ (gate_type & 1)
                            else: target_output = (high & 1) ^ (gate_type & 1)
                        else: target_output = UNKNOWN

                if target_output != target.output:
                    target.output = target_output
                    if not target.update:
                        target.update = True
                        self.visual_queue.append(target)
                    if not target.scheduled:
                        heapq.heappush(
                            self.time_queue,
                            Task(target, self.Global_Clock + Global_delay[target.id] + target.inputlimit, target.location)
                        )
                        target.scheduled = True
                profile.output = new_output
        # this is completely experimental don't write anything named CLKx for now, 
        # unless you want to use it as a auto-toggle
        # tests passed but needs much more polishing and improvements
        # just a work around, will be changed in the future
        if gate.custom_name == 'CLKx':
            gate.value ^= 1
            gate.output = gate.value
            delay = 100 # this is different for different circuitss
            heapq.heappush(
                self.time_queue,
                Task(gate, self.Global_Clock + delay + gate.inputlimit, gate.location)
            )
            gate.scheduled = True

    def propagate(self, origin: Gate):
        """Double-buffer, fixed-size queue — mirrors reactor's queue[2][LIMIT] pattern."""
        if Const.MODE==FLIPFLOP:
            if not origin.scheduled:
                heapq.heappush(self.time_queue,Task(origin,self.Global_Clock+Global_delay[origin.id]+origin.inputlimit,origin.location))
                origin.scheduled=True
            if self.runner is None or self.runner.done():
                self.runner=asyncio.create_task(self.task_manager())
            return

        read_buf: list = self.queue[0]
        write_buf: list = self.queue[1]
        read_end: int = 1
        write_end: int = 0
        counter: int = 0
        read_buf[0] = origin
        if not origin.update:
            origin.update=True
            self.visual_queue.append(origin)             
        while read_end > 0:
            if counter > self.counter:
                for i in range(read_end):
                    gate = read_buf[i]
                    gate.mark=False
                    if not gate.scheduled:
                        heapq.heappush(self.time_queue,Task(gate,self.Global_Clock+Global_delay[gate.id]+gate.inputlimit,gate.location))
                        gate.scheduled=True
                if self.runner is None or self.runner.done():
                    self.runner=asyncio.create_task(self.task_manager())
                return
            counter += 1

            for i in range(read_end):
                gate = read_buf[i]
                gate.mark = False
                new_output = gate.output
                for profile in gate.hitlist:
                    self.eval_count += 1
                    profile_output = profile.output
                    if profile_output != new_output:
                        target = profile.target
                        gate_type = target.id
                        limit = target.inputlimit
                        if gate_type>VARIABLE_ID:
                            if new_output>HIGH:target_output = new_output
                            else:target_output = new_output ^ (gate_type == NOT_ID)
                        else:
                            book = target.book
                            book[profile_output] -= 1
                            book[new_output] += 1
                            if new_output>HIGH:target_output = new_output
                            else:
                                high = book[HIGH]
                                low = book[LOW]
                                realsource = high + low
                                if realsource == limit or (realsource and realsource + book[UNKNOWN] == limit):
                                    if gate_type <= NAND_ID:target_output = int(low == 0)^(gate_type & 1)
                                    elif gate_type <= NOR_ID:target_output = int(high > 0)^(gate_type & 1)
                                    else:target_output = (high & 1)^(gate_type & 1)
                                else:target_output = UNKNOWN

                        if target_output != target.output:
                            target.output = target_output
                            if not target.update:
                                target.update = True
                                self.visual_queue.append(target)
                            if not target.mark:
                                target.mark = True
                                write_buf[write_end] = target
                                write_end += 1
                        profile.output = new_output
            read_buf, write_buf = write_buf, read_buf
            read_end, write_end = write_end, 0

    # ── Visual-queue helpers (called from the UI layer) ──────────────
    def visual_queue_empty(self) -> bool:
        """Return True when there are no pending dirty gate locations."""
        return len(self.visual_queue) == 0

    def visual_queue_clear(self):
        """Return True when there are no pending dirty gate locations."""
        for gate in self.visual_queue:
            gate.update=False
        self.visual_queue.clear()
        
    def pop_visual_queue(self) -> int:
        """Pop and return the next dirty gate location."""
        gate= self.visual_queue.popleft()
        gate.update=False
        return gate.location

    def visual_queue_size(self) -> int:
        """Return the size of the visual queue."""
        return len(self.visual_queue)
