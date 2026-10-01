# -*- coding: utf-8 -*-
from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from machine_builder_core import (
    ROBOT_DEVICES,
    ROBOT_TYPES,
    default_robot_parameters,
    group_axis_order,
    normalize_robot_group,
    normalize_robot_parameters,
    robot_parameter_definitions,
    robot_parameter_errors,
)


ROBOT_LABELS = {
    "CARTESIAN_2D": "Cartesiano 2D (X/Z)",
    "CARTESIAN_3D": "Cartesiano 3D (X/Y/Z)",
    "CARTESIAN_4D": "Cartesiano 4D (X/Y/Z/C)",
    "PORTAL_AC_5DOF": "Portal AC 5 DOF",
    "BELT_2DOF": "Belt Kinematic 2 DOF",
    "SCARA_3DOF": "SCARA 3 DOF",
    "SCARA": "SCARA 4 DOF",
    "DELTA_2DOF": "Delta 2 DOF",
    "DELTA": "Delta 3 DOF",
    "DELTA_4DOF": "Delta 4 DOF",
    "DELTA_5DOF": "Delta 5 DOF",
    "LINEAR_DELTA_3DOF": "Linear Delta 3 DOF",
    "LINEAR_DELTA_4DOF": "Linear Delta 4 DOF",
    "ARTICULATED_4DOF": "Articulated 4 DOF",
    "ARTICULATED_LINEAR_A1_4DOF": "Articulated + Linear A1 4 DOF",
}


