from __future__ import annotations
from typing import Callable, cast, TYPE_CHECKING, Any
from core.QtCore import *
from core.LogicCore import *
from core.Enums import Facing, CompEdge, Prop
import core.grid as GRID

import editor.theme as theme
from editor.styles import Font
from .pins import PinItem, InputPin, OutputPin

if TYPE_CHECKING:
    from .canvas import CircuitScene






class CompItem(QGraphicsItem):
    ID: int      # Value assigned via `catalog.py`
    LOGIC: int   # Assigned in child classes

    TAG: str
    NAME: str
    DESC: str

    rLength: int
    rBreadth: int
    
    def __init__(self, pos: QPointF, **kwargs):

        # Properties
        self.tag = str(kwargs.get("tag", self.TAG))
        self.facing = Facing(kwargs.get("facing", Facing.EAST))
        self.isMirrored = bool(kwargs.get("mirror", False))

        # isMirrored is for flipping the TOP-BOTTOM edges instead of the
        # INPUT-OUTPUT edges, as doing so will make the component
        # visually face the opposite way, ultimately making
        # self.facing sound STUPID!
        
        self._pinslist: list[list[PinItem]] = [[], [], [], []]

        super().__init__()
        self.setPos(GRID.snapF(pos))
        self.setZValue(0)
        self.setFlags(
            GraphicsItemFlag.ItemIsMovable |
            GraphicsItemFlag.ItemIsSelectable |
            GraphicsItemFlag.ItemSendsGeometryChanges
            # GraphicsItemFlag.ItemSendsScenePositionChanges
        )
        theme.theme_changed.connect(self.update)

        # Behavior
        self._dirty = True
        self._rect = QRectF()
        self._cached_hitbox = QPainterPath()
        self._cached_brect = QRectF()
        self._gate_path: QPainterPath | None = None   # Set by subclasses to override drawRect
        self._custom_draw: bool = False               # Set True by GateComp to skip drawRect
        self._prop_change_listener: list[Callable[[], None]] = []

        if self.LOGIC != Const.IC_ID:
            self._unit = cast(Any, logic.getcomponent(self.LOGIC))
            self._unit.custom_name = self.tag

        self._setupDefaultPins = False if ("pinslist" in kwargs) else True
        if not self._setupDefaultPins:
            new_pinslist = cast(dict[str, list[dict]], kwargs.get("pinslist", {}))
            for _edge, pins in new_pinslist.items():
                edge = CompEdge(int(_edge))
                facing = self.edgeToFacing(edge)
                pinslist = self._pinslist[edge]
                for pin in pins:
                    PinType = InputPin if pin["isInput"] else OutputPin
                    newpin = PinType(self, QPointF(*pin["pos"]), facing)
                    #? Logical Not Set Yet. Do that in the child classes
                    pinslist.append(newpin)

        # Proxy & Hovering
        self.hoverLeaveTimer = QTimer()
        self.hoverLeaveTimer.setSingleShot(True)
        self.hoverLeaveTimer.timeout.connect(self.betterHoverLeave)
        self.hoverLeaveTimer.setInterval(30)

        # How to Write Constructors for children of CompItem:
        # 1. Properties
        # 2. Pins Setup
        # 3. Pins Casting
        # 4. Setting Pin Logicals (For both regular constructor and deserialization)
        # 5. Final Setup
        # Methods to Override (Mandatory):
        #    => getRel Size/Padding, 
        # Methods to Override (Optional):
        #    => getData, get/set Properties
        #    => pinUpdate, proxyPin, betterHoverEnter, betterHoverLeave
        #    => draw


    @property
    def cscene(self): return cast('CircuitScene', self.scene())

    
    ### Properties Data
    def getData(self):
        return {
            "id"       : self.ID,
            "pos"      : GRID.fromPointF(self.pos()),
            "tag"      : self.tag,
            "facing"   : self.facing.value,
            "mirror"   : self.isMirrored,
            "pinslist" : {
                edge: [p.getData() for p in pins]
                for edge, pins in enumerate(self._pinslist)
            },
        }

    def getProperties(self) -> dict[Prop, Any]:
        return {
            Prop.TAG       : self.tag,
            Prop.FACING    : self.facing,
            Prop.MIRROR    : self.isMirrored,
        }
    
    def setProperty(self, prop: Prop, value) -> bool:
        match prop:
            case Prop.LABEL:
                self.tag = str(value)
                if self._unit: self._unit.custom_name = self.tag
                self.update()
                self.propertyChanged(); return True
            
            case Prop.FACING:
                self.setFacing(Facing(value))
                self.propertyChanged(); return True
            
            case Prop.MIRROR:
                if self.isMirrored != bool(value):
                    self.mirror()
                self.propertyChanged(); return True
            
            case _:
                return False

    def addPropertyChangedListener(self, listener):
        self._prop_change_listener.append(listener)
    def removePropertyChangedListener(self, listener):
        self._prop_change_listener.remove(listener)
    
    def propertyChanged(self):
        for listener in self._prop_change_listener:
            listener()



    ### Logical Unit
    def updatePinsLayout(self):
        ...    # ABSTRACT METHOD
    
    # def updatePinsLayout(self):  #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!fuck
    #     """Automatically calls `updateShape()` right after"""
    #     for edge, pins in self._pinslist.items():
    #         fa, gen = self.getPinPosGenerator(edge)

    #         for i, pin in enumerate(pins):
    #             pin.facing = fa
    #             self.setPinPos(pin, gen(i))
    #     self.updateShape()
    
    
    def unitStateChanged(self, state: int):
        ...    # ABSTRACT METHOD

    def poll_update(self) -> bool:
        ...    # ABSTRACT METHOD


    ### Facing and Rotation
    def edgeToFacing(self, edge: CompEdge) -> Facing:
        return Facing(self.facing + (-edge if self.isMirrored else edge))
    
    def facingToEdge(self, facing: Facing) -> CompEdge:
        return CompEdge((facing - self.facing) * (-1 if self.isMirrored else 1))

    def getPinPosGenerator(self, edge: CompEdge|int) -> tuple[Facing, Callable[[int], QPointF]]:
        """Set `facing` and `size` before calling"""
        # This was way too complicated then expected
        w, h = self.getAbsSize()
        M = self.isMirrored

        # Final Facing (fa)
        # A, B, C, D => E, S, W, N
        # A* = Edge facing East COUNTER-CLOCKWISE
        fa = Facing(self.facing + (-edge if M else edge))

        # Final Direction (fd): (False -> Clockwise), (True -> Counter-Clockwise)
        fd = M ^ (edge in (1, 2))
        # print((["A", "B", "C", "D", "A*", "B*", "C*", "D*"])[fa + (4 if fd else 0)])
        match fa + (4 if fd else 0):
            case 0: return ( fa, lambda i: QPointF(w  , i  ) * GRID.SIZE )    # A
            case 1: return ( fa, lambda i: QPointF(w-i, h  ) * GRID.SIZE )    # B
            case 2: return ( fa, lambda i: QPointF(0  , h-i) * GRID.SIZE )    # C
            case 3: return ( fa, lambda i: QPointF(i  , 0  ) * GRID.SIZE )    # D
            case 4: return ( fa, lambda i: QPointF(w  , h-i) * GRID.SIZE )    # A*
            case 5: return ( fa, lambda i: QPointF(i  , h  ) * GRID.SIZE )    # B*
            case 6: return ( fa, lambda i: QPointF(0  , i  ) * GRID.SIZE )    # C*
            case _: return ( fa, lambda i: QPointF(w-i, 0  ) * GRID.SIZE )    # D*


    ### Pin Configuration
    def addInputPin(self, edge: CompEdge, index: int) -> InputPin:
        """Call updateShape() afterwards if needed"""
        pinslist = self._pinslist[edge]

        fa, gen = self.getPinPosGenerator(edge)
        newpin = InputPin(self, gen(index), fa)
        pinslist.append(newpin)
        return newpin
    
    def addOutputPin(self, edge: CompEdge, index: int) -> OutputPin:
        """Call updateShape() afterwards if needed"""
        pinslist = self._pinslist[edge]

        fa, gen = self.getPinPosGenerator(edge)
        newpin = OutputPin(self, gen(index), fa)
        pinslist.append(newpin)
        return newpin
    
    def removePin(self, edge: CompEdge, index: int):
        """Call `updateShape()` afterwards if needed"""
        pinlist = self._pinslist[edge]
        pin = pinlist[index]
        pin.disconnect()
        
        pinlist.pop(index)
        pin.setParentItem(None)  # pyright: ignore
        self.cscene.removeItem(pin)

    def setPinPos(self, pin: PinItem, placement: QPointF):
        """Set `pin.facing` before calling"""
        pin.setPos(placement)
        if pin._wire: pin._wire.updateShape()
    
    def cutConnections(self):
        list_of_pinlists = self._pinslist
        pins = [pin for pinlist in list_of_pinlists for pin in pinlist]    # Funniest line ever
        for p in pins:
            p.disconnect()
    
    def pinUpdate(self, pin: PinItem, activePinCountChange: int):
        ...    # ABSTRACT METHOD


    ### Smart Hover System (refactored :P)
    # The system had been refactored so its not really smart anymore
    # but it still kinda is ig
    # betterHoverEnter/Leave is now controlled via the SCENE
    def proxyPin(self) -> InputPin|None:
        """The getter function for the proxy pin. If the proxy pin is stored as an index, then dereference it here"""
        return None    # ABSTRACT METHOD (defaults to None)
    
    def betterHoverEnter(self):
        ...    # ABSTRACT METHOD
    def betterHoverLeave(self):
        ...    # ABSTRACT METHOD
    
    
    ### Updating Overall Shape
    def _updateShape(self):
        """DO NOT set _dirty to False before call this"""
        # This part changes the bounding rect and "shape" of the compItem
        self._rect = self.getRect()
        
        path = QPainterPath()
        path.addRect(self._rect)
        self._cached_hitbox = path
        self._cached_brect = path.boundingRect()
    
    def shape(self) -> QPainterPath:
        return self._cached_hitbox
    def boundingRect(self) -> QRectF:
        return self._cached_brect


    ### Dimension
    def getRect(self):
        g = GRID.SIZE
        if self.facing%2 == 0: return QRectF(0, 0, self.rLength *g, self.rBreadth*g)
        else:                  return QRectF(0, 0, self.rBreadth*g, self.rLength *g)
    
    def getAbsSize(self) -> tuple[int, int]:
        """Calculates absolute size in GRID units: `(width, height)`"""
        if self.facing%2 == 0: return (self.rLength , self.rBreadth)
        else:                  return (self.rBreadth, self.rLength)


    ### Events
    def itemChange(self, change: GraphicsItemChange, value):
        if change == GraphicsItemChange.ItemPositionChange:
            return GRID.snapF(value)

        return super().itemChange(change, value)
    
    def updateShape(self):
        """No need to call `setHitbox()` afterwards"""
        if not self._dirty: self.prepareGeometryChange(); self.update(); self._dirty = True
    
    def draw(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        ...    # ABSTRACT METHOD
    def paint(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        if self._dirty: self._updateShape(); self._dirty = False

        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        Color = theme.get_theme()
        if option.state & QStyle.StateFlag.State_Selected:    # type: ignore ; fuck off pyright
            painter.setPen(QPen(Color.hl_text_bg, 2, Qt.PenStyle.DashLine))
        else:
            painter.setPen(QPen(Color.outline, 2))
        painter.setBrush(Color.comp_body)

        self.draw(painter, option, widget)

        # _gate_path=None → non-gate: draw rect fallback.
        # _custom_draw=True → GateItem drew shape+text inside draw(); skip both.
        if self._gate_path is not None:
            painter.drawPath(self._gate_path)
        elif not self._custom_draw:
            painter.drawRect(self._rect)

        # Text: only for non-custom components. GateItem.draw() handles its own.
        if not self._custom_draw:
            painter.setPen(Color.text)
            painter.setFont(Font.default)
            painter.drawText(self._rect, Qt.AlignmentFlag.AlignCenter, self.tag)





    ###======= ACTIONS =======###
    def setFacing(self, facing: Facing):
        if facing == self.facing: return
        
        self.facing = facing
        self.propertyChanged()
        self.updatePinsLayout()
        # self.updateShape()

    def mirror(self):
        self.isMirrored = not self.isMirrored
        self.propertyChanged()
        self.updatePinsLayout()
        # self.updateShape()
    
    def flip(self):
        self.isMirrored = not self.isMirrored
        self.setFacing(Facing(self.facing+2))
        self.propertyChanged()
        # self.updateShape()



    def rotateCW(self):
        self.setFacing(Facing(self.facing + 1))
    def rotateCCW(self):
        self.setFacing(Facing(self.facing + 3))

    def flipHorizontal(self):
        if self.facing%2 == 0: self.flip()
        else:                  self.mirror()

    def flipVertical(self):
        if self.facing%2 == 0: self.mirror()
        else:                  self.flip()
