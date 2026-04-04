from core.QtCore import QUndoCommand
from editor.circuit.compitem import CompItem
from editor.circuit.wireitem import WireItem
from core.LogicCore import logic
from core.Enums import EditorState

class AddCompCommand(QUndoCommand):
    """Command to add a new component"""
    def __init__(self, scene, x, y, comp_id):
        super().__init__()
        self.scene = scene
        self.x = x
        self.y = y
        self.comp_id = comp_id
        self.comp = None  # Will hold the visual CompItem

    def redo(self):
        if self.comp is None:
            # First time: create it normally. addComp also calls register_comp and logic.
            self.comp = self.scene.addComp(self.x, self.y, self.comp_id)
        else:
            # Redo: restore the existing visual item and logic
            self.scene.addItem(self.comp)
            self.scene.comps.append(self.comp)
            self.scene.register_comp(self.comp)
            if self.comp._unit:
                logic.reveal([self.comp._unit])

    def undo(self):
        # Hide from scene and logic, but keep the Python object exactly as is
        self.scene.removeItem(self.comp)
        self.scene.comps.remove(self.comp)
        self.scene.unregister_comp(self.comp)
        if self.comp._unit:
            logic.hide([self.comp._unit])


class DeleteCommand(QUndoCommand):
    def __init__(self, scene, items_to_delete, explicit_wires=None):
        super().__init__()
        self.scene = scene
        self.items_to_delete = items_to_delete
        
        # Capture all the wires connected to these comps
        self.wires_to_delete = self._get_attached_wires()
        if explicit_wires:
            for w in explicit_wires:
                if w not in self.wires_to_delete:
                    self.wires_to_delete.append(w)

    def _get_attached_wires(self):
        wires = set()
        for comp in self.items_to_delete:
            for pinlist in comp._pinslist.values():
                for pin in pinlist:
                    if pin.hasWire():
                        wires.add(pin.getWire())
        return list(wires)

    def redo(self):
        # Perform actual deletion (hide from scene & logic)
        for wire in self.wires_to_delete:
            self.scene.removeWire(wire)
        for comp in self.items_to_delete:
            self.scene.removeComp(comp)

    def undo(self):
        # Restore components
        for comp in self.items_to_delete:
            self.scene.addItem(comp)
            self.scene.comps.append(comp)
            self.scene.register_comp(comp)
            if comp._unit:
                logic.reveal([comp._unit])
                
        for wire in self.wires_to_delete:
            self.scene.addItem(wire)
            self.scene.wires.append(wire)
            # Reattach UI
            wire.source.setWire(wire)
            for supply in wire.supplies:
                supply.setWire(wire)
                # Reattach Logic
                if wire.source.logical and supply.logical:
                    unit, idx = supply.logical
                    logic.connect(unit, wire.source.logical, idx)
            wire.updateShape()

        
        # Restore wires


class ConnectCommand(QUndoCommand):
    def __init__(self, scene, source_pin, target_pin, ghost_wire, multi_wire_mode=False):
        super().__init__()
        self.scene = scene
        self.source_pin = source_pin
        self.target_pin = target_pin
        self.wire = ghost_wire  # The WireItem started/created during dragging
        self.multi_wire_mode = multi_wire_mode
        self.added_to_scene = False

    def redo(self):
        # 1. Update visual wire state
        self.wire.supplies.append(self.target_pin)
        self.target_pin.setWire(self.wire)
        
        if self.wire not in self.scene.wires:
            self.scene.wires.append(self.wire)
            if self.wire.scene() != self.scene:
                self.scene.addItem(self.wire)
            self.added_to_scene = True
            
        self.wire.updateShape()

        # 2. Update logic state
        if self.target_pin.logical and self.source_pin.logical:
            unit, idx = self.target_pin.logical
            source_logic = self.source_pin.logical
            
            from core.LogicCore import Gate
            if isinstance(unit, Gate) and idx >= unit.inputlimit:
                unit.setlimits(idx + 1)
            
            logic.connect(unit, source_logic, idx)

    def undo(self):
        # 1. Undo logic
        if self.target_pin.logical:
            unit, idx = self.target_pin.logical
            logic.disconnect(unit, idx)
            
        # 2. Undo UI
        self.wire.supplies.remove(self.target_pin)
        self.target_pin.setWire(None)
        self.wire.updateShape()
        
        if self.added_to_scene:
            if self.wire in self.scene.wires:
                self.scene.wires.remove(self.wire)
            self.scene.removeItem(self.wire)
            self.added_to_scene = False


