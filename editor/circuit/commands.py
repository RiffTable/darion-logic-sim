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

        # 3. DISAPPEAR WIRES & HANDLE BOUNDARY LOGIC
        for wire in self.wires_to_delete:
            self.scene.removeItem(wire)
            self.scene.wires.remove(wire)
            
            if wire.source and wire.source.logical:
                source_unit = wire.source.logical
                
                for supply in wire.supplies:
                    if supply.logical:
                        target_unit, target_idx = supply.logical
                        
                        if target_unit.id >= 0 or source_unit.id >= 0:
                            logic.disconnect(target_unit, target_idx)
                            supply.setWire(None)
                            if target_unit.id >= 0:
                                comp = self.scene.comp_registry[target_unit.location]
                                if comp: comp.poll_update()
                            
                if source_unit.id >= 0:
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
            
        # 3. REAPPEAR WIRES & RECONNECT BOUNDARY LOGIC
        for wire in self.wires_to_delete:
            self.scene.addItem(wire)
            self.scene.wires.append(wire)
            
            if wire.source and wire.source.logical:
                source_unit = wire.source.logical
                
                # wire inherits the freshest possible state.
                if source_unit.id >= 0:
                    comp = self.scene.comp_registry[source_unit.location]
                    if comp: comp.poll_update()
                
                for supply in wire.supplies:
                    if supply.logical:
                        target_unit, target_idx = supply.logical
                        
                        if supply.getWire() is None: 
                            logic.connect(target_unit, source_unit, target_idx)
                            supply.setWire(wire)
                            
                            # THE FIX: Force the target to update its UI wires instantly
                            if target_unit.id >= 0:
                                comp = self.scene.comp_registry[target_unit.location]
                                if comp: comp.poll_update()
                                
                wire.source.setWire(wire)
                
            wire.updateShape()

