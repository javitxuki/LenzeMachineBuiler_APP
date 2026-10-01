# -*- coding: utf-8 -*-
"""Genera machine_builder_core_v090.py desde el machine_builder_core.py actual.

Ejecutar en la raiz del proyecto:
    python upgrade_machine_builder_core_v090.py

No sobrescribe el original. Genera machine_builder_core_v090.py completo.
"""
from pathlib import Path
import re

SOURCE = Path("machine_builder_core.py")
TARGET = Path("machine_builder_core_v090.py")

if not SOURCE.is_file():
    raise SystemExit("No se encuentra machine_builder_core.py en la carpeta actual.")

text = SOURCE.read_text(encoding="utf-8")

DEFINITIONS = r'''

# ============================================================ parametros de Robot Groups
# V0.9.0: modelo de metadatos para construir la interfaz y persistir el JSON.
# Los parametros cartesianos no requieren datos geometricos adicionales.
# Los IDs de PLC Designer se incorporaran cuando se hayan extraido y verificado.
ROBOT_PARAMETER_DEFINITIONS = {
    "CARTESIAN_2D": [],
    "CARTESIAN_3D": [],
    "CARTESIAN_4D": [],
    "DELTA_2DOF": [
        {"key": "arm_length_l1", "label": "Arm Length L1", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "arm_length_l2", "label": "Arm Length L2", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "base_radius_rbase", "label": "Base Radius Rbase", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "end_effector_radius_rtcp", "label": "End Effector Radius Rtcp", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
    ],
    "DELTA": [
        {"key": "arm_length_l1", "label": "Arm Length L1", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "arm_length_l2", "label": "Arm Length L2", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "base_radius_rbase", "label": "Base Radius Rbase", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "end_effector_radius_rtcp", "label": "End Effector Radius Rtcp", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "parallelogram_width_d", "label": "Parallelogram Width D", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
    ],
    "DELTA_4DOF": [
        {"key": "arm_length_l1", "label": "Arm Length L1", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "arm_length_l2", "label": "Arm Length L2", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "base_radius_rbase", "label": "Base Radius Rbase", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "end_effector_radius_rtcp", "label": "End Effector Radius Rtcp", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "parallelogram_width_d", "label": "Parallelogram Width D", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
    ],
    "DELTA_5DOF": [
        {"key": "arm_length_l1", "label": "Arm Length L1", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "arm_length_l2", "label": "Arm Length L2", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "base_radius_rbase", "label": "Base Radius Rbase", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "end_effector_radius_rtcp", "label": "End Effector Radius Rtcp", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "parallelogram_width_d", "label": "Parallelogram Width D", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "vertical_tcp_offset_l3", "label": "Vertical TCP Offset L3", "unit": "mm", "type": "float", "default": 0.0},
        {"key": "horizontal_tcp_offset_l4", "label": "Horizontal TCP Offset L4", "unit": "mm", "type": "float", "default": 0.0},
        {"key": "flange_length_l5", "label": "Flange Length L5", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0},
        {"key": "axis_offset_a4offx", "label": "Axis Offset A4Offx", "unit": "mm", "type": "float", "default": 0.0},
        {"key": "axis_offset_a4offy", "label": "Axis Offset A4Offy", "unit": "mm", "type": "float", "default": 0.0},
    ],
    "SCARA_3DOF": [
        {"key": "arm_length_l1", "label": "Arm Length L1", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "arm_length_l2", "label": "Arm Length L2", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
    ],
    "SCARA": [
        {"key": "arm_length_l1", "label": "Arm Length L1", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "arm_length_l2", "label": "Arm Length L2", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
    ],
    "BELT_2DOF": [
        {"key": "feed_constant", "label": "Feed Constant pi*B", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
    ],
    "PORTAL_AC_5DOF": [
        {"key": "axis_offset_a5offx", "label": "Axis Offset A5Offx", "unit": "mm", "type": "float", "default": 0.0},
        {"key": "axis_offset_a5offy", "label": "Axis Offset A5Offy", "unit": "mm", "type": "float", "default": 0.0},
        {"key": "axis_offset_a5offz", "label": "Axis Offset A5Offz", "unit": "mm", "type": "float", "default": 0.0},
        {"key": "flange_length_l", "label": "Flange Length L", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0},
    ],
    "LINEAR_DELTA_3DOF": [
        {"key": "linear_angle_a", "label": "Linear Angle a", "unit": "deg", "type": "float", "default": 0.0, "min": -360.0, "max": 360.0},
        {"key": "arm_length_l2", "label": "Arm Length L2", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "base_radius_rbase", "label": "Base Radius Rbase", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "end_effector_radius_rtcp", "label": "End Effector Radius Rtcp", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "parallelogram_width_d", "label": "Parallelogram Width D", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
    ],
    "LINEAR_DELTA_4DOF": [
        {"key": "linear_angle_a", "label": "Linear Angle a", "unit": "deg", "type": "float", "default": 0.0, "min": -360.0, "max": 360.0},
        {"key": "arm_length_l2", "label": "Arm Length L2", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "base_radius_rbase", "label": "Base Radius Rbase", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "end_effector_radius_rtcp", "label": "End Effector Radius Rtcp", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "parallelogram_width_d", "label": "Parallelogram Width D", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
    ],
    "ARTICULATED_4DOF": [
        {"key": "arm_length_l1", "label": "Arm Length L1", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "arm_length_l2", "label": "Arm Length L2", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "axis_offset_a2off", "label": "Axis Offset A2Off", "unit": "mm", "type": "float", "default": 0.0},
        {"key": "axis_offset_a3off", "label": "Axis Offset A3Off", "unit": "mm", "type": "float", "default": 0.0},
        {"key": "axis_offset_a4off", "label": "Axis Offset A4Off", "unit": "mm", "type": "float", "default": 0.0},
        {"key": "mounting_a3", "label": "Mounting A3", "unit": "", "type": "bool", "default": False, "false_label": "Elbow", "true_label": "Shoulder"},
    ],
    "ARTICULATED_LINEAR_A1_4DOF": [
        {"key": "arm_length_l1", "label": "Arm Length L1", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "arm_length_l2", "label": "Arm Length L2", "unit": "mm", "type": "float", "default": 0.0, "min": 0.0, "positive": True},
        {"key": "axis_offset_a2off", "label": "Axis Offset A2Off", "unit": "mm", "type": "float", "default": 0.0},
        {"key": "axis_offset_a4off", "label": "Axis Offset A4Off", "unit": "mm", "type": "float", "default": 0.0},
        {"key": "mounting_a3", "label": "Mounting A3", "unit": "", "type": "bool", "default": False, "false_label": "Elbow", "true_label": "Shoulder"},
    ],
}


def robot_parameter_definitions(kind):
    return list(ROBOT_PARAMETER_DEFINITIONS.get(str(kind), []))


def default_robot_parameters(kind):
    return {
        definition["key"]: definition.get("default")
        for definition in robot_parameter_definitions(kind)
    }


def normalize_robot_parameters(kind, values=None):
    source = dict(values or {})
    normalized = {}
    for definition in robot_parameter_definitions(kind):
        key = definition["key"]
        value = source.get(key, definition.get("default"))
        if definition.get("type") == "bool":
            if isinstance(value, str):
                value = value.strip().lower() in ("1", "true", "yes", "si", "sí", "shoulder")
            normalized[key] = bool(value)
        else:
            try:
                normalized[key] = normalize_number(value)
            except Exception:
                normalized[key] = definition.get("default", 0.0)
    return normalized


def normalize_robot_group(group, index=1):
    raw = dict(group or {})
    kind = str(raw.get("type", next(iter(ROBOT_TYPES))))
    if kind not in ROBOT_TYPES:
        kind = next(iter(ROBOT_TYPES))
    mapping = dict(raw.get("axes") or {})
    if kind == "CARTESIAN_2D" and "Z" not in mapping and "Y" in mapping:
        mapping["Z"] = mapping["Y"]
    return {
        "name": str(raw.get("name", "RobotGroup_%02d" % index)).strip() or "RobotGroup_%02d" % index,
        "type": kind,
        "axes": {role: str(mapping.get(role, "")) for role in ROBOT_TYPES[kind]},
        "group_parameters": normalize_robot_parameters(kind, raw.get("group_parameters")),
    }


def robot_parameter_errors(group):
    normalized = normalize_robot_group(group)
    kind = normalized["type"]
    values = normalized["group_parameters"]
    errors = []
    for definition in robot_parameter_definitions(kind):
        key = definition["key"]
        label = definition["label"]
        value = values.get(key)
        if definition.get("type") == "bool":
            continue
        try:
            number = normalize_number(value)
        except Exception:
            errors.append(label + " no es un numero.")
            continue
        if definition.get("positive") and number <= 0:
            errors.append(label + " debe ser mayor que cero.")
        if "min" in definition and number < definition["min"]:
            errors.append(label + " debe ser mayor o igual que " + str(definition["min"]) + ".")
        if "max" in definition and number > definition["max"]:
            errors.append(label + " debe ser menor o igual que " + str(definition["max"]) + ".")
    return errors
'''

