from __future__ import annotations
from functools import partial
from typing import Any
from core.QtCore import *
from core.Enums import Prop
from editor.styles import Color, Font

from editor.circuit.compitem import CompItem


class PropertiesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.comp: CompItem|None = None
        self.labels: dict[Prop, QLabel] = {}
        self.widgets: dict[Prop, Any] = {}
        self.buildUI()
        self.hide()

    def buildUI(self):
        self.setFixedWidth(175)
        self.setStyleSheet(f"""
            PropertiesPanel {{
                background: {Color.secondary_bg.name()};
                border-radius: 8px;
            }}
            QLabel#title {{
                font-size: 13px;
                font-weight: bold;
                color: {Color.text.name()};
                padding-bottom: 4px;
            }}
            QLabel {{
                color: {Color.text.name()};
                font-size: 11px;
            }}
            QSpinBox {{
                background: {Color.primary_bg.name()};
                color: {Color.text.name()};
                border: 1px solid #555;
                border-radius: 4px;
                padding: 2px 4px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                width: 16px;
            }}
        """)

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
        # All compItems have "pos", "tag", "facing", "mirror"
        self.labels[Prop.POS] = QLabel("Pos:")
        self.widgets[Prop.POS] = QLabel("-")

        self.labels[Prop.TAG] = QLabel("Tag:")
        self.widgets[Prop.TAG] = QLabel("-")

        self.labels[Prop.FACING] = QLabel("Facing:")
        self.widgets[Prop.FACING] = QLabel("-")

        self.labels[Prop.MIRROR] = QLabel("Mirror:")
        self.widgets[Prop.MIRROR] = QLabel("-")

        self.labels[Prop.STATE] = QLabel("State:")
        self.widgets[Prop.STATE] = QLabel("-")

        self.labels[Prop.INPUTSIZE] = QLabel("No of Inputs:")
        self.widgets[Prop.INPUTSIZE] = QSpinBox()
        self.widgets[Prop.INPUTSIZE].valueChanged.connect(partial(self.changeProperty, Prop.INPUTSIZE))

        for prop in self.widgets.keys():
            form.addRow(self.labels[prop], self.widgets[prop])

        outer.addLayout(form)
        outer.addStretch()
    

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