from __future__ import annotations
from functools import partial
from typing import Any
from core.QtCore import *
from core.Enums import Prop

import editor.theme as theme
from editor.circuit.compitem import CompItem


class PropertiesPanel(QWidget):
    positionChanged = Signal(QPoint)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.comp: CompItem|None = None
        self.labels: dict[Prop, QLabel] = {}
        self.widgets: dict[Prop, Any] = {}
        self.buildUI()
        self.hide()

        self.drag_pos = None
        self.title.installEventFilter(self)

    def buildUI(self):
        self.setFixedWidth(175)
        self.apply_theme()

        outer = QVBoxLayout(self)
        outer.setContentsMargins(12, 12, 12, 12)
        outer.setSpacing(10)

        # Title
        self.title = QLabel("Properties")
        self.title.setObjectName("title")
        outer.addWidget(self.title)

        # Divider
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setStyleSheet("color: #555;")
        outer.addWidget(line)

        # Form
        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)

        # Properties
        # All compItems have "tag", "facing"

        self.labels[Prop.TAG] = QLabel("Tag:")
        self.widgets[Prop.TAG] = QLabel("-")

        self.labels[Prop.FACING] = QLabel("Facing:")
        self.widgets[Prop.FACING] = QLabel("-")

        self.labels[Prop.INPUTSIZE] = QLabel("No of Inputs:")
        self.widgets[Prop.INPUTSIZE] = QSpinBox()
        self.widgets[Prop.INPUTSIZE].valueChanged.connect(partial(self.changeProperty, Prop.INPUTSIZE))

        for prop in self.widgets.keys():
            form.addRow(self.labels[prop], self.widgets[prop])

        outer.addLayout(form)
        outer.addStretch()
        

    def apply_theme(self):
        colors = theme.get_theme()
        self.setStyleSheet(f"""
            PropertiesPanel {{
                background: {colors.secondary_bg.name()};
                border-radius: 8px;
            }}
            QLabel#title {{
                font-size: 13px;
                font-weight: bold;
                color: {colors.text.name()};
                padding-bottom: 4px;
            }}
            QLabel {{
                color: {colors.text.name()};
                font-size: 11px;
            }}
            QSpinBox {{
                background: {colors.primary_bg.name()};
                color: {colors.text.name()};
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px 4px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 16px;
            }}
        """)

    def on_theme_changed(self):
        self.apply_theme()
        self.update()

    def eventFilter(self, obj, event):
        if obj is self.title and event.type() == QEvent.Type.MouseButtonPress:
            if event.button() == Qt.MouseButton.LeftButton:
                self.drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
                return True
        elif obj is self.title and event.type() == QEvent.Type.MouseMove:
            if event.buttons() & Qt.MouseButton.LeftButton and self.drag_pos:
                self.move(event.globalPosition().toPoint() - self.drag_pos)
                return True
        elif obj is self.title and event.type() == QEvent.Type.MouseButtonRelease:
            if event.button() == Qt.MouseButton.LeftButton:
                self.drag_pos = None
                return True
        return super().eventFilter(obj, event)
    
    def moveEvent(self, event):
        """Emit the new absolute position whenever the panel moves."""
        super().moveEvent(event)
        self.positionChanged.emit(self.pos())

    def selectionChanged(self, selectedItems: list[QGraphicsItem]):
        n = len(selectedItems)

        if n > 1 or n == 0:
            self.comp = None
            self.hide()
        elif isinstance(selectedItems[0], CompItem):
            if self.comp:
                self.comp.removePropertyChangedListener(self.updateTab)
            self.comp = selectedItems[0]
            self.comp.addPropertyChangedListener(self.updateTab)
            self.updateTab()


    def updateTab(self):
        if self.comp:
            compProps = self.comp.getProperties()

            # Display name
            tag = compProps[Prop.TAG]
            self.title.setText(f"Properties: {tag}")

            for prop in self.widgets.keys():
                isVisible = (prop in compProps)
                self.widgets[prop].setVisible(isVisible)
                self.labels[prop].setVisible(isVisible)

                if isVisible:
                    if prop == Prop.INPUTSIZE:
                        spinbox = self.widgets[prop]
                        spinbox.blockSignals(True)
                        spinbox.setValue(compProps[prop])
                        spinbox.blockSignals(False)
                    elif prop == Prop.FACING:
                        self.widgets[prop].setText(compProps[prop].name.capitalize())
                    else:
                        self.widgets[prop].setText(str(compProps[prop]))

            self.show()
        else:
            self.hide()


    def changeProperty(self, prop: Prop, value):
        if not self.comp: return
        # setProperty() automatically calls updateTab() using listener IF the property actually changed

        if not self.comp.setProperty(prop, value):
            self.updateTab()