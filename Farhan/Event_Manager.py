from typing import TYPE_CHECKING
from Circuit import Circuit
from Const import Const
from Gates import InputPin, OutputPin, Variable, Gate, Probe, NOT,Nothing


class Event(Circuit):

    def __init__(self):
        super().__init__()
        self.undolist = []
        self.redolist = []

    def addtoundo(self, token):
        self.undolist.append(token)
        self.redolist = []

    def popfromundo(self):
        x = self.undolist.pop()
        self.redolist.append(x)
        return x

    def popfromredo(self):
        x = self.redolist.pop()
        self.undolist.append(x)
        return x

    def undo(self):
        if len(self.undolist) == 0:
            return
        event = self.popfromundo()
        command = event[0]

        if command == Const.ADD:
            super().hideComponent(event[1])

        elif command == Const.DELETE:
            super().renewComponent(event[1])

        elif command == Const.CONNECT:
            super().disconnect(event[1], event[2], event[3])

        elif command == Const.DISCONNECT:
            super().connect(event[1], event[2], event[3])

        elif command == Const.PASTE:
            gates = event[2]
            for i in gates:
                self.terminate(i)
            self.rank_reset()

        elif command == Const.TOGGLE:
            self.toggle(event[1], event[2]^1)

    def redo(self):
        if len(self.redolist) == 0:
            return
        event = self.popfromredo()
        command = event[0]

        if command == Const.ADD:
            self.renewComponent(event[1])

        elif command == Const.DELETE:
            self.hideComponent(event[1])

        elif command == Const.CONNECT:
            self.connect(event[1], event[2], event[3])

        elif command == Const.DISCONNECT:
            self.disconnect(event[1], event[2], event[3])

        elif command == Const.PASTE:
            gates = [self.getobj(code) for code in event[1]]
            super().copy(gates)
            super().paste()

        elif command == Const.TOGGLE:
            self.toggle(event[1], event[2])

    def addcomponent(self, gate_option) -> Gate:
        gate = self.getcomponent(gate_option)
        if gate:
            self.addtoundo((Const.ADD, gate))
        return gate

    def livehide(self, gate):
        self.hideComponent(gate)
        self.addtoundo((Const.DELETE, gate))

    def liveconnect(self, parent: Gate, child: Gate, index):
        if parent.inputpoint == False or child.outputpoint == False or parent.children[index] != Nothing:
            return False
        self.connect(parent, child, index)
        self.addtoundo((Const.CONNECT, parent, child, index))
        return True

    def input(self, var, value):
        self.toggle(var, int(value))
        self.addtoundo((Const.TOGGLE, var, int(value)))

    def livedisconnect(self, parent: Gate, index):
        self.addtoundo((Const.DISCONNECT,parent, parent.children[index], index))
        self.disconnect(parent, index)


    def copy(self, components):
        super().copy(components)

    def paste(self):
        if len(self.copydata):
            gates = super().paste()
            self.addtoundo((Const.PASTE, self.copydata, gates))

    def load(self, file_location):
        # self.clearcircuit()
        self.undolist.clear()
        self.redolist.clear()
        self.readfromjson(file_location)

    def save(self, file_location):
        self.writetojson(file_location)

    def __str__(self):
        return 'Designer'

    def __repr__(self):
        return 'Designer'
