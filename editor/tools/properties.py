from __future__ import annotations
from functools import partial
from typing import cast
from core.QtCore import *
from core.Enums import Prop, Facing

import editor.theme as theme
from editor.circuit.compitem import CompItem


class PropertiesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.comp: CompItem|None = None
        self.labels: dict[Prop, QLabel] = {}
        self.widgets: dict[Prop, QWidget] = {}
        self.buildUI()
        theme.theme_changed.connect(self.apply_theme)
        self.apply_theme()
        self.hide()

    def buildUI(self):
        self.setFixedWidth(175)

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

        # Tag Property
        self.labels[Prop.TAG] = QLabel("Tag:")
        self.widgets[Prop.TAG] = QLabel("-")

        # Facing Property
        self.labels[Prop.FACING] = QLabel("Facing:")
        facingCombo = QComboBox()
        facing_map = {
            Facing.EAST:  "East",
            Facing.SOUTH: "South",
            Facing.WEST:  "West",
            Facing.NORTH: "North",
        }
        for i, label in facing_map.items():
            facingCombo.addItem(label, i)

        facingCombo.currentIndexChanged.connect(partial(self.changeProperty, Prop.FACING))
        self.widgets[Prop.FACING] = facingCombo

        # Input Size Property
        self.labels[Prop.INPUTSIZE] = QLabel("No of Inputs:")
        inputSpinbox = QSpinBox()
        inputSpinbox.valueChanged.connect(partial(self.changeProperty, Prop.INPUTSIZE))
        self.widgets[Prop.INPUTSIZE] = inputSpinbox


        # Assembling Property Widgets
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
                    match prop:
                        case Prop.INPUTSIZE:
                            cprop = cast(int, compProps[prop])
                            widget = cast(QSpinBox, self.widgets[prop])
                            widget.blockSignals(True)
                            widget.setValue(cprop)
                            widget.blockSignals(False)

                        case Prop.FACING:
                            cprop = cast(Facing, compProps[prop])
                            widget = cast(QComboBox, self.widgets[prop])
                            widget.blockSignals(True)
                            widget.setCurrentIndex(cprop.value)
                            widget.blockSignals(False)

                        case Prop.STATE:
                            cprop = compProps[prop]
                            widget = cast(QLabel, self.widgets[prop])
                            widget.setText("ON" if cprop else "OFF")

                        case _:
                            cprop = compProps[prop]
                            widget = cast(QLabel, self.widgets[prop])
                            widget.setText(str(cprop))

            self.show()
        else:
            self.hide()


    def changeProperty(self, prop: Prop, value):
        if not self.comp: return
        
        # setProperty() automatically calls updateTab() using listener IF the property actually changed
        if not self.comp.setProperty(prop, value):
            self.updateTab()