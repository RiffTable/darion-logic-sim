from typing import TYPE_CHECKING, cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import EditorState, Prop
from .catalog import CompItem, WireItem, InputPinItem, OutputPinItem, GateItem

if TYPE_CHECKING:
    from .canvas import CircuitScene


# Note to self: redo() is called when a QUndoCommand is constructed


class AddCompCommand(QUndoCommand):
    """Command to add a new component"""
    def __init__(self, scene: "CircuitScene", pos: QPointF, comp_id: int):
        super().__init__()
        self.scene = scene
        self.x ,self.y = pos.toTuple()
        self.comp_id = comp_id
        self.comp = None

    def redo(self):
        if self.comp is None:
            # Create the CompItem and store it in memory
            self.comp = self.scene.addComp(self.x, self.y, self.comp_id)
        else:
            self.scene.addItem(self.comp)
            self.scene.comps.append(self.comp)
            self.scene.register_comp(self.comp)
            if self.comp._unit:
                logic.reveal([self.comp._unit])

    def undo(self):
        if self.comp is None:
            return    # This is for pyright
        
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
        # 1. MARK DELETED GATES
        for comp in self.items_to_delete:
            if comp._unit:
                logic.delobj(comp._unit)

        # 2. DISAPPEAR COMPONENTS
        for comp in self.items_to_delete:
            self.scene.removeItem(comp)
            self.scene.comps.remove(comp)
            self.scene.unregister_comp(comp)

        # 3. DISAPPEAR WIRES & HANDLE BOUNDARY LOGIC
        for wire in self.wires_to_delete:
            self.scene.removeItem(wire)
            self.scene.wires.remove(wire)
            
            if wire.source and wire.source.logical:
                source_unit = wire.source.logical
                
                for supply in wire.supplies:
                    if supply.logical:
                        target_unit, target_idx = supply.logical
                        
                        if target_unit.location >= 0 or source_unit.location >= 0:
                            logic.disconnect(target_unit, target_idx)
                            supply.setWire(None)
                            
                            # THE FIX: Force the alive target to update its UI wires instantly
                            if target_unit.location >= 0:
                                comp = self.scene.comp_registry[target_unit.location]
                                if comp: comp.poll_update()
                            
                if source_unit.location >= 0:
                    wire.source.setWire(None)


    def undo(self):
        # 1. UNMARK DELETED GATES FIRST
        for comp in self.items_to_delete:
            if comp._unit:
                logic.renewobj(comp._unit)

        # 2. REAPPEAR COMPONENTS
        for comp in self.items_to_delete:
            self.scene.addItem(comp)
            self.scene.comps.append(comp)
            self.scene.register_comp(comp)
            
        # 3. REAPPEAR WIRES & RECONNECT BOUNDARY LOGIC
        for wire in self.wires_to_delete:
            self.scene.addItem(wire)
            self.scene.wires.append(wire)
            
            if wire.source and wire.source.logical:
                source_unit = wire.source.logical
                
                # THE FIX: Force the source to update its UI pins so the restored 
                # wire inherits the freshest possible state.
                if source_unit.location >= 0:
                    comp = self.scene.comp_registry[source_unit.location]
                    if comp: comp.poll_update()
                
                for supply in wire.supplies:
                    if supply.logical:
                        target_unit, target_idx = supply.logical
                        
                        if supply.getWire() is None: 
                            logic.connect(target_unit, source_unit, target_idx)
                            supply.setWire(wire)
                            
                            # THE FIX: Force the target to update its UI wires instantly
                            if target_unit.location >= 0:
                                comp = self.scene.comp_registry[target_unit.location]
                                if comp: comp.poll_update()
                                
                wire.source.setWire(wire)
                
            wire.updateShape()

#TODO: clean-up
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


