from Control import Command
from collections import deque

class Event:
    # This class handles time travel (undo/redo)
    # It remembers every action so we can reverse it
    __slots__ = ['undolist', 'redolist']
    
    def __init__(self): 
        self.undolist:deque[Command] = deque()
        self.redolist:deque[Command] = deque()

    # saves an action to history
    def register(self, token:Command):
        self.undolist.append(token)
        if len(self.undolist) > 250:
            self.undolist.popleft()
        if self.redolist:
            self.redolist.clear()        

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
        if self.undolist:
            command = self.popfromundo()
            command.undo()

    # re-applies an action we just undid
    def redo(self):
        if self.redolist:
            command = self.popfromredo()
            command.redo()

    def __str__(self):
        return 'Event Manager'

    def __repr__(self):
        return 'Event Manager'