class RobotGroupsTab(QWidget):
    """Robot Groups V0.9.0 con parámetros geométricos dinámicos."""

    def __init__(self, axis_names_provider, parent=None):
        super().__init__(parent)
        self.axis_names_provider = axis_names_provider
        self.groups = []
        self.current_index = -1
        self.loading = False
        self.role_combos = {}
        self.parameter_widgets = {}
        self._build_ui()
        self.refresh_group_list()
        self.set_empty_state(True)

    def _build_ui(self):
        root = QHBoxLayout(self)
        root.setContentsMargins(16, 16, 16, 16)
        root.setSpacing(14)

        left = QGroupBox("Robot Groups configurados")
        left.setMinimumWidth(260)
        left.setMaximumWidth(350)
        left_layout = QVBoxLayout(left)

        self.empty_list_label = QLabel(
            "No hay Robot Groups definidos.\n"
            "Pulsa «+ Añadir grupo» para crear uno."
        )
        self.empty_list_label.setAlignment(Qt.AlignCenter)
        self.empty_list_label.setWordWrap(True)
        self.empty_list_label.setStyleSheet("color:#6b7280;padding:18px;")

        self.group_list = QListWidget()
        self.group_list.currentRowChanged.connect(self.select_group)
        left_layout.addWidget(self.empty_list_label)
        left_layout.addWidget(self.group_list, 1)

        button_row = QHBoxLayout()
        self.add_button = QPushButton("+ Añadir grupo")
        self.remove_button = QPushButton("- Eliminar grupo")
        self.add_button.clicked.connect(self.add_group)
        self.remove_button.clicked.connect(self.remove_group)
        button_row.addWidget(self.add_button)
        button_row.addWidget(self.remove_button)
        left_layout.addLayout(button_row)
        root.addWidget(left)

        self.editor_scroll = QScrollArea()
        self.editor_scroll.setWidgetResizable(True)
        self.editor_scroll.setFrameShape(QScrollArea.NoFrame)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 8, 0)
        right_layout.setSpacing(12)
        self.editor_scroll.setWidget(right)

        self.empty_editor_label = QLabel(
            "No hay ningún Robot Group seleccionado.\n"
            "Crea uno para configurar su cinemática, ejes y parámetros."
        )
        self.empty_editor_label.setAlignment(Qt.AlignCenter)
        self.empty_editor_label.setWordWrap(True)
        self.empty_editor_label.setStyleSheet(
            "color:#6b7280;font-size:14px;padding:35px;"
        )
        right_layout.addWidget(self.empty_editor_label)

        self.general_group = QGroupBox("Datos generales del Robot Group")
        general_form = QFormLayout(self.general_group)
        general_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.name_edit = QLineEdit()
        self.type_combo = QComboBox()
        for kind in ROBOT_TYPES:
            self.type_combo.addItem(ROBOT_LABELS.get(kind, kind), kind)
        self.device_label = QLabel()
        self.device_label.setWordWrap(True)
        general_form.addRow(self._label("Nombre IEC"), self.name_edit)
        general_form.addRow(self._label("Tipo de robot"), self.type_combo)
        general_form.addRow(self._label("Dispositivo Lenze"), self.device_label)
        right_layout.addWidget(self.general_group)

        self.axes_group = QGroupBox("Asignación de ejes")
        self.axes_form = QFormLayout(self.axes_group)
        self.axes_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        right_layout.addWidget(self.axes_group)

        self.parameters_group = QGroupBox("Parámetros del Robot")
        self.parameters_form = QFormLayout(self.parameters_group)
        self.parameters_form.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)
        self.parameters_empty_label = QLabel(
            "Este tipo de robot no necesita parámetros geométricos adicionales."
        )
        self.parameters_empty_label.setWordWrap(True)
        self.parameters_empty_label.setStyleSheet("color:#6b7280;padding:8px;")
        right_layout.addWidget(self.parameters_group)

        self.validation_group = QGroupBox("Validación y resumen")
        validation_layout = QVBoxLayout(self.validation_group)
        self.validation_label = QLabel()
        self.validation_label.setWordWrap(True)
        self.validate_button = QPushButton("Validar Robot Group")
        self.validate_button.clicked.connect(self.show_validation)
        validation_layout.addWidget(self.validation_label)
        validation_layout.addWidget(self.validate_button, 0, Qt.AlignRight)
        right_layout.addWidget(self.validation_group)
        right_layout.addStretch()
        root.addWidget(self.editor_scroll, 1)

        self.name_edit.textChanged.connect(self.store_current)
        self.type_combo.currentIndexChanged.connect(self.robot_type_changed)

    @staticmethod
    def _label(text):
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        label.setMinimumWidth(190)
        return label

    @staticmethod
    def _clear_form(form):
        while form.rowCount():
            form.removeRow(0)

    def set_empty_state(self, empty):
        self.empty_list_label.setVisible(empty)
        self.group_list.setVisible(not empty)
        self.empty_editor_label.setVisible(empty)
        self.general_group.setVisible(not empty)
        self.axes_group.setVisible(not empty)
        self.parameters_group.setVisible(not empty)
        self.validation_group.setVisible(not empty)
        self.remove_button.setEnabled(not empty)

        if empty:
            self.current_index = -1
            self.role_combos = {}
            self.parameter_widgets = {}
            self.name_edit.clear()
            self.device_label.clear()
            self.validation_label.clear()
            self._clear_form(self.axes_form)
            self._clear_form(self.parameters_form)

    def active_axis_names(self):
        return [
            str(value)
            for value in (self.axis_names_provider() or [])
            if str(value).strip()
        ]

    def default_group(self, index):
        kind = next(iter(ROBOT_TYPES))
        names = self.active_axis_names()
        return {
            "name": f"RobotGroup_{index:02d}",
            "type": kind,
            "axes": {
                role: names[i] if i < len(names) else ""
                for i, role in enumerate(ROBOT_TYPES[kind])
            },
            "group_parameters": default_robot_parameters(kind),
        }

    def add_group(self):
        self.store_current()
        self.groups.append(self.default_group(len(self.groups) + 1))
        self.set_empty_state(False)
        self.refresh_group_list()
        self.group_list.setCurrentRow(len(self.groups) - 1)

    def remove_group(self):
        row = self.group_list.currentRow()
        if row < 0 or row >= len(self.groups):
            return
        self.groups.pop(row)
        self.current_index = -1
        self.refresh_group_list()
        if self.groups:
            self.group_list.setCurrentRow(min(row, len(self.groups) - 1))
        else:
            self.set_empty_state(True)

    def refresh_group_list(self):
        row = self.group_list.currentRow()
        self.group_list.blockSignals(True)
        self.group_list.clear()
        for group in self.groups:
            label = ROBOT_LABELS.get(group.get("type"), group.get("type", ""))
            self.group_list.addItem(
                f"{group.get('name', 'RobotGroup')}  ·  {label}"
            )
        if 0 <= row < len(self.groups):
            self.group_list.setCurrentRow(row)
        self.group_list.blockSignals(False)
        self.empty_list_label.setVisible(not self.groups)
        self.group_list.setVisible(bool(self.groups))
        self.remove_button.setEnabled(bool(self.groups))

    def select_group(self, row):
        self.store_current()
        if row < 0 or row >= len(self.groups):
            self.current_index = -1
            return
        self.current_index = row
        self.set_empty_state(False)
        self.load_group(self.groups[row])

    def load_group(self, group):
        self.loading = True
        normalized = normalize_robot_group(group, self.current_index + 1)
        self.groups[self.current_index] = normalized
        self.name_edit.setText(normalized["name"])
        kind = normalized["type"]
        self.type_combo.setCurrentIndex(max(0, self.type_combo.findData(kind)))
        self.rebuild_axis_assignments(normalized["axes"])
        self.rebuild_parameter_fields(normalized["group_parameters"])
        self.update_device_label()
        self.loading = False
        self.update_validation()

    def robot_type_changed(self, *_):
        if self.loading:
            return
        previous_axes = self.current_axes_mapping()
        previous_parameters = self.current_group_parameters()
        self.rebuild_axis_assignments(previous_axes)
        self.rebuild_parameter_fields(previous_parameters)
        self.update_device_label()
        self.store_current()
        self.update_validation()

    def rebuild_axis_assignments(self, previous=None):
        previous = dict(previous or {})
        self._clear_form(self.axes_form)
        self.role_combos = {}
        kind = self.type_combo.currentData()
        names = self.active_axis_names()

        for index, role in enumerate(ROBOT_TYPES.get(kind, [])):
            combo = QComboBox()
            combo.addItem("Sin asignar", "")
            for name in names:
                combo.addItem(name, name)
            wanted = previous.get(role, "")
            selected = combo.findData(wanted) if wanted else (
                index + 1 if index < len(names) else 0
            )
            combo.setCurrentIndex(max(0, selected))
            combo.currentIndexChanged.connect(self.axis_assignment_changed)
            self.role_combos[role] = combo
            self.axes_form.addRow(self._label(role), combo)

    def rebuild_parameter_fields(self, previous=None):
        previous = dict(previous or {})
        self._clear_form(self.parameters_form)
        self.parameter_widgets = {}
        kind = self.type_combo.currentData()
        definitions = robot_parameter_definitions(kind)
        normalized = normalize_robot_parameters(kind, previous)

        if not definitions:
            self.parameters_form.addRow(self.parameters_empty_label)
            return

        for definition in definitions:
            key = definition["key"]
            label_text = definition["label"]
            unit = definition.get("unit", "")
            if unit:
                label_text += f" ({unit})"

            if definition.get("type") == "bool":
                widget = QComboBox()
                widget.addItem(definition.get("false_label", "False"), False)
                widget.addItem(definition.get("true_label", "True"), True)
                widget.setCurrentIndex(1 if normalized.get(key) else 0)
                widget.currentIndexChanged.connect(self.parameter_value_changed)
            else:
                widget = QDoubleSpinBox()
                widget.setDecimals(6)
                widget.setSingleStep(1.0)
                widget.setRange(
                    float(definition.get("min", -1_000_000_000.0)),
                    float(definition.get("max", 1_000_000_000.0)),
                )
                widget.setValue(float(normalized.get(key, 0.0)))
                widget.valueChanged.connect(self.parameter_value_changed)

            self.parameter_widgets[key] = widget
            self.parameters_form.addRow(self._label(label_text), widget)

    def refresh_axes(self):
        if self.current_index < 0 or self.current_index >= len(self.groups):
            return
        previous = self.current_axes_mapping()
        self.rebuild_axis_assignments(previous)
        self.store_current()
        self.update_validation()

    def current_axes_mapping(self):
        return {
            role: combo.currentData() or ""
            for role, combo in self.role_combos.items()
        }

    def current_group_parameters(self):
        values = {}
        for key, widget in self.parameter_widgets.items():
            if isinstance(widget, QComboBox):
                values[key] = bool(widget.currentData())
            else:
                values[key] = float(widget.value())
        return normalize_robot_parameters(self.type_combo.currentData(), values)

    def axis_assignment_changed(self, *_):
        self.store_current()
        self.update_validation()

    def parameter_value_changed(self, *_):
        self.store_current()
        self.update_validation()

    def store_current(self, *_):
        if self.loading or self.current_index < 0 or self.current_index >= len(self.groups):
            return
        self.groups[self.current_index] = {
            "name": self.name_edit.text().strip(),
            "type": self.type_combo.currentData(),
            "axes": self.current_axes_mapping(),
            "group_parameters": self.current_group_parameters(),
        }
        self.refresh_group_list()

    def update_device_label(self):
        device = ROBOT_DEVICES.get(self.type_combo.currentData())
        if device:
            self.device_label.setText(
                f"Type {device[0]} · ID {device[1]} · Version {device[2]}"
            )
        else:
            self.device_label.setText("Sin dispositivo Lenze asociado")

    def validation_errors(self):
        if self.current_index < 0:
            return ["No hay Robot Groups definidos."]

        kind = self.type_combo.currentData()
        mapping = self.current_axes_mapping()
        roles = ROBOT_TYPES.get(kind, [])
        selected = [mapping.get(role, "") for role in roles]
        errors = []

        if not self.name_edit.text().strip():
            errors.append("El nombre del grupo está vacío.")
        if any(not value for value in selected):
            errors.append("Falta asignar uno o más ejes.")

        assigned = [value for value in selected if value]
        if len(assigned) != len(set(assigned)):
            errors.append("Un mismo eje está asignado más de una vez.")
        if any(value not in set(self.active_axis_names()) for value in assigned):
            errors.append(
                "Hay ejes asignados que ya no existen o están desactivados."
            )

        temporary_group = {
            "name": self.name_edit.text().strip(),
            "type": kind,
            "axes": mapping,
            "group_parameters": self.current_group_parameters(),
        }
        errors.extend(robot_parameter_errors(temporary_group))
        return errors

    def update_validation(self):
        errors = self.validation_errors()
        if errors:
            self.validation_label.setText("⚠ " + "\n⚠ ".join(errors))
            self.validation_label.setStyleSheet(
                "color:#a13d00;font-weight:600;"
            )
            return

        order = group_axis_order(
            {
                "type": self.type_combo.currentData(),
                "axes": self.current_axes_mapping(),
            }
        )
        parameter_count = len(self.parameter_widgets)
        summary = "✓ Grupo válido\nOrden A1..An: " + " → ".join(order)
        summary += f"\nParámetros geométricos: {parameter_count}"
        self.validation_label.setText(summary)
        self.validation_label.setStyleSheet(
            "color:#16713b;font-weight:600;"
        )

    def show_validation(self):
        self.update_validation()
        errors = self.validation_errors()
        if errors:
            QMessageBox.warning(
                self,
                "Robot Group no válido",
                "\n".join(f"• {error}" for error in errors),
            )
        else:
            QMessageBox.information(
                self,
                "Robot Group válido",
                "La asignación y los parámetros del grupo son válidos.",
            )

    def configuration(self):
        self.store_current()
        return deepcopy(self.groups)

    def load_configuration(self, groups):
        self.groups = [
            normalize_robot_group(raw, index)
            for index, raw in enumerate(groups or [], 1)
        ]
        self.current_index = -1
        self.refresh_group_list()
        if self.groups:
            self.set_empty_state(False)
            self.group_list.setCurrentRow(0)
        else:
            self.set_empty_state(True)
