from __future__ import annotations
from typing import cast
from core.QtCore import *
from core.LogicCore import *
from core.Enums import CompEdge, EditorState, Facing, Prop

import core.grid as GRID
import editor.theme as theme
from editor.styles import Font

from .compitem import CompItem
from .pins import PinItem, InputPin, OutputPin


# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

BUBBLE_R        = 5      # Inversion-bubble radius (px) – fused flush against body tip
OR_CX_FRAC      = 0.28   # Concavity of OR back-edge as fraction of body width
XOR_OFFSET_FRAC = 0.13   # Extra-stroke offset fraction for XOR outer curve
PIN_MARGIN_REL  = 0.5    # Margin (in grid units) kept at each end of input edge

# Visual-centre nudge: fraction of body size to shift text toward the 'thick'
# end of each gate shape so it reads as centered inside the drawn outline.
# Positive X → shift right (toward output); Positive Y → shift down.
_TEXT_NUDGE: dict[str, tuple[float, float]] = {
    "AND"  : (-0.05, 0.0),
    "NAND" : (-0.05, 0.0),
    "OR"   : (-0.07, 0.0),
    "NOR"  : (-0.07, 0.0),
    "XOR"  : (-0.07, 0.0),
    "XNOR" : (-0.07, 0.0),
    "NOT"  : (-0.18, 0.0),
}


# ─────────────────────────────────────────────────────────────────────────────
# Canonical path builders
# All builders produce paths in an EAST-facing, unmirrored coordinate space:
#   origin (0,0) = top-left,  (W, H) = bottom-right
#   inputs on the LEFT  (x = 0)
#   output on the RIGHT (x = W)
# W = w_rel * GRID.SIZE,  H = h_rel * GRID.SIZE  (from getRelSize, NOT getAbsSize)
# ─────────────────────────────────────────────────────────────────────────────

def _and_path(W: float, H: float) -> QPainterPath:
    """D-shape: straight back (left) + flat top/bottom + semi-ellipse on right.
    The ellipse rect spans the full (0,0,W,H) box so the output tip lands
    exactly at (W, H/2), matching the output-pin coordinate generator."""
    half = W / 2
    path = QPainterPath()
    path.moveTo(0, 0)
    path.lineTo(half, 0)
    # arcTo uses an ellipse defined by the bounding rect.
    # QRectF(0, 0, W, H) → centre (W/2, H/2), rx=W/2, ry=H/2.
    # Rightmost point of that ellipse = (W, H/2).  Start 90° → sweep −180° CW.
    path.arcTo(QRectF(0, 0, W, H), 90, -180)
    path.lineTo(0, H)
    path.closeSubpath()
    return path


def _or_path(W: float, H: float) -> QPainterPath:
    """Concave-back shield."""
    cx = W * OR_CX_FRAC
    path = QPainterPath()
    path.moveTo(0, 0)
    path.quadTo(cx, H / 2, 0, H)
    path.quadTo(W * 0.75, H,  W, H / 2)
    path.quadTo(W * 0.75, 0,  0, 0)
    path.closeSubpath()
    return path


def _xor_extra_stroke(W: float, H: float) -> QPainterPath:
    """Open quadratic arc placed XOR_OFFSET_FRAC*W behind the OR body."""
    cx  = W * OR_CX_FRAC
    off = W * XOR_OFFSET_FRAC
    path = QPainterPath()
    path.moveTo(-off, 0)
    path.quadTo(cx - off, H / 2, -off, H)
    return path


def _not_path(W: float, H: float) -> QPainterPath:
    """Right-pointing triangle; bubble drawn separately."""
    path = QPainterPath()
    path.moveTo(0, 0)
    path.lineTo(W, H / 2)
    path.lineTo(0, H)
    path.closeSubpath()
    return path


# ─────────────────────────────────────────────────────────────────────────────
# Painter transform  (canonical EAST → actual facing + mirror)
#
# The 8 cases below are derived from matching how getPinPosGenerator positions
# pins for each (facing, mirror) combination.
#
# For EAST|WEST: screen rect = (W × H); for SOUTH|NORTH: screen rect = (H × W)
# ─────────────────────────────────────────────────────────────────────────────

