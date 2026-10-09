# -*- coding: utf-8 -*-
from copy import deepcopy
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QCheckBox, QComboBox, QGroupBox, QHBoxLayout,
                               QLabel, QListWidget, QListWidgetItem,
                               QPushButton, QVBoxLayout, QWidget, QMessageBox,
                               QAbstractItemView, QInputDialog)
from ui.scroll_area import make_scroll_area
from machine_builder_core import normalize_axis


class HotConnectTab(QWidget):
    """Pestaña para configurar Hot Connect Groups."""

    def __init__(self, axes_provider, parent=None):
        super().__init__(parent)
        self.axes_provider = axes_provider  # callable que devuelve lista de ejes
        self.hot_connect_groups = []  # lista de dicts: {"name": "", "axes": []}
        self._build_ui()

    def _build_ui(self):
        container = QWidget()
        root = QVBoxLayout(container)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(12)

        # Lista de grupos
        group_box = QGroupBox("Hot Connect Groups")
        g_layout = QVBoxLayout(group_box)

        # Toolbar para grupos
        toolbar = QHBoxLayout()
        self.add_group_btn = QPushButton("➕ Añadir grupo")
        self.add_group_btn.clicked.connect(self.add_group)
        self.remove_group_btn = QPushButton("🗑️ Eliminar grupo")
        self.remove_group_btn.clicked.connect(self.remove_group)
        toolbar.addWidget(self.add_group_btn)
        toolbar.addWidget(self.remove_group_btn)
        toolbar.addStretch()
        g_layout.addLayout(toolbar)

        # Lista de grupos
        self.group_list = QListWidget()
        self.group_list.setSelectionMode(QAbstractItemView.SingleSelection)
        self.group_list.currentRowChanged.connect(self.on_group_selected)
        g_layout.addWidget(self.group_list)

        # Ejes disponibles / asignados para el grupo seleccionado
        axes_box = QGroupBox("Ejes del grupo seleccionado")
        axes_layout = QVBoxLayout(axes_box)

        # Dos listas: disponibles y asignados
        lists_layout = QHBoxLayout()

        # Disponibles
        avail_box = QVBoxLayout()
        avail_box.addWidget(QLabel("Ejes disponibles"))
        self.avail_list = QListWidget()
        self.avail_list.setSelectionMode(QAbstractItemView.MultiSelection)
        avail_box.addWidget(self.avail_list)
        lists_layout.addLayout(avail_box)

        # Botones mover
        move_btns = QVBoxLayout()
        self.add_axis_btn = QPushButton("▶ Añadir")
        self.add_axis_btn.clicked.connect(self.add_axes_to_group)
        self.remove_axis_btn = QPushButton("◀ Quitar")
        self.remove_axis_btn.clicked.connect(self.remove_axes_from_group)
        move_btns.addStretch()
        move_btns.addWidget(self.add_axis_btn)
        move_btns.addWidget(self.remove_axis_btn)
        move_btns.addStretch()
        lists_layout.addLayout(move_btns)

        # Asignados
        assigned_box = QVBoxLayout()
        assigned_box.addWidget(QLabel("Ejes en el grupo"))
        self.assigned_list = QListWidget()
        self.assigned_list.setSelectionMode(QAbstractItemView.MultiSelection)
        assigned_box.addWidget(self.assigned_list)
        lists_layout.addLayout(assigned_box)

        axes_layout.addLayout(lists_layout)
        g_layout.addWidget(axes_box)

        root.addWidget(group_box, 1)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(make_scroll_area(container))

    def showEvent(self, event):
        """Se llama cuando la pestaña se hace visible."""
        super().showEvent(event)
        self.refresh_axes()
        self.refresh_assigned_list()

    def on_group_selected(self, row):
        self.refresh_assigned_list()

    def refresh_axes(self):
        """Actualiza la lista de ejes disponibles desde el proveedor."""
        axes = self.axes_provider() or []
        self.all_axes = [a for a in axes if a.get("enabled", True)]
        self.refresh_assigned_list()

    def refresh_assigned_list(self):
        row = self.group_list.currentRow()
        if row < 0 or row >= len(self.hot_connect_groups):
            self.assigned_list.clear()
            self.avail_list.clear()
            return

        group = self.hot_connect_groups[row]
        assigned_names = set(group.get("axes", []))

        self.assigned_list.clear()
        self.avail_list.clear()

        for axis in self.all_axes:
            name = axis.get("name", "")
            if name in assigned_names:
                self.assigned_list.addItem(name)
            else:
                self.avail_list.addItem(name)

    def add_group(self):
        name, ok = QInputDialog.getText(self, "Nuevo grupo", "Nombre del grupo Hot Connect:")
        if ok and name.strip():
            name = name.strip()
            if any(g["name"] == name for g in self.hot_connect_groups):
                QMessageBox.warning(self, "Nombre duplicado", "Ya existe un grupo con ese nombre.")
                return
            self.hot_connect_groups.append({"name": name, "axes": []})
            self.group_list.addItem(name)
            self.group_list.setCurrentRow(len(self.hot_connect_groups) - 1)

    def remove_group(self):
        row = self.group_list.currentRow()
        if row >= 0:
            self.hot_connect_groups.pop(row)
            self.group_list.takeItem(row)
            self.refresh_assigned_list()

    def add_axes_to_group(self):
        row = self.group_list.currentRow()
        if row < 0:
            return
        selected = [item.text() for item in self.avail_list.selectedItems()]
        if not selected:
            return
        group = self.hot_connect_groups[row]
        for name in selected:
            if name not in group["axes"]:
                group["axes"].append(name)
        self.refresh_assigned_list()

    def remove_axes_from_group(self):
        row = self.group_list.currentRow()
        if row < 0:
            return
        selected = [item.text() for item in self.assigned_list.selectedItems()]
        if not selected:
            return
        group = self.hot_connect_groups[row]
        for name in selected:
            group["axes"].remove(name)
        self.refresh_assigned_list()

    def configuration(self):
        """Devuelve la configuración de grupos para guardar en config."""
        self.refresh_axes()
        # Validar que los ejes asignados siguen existiendo
        valid_axes = {a.get("name", "") for a in self.axes_provider() or [] if a.get("enabled", True)}
        for group in self.hot_connect_groups:
            group["axes"] = [a for a in group.get("axes", []) if a in group.get("axes", []) and a in {a.get("name", "") for a in self.axes_provider() or []}]
        return deepcopy(self.hot_connect_groups)

    def load_configuration(self, groups):
        self.hot_connect_groups = deepcopy(groups) if groups else []
        self.group_list.clear()
        for g in self.hot_connect_groups:
            self.group_list.addItem(g["name"])
        if self.hot_connect_groups:
            self.group_list.setCurrentRow(0)
        self.refresh_axes()
        self.refresh_assigned_list()


# Test standalone
if __name__ == "__main__":
    from PySide6.QtWidgets import QApplication
    import sys
    app = QApplication(sys.argv)
    
    def dummy_axes():
        return [
            {"name": "Axis_01", "enabled": True},
            {"name": "Axis_02", "enabled": True},
            {"name": "Axis_03", "enabled": True},
        ]
    
    w = HotConnectTab(dummy_axes)
    w.show()
    sys.exit(app.exec())