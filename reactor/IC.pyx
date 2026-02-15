# distutils: language = c++
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
from Gates cimport Gate, InputPin, OutputPin, Profile, create, add, hide, reveal, remove

from Store cimport get
from Const cimport IC_ID, INPUT_PIN_ID, OUTPUT_PIN_ID,UNKNOWN

cdef class IC:
    # Integrated Circuit: a custom chip made of other gates
    # It acts like a black box with inputs and outputs
    def __cinit__(self):
        self.id = IC_ID
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

    # helps created parts inside the IC
    cpdef getcomponent(self, int choice):
        # We need to treat choice as int if possible or object
        cdef object gt = get(choice)
        cdef int rank
        if gt:
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
        # Source can be Gate, OutputPin, InputPin. But they are all Gate subclasses (except InputPin inherits Probe->Gate)
        # So source is Gate.
        cdef int rank

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

    # sets up the IC from a saved plan
    cpdef configure(self, dict dictionary):
        cdef dict pseudo = {}
        pseudo[('X', 'X')] = None
        self.custom_name = dictionary["custom_name"]
        self.map = dictionary["map"]
        self.load_components(dictionary, pseudo)
        self.clone(pseudo)

    cdef decode(self, list code):
        if len(code) == 2:
            return tuple(code)
        return (code[0], code[1], self.decode(code[2]))

    # brings the components to life based on the plan
    cpdef load_components(self, dict dictionary, dict pseudo):
        # generate all the necessary components
        cdef object gate
        for comp_code in dictionary["components"]: # Rename var to avoid conflict with `code` field
            gate = self.getcomponent(comp_code[0]) # comp_code is tuple/list from json
            pseudo[self.decode(comp_code)] = gate

    # prepares data to be saved to file
    cpdef json_data(self):
        # Needs to construct dict efficiently
        # Gates have .code, .name etc accessible
        cdef dict dictionary = {
            "name": self.name,
            "custom_name": self.custom_name,
            "code": self.code,
            "components": [gate.code for gate in self.internal+self.inputs+self.outputs],
            "map": []
        }
        for i in self.internal+self.inputs+self.outputs:
            dictionary["map"].append(i.json_data())
        return dictionary

    cpdef clone(self, dict pseudo):
        cdef object gate
        cdef object code
        for i in self.map:
            code = self.decode(i["code"])
            gate = pseudo[code]
            if gate.id==IC_ID:
                gate.map = i["map"]
                gate.load_components(i, pseudo)
                (<IC>gate).clone(pseudo)
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
        cdef dict dictionary = {
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
    cpdef implement(self, dict pseudo):
        cdef object gate
        cdef object code
        for i in self.map:
            code = self.decode(i["code"])
            gate = pseudo[code]
            if gate.id==IC_ID:
                gate.map = i["map"]
                gate.load_components(i, pseudo)
                gate.implement(pseudo)
            else:
                gate.clone(i, pseudo) # clone() on Gate acts as implement/connect

    # disconnects internal logic (used when deleting)
    cpdef hide(self):
        # Disconnect output pins from their targets
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
            
            # for i in range(size):
            #     target = <Gate>hitlist[i].target
            #     if target is not self: # Identity check
            #        target.process()        
        # Disconnect input pins from their sources
        for pin_in in self.inputs:
            for index, source in enumerate(pin_in.sources):
                if source:
                    src = <Gate>source
                    remove(src.hitlist, pin_in, index)
                    pin_in.sources[index]=source


    # reconnects internal logic
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
            for index, source in enumerate(pin_in.sources):
                if source:
                    src = <Gate>source
                    add(src.hitlist, pin_in, index, src.output)
            pin_in.process()

        # Original code line 180: iterate self.outputs
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

        # Show inputs
        if self.inputs:
            print("  INPUTS:")
            for pin in self.inputs:
                targets = [str(target) for target in pin.hitlist]
                print(f"    {pin.name}: out={pin.getoutput()}, to={', '.join(targets) if targets else 'None'}")

        # Show internal components
        if self.internal:
            print("  INTERNAL:")
            for comp in self.internal:
                if comp.id==IC_ID:
                    (<IC>comp).info()
                else:
                    # Sources (list with indices)
                    if isinstance(comp.sources, list):
                        ch = [f"[{i}]:{c}" for i, c in enumerate(comp.sources) if c is not None]
                        ch_str = ", ".join(ch) if ch else "None"
                    else:
                        ch_str = f"val:{comp.sources}"
                    # Targets
                    tgt = [str(target) for target in comp.hitlist]
                    tgt_str = ", ".join(tgt) if tgt else "None"
                    print(f"    {comp.name}: out={comp.getoutput()}, sources={ch_str}, targets={tgt_str}")

        # Show outputs
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
