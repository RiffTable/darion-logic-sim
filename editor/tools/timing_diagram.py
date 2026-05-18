"""
Timing Diagram  ─  real-time oscilloscope viewer
=================================================
• Opens idle; records only when   Record is pressed
• No frequency changes — user controls simulation speed
• Canvas always follows the most recent event (live scroll)
• Auto-fits row heights to fill the available space
• Signal names clearly shown in the left label column
"""

from __future__ import annotations
from core.QtCore import *
from PySide6.QtCore import QSize
from PySide6.QtGui import QFontMetrics
from PySide6.QtWidgets import QSizePolicy
import editor.theme as theme

try:
    from editor.tools.timing_tracer import tracer
except ImportError:
    from timing_tracer import tracer  # type: ignore  (run standalone)

# ── Layout constants ───────────────────────────────────────────────────────────
LABEL_W  = 150      # left column width (px)
RULER_H  = 28       # ruler at top (px)
MIN_ROW  = 40       # minimum row height
MAX_ROW  = 120      # maximum row height
MIN_PPT  = 0.25     # min pixels-per-time-unit (extreme zoom-out: whole run in view)
MAX_PPT  = 600.0   # max pixels-per-time-unit (extreme zoom-in: single edge)
DEF_PPT  = 16.0
WAVE_PAD = 10       # vertical padding inside a waveform row


