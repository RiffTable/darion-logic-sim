from Gates import Gate
from Circuit import Circuit

class Command:
    def execute():pass
    def undo():pass
    def redo():pass

class Add(Command):
    __slots__ = ['circuit', 'choice', 'gate']
    def __init__(self, circuit:Circuit, choice:int):
        self.circuit = circuit
        self.choice=choice
        self.gate = None
    def execute(self):
        self.gate=self.circuit.getcomponent(self.choice)
        return self.gate is not None
    def undo(self):
        self.circuit.delobj(self.gate)
    def redo(self):
        self.circuit.renewobj(self.gate)

class AddIC(Command):
    __slots__ = ['circuit', 'location', 'ic']
    def __init__(self,circuit:Circuit, location:str):
        self.circuit = circuit
        self.location = location
        self.ic = None
    def execute(self):
        self.ic = self.circuit.getIC(self.location)
        return self.ic is not None
    def undo(self):
        self.circuit.delobj(self.ic)
    def redo(self):
        self.circuit.renewobj(self.ic)

class Delete(Command):
    __slots__ = ['circuit', 'gatelist']
    def __init__(self,circuit:Circuit, gatelist:list[Gate]):
        self.circuit = circuit
        self.gatelist = gatelist
    def execute(self):
        if self.gatelist is None:
            return False
        self.circuit.hide(self.gatelist)
        return True
    def undo(self):
        self.circuit.reveal(self.gatelist)
    def redo(self):
        self.execute()
    
class Connect(Command):
    __slots__ = ['circuit', 'target', 'source', 'index']
    def __init__(self,circuit:Circuit, target:Gate, source:Gate, index:int):
        self.circuit = circuit
        self.target = target
        self.source = source
        self.index = index
    def execute(self):
        if self.target.sources[self.index] is not None:
            return False
        self.circuit.connect(self.target, self.source, self.index)
        return True
    def undo(self):
        self.circuit.disconnect(self.target, self.index)
    def redo(self):
        self.circuit.connect(self.target, self.source, self.index)

class Disconnect(Command):
    __slots__ = ['circuit', 'target', 'index', 'source']
    def __init__(self,circuit:Circuit, target:Gate, index:int):
        self.circuit = circuit
        self.target = target
        self.index = index
        self.source = target.sources[index]
    def execute(self):
        if self.source is None:
            return False
        self.circuit.disconnect(self.target, self.index)
        return True
    def undo(self):
        self.circuit.connect(self.target, self.source, self.index)
    def redo(self):
        self.circuit.disconnect(self.target, self.index)

class Paste(Command):
    __slots__ = ['circuit', 'new_gatelist']
    def __init__(self,circuit:Circuit):
        self.circuit = circuit
        self.new_gatelist=[]
    def execute(self):
        self.new_gatelist=self.circuit.paste()
        return self.new_gatelist is not None
    def undo(self):
        for i in self.new_gatelist:
            self.circuit.delobj(i)
    def redo(self):
        for i in self.new_gatelist:
            self.circuit.renewobj(i)

class Toggle(Command):
    __slots__ = ['circuit', 'gate', 'value']
    def __init__(self,circuit:Circuit, gate:Gate, value:int):
        self.circuit = circuit
        self.gate = gate
        self.value = value
    def execute(self):
        if self.gate.value==self.value:
            return False
        self.circuit.toggle(self.gate, self.value)
        return True
    def undo(self):
        self.circuit.toggle(self.gate, self.value^1)
    def redo(self):
        self.circuit.toggle(self.gate, self.value)

class SetLimits(Command):
    __slots__ = ['gate', 'new_size', 'old_size']
    def __init__(self, gate:Gate, new_size:int):
        self.gate = gate
        self.new_size = new_size
        self.old_size = gate.inputlimit
    def execute(self):
        return self.gate.setlimits(self.new_size)
    def undo(self):
        self.gate.setlimits(self.old_size)
    def redo(self):
        self.gate.setlimits(self.new_size)

class Rename(Command):
    __slots__ = ['gate', 'new_name', 'old_name']
    def __init__(self,gate:Gate, new_name:str):
        self.gate = gate
        self.new_name = new_name
        self.old_name = gate.name
    def execute(self):
        if len(self.new_name)>25:
            return False
        self.gate.custom_name = self.new_name
        return True
    def undo(self):
        self.gate.custom_name = self.old_name
    def redo(self):
        self.gate.custom_name = self.new_name