class PasteCommand(QUndoCommand):
    def __init__(self, scene, data):
        super().__init__()
        self.scene = scene
        self.data = data
        self.comps = []
        self.wires = []
        self.first_time = True

    def redo(self):
        if self.first_time:
            self.first_time = False
            self.comps, self.wires = self.scene.deserialize(self.data, addToSelected=True)
        else:
            # Restore components
            for comp in self.comps:
                self.scene.addItem(comp)
                self.scene.comps.append(comp)
                self.scene.register_comp(comp)
                if comp._unit:
                    logic.reveal([comp._unit])
            
            # Restore wires
            for wire in self.wires:
                self.scene.addItem(wire)
                self.scene.wires.append(wire)
                wire.source.setWire(wire)
                for supply in wire.supplies:
                    supply.setWire(wire)
                    if wire.source.logical and supply.logical:
                        unit, idx = supply.logical
                        logic.connect(unit, wire.source.logical, idx)
                wire.updateShape()

    def undo(self):
        # Like DeleteCommand.redo()
        for wire in self.wires:
            self.scene.removeWire(wire)
        for comp in self.comps:
            self.scene.removeComp(comp)


class MoveCommand(QUndoCommand):
    def __init__(self, scene, moved_items):
        super().__init__()
        self.scene = scene
        self.moved_items = moved_items  # list of (comp, old_pos, new_pos)

    def redo(self):
        for comp, old_pos, new_pos in self.moved_items:
            comp.setPos(new_pos)

    def undo(self):
        for comp, old_pos, new_pos in self.moved_items:
            comp.setPos(old_pos)


class SetInputCountCommand(QUndoCommand):
    def __init__(self, changes):
        super().__init__()
        self.changes = changes  # list of (item, old_size, new_size)

    def redo(self):
        for item, old_size, new_size in self.changes:
            item.setInputCount(new_size)

    def undo(self):
        for item, old_size, new_size in self.changes:
            item.setInputCount(old_size)


class SwapWireCommand(QUndoCommand):
    def __init__(self, scene, g_wire, t_wire, target, g_pin):
        super().__init__()
        self.scene = scene
        self.g_wire = g_wire
        self.t_wire = t_wire
        self.target = target
        self.g_pin = g_pin
        self.added_to_scene = False

    def redo(self):
        if self.g_pin in self.g_wire.supplies:
            self.g_wire.supplies.remove(self.g_pin)
        self.g_wire.supplies.append(self.target)
        
        self.t_wire.supplies.append(self.g_pin)
        if self.target in self.t_wire.supplies:
            self.t_wire.supplies.remove(self.target)
        
        if self.target.logical:
            unit, idx = self.target.logical
            logic.disconnect(unit, idx)
        
        self.g_wire.logicalConnect(self.g_wire.source, self.target)
        
        self.g_pin.setWire(self.t_wire)
        self.target.setWire(self.g_wire)
        
        self.g_wire.updateShape()
        self.t_wire.updateShape()
        
        self.scene.ghostWire = self.t_wire
        self.scene.setState(EditorState.WIRING)
        
        if self.g_wire not in self.scene.wires:
            self.scene.wires.append(self.g_wire)
            if self.g_wire.scene() != self.scene:
                self.scene.addItem(self.g_wire)
            self.added_to_scene = True

    def undo(self):
        if self.g_pin in self.t_wire.supplies:
            self.t_wire.supplies.remove(self.g_pin)
        self.t_wire.supplies.append(self.target)
        
        self.g_wire.supplies.append(self.g_pin)
        if self.target in self.g_wire.supplies:
            self.g_wire.supplies.remove(self.target)
        
        if self.target.logical:
            unit, idx = self.target.logical
            logic.disconnect(unit, idx)
            
        self.t_wire.logicalConnect(self.t_wire.source, self.target)
        
        self.g_pin.setWire(self.g_wire)
        self.target.setWire(self.t_wire)
        
        self.g_wire.updateShape()
        self.t_wire.updateShape()
        
        self.scene.ghostWire = self.g_wire
        self.scene.setState(EditorState.WIRING)
        
        if self.added_to_scene:
            if self.g_wire in self.scene.wires:
                self.scene.wires.remove(self.g_wire)
            self.scene.removeItem(self.g_wire)
            self.added_to_scene = False