#TODO: clean-up
class ConnectCommand(QUndoCommand):
    def __init__(self, scene: "CircuitScene", source_pin: OutputPinItem, target_pin: InputPinItem, ghost_wire: WireItem, multi_wire_mode: bool = False):
        super().__init__()
        self.scene = scene
        self.source_pin = source_pin
        self.target_pin = target_pin
        self.ghost_wire = ghost_wire  # The WireItem created during dragging
        self.multi_wire_mode = multi_wire_mode
        self.added_to_scene = False

    def redo(self):
        scene = self.scene
        g_wire = self.ghost_wire
        t_pin = self.target_pin
        source = self.source_pin

        # Visual (UI) Connection
        g_wire._addSupply(t_pin)
        
        if g_wire not in scene.wires:
            scene.wires.append(g_wire)
            if g_wire.scene() != scene:
                scene.addItem(g_wire)
            self.added_to_scene = True
            
        g_wire.updateShape()

        # Logical Connection
        if t_pin.logical and source.logical:
            unit, idx = t_pin.logical
            
            # Connecting at a peeking pin
            if isinstance(unit, Gate) and idx >= unit.inputlimit:
                unit.setlimits(idx + 1)
            
            logic.connect(unit, source.logical, idx)

    def undo(self):
        scene = self.scene
        g_wire = self.ghost_wire
        t_pin = self.target_pin

        # 1. Undo logical connection
        if t_pin.logical: logic.disconnect(*t_pin.logical)
            
        # 2. Undo UI connection
        g_wire._cutSupply(t_pin)
        g_wire.updateShape()
        
        if self.added_to_scene:
            if g_wire in scene.wires:
                scene.wires.remove(g_wire)
            scene.removeItem(g_wire)
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

                # wire inherits the freshest possible state.
                if source_unit.id >= 0:
                    comp = self.scene.comp_registry[source_unit.location]
                    if comp: comp.poll_update()

                for supply in wire.supplies:
                    if supply.logical:
                        target_unit, target_idx = supply.logical

                        if supply.getWire() is None: 
                            logic.connect(target_unit, source_unit, target_idx)
                            supply.setWire(wire)

                            # THE FIX: Force the target to update its UI wires instantly
                            if target_unit.id >= 0:
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

                        if target_unit.id >= 0 or source_unit.id >= 0:
                            logic.disconnect(target_unit, target_idx)
                            supply.setWire(None)

                            # THE FIX: Force the alive target to update its UI wires instantly
                            if target_unit.id >= 0:
                                comp = self.scene.comp_registry[target_unit.location]
                                if comp: comp.poll_update()

                if source_unit.id >= 0:
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
    def __init__(self, scene: "CircuitScene", g_wire: WireItem, t_wire: WireItem, target: InputPinItem, g_pin: InputPinItem):
        super().__init__()
        self.scene = scene
        self.g_wire = g_wire
        self.t_wire = t_wire
        self.target = target
        self.g_pin = g_pin
        self.added_to_scene = False

    def redo(self):
        g_wire = self.g_wire
        g_pin = self.g_pin
        target = self.target
        t_wire = self.t_wire
        scene = self.scene

        ### Swapping Wires
        # Disconnect g_wire from g_pin
        if g_pin in g_wire.supplies:
            g_wire._cutSupply(g_pin)
            
        # Disconnect t_wire from target
        if target in t_wire.supplies:
            t_wire._cutSupply(target)
        
        # Connect g_wire to target
        g_wire._addSupply(target)
        
        # Logically connect/disconnect
        if target.logical: logic.disconnect(*target.logical)
        g_wire.logicalConnect(g_wire.source, target)

        # UI cleanup for old wire
        if len(t_wire.supplies) == 0:
            t_wire.source.setWire(None)
            if t_wire in scene.wires:
                scene.wires.remove(t_wire)
            scene.removeItem(t_wire)
        else:
            t_wire.updateShape()

        # Update new wire's shape
        g_wire.updateShape()
        
        scene.ghostWire = None       # Wire vanishes, does not become ghost wire
        scene.setState(EditorState.NORMAL)
        
        if g_wire not in scene.wires:
            scene.wires.append(g_wire)
            if g_wire.scene() != scene:
                scene.addItem(g_wire)
            self.added_to_scene = True

    def undo(self):
        g_wire = self.g_wire
        g_pin = self.g_pin
        target = self.target
        t_wire = self.t_wire
        scene = self.scene
        
        # Reconnect g_wire to g_pin
        g_wire._addSupply(g_pin)
        
        # Disconnect g_wire from target
        if target in g_wire.supplies:
            g_wire._cutSupply(target)
            
        # Reconnect t_wire to target
        t_wire._addSupply(target)
        
        # Logically disconnect/connect
        if target.logical: logic.disconnect(*target.logical)
        t_wire.logicalConnect(t_wire.source, target)
        
        # Restore t_wire physically if it was removed
        if len(t_wire.supplies) == 1:
            t_wire.source.setWire(t_wire)
            if t_wire not in scene.wires:
                scene.wires.append(t_wire)
            if t_wire.scene() != scene:
                scene.addItem(t_wire)

        g_wire.updateShape()
        t_wire.updateShape()
        
        scene.ghostWire = g_wire
        scene.setState(EditorState.WIRING)
        
        if self.added_to_scene:
            if g_wire in scene.wires:
                scene.wires.remove(g_wire)
            scene.removeItem(g_wire)
            self.added_to_scene = False

class DisconnectWireCommand(QUndoCommand):
    def __init__(self, scene: "CircuitScene", t_wire: WireItem, target: InputPinItem):
        super().__init__()
        self.scene = scene
        self.t_wire = t_wire
        self.target = target

    def redo(self):
        t_wire = self.t_wire
        target = self.target
        scene = self.scene
        
        # UI Disconnect
        t_wire._cutSupply(target)
        
        # Logical Disconnect
        if target.logical: logic.disconnect(*target.logical)
        
        if len(t_wire.supplies) == 0:
            t_wire.source.setWire(None)
            if t_wire in scene.wires:
                scene.wires.remove(t_wire)
            scene.removeItem(t_wire)
        else:
            t_wire.updateShape()

    def undo(self):
        t_wire = self.t_wire
        target = self.target
        scene = self.scene
        
        # UI Reconnect
        t_wire._addSupply(target)
        
        # Logical Reconnect
        if target.logical:
            from core.LogicCore import logic
            t_wire.logicalConnect(t_wire.source, target)
            
        if len(t_wire.supplies) == 1:
            t_wire.source.setWire(t_wire)
            if t_wire not in scene.wires:
                scene.wires.append(t_wire)
            if t_wire.scene() != scene:
                scene.addItem(t_wire)
                
        t_wire.updateShape()


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