#TODO: clean-up
class PasteCommand(QUndoCommand):
    def __init__(self, scene: "CircuitScene", data):
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
            return

        # 1. UNMARK DELETED GATES FIRST
        for comp in self.comps:
            if comp._unit:
                logic.renewobj(comp._unit)

        # 2. REAPPEAR COMPONENTS
        for comp in self.comps:
            self.scene.addItem(comp)
            self.scene.comps.append(comp)
            self.scene.register_comp(comp)

        # 3. REAPPEAR AND RECONNECT WIRES
        for wire in self.wires:
            self.scene.addItem(wire)
            self.scene.wires.append(wire)

            if wire.source and wire.source.logical:
                source_unit = wire.source.logical

                # THE FIX: Force the source to update its UI pins so the restored 
                # wire inherits the freshest possible state.
                if source_unit.location >= 0:
                    comp = self.scene.comp_registry[source_unit.location]
                    if comp: comp.poll_update()

                for supply in wire.supplies:
                    if supply.logical:
                        target_unit, target_idx = supply.logical

                        if supply.getWire() is None: 
                            logic.connect(target_unit, source_unit, target_idx)
                            supply.setWire(wire)

                            # THE FIX: Force the target to update its UI wires instantly
                            if target_unit.location >= 0:
                                comp = self.scene.comp_registry[target_unit.location]
                                if comp: comp.poll_update()

                wire.source.setWire(wire)
                
            wire.updateShape()

    def undo(self):
        # 1. MARK DELETED GATES
        for comp in self.comps:
            if comp._unit:
                logic.delobj(comp._unit)

        # 2. DISAPPEAR COMPONENTS
        for comp in self.comps:
            self.scene.removeItem(comp)
            self.scene.comps.remove(comp)
            self.scene.unregister_comp(comp)

        # 3. DISAPPEAR AND DISCONNECT WIRES
        for wire in self.wires:
            self.scene.removeItem(wire)
            if wire in self.scene.wires:
                self.scene.wires.remove(wire)

            if wire.source and wire.source.logical:
                source_unit = wire.source.logical

                for supply in wire.supplies:
                    if supply.logical:
                        target_unit, target_idx = supply.logical

                        if target_unit.location >= 0 or source_unit.location >= 0:
                            logic.disconnect(target_unit, target_idx)
                            supply.setWire(None)

                            # THE FIX: Force the alive target to update its UI wires instantly
                            if target_unit.location >= 0:
                                comp = self.scene.comp_registry[target_unit.location]
                                if comp: comp.poll_update()

                if source_unit.location >= 0:
                    wire.source.setWire(None)


class MoveCommand(QUndoCommand):
    def __init__(self, scene: "CircuitScene", moved_items: list[tuple[CompItem, QPointF, QPointF]], execute_redo: bool = False):
        super().__init__()
        self.scene = scene
        self.moved_items = moved_items   # list of (comp, old_pos, new_pos)

        # If the items are already moved, redo() should not be called after pushing to undo stack
        self.first_time = not execute_redo

    def redo(self):
        if self.first_time:
            self.first_time = False
            return
        
        for comp, old_pos, new_pos in self.moved_items:
            comp.setPos(new_pos)

    def undo(self):
        for comp, old_pos, new_pos in self.moved_items:
            comp.setPos(old_pos)


class SetInputCountCommand(QUndoCommand):
    def __init__(self, changes: list[tuple[GateItem, int, int]]):
        super().__init__()
        self.changes = changes  # list of (item, old_size, new_size)
        self.first_time = False

    def redo(self):
        if self.first_time:
            self.first_time = False
            return
        
        for item, old_size, new_size in self.changes:
            item.setInputCount(new_size)

    def undo(self):
        for item, old_size, new_size in self.changes:
            item.setInputCount(old_size)


#TODO: clean-up
class SwapWireCommand(QUndoCommand):
    def __init__(self, scene: "CircuitScene", g_wire, t_wire, target, g_pin):
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


class PropertyChangeCommand(QUndoCommand):
    def __init__(self, item: CompItem, prop: Prop, old_value, new_value, execute_redo: bool = False):
        super().__init__()
        self.item = item
        self.prop = prop
        self.old_value = old_value
        self.new_value = new_value

        self.first_time = not execute_redo

    def redo(self):
        if self.first_time:
            self.first_time = False
            return
        
        self.item.setProperty(self.prop, self.new_value)

    def undo(self):
        self.item.setProperty(self.prop, self.old_value)