# ─────────────────────────────────────────────────────────────────────────────
# Canvas
# ─────────────────────────────────────────────────────────────────────────────
class TimingCanvas(QWidget):
    """Scrollable waveform drawing area."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._data: list[dict] = []
        self._ppt: float = DEF_PPT
        self._scroll_x: int = 0
        self._max_time: int = 1
        self._follow: bool = True
        self._row_h: int = MIN_ROW
        self._drag_start: QPoint | None = None
        self._drag_scroll0: int = 0
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.WheelFocus)

    # ── Geometry helpers ──────────────────────────────────────────────────────

    def _compute_row_h(self) -> int:
        """Auto-fit row height so all signals fill the visible canvas height."""
        n = max(1, len(self._data))
        available = max(self.height() - RULER_H, MIN_ROW * n)
        rh = available // n
        return max(MIN_ROW, min(MAX_ROW, rh))

    def _visible_w(self) -> int:
        return max(1, self.width() - LABEL_W)

    def _total_px(self) -> int:
        return int(self._max_time * self._ppt)

    def _scroll_to_end(self):
        self._scroll_x = max(0, self._total_px() - self._visible_w() + 30)

    def _clamp_scroll(self):
        self._scroll_x = max(0, min(
            self._scroll_x,
            max(0, self._total_px() - self._visible_w() + 30)
        ))

    # ── Data ─────────────────────────────────────────────────────────────────

    def set_data(self, data: list[dict], max_time: int):
        self._data = data
        self._max_time = max(max_time, 1)
        self._row_h = self._compute_row_h()
        if self._follow:
            self._scroll_to_end()
        self.update()
        self.updateGeometry()

    # ── Mouse interaction ─────────────────────────────────────────────────────

    def wheelEvent(self, event: QWheelEvent):
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
            self._ppt = max(MIN_PPT, min(MAX_PPT, self._ppt * factor))
            if self._follow:
                self._scroll_to_end()
            else:
                self._clamp_scroll()
        else:
            self._scroll_x -= event.angleDelta().y() // 3
            self._scroll_x -= event.angleDelta().x()
            self._follow = False
            self._clamp_scroll()
        self.update()
        event.accept()

    def mousePressEvent(self, event: QMouseEvent):
        mid = event.button() == Qt.MouseButton.MiddleButton
        alt = (event.button() == Qt.MouseButton.LeftButton and
               event.modifiers() & Qt.KeyboardModifier.AltModifier)
        if mid or alt:
            self._drag_start   = event.pos()
            self._drag_scroll0 = self._scroll_x
            self._follow       = False
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._drag_start is not None:
            dx = event.pos().x() - self._drag_start.x()
            self._scroll_x = max(0, self._drag_scroll0 - dx)
            self._clamp_scroll()
            self.update()

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._drag_start is not None:
            self._drag_start = None
            self.setCursor(Qt.CursorShape.ArrowCursor)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._row_h = self._compute_row_h()
        if self._follow:
            self._scroll_to_end()

    # ── Paint ─────────────────────────────────────────────────────────────────

    def paintEvent(self, _):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        C  = theme.get_theme()
        W  = self.width()
        H  = self.height()
        rh = self._row_h
        ppt, sx = self._ppt, self._scroll_x

        # Background
        painter.fillRect(0, 0, W, H, C.secondary_bg)

        # Draw rows
        clip = QRect(LABEL_W, RULER_H, W - LABEL_W, H - RULER_H)
        painter.setClipRect(clip)
        for i, sig in enumerate(self._data):
            y0 = RULER_H + i * rh
            self._draw_row(painter, C, sig, i, y0, W, ppt, sx, rh)
        painter.setClipping(False)

        # Label column overlay (drawn on top so waveforms don't bleed into it)
        painter.fillRect(0, 0, LABEL_W, H, C.primary_bg)
        painter.setPen(QPen(C.outline, 1))
        painter.drawLine(LABEL_W, 0, LABEL_W, H)

        # Draw labels on top
        for i, sig in enumerate(self._data):
            y0 = RULER_H + i * rh
            self._draw_label(painter, C, sig, y0, rh)
            painter.setPen(QPen(C.outline, 1))
            painter.drawLine(0, y0, W, y0)

        # Bottom separator
        bot = RULER_H + len(self._data) * rh
        painter.setPen(QPen(C.outline, 1))
        painter.drawLine(0, bot, W, bot)

        # Ruler (drawn last so it's on top)
        self._draw_ruler(painter, C, W, ppt, sx)
        painter.setPen(QPen(C.outline, 1))
        painter.drawLine(0, RULER_H, W, RULER_H)

    # ── Label column ─────────────────────────────────────────────────────────

    def _draw_label(self, painter: QPainter, C, sig: dict, y0: int, rh: int):
        is_clock = sig["is_clock"]
        name     = sig["name"] or ("CLK" if is_clock else "OUT")

        sig_col = QColor("#FFAA00") if is_clock else QColor("#00D4FF")

        # Type badge
        badge_font = QFont("Segoe UI", 6, QFont.Weight.Bold)
        painter.setFont(badge_font)
        painter.setPen(sig_col)
        badge = "CLOCK" if is_clock else "PROBE"
        painter.drawText(QRect(4, y0 + 6, LABEL_W - 8, 14),
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter,
                         badge)

        # Signal name — larger, prominent
        name_font = QFont("Segoe UI", 10, QFont.Weight.Bold)
        painter.setFont(name_font)
        painter.setPen(C.text)
        text_rect = QRect(4, y0 + 18, LABEL_W - 8, rh - 24)
        painter.drawText(text_rect,
                         Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop,
                         name)

        # Colour accent bar on the left edge
        painter.fillRect(0, y0 + 2, 3, rh - 4, sig_col)

    # ── Ruler ─────────────────────────────────────────────────────────────────

    def _draw_ruler(self, painter: QPainter, C, W: int, ppt: float, sx: int):
        painter.fillRect(0, 0, W, RULER_H, C.primary_bg)
        font = QFont("Segoe UI", 7)
        painter.setFont(font)
        fm   = QFontMetrics(font)

        tick = max(10, int(40 / ppt) * 10)
        t = 0
        while True:
            px = LABEL_W + int(t * ppt) - sx
            if px > W: break
            if px >= LABEL_W:
                painter.setPen(QPen(C.outline, 1))
                painter.drawLine(px, RULER_H - 6, px, RULER_H)
                lbl = str(t)
                painter.setPen(QPen(C.text, 1))
                painter.drawText(px - fm.horizontalAdvance(lbl) // 2,
                                 RULER_H - 9, lbl)
            t += tick

    # ── Waveform row ─────────────────────────────────────────────────────────

    def _draw_row(self, painter: QPainter, C, sig: dict,
                  row_idx: int, y0: int, W: int,
                  ppt: float, sx: int, rh: int):
        is_clock = sig["is_clock"]
        events   = sig["events"]
        max_t    = self._max_time

        row_bg = C.primary_bg if row_idx % 2 == 0 else C.secondary_bg
        painter.fillRect(LABEL_W, y0, W - LABEL_W, rh, row_bg)

        sig_col = QColor("#FFAA00") if is_clock else QColor("#00D4FF")
        wt = y0 + WAVE_PAD          # wave top (HIGH y)
        wb = y0 + rh - WAVE_PAD     # wave bottom (LOW y)
        wm = (wt + wb) // 2         # midline

        def t2px(t: int) -> int:
            return LABEL_W + int(t * ppt) - sx

        def yval(v: int) -> int:
            if v == 1: return wt
            if v == 0: return wb
            return wm  # UNKNOWN

        if not events:
            painter.setPen(QPen(C.outline, 1, Qt.PenStyle.DashLine))
            painter.drawLine(LABEL_W, wm, W, wm)
            return

        # Build waveform path
        first_t, first_v = events[0]
        pre_v  = first_v if first_t == 0 else 2
        cur_y  = yval(pre_v)

        path = QPainterPath()
        path.moveTo(t2px(0), cur_y)
        if first_t > 0:
            path.lineTo(t2px(first_t), cur_y)

        for i, (t, v) in enumerate(events):
            px = t2px(t)
            ny = yval(v)
            path.lineTo(px, cur_y)
            path.lineTo(px, ny)
            cur_y = ny
            nx = t2px(events[i + 1][0]) if i + 1 < len(events) else t2px(max_t)
            path.lineTo(nx, cur_y)

        painter.setPen(QPen(sig_col, 2))
        painter.drawPath(path)

        # Fill HIGH regions
        fill = QColor(sig_col); fill.setAlpha(30)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(fill)
        all_evts = ([(0, pre_v)] if first_t > 0 else []) + list(events)
        for idx in range(len(all_evts)):
            ts, vs = all_evts[idx]
            te = all_evts[idx + 1][0] if idx + 1 < len(all_evts) else max_t
            if vs == 1:
                painter.drawRect(QRectF(t2px(ts), wt, t2px(te) - t2px(ts), wb - wt))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        # Transition dotted markers
        painter.setPen(QPen(sig_col.lighter(150), 1, Qt.PenStyle.DotLine))
        for t, _ in events:
            px = t2px(t)
            if LABEL_W <= px <= W:
                painter.drawLine(px, y0, px, y0 + rh)

    def sizeHint(self) -> QSize:
        n = max(1, len(self._data))
        return QSize(800, RULER_H + n * self._row_h + 10)


# ─────────────────────────────────────────────────────────────────────────────
# Dialog
# ─────────────────────────────────────────────────────────────────────────────
class TimingDiagramDialog(QDialog):
    """
    Real-time timing diagram. Press Record to start capturing.
    The simulation speed is NOT changed — you control that via the toolbar.
    The canvas always auto-scrolls to the most recent event.
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Timing Diagram")
        self.setMinimumSize(800, 360)
        self.resize(1100, 560)
        self.setWindowFlag(Qt.WindowType.Window)

        self._refresh_timer = QTimer(self)
        self._refresh_timer.setInterval(80)      # ~12 fps update
        self._refresh_timer.timeout.connect(self._refresh)

        self._build_ui()
        self._apply_theme()
        theme.theme_changed.connect(self._apply_theme)
        self._update_controls()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── Toolbar ──────────────────────────────────────────────────────────
        bar = QWidget(); bar.setObjectName("timingBar")
        bl  = QHBoxLayout(bar)
        bl.setContentsMargins(10, 6, 10, 6); bl.setSpacing(8)

        # Status
        self._dot  = QLabel("●"); self._dot.setFixedWidth(16)
        self._slbl = QLabel("Idle"); self._slbl.setFixedWidth(90)
        bl.addWidget(self._dot); bl.addWidget(self._slbl)
        bl.addSpacing(12)

        def mkbtn(label, name, slot, enabled=True, checkable=False):
            b = QPushButton(label)
            b.setObjectName(name)
            b.setFixedHeight(30)
            b.setEnabled(enabled)
            b.setCheckable(checkable)
            b.clicked.connect(slot)
            bl.addWidget(b)
            return b

        self._btn_rec   = mkbtn("Record", "btnRecord", self._on_record)
        self._btn_stop  = mkbtn("Stop",   "btnStop",  self._on_stop,  False)
        self._btn_clear = mkbtn("Clear",  "btnClear", self._on_clear)
        bl.addSpacing(16)

        # Follow toggle
        self._btn_follow = QPushButton("⤵ Follow")
        self._btn_follow.setObjectName("btnFollow")
        self._btn_follow.setCheckable(True)
        self._btn_follow.setChecked(True)
        self._btn_follow.setFixedHeight(30)
        self._btn_follow.toggled.connect(self._on_follow)
        bl.addWidget(self._btn_follow)

        bl.addSpacing(16)

        # Zoom
        bl.addWidget(QLabel("Zoom:"))
        mkbtn("+",   "btnZ", self._zoom_in)
        mkbtn("−",   "btnZ", self._zoom_out)
        mkbtn("Fit", "btnZ", self._zoom_fit)

        bl.addStretch()

        self._sig_lbl = QLabel("0 signals")
        bl.addWidget(self._sig_lbl)
        bl.addSpacing(8)

        x = QPushButton("✕"); x.setFixedSize(28, 28); x.clicked.connect(self.close)
        bl.addWidget(x)

        root.addWidget(bar)

        # Hint bar
        hint = QLabel(
            "  Ctrl+Wheel = zoom  ·  Middle / Alt+drag = pan  ·  "
            "Clocks = amber  ·  Probes = cyan  ·  ⤵ Follow scrolls to live edge"
        )
        hint.setObjectName("timingHint"); hint.setFixedHeight(20)
        root.addWidget(hint)

        # Canvas (no scroll area — canvas fills the space and draws its own scroll)
        self._canvas = TimingCanvas()
        self._canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        root.addWidget(self._canvas)

        # Footer
        self._footer = QLabel("  Press Record to begin capturing signal transitions.")
        self._footer.setObjectName("timingFooter"); self._footer.setFixedHeight(22)
        root.addWidget(self._footer)

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        C = theme.get_theme()
        bg=C.primary_bg.name(); bg2=C.secondary_bg.name()
        txt=C.text.name(); brd=C.outline.name()
        btn_c=C.button.name(); hi=C.hl_text_bg.name()
        self.setStyleSheet(f"""
            QDialog    {{ background:{bg}; color:{txt}; }}
            #timingBar {{ background:{bg2}; border-bottom:1px solid {brd}; }}
            #timingHint  {{ background:{bg}; color:{brd}; font-size:8pt;
                            padding-left:5px; border-bottom:1px solid {brd}; }}
            #timingFooter{{ background:{bg}; color:{brd}; font-size:8pt;
                            padding-left:6px; border-top:1px solid {brd}; }}
            QPushButton {{
                background:{btn_c}; color:{txt}; border:1px solid {brd};
                border-radius:4px; padding:2px 10px; font-size:9pt;
            }}
            QPushButton:hover    {{ background:{hi}; color:#fff; }}
            QPushButton:checked  {{ background:{hi}; color:#fff; }}
            QPushButton:disabled {{ color:{brd}; }}
            #btnRecord {{ background:#6b1010; color:#ffaaaa; border-color:#aa3333; }}
            #btnRecord:hover {{ background:#aa1a1a; color:#fff; }}
            #btnRecord:disabled {{ background:{btn_c}; color:{brd}; border-color:{brd}; }}
            #btnStop {{ background:#1a3a6b; color:#aaccff; border-color:#3366aa; }}
            #btnStop:hover {{ background:#1a5aaa; color:#fff; }}
            #btnStop:disabled {{ background:{btn_c}; color:{brd}; border-color:{brd}; }}
            #btnFollow {{ background:#1a2e1a; color:#88cc88; border-color:#336633; }}
            #btnFollow:checked {{ background:#2a5a2a; color:#aaffaa; }}
            QLabel {{ color:{txt}; font-family:"Segoe UI"; font-size:9pt; }}
        """)
        self._canvas.update()

    # ── Controls state ────────────────────────────────────────────────────────

    def _update_controls(self):
        rec = tracer.recording
        has = tracer.has_data()
        self._btn_rec.setEnabled(not rec)
        self._btn_stop.setEnabled(rec)
        self._btn_clear.setEnabled(has or rec)
        if rec:
            self._dot.setStyleSheet("color:#ff3333; font-size:14pt;")
            self._slbl.setText("Recording…")
        elif has:
            self._dot.setStyleSheet("color:#33cc66; font-size:14pt;")
            self._slbl.setText("Captured")
        else:
            self._dot.setStyleSheet("color:#555; font-size:14pt;")
            self._slbl.setText("Idle")

    # ── Actions ───────────────────────────────────────────────────────────────

    def _on_record(self):
        try:
            from core.LogicCore import logic
            start_t = logic.Global_Clock
            logic.recording = True
        except Exception:
            start_t = 0
        tracer.start(start_t)
        self._canvas._follow = True
        self._btn_follow.setChecked(True)
        self._refresh_timer.start()
        self._update_controls()

    def _on_stop(self):
        try:
            from core.LogicCore import logic
            logic.recording = False
        except Exception:
            pass
        tracer.stop()
        self._refresh_timer.stop()
        self._refresh()
        self._update_controls()

    def _on_clear(self):
        was_rec = tracer.recording
        tracer.clear()
        if was_rec:
            try:
                from core.LogicCore import logic
                logic.recording = False
            except Exception:
                pass
            self._refresh_timer.stop()
        self._canvas.set_data([], 1)
        self._sig_lbl.setText("0 signals")
        self._footer.setText("  Cleared — press Record to capture again.")
        self._update_controls()

    def _on_follow(self, checked: bool):
        self._canvas._follow = checked
        if checked:
            self._canvas._scroll_to_end()
            self._canvas.update()

    # ── Zoom ──────────────────────────────────────────────────────────────────

    def _zoom_in(self):
        self._canvas._ppt = min(MAX_PPT, self._canvas._ppt * 1.3)
        if self._canvas._follow: self._canvas._scroll_to_end()
        self._canvas.update()

    def _zoom_out(self):
        self._canvas._ppt = max(MIN_PPT, self._canvas._ppt / 1.3)
        if self._canvas._follow: self._canvas._scroll_to_end()
        self._canvas.update()

    def _zoom_fit(self):
        vw = self._canvas._visible_w()
        mt = self._canvas._max_time
        if mt > 0 and vw > 0:
            self._canvas._ppt     = max(MIN_PPT, min(MAX_PPT, vw / mt))
            self._canvas._scroll_x = 0
            self._canvas._follow   = False
            self._btn_follow.setChecked(False)
            self._canvas.update()

    # ── Refresh ───────────────────────────────────────────────────────────────

    def _refresh(self):
        data     = tracer.snapshot()
        max_time = tracer.max_time()
        self._canvas.set_data(data, max(max_time, 1))
        n = len(data)
        self._sig_lbl.setText(f"{n} signal{'s' if n != 1 else ''}")

        if data:
            nc  = sum(1 for s in data if s["is_clock"])
            np_ = n - nc
            ne  = sum(len(s["events"]) for s in data)
            self._footer.setText(
                f"  {nc} clock(s)  ·  {np_} probe(s)  "
                f"·  {ne} transitions  ·  t = 0 – {max_time}"
            )
        else:
            self._footer.setText(
                "  No data — press Record while the simulation is running."
            )
        self._update_controls()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def showEvent(self, event):
        super().showEvent(event)
        self._refresh()

    def closeEvent(self, event):
        if tracer.recording:
            try:
                from core.LogicCore import logic
                logic.recording = False
            except Exception:
                pass
            tracer.stop()
            self._refresh_timer.stop()
        super().closeEvent(event)
