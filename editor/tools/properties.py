from __future__ import annotations
from functools import partial
from typing import cast
from core.QtCore import *
from core.Enums import Prop, Facing

import editor.theme as theme
from editor.circuit.catalog import CompItem, GateItem
from editor.circuit.commands import PropertyChangeCommand


class PropertiesPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.comp: CompItem|None = None
        self.labels: dict[Prop, QLabel] = {}
        self.widgets: dict[Prop, QWidget] = {}

        self.closetimer = QTimer()
        self.closetimer.setSingleShot(True)
        self.closetimer.timeout.connect(self.closeTab)
        self.closetimer.setInterval(30)

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
        # All compItems have "tag/label", "facing"

        # Tag Property
        self.labels[Prop.TAG] = QLabel("Tag:")
        tagUnEdit = QLineEdit("-")
        tagUnEdit.setReadOnly(True)
        self.widgets[Prop.TAG] = tagUnEdit

        self.labels[Prop.LABEL] = QLabel("Tag:")
        labelEdit = QLineEdit("-")
        labelEdit.returnPressed.connect(lambda: self.changeProperty(Prop.LABEL, labelEdit.text()))
        
        self.widgets[Prop.LABEL] = labelEdit

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
        """This function is called everytime the selectedItems list changes in the canvas/scene"""
        n = len(selectedItems)

        if n > 1 or n == 0:
            # None or multiple items selected
            if self.comp:
                self.closetimer.start()
        
        elif isinstance(selectedItems[0], CompItem):
            # Single CompItem selected
            da_comp = selectedItems[0]
            self.closetimer.stop()

            if self.comp:
                if self.comp is da_comp:
                    return
                self.comp.removePropertyChangedListener(self.updateTab)
            self.comp = da_comp
            self.comp.addPropertyChangedListener(self.updateTab)
            self.updateTab()
    
    
    def closeTab(self):
        self.comp = None
        self.hide()

    def updateTab(self):
        if self.comp is None:
            self.hide()
            return
            

        # Setting and unhiding properties
        compProps = self.comp.getProperties()
        tag = compProps.get(Prop.TAG, None)
        if tag is None:
            tag = compProps.get(Prop.LABEL, None)
        
        self.title.setText(f"Properties: {tag}")

        for prop in self.widgets.keys():
            isVisible = (prop in compProps)
            self.widgets[prop].setVisible(isVisible)
            self.labels[prop].setVisible(isVisible)

            if not isVisible:
                continue
            self.widgets[prop].blockSignals(True)
            match prop:
                case Prop.LABEL:
                    cprop = cast(str, compProps[prop])
                    widget = cast(QLineEdit, self.widgets[prop])
                    widget.setText(cprop)
                
                case Prop.INPUTSIZE:
                    cprop = cast(int, compProps[prop])
                    widget = cast(QSpinBox, self.widgets[prop])
                    widget.setValue(cprop)

                case Prop.FACING:
                    cprop = cast(Facing, compProps[prop])
                    widget = cast(QComboBox, self.widgets[prop])
                    widget.setCurrentIndex(cprop.value)

                case Prop.STATE:
                    cprop = compProps[prop]
                    widget = cast(QLabel, self.widgets[prop])
                    widget.setText("ON" if cprop else "OFF")

                case _:
                    cprop = compProps[prop]
                    widget = cast(QLabel, self.widgets[prop])
                    widget.setText(str(cprop))
            
            self.widgets[prop].blockSignals(False)

        self.show()


    def changeProperty(self, prop: Prop, value):
        if not self.comp: return
        
        cmd = PropertyChangeCommand(self.comp, prop, self.comp.getProperties()[prop], value)
        self.comp.cscene.undo_stack.push(cmd)
        
        # setProperty() automatically calls updateTab() using listener IF the property actually changed
        if not self.comp.setProperty(prop, value):
            self.updateTab()