# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
from Gates cimport Gate, InputPin, OutputPin, Profile, hide, reveal, pop

from Store cimport get
from Const cimport *

cdef class IC:
    def __cinit__(self):
        self.id = IC_ID
        self.counter = 0
    def __init__(self):
        self.inputs = []
        self.internal = []
        self.outputs = []

        self.name = 'IC'
        self.custom_name = ''
        self.code = ()
        self.map = []

    def __repr__(self):
        return self.name if self.custom_name == '' else self.custom_name

    def __str__(self):
        return self.name if self.custom_name == '' else self.custom_name

    cpdef getcomponent(self, int choice):
        cdef object gt = get(choice)
        if gt:
            self.counter+=1
            if gt.id==INPUT_PIN_ID:
                rank = len(self.inputs)
                self.inputs.append(gt)
                gt.name = 'in-'+str(len(self.inputs))
            elif gt.id==OUTPUT_PIN_ID:
                rank = len(self.outputs)
                self.outputs.append(gt)
                gt.name = 'out-'+str(len(self.outputs))
            else:
                rank = len(self.internal)
                self.internal.append(gt)
                gt.name = gt.__class__.__name__+'-'+str(len(self.internal))
            gt.code = (choice, rank, self.code)
        return gt

    cpdef addgate(self, object source):
        if source.id==INPUT_PIN_ID:
            rank = len(self.inputs)
            self.inputs.append(source)
            source.name = 'in-'+str(len(self.inputs))
        elif source.id==OUTPUT_PIN_ID:
            rank = len(self.outputs)
            self.outputs.append(source)
            source.name = 'out-'+str(len(self.outputs))
        else:
            rank = len(self.internal)
            self.internal.append(source)
            source.name = source.__class__.__name__+'-'+str(len(self.internal))
        source.code = (source.code[0], rank, self.code)

    cpdef configure(self, list dictionary):
        cdef dict pseudo = {}
        pseudo[('X', 'X')] = None
        self.custom_name = dictionary[CUSTOM_NAME]
        self.map = dictionary[MAP]
        self.load_components(dictionary, pseudo)
        self.clone(pseudo, 0)

    cdef decode(self, list code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    cpdef load_components(self, list dictionary, dict pseudo):
        cdef object gate
        for comp_code in dictionary[COMPONENTS]:
            gate = self.getcomponent(comp_code[0])
            pseudo[self.decode(comp_code)] = gate

    cpdef json_data(self):
        cdef list dictionary = [
            
            self.custom_name,
            self.code,
            [gate.code for gate in self.internal+self.inputs+self.outputs],
            []
        ]
        for i in self.internal+self.inputs+self.outputs:
            dictionary[MAP].append(i.json_data())
        return dictionary

    cpdef clone(self, dict pseudo,int depth):
        cdef object gate
        cdef object code
        if depth>250:
            raise RecursionError("Infinite recursion detected, map is corrupted")
        for i in self.map:
            code = self.decode(i[CODE])
            gate = pseudo[code]
            if gate.id==IC_ID:
                gate.map = i[MAP]
                gate.load_components(i, pseudo)
                (<IC>gate).clone(pseudo,depth+1)
                self.counter+=gate.counter
            else:
                gate.clone(i, pseudo)

    cpdef load_to_cluster(self, set cluster):
        for i in self.inputs+self.internal+self.outputs:
            if i.id==IC_ID:
                cluster.add(i)
                (<IC>i).load_to_cluster(cluster)
            else:
                cluster.add(i)

    cpdef copy_data(self, set cluster):
        cdef list dictionary = [
            
            self.custom_name,
            self.code,
            [gate.code for gate in self.internal+self.inputs+self.outputs],
            [],
        ]
        for i in self.internal+self.inputs+self.outputs:
            dictionary[MAP].append(i.copy_data(cluster))
        return dictionary

    cpdef implement(self, dict pseudo,int depth):
        cdef object gate
        cdef object code
        if depth>250:
            raise RecursionError("Infinite recursion detected, map is corrupted")
        for i in self.map:
            code = self.decode(i[CODE])
            gate = pseudo[code]
            if gate.id==IC_ID:
                gate.map = i[MAP]
                gate.load_components(i, pseudo)
                (<IC>gate).implement(pseudo,depth+1)
                self.counter+=gate.counter
            else:
                gate.clone(i, pseudo)

    cpdef hide(self):
        cdef OutputPin pin_out
        cdef InputPin pin_in
        cdef Profile* hitlist
        cdef int index
        cdef int loc
        cdef size_t i
        cdef size_t size
        cdef Gate src
        cdef Gate target
        for pin_out in self.outputs:
            hitlist = pin_out.hitlist.data()
            size = pin_out.hitlist.size()
            for i in range(size):
                hide(hitlist[i])
        for pin_in in self.inputs:
            for index, source in enumerate(pin_in.sources):
                if source is not None:
                    src = <Gate>source
                    pop(src.hitlist, <void*>pin_in, index)

    cpdef reveal(self):
        cdef InputPin pin_in
        cdef OutputPin pin_out
        cdef int index
        cdef int loc
        cdef Profile* hitlist
        cdef size_t i
        cdef size_t size
        cdef Gate src
        for pin_in in self.inputs:
            source=<Gate>pin_in.sources[0]
            if source is not None:
                source.hitlist.emplace_back(<void*>pin_in, 0, source.output)
            pin_in.process()

            pin_in.process()
        for pin_out in self.outputs:
            hitlist = pin_out.hitlist.data()
            size = pin_out.hitlist.size()
            for i in range(size):
                reveal(hitlist[i], pin_out)      

    cpdef reset(self):
        for i in self.inputs+self.internal+self.outputs:
            if i.id!=IC_ID:
                (<Gate>i).reset()
            else:
                (<IC>i).reset()

    cpdef showinputpins(self):
        for i, gate in enumerate(self.inputs):
            print(f'{i}. {gate}')

    cpdef showoutputpins(self):
        for i, gate in enumerate(self.outputs):
            print(f'{i}. {gate}')
    # cdef purge(self):
    #     for i in self.inputs+self.internal+self.outputs:
    #         i.purge()
    cpdef info(self):
        """Show all IC components in an organized way."""
        print(f"\n  IC: {self.name} (Code: {self.code})")
        print("  " + "-" * 40)

        if self.inputs:
            print("  INPUTS:")
            print("  INPUTS:")
            for pin in self.inputs:
                targets = [str(target) for target in pin.hitlist]
                print(f"    {pin.name}: out={pin.getoutput()}, to={', '.join(targets) if targets else 'None'}")

        if self.internal:
            print("  INTERNAL:")
            for comp in self.internal:
                if comp.id==IC_ID:
                    (<IC>comp).info()
                else:
                    if isinstance(comp.sources, list):
                        ch = [f"[{i}]:{c}" for i, c in enumerate(comp.sources) if c is not None]
                        ch_str = ", ".join(ch) if ch else "None"
                    else:
                        ch_str = f"val:{comp.sources}"
                    # Targets
                    tgt = [str(target) for target in comp.hitlist]
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
