from Circuit import Circuit
from Const import Const
from Gates import Gate,Nothing
from collections import deque

class Event:
    # This class handles time travel (undo/redo)
    # It remembers every action so we can reverse it
    __slots__ = ['circuit', 'undolist', 'redolist']
    
    def __init__(self,circuit:Circuit): 
        self.circuit = circuit
        self.undolist:deque[tuple] = deque()
        self.redolist:deque[tuple] = deque()

    # saves an action to history
    def addtoundo(self, token):
        self.undolist.append(token)
        self.redolist=deque()
        if len(self.undolist) > Const.LIMIT:
            event=self.undolist.popleft()
            if event[0]==Const.DELETE:
                gate= event[1]
                row=gate.code[0]
                col=gate.code[1]
                lastgate=self.circuit.objlist[row][-1]
                self.circuit.objlist[row][col]=lastgate
                lastgate.code=(row,col)
                lastgate.name=gate.name
                self.circuit.objlist[row].pop()


    def popfromundo(self):
        x = self.undolist.pop()
        self.redolist.append(x)
        return x

    def popfromredo(self):
        x = self.redolist.pop()
        self.undolist.append(x)
        return x

    # reverses the last action
    def undo(self):
        if len(self.undolist) == 0:
            return
        event = self.popfromundo()
        command = event[0]

        if command == Const.ADD:
            self.circuit.hideComponent(event[1])

        elif command == Const.DELETE:
            self.circuit.renewComponent(event[1])

        elif command == Const.CONNECT:
            self.circuit.disconnect(event[1], event[3])

        elif command == Const.DISCONNECT:
            self.circuit.connect(event[1], event[2], event[3])

        elif command == Const.PASTE:
            gates = event[2]
            for i in gates:
                self.circuit.terminate(i)
            self.circuit.rank_reset()

        elif command == Const.TOGGLE:
            self.circuit.toggle(event[1], event[2]^1)

        elif command == Const.SETLIMITS:
            self.circuit.setlimits(event[1], event[2])

    # re-applies an action we just undid
    def redo(self):
        if len(self.redolist) == 0:
            return
        event = self.popfromredo()
        command = event[0]

        if command == Const.ADD:
            self.circuit.renewComponent(event[1])

        elif command == Const.DELETE:
            self.circuit.hideComponent(event[1])

        elif command == Const.CONNECT:
            self.circuit.connect(event[1], event[2], event[3])

        elif command == Const.DISCONNECT:
            self.circuit.disconnect(event[1], event[3])

        elif command == Const.PASTE:
            gates = [self.getobj(code) for code in event[1]]
            self.circuit.copy(gates)
            self.circuit.paste()

        elif command == Const.TOGGLE:
            self.circuit.toggle(event[1], event[2])

        elif command == Const.SETLIMITS:
            self.circuit.setlimits(event[1], event[3])

    def addcomponent(self, gate_option) -> Gate:
        gate = self.circuit.getcomponent(gate_option)
        if gate:
            self.addtoundo((Const.ADD, gate))
        return gate
    
    def getIC(self, name):
        ic=self.circuit.getIC(name)
        if ic:
            self.addtoundo((Const.ADD, ic))

    def hide(self, gate):
        self.circuit.hideComponent(gate)
        self.addtoundo((Const.DELETE, gate))

    def connect(self, parent: Gate, child: Gate, index):
        if parent.children[index] != Nothing:
            return False
        self.circuit.connect(parent, child, index)
        self.addtoundo((Const.CONNECT, parent, child, index))
        return True

    def input(self, var, value):
        self.circuit.toggle(var, int(value))
        self.addtoundo((Const.TOGGLE, var, int(value)))

    def disconnect(self, parent: Gate, index):
        self.addtoundo((Const.DISCONNECT,parent, parent.children[index], index))
        self.circuit.disconnect(parent, index)

    def setlimits(self,gate,size):
        prev_size=gate.inputlimit
        if self.circuit.setlimits(gate,size):
            self.addtoundo((Const.SETLIMITS,gate,prev_size,size))
            return True
        return False

    def copy(self, components):
        self.circuit.copy(components)

    def paste(self):
        if len(self.circuit.copydata):
            gates = self.circuit.paste()
            self.addtoundo((Const.PASTE, self.circuit.copydata, gates))

    def load(self, file_location):
        # self.clearcircuit()
        self.undolist=deque()
        self.redolist=deque()
        self.circuit.readfromjson(file_location)

    def save(self, file_location):
        self.circuit.writetojson(file_location)

    def __str__(self):
        return 'Designer'

    def __repr__(self):
        return 'Designer'