# Inserta las definiciones justo antes de los tipos no soportados.
marker = '# Tipos que tenían versiones anteriores de la herramienta'
if 'ROBOT_PARAMETER_DEFINITIONS = {' not in text:
    if marker not in text:
        raise SystemExit('No se encontro el punto de insercion para parametros de robot.')
    text = text.replace(marker, DEFINITIONS + '\n\n' + marker, 1)

# Normaliza los grupos antes de validar.
old_loop = '    for group in cfg.get("robot_groups", []) or []:\n        label = str(group.get("name", "Grupo"))'
new_loop = '    for group_index, raw_group in enumerate(cfg.get("robot_groups", []) or [], 1):\n        group = normalize_robot_group(raw_group, group_index)\n        label = str(group.get("name", "Grupo"))'
if old_loop in text:
    text = text.replace(old_loop, new_loop, 1)
elif new_loop not in text:
    raise SystemExit('No se encontro el bucle de validacion de Robot Groups.')

# Añade errores de parámetros al final de cada validación de grupo.
needle = '        for axis_name in used:\n            if axis_name and axis_name.lower() not in names:\n                errors.append(f"{label}: el eje {axis_name} no existe o no está activo.")'
replacement = needle + '\n        for parameter_error in robot_parameter_errors(group):\n            errors.append(f"{label}: {parameter_error}")'
if 'for parameter_error in robot_parameter_errors(group):' not in text:
    if needle not in text:
        raise SystemExit('No se encontro el bloque de validacion de ejes del grupo.')
    text = text.replace(needle, replacement, 1)

# Incluye group_parameters normalizados en la estructura que recibe el script.
old_append = '        groups.append({"name": str(g.get("name", "")), "type": kind,\n                       "device": list(ROBOT_DEVICES[kind]), "order": group_axis_order(g)})'
new_append = '        normalized_group = normalize_robot_group(g, len(groups) + 1)\n        groups.append({"name": normalized_group["name"], "type": kind,\n                       "device": list(ROBOT_DEVICES[kind]),\n                       "order": group_axis_order(normalized_group),\n                       "group_parameters": normalized_group["group_parameters"]})'
if old_append in text:
    text = text.replace(old_append, new_append, 1)
elif '"group_parameters": normalized_group["group_parameters"]' not in text:
    raise SystemExit('No se encontro el bloque de generacion de Robot Groups.')

# Valida sintaxis y guarda el archivo completo nuevo.
compile(text, str(TARGET), 'exec')
TARGET.write_text(text, encoding='utf-8')
print('Generado correctamente: ' + str(TARGET.resolve()))
print('El original no se ha modificado.')
