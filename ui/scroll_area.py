# -*- coding: utf-8 -*-
"""QScrollArea reutilizable para las pestañas que pueden desbordar en pantallas bajas."""
from PySide6.QtWidgets import QFrame, QScrollArea

STYLE = (
    "QScrollArea{border:none;background-color:#f5f7fb;}"
    "QScrollArea>QWidget{background:transparent;}"
    "QScrollArea>QWidget>QWidget{background:transparent;}"
)


def make_scroll_area(widget):
    """Envuelve widget en un QScrollArea con scroll vertical cuando no cabe."""
    area = QScrollArea()
    area.setWidgetResizable(True)
    area.setFrameShape(QFrame.NoFrame)
    area.setStyleSheet(STYLE)
    area.setWidget(widget)
    return area