def _gate_transform(facing: Facing, mirrored: bool, W: float, H: float) -> QTransform:
    """
    Returns a QTransform that maps canonical (EAST, unmirrored) pixel coords
    to item-local screen coords for the given (facing, mirrored) state.

    QTransform(m11, m12, m21, m22, dx, dy) maps (x,y) to:
        x' = m11*x + m21*y + dx
        y' = m12*x + m22*y + dy
    """
    # fmt: off
    if   facing == Facing.EAST  and not mirrored: return QTransform( 1,  0,  0,  1,  0,  0)  # identity
    elif facing == Facing.EAST  and     mirrored: return QTransform( 1,  0,  0, -1,  0,  H)  # flip Y
    elif facing == Facing.SOUTH and not mirrored: return QTransform( 0,  1, -1,  0,  H,  0)  # 90° CW
    elif facing == Facing.SOUTH and     mirrored: return QTransform( 0,  1,  1,  0,  0,  0)  # 90° CW + flip
    elif facing == Facing.WEST  and not mirrored: return QTransform(-1,  0,  0, -1,  W,  H)  # 180°
    elif facing == Facing.WEST  and     mirrored: return QTransform(-1,  0,  0,  1,  W,  0)  # 180° + flip
    elif facing == Facing.NORTH and not mirrored: return QTransform( 0, -1,  1,  0,  0,  W)  # 90° CCW
    else:                                         return QTransform( 0, -1, -1,  0,  H,  W)  # 90° CCW + flip
    # fmt: on


# ─────────────────────────────────────────────────────────────────────────────
# OR/XOR curved-back pin placement math
# ─────────────────────────────────────────────────────────────────────────────

def _or_curve_x(y: float, H: float, cx: float) -> float:
    """
    x-depth from left edge at position y along the OR back-edge quadratic.

    The OR back is drawn as quadTo(P0=(0,0), ctrl=(cx, H/2), P2=(0,H)).
    For that Bézier: x(t) = 2t(1-t)·cx,  y(t) = tH  →  t = y/H.
    Substituting: x = 2·(y/H)·(1 - y/H)·cx.
    """
    if H <= 0:
        return 0.0
    t = y / H          # exact inversion of the Bézier y(t)=tH
    return 2.0 * t * (1.0 - t) * cx


def _make_curved_pin_pos(
    gate: GateComp,
    pin_index: int,
    n_pins: int,
    body_w: float,
    body_h: float,
    x_depth_fn,    # callable(y_canon, body_h) → x-depth from input edge
) -> QPointF:
    """
    Compute item-local pixel position for a curved-back input pin.

    We work in canonical space (EAST facing, no mirror):
      - y_canon in [margin .. body_h - margin]
      - x_depth = how far the curve pushes the pin INTO the body from x=0

    Then we apply the same 8-case mapping that getPinPosGenerator uses,
    converting the canonical position to actual item-local coords.
    """
    margin = PIN_MARGIN_REL * GRID.SIZE

    if n_pins == 1:
        y_canon = body_h / 2.0
    else:
        span = body_h - 2 * margin
        y_canon = margin + pin_index * span / (n_pins - 1)

    x_depth = x_depth_fn(y_canon, body_h)

    M  = gate.isMirrored
    fa = Facing(gate.facing + (-CompEdge.INPUT if M else CompEdge.INPUT))
    fd = M ^ (CompEdge.INPUT in (1, 2))
    case = fa + (4 if fd else 0)

    S  = GRID.SIZE
    w_g = body_w / S
    h_g = body_h / S

    # fmt: off
    # Each case applies the matching _gate_transform to canonical (x_depth, y_canon).
    # Derivation: QTransform(m11,m12,m21,m22,dx,dy) gives x'=m11·x+m21·y+dx, y'=m12·x+m22·y+dy
    match case:
        case 0: return QPointF(w_g * S - x_depth,   y_canon          )  # A   WEST  mirrored   (-1,0,0,1,W,0)
        case 1: return QPointF(h_g * S - y_canon,   w_g * S - x_depth)  # B   NORTH mirrored   (0,-1,-1,0,H,W)
        case 2: return QPointF(x_depth,             h_g * S - y_canon)  # C   EAST  mirrored   (1,0,0,-1,0,H)
        case 3: return QPointF(y_canon,             x_depth          )  # D   SOUTH mirrored   (0,1,1,0,0,0)
        case 4: return QPointF(w_g * S - x_depth,   h_g * S - y_canon)  # A*  WEST  unmirrored (-1,0,0,-1,W,H)
        case 5: return QPointF(y_canon,             w_g * S - x_depth)  # B*  NORTH unmirrored (0,-1,1,0,0,W)
        case 6: return QPointF(x_depth,             y_canon          )  # C*  EAST  unmirrored identity
        case _: return QPointF(h_g * S - y_canon,   x_depth          )  # D*  SOUTH unmirrored (0,1,-1,0,H,0)
    # fmt: on


# ─────────────────────────────────────────────────────────────────────────────
# GateItem base
# ─────────────────────────────────────────────────────────────────────────────

class GateComp(CompItem):
    MIN_INPUT  = 2
    MAX_INPUT  = 69
    HAS_BUBBLE = False
    IS_XOR     = False

    def getRelSize(self):
        n = len(self._pinslist[CompEdge.INPUT])
        w = 6 if n < 5 else (8 if n < 10 else 10)
        h = 2*(n-1) if n > 3 else 4
        return (w, h)

    def getRelPadding(self): return (0, 9)

    def __init__(self, pos: QPointF, **kwargs):
        super().__init__(pos, **kwargs)

        self._unit = cast(Gate, self._unit)
        self.state: int = Const.LOW
        self.prevState = -1
        self.minInput = self.MIN_INPUT
        self.maxInput = self.MAX_INPUT

        # Signal to CompItem.paint() to skip its drawRect fallback
        self._custom_draw = True

        if self._setupDefaultPins:
            if self.minInput <= 2:
                for i in range(self.minInput):
                    self.addInputPin(CompEdge.INPUT, 2*i+1)
            else:
                for i in range(self.minInput):
                    self.addInputPin(CompEdge.INPUT, 2*i)

            _, h = self.getRelSize()
            self.addOutputPin(CompEdge.OUTPUT, h//2)
            self.updateShape()

        self.inputPins  = cast(list[InputPin], self._pinslist[CompEdge.INPUT])
        self.outputPin  = cast(OutputPin,      self._pinslist[CompEdge.OUTPUT][0])

        for i, p in enumerate(self.inputPins):
            p.setLogical(self._unit, i)
        self.outputPin.setLogical(self._unit)

        logic.setlimits(self._unit, len(self.inputPins))

        self.proxyIndex  = self.findFirstEmptyPin()
        self.peekingPin: PinItem|None = None
        self.stashedPins: list[InputPin] = []


    # ── Properties ────────────────────────────────────────────────────────────

    def getProperties(self) -> dict:
        return super().getProperties() | {
            Prop.STATE     : self.state,
            Prop.INPUTSIZE : len(self.inputPins),
        }

    def setProperty(self, prop: Prop, value):
        if prop == Prop.INPUTSIZE:
            if self.setInputCount(value):
                self.propertyChanged(); return True
            return False
        return super().setProperty(prop, value)

    def unitStateChanged(self, state: int):
        self.state = state
        self.outputPin.logicalStateChanged(state)

    def poll_update(self) -> bool:
        if self._unit is None: return False
        current = self._unit.output
        if self.prevState != current:
            self.prevState = current
            self.unitStateChanged(current)
            return True
        return False


    # ── Proxying ──────────────────────────────────────────────────────────────

    def proxyPin(self):
        return self.inputPins[self.proxyIndex] if self.proxyIndex < len(self.inputPins) else None

    def findFirstEmptyPin(self):
        for i, p in enumerate(self.inputPins):
            if not p.hasWire(): return i
        return len(self.inputPins)


    # ── Pin configuration ─────────────────────────────────────────────────────

    def pushGatePin(self):
        n = len(self.inputPins)
        fa, gen = self.getPinPosGenerator(CompEdge.INPUT)
        if n == 2:
            self.setPinPos(self.inputPins[0], gen(0))
            self.setPinPos(self.inputPins[1], gen(2))
        if self.stashedPins:
            pin = self.stashedPins.pop()
            pin.facing = fa
            pin.setPos(gen(2*n))
            self.inputPins.append(pin)
            pin.setParentItem(self)
        else:
            pin = self.addInputPin(CompEdge.INPUT, 2*n)
        return pin.setLogical(self._unit, n)

    def popGatePin(self):
        n = len(self.inputPins)
        _, gen = self.getPinPosGenerator(CompEdge.INPUT)
        if n == 3:
            self.setPinPos(self.inputPins[0], gen(1))
            self.setPinPos(self.inputPins[1], gen(3))
        self.stashedPins.append(self.inputPins[n-1])
        self.removePin(CompEdge.INPUT, n-1)

    def pinUpdate(self, pin: PinItem, activePinCountChange: int):
        if (activePinCountChange == +1) and pin is self.proxyPin():
            self.proxyIndex = self.findFirstEmptyPin()
        if (activePinCountChange == -1) and pin in self.inputPins:
            index = self.inputPins.index(cast(InputPin, pin))
            self.proxyIndex = min(self.proxyIndex, index)

    def setInputCount(self, size: int) -> bool:
        n = len(self.inputPins)
        if size < self.minInput or size > self.maxInput or size == n:
            return False
        if size > n:
            for i in range(n, size): self.pushGatePin()
        else:
            left = n - size
            for i in range(n-1, -1, -1):
                if left == 0 or self.inputPins[i].hasWire(): break
                self.popGatePin(); left -= 1
        logic.setlimits(self._unit, size)
        self.updateShape()
        self.prevState = -1
        self.propertyChanged()
        return True


    # ── Hover / proxy ─────────────────────────────────────────────────────────

    def betterHoverEnter(self):
        if self.cscene.peeking_disabled: return
        if (self.proxyIndex == len(self.inputPins)
                and len(self.inputPins) < self.maxInput
                and self.cscene.checkState(EditorState.WIRING)):
            self.peekingPin = self.pushGatePin()
            self.updateShape()

    def betterHoverLeave(self):
        if self.peekingPin and not self.peekingPin.hasWire():
            self.popGatePin()
            self.updateShape()
        self.peekingPin = None


    # ── Shape / path ──────────────────────────────────────────────────────────

    def _build_canonical_path(self) -> QPainterPath:
        """Return gate body path in canonical EAST-facing space using getRelSize()."""
        return QPainterPath()

    def _reposition_input_pins(self, body_w: float, body_h: float):
        """Redistribute straight-edge input pins with margin so they never sit
        on sharp corners.  OR/XOR subclasses override this for curved placement.
        Pin Y positions are snapped to GRID.SIZE so wires stay on the grid."""
        
        n = len(self.inputPins)
        if not n:
            return
        margin = PIN_MARGIN_REL * GRID.SIZE
        fa, gen = self.getPinPosGenerator(CompEdge.INPUT)
        w_rel, h_rel = self.getRelSize()
        body_h_px = h_rel * GRID.SIZE
        if n == 1:
            raw = body_h_px / 2.0
        else:
            span = body_h_px - 2 * margin

        S = GRID.SIZE
        def _snap(raw_px: float) -> float:
            """Snap to nearest grid line, clamped to [S .. body_h_px-S]."""
            snapped = int(raw_px / S + 0.5) * S
            return max(S, min(body_h_px - S, snapped))

        if n == 1:
            positions = [_snap(raw)]
        else:
            positions = [_snap(margin + i * span / (n - 1)) for i in range(n)]
        for pin, y_canon in zip(self.inputPins, positions):
            pin.facing = fa
            # gen() expects grid-unit index; pass pixel / GRID.SIZE
            self.setPinPos(pin, gen(y_canon / GRID.SIZE))

    def _updateShape(self):
        w_rel, h_rel = self.getRelSize()
        body_w = w_rel * GRID.SIZE   # canonical pixel width
        body_h = h_rel * GRID.SIZE   # canonical pixel height

        # Store canonical path (used in draw())
        self._canonical_path = self._build_canonical_path()

        # Reposition curved input pins (OR/XOR family)
        self._reposition_input_pins(body_w, body_h)

        # Output pin: place at canonical output edge midpoint, offset past bubble
        opin = self.outputPin
        fa, gen = self.getPinPosGenerator(CompEdge.OUTPUT)
        opin.facing = fa
        base_pos = gen(h_rel // 2)
        if self.HAS_BUBBLE:
            base_pos = base_pos + fa.toPointF(2 * BUBBLE_R)
        self.setPinPos(opin, base_pos)

        super()._updateShape()


    # ── Paint ─────────────────────────────────────────────────────────────────

    def draw(self, painter: QPainter, option: QStyleOptionGraphicsItem, widget: QWidget):
        """
        Draw the ANSI gate body (and extras) with a QTransform that maps the
        canonical EAST-facing path to the current facing/mirror state.
        The label is drawn upright by mapping the visual centre through the
        gate transform, then resetting the painter to draw axis-aligned text.
        """
        Color = theme.get_theme()
        w_rel, h_rel = self.getRelSize()
        W = w_rel * GRID.SIZE   # canonical dims
        H = h_rel * GRID.SIZE

        is_sel = bool(option.state & QStyle.StateFlag.State_Selected)

        # ── Per-gate colours ──────────────────────────────────────────────
        _fallback = (Color.gate_body, Color.gate_outline, Color.gate_label)
        g_body, g_outline, g_label = Color.gate_colors.get(self.TAG, _fallback)

        def _pen():
            if is_sel:
                return QPen(Color.gate_sel_outline, 1.8, Qt.PenStyle.DashLine)
            return QPen(g_outline, 1.8)

        T = _gate_transform(self.facing, self.isMirrored, W, H)

        # ── Visual centre in item-local coords ────────────────────────────
        nx_frac, ny_frac = _TEXT_NUDGE.get(self.TAG, (0.0, 0.0))
        item_cx, item_cy = T.map(W * (0.5 + nx_frac), H * 0.5)

        painter.save()
        painter.setWorldTransform(T, combine=True)

        # ── XOR extra back stroke (open path, no fill) ──────────────────
        if self.IS_XOR:
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.setPen(_pen())
            painter.drawPath(_xor_extra_stroke(W, H))

        # ── Gate body ────────────────────────────────────────────────────
        painter.setBrush(g_body)
        painter.setPen(_pen())
        painter.drawPath(self._canonical_path)

        # ── Inversion bubble (fused flush to the body output tip) ────────
        if self.HAS_BUBBLE:
            painter.setBrush(g_body)
            painter.setPen(_pen())
            painter.drawEllipse(QPointF(W + BUBBLE_R, H / 2), BUBBLE_R, BUBBLE_R)

        painter.restore()

        # ── Label: always upright, position follows the gate ─────────────
        w_abs, h_abs = self.getAbsSize()
        short_px = min(w_abs, h_abs) * GRID.SIZE
        box_w = short_px * 1.4
        box_h = short_px * 0.55
        painter.save()
        painter.translate(item_cx, item_cy)
        painter.setPen(g_label)
        painter.setFont(Font.gate)
        painter.drawText(QRectF(-box_w / 2, -box_h / 2, box_w, box_h),
                         Qt.AlignmentFlag.AlignCenter, self.tag)
        painter.restore()


# ─────────────────────────────────────────────────────────────────────────────
# Concrete gate classes
# ─────────────────────────────────────────────────────────────────────────────

class NOTGate(GateComp):
    TAG = "NOT";  LOGIC = Const.NOT_ID;  NAME = DESC = "NOT Gate"
    MIN_INPUT = MAX_INPUT = 1
    HAS_BUBBLE = True

    def getRelSize(self):    return (4, 4)   # square: triangle fits neatly
    def getRelPadding(self): return (0, 4)

    def _build_canonical_path(self) -> QPainterPath:
        w, h = self.getRelSize()
        return _not_path(w * GRID.SIZE, h * GRID.SIZE)


class ANDGate(GateComp):
    TAG = "AND";  LOGIC = Const.AND_ID;  NAME = DESC = "AND Gate"

    def _build_canonical_path(self) -> QPainterPath:
        w, h = self.getRelSize()
        return _and_path(w * GRID.SIZE, h * GRID.SIZE)


class NANDGate(GateComp):
    TAG = "NAND"; LOGIC = Const.NAND_ID; NAME = DESC = "NAND Gate"
    HAS_BUBBLE = True

    def _build_canonical_path(self) -> QPainterPath:
        w, h = self.getRelSize()
        return _and_path(w * GRID.SIZE, h * GRID.SIZE)


# ── OR / NOR ──────────────────────────────────────────────────────────────────

class _ORMixin(GateComp):
    def _build_canonical_path(self) -> QPainterPath:
        w, h = self.getRelSize()
        return _or_path(w * GRID.SIZE, h * GRID.SIZE)

    def _curved_x_fn(self, body_w: float):
        cx = body_w * OR_CX_FRAC
        return lambda y, h: _or_curve_x(y, h, cx)

    def _reposition_input_pins(self, body_w: float, body_h: float):
        n = len(self.inputPins)
        if not n: return
        x_fn = self._curved_x_fn(body_w)
        for i, pin in enumerate(self.inputPins):
            pos = _make_curved_pin_pos(self, i, n, body_w, body_h, x_fn)
            self.setPinPos(pin, pos)


class ORGate(_ORMixin, GateComp):
    TAG = "OR";   LOGIC = Const.OR_ID;   NAME = DESC = "OR Gate"


class NORGate(_ORMixin, GateComp):
    TAG = "NOR";  LOGIC = Const.NOR_ID;  NAME = DESC = "NOR Gate"
    HAS_BUBBLE = True


# ── XOR / XNOR ────────────────────────────────────────────────────────────────

class _XORMixin(_ORMixin):
    IS_XOR = True

    def _curved_x_fn(self, body_w: float):
        cx  = body_w * OR_CX_FRAC
        off = body_w * XOR_OFFSET_FRAC
        # Pins sit on the outer stroke: x_depth = inner_curve_x - off (can be < 0)
        return lambda y, h: _or_curve_x(y, h, cx) - off


class XORGate(_XORMixin, GateComp):
    TAG = "XOR";  LOGIC = Const.XOR_ID;  NAME = DESC = "XOR Gate"


class XNORGate(_XORMixin, GateComp):
    TAG = "XNOR"; LOGIC = Const.XNOR_ID; NAME = DESC = "XNOR Gate"
    HAS_BUBBLE = True