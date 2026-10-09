# -*- coding: utf-8 -*-
"""Lógica de Machine Builder: catálogo, validación y generación del script.

No depende de Streamlit, así que se puede probar sola (tests/test_core.py).
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path

CPU_MODELS = ["c430", "c520", "c550"]
DRIVES = ["i550", "i750", "i950"]
SAFETY = ["Basic Safety", "Extended Safety"]
I950_VARIANTS = ["Normal", "DC-Link"]
KINEMATICS = ["ROTARY", "LEADSCREW", "BELT", "RACK_PINION"]
TRAVERSING = ["MODULO", "LIMITED"]

# Grupos de robot: las cinemáticas Lenze que existen como dispositivo (tipo 33121)
# bajo Device > Kinematics. Los roles van en el orden A1..An del grupo: cada uno es
# el parámetro "Connected drive An" del grupo. Portal_2dof trabaja en el plano X-Z.
ROBOT_TYPES = {
    "CARTESIAN_2D": ["X", "Z"],
    "CARTESIAN_3D": ["X", "Y", "Z"],
    "CARTESIAN_4D": ["X", "Y", "Z", "C"],
    "PORTAL_AC_5DOF": ["X", "Y", "Z", "A", "C"],
    "BELT_2DOF": ["X", "Y"],
    "SCARA_3DOF": ["J1", "J2", "Z"],
    "SCARA": ["J1", "J2", "Z", "R"],
    "DELTA_2DOF": ["ARM1", "ARM2"],
    "DELTA": ["ARM1", "ARM2", "ARM3"],
    "DELTA_4DOF": ["ARM1", "ARM2", "ARM3", "R"],
    "DELTA_5DOF": ["ARM1", "ARM2", "ARM3", "A", "B"],
    "LINEAR_DELTA_3DOF": ["ARM1", "ARM2", "ARM3"],
    "LINEAR_DELTA_4DOF": ["ARM1", "ARM2", "ARM3", "R"],
    "ARTICULATED_4DOF": ["J1", "J2", "J3", "J4"],
    "ARTICULATED_LINEAR_A1_4DOF": ["A1", "J1", "J2", "J3", "J4"],
}

ROBOT_DEVICES = {
    "CARTESIAN_2D": (33121, "1028 0124", "4.2.0.0"),  # Portal_2dof
    "CARTESIAN_3D": (33121, "1028 0102", "4.0.0.0"),  # Portal_3dof
    "CARTESIAN_4D": (33121, "1028 0113", "4.0.0.0"),  # Portal_4dof
    "PORTAL_AC_5DOF": (33121, "1028 0121", "4.0.0.0"),
    "BELT_2DOF": (33121, "1028 0107", "4.0.0.0"),
    "SCARA_3DOF": (33121, "1028 0104", "4.0.0.0"),
    "SCARA": (33121, "1028 0105", "4.0.0.0"),  # Scara_4dof
    "DELTA_2DOF": (33121, "1028 0106", "4.0.0.0"),
    "DELTA": (33121, "1028 0101", "4.0.0.0"),  # Delta3_3dof
    "DELTA_4DOF": (33121, "1028 0116", "4.0.0.0"),
    "DELTA_5DOF": (33121, "1028 0112", "4.0.0.0"),
    "LINEAR_DELTA_3DOF": (33121, "1028 0111", "4.0.0.0"),
    "LINEAR_DELTA_4DOF": (33121, "1028 0115", "4.0.0.0"),
    "ARTICULATED_4DOF": (33121, "1028 0108", "4.0.0.0"),
    "ARTICULATED_LINEAR_A1_4DOF": (33121, "1028 0123", "4.2.0.0"),
}



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


# Subíndices de los parámetros geométricos de cada Robot Group en PLC Designer.
# El grupo los expone con el mismo esquema que los datos de maquina del eje:
# Id = 0x10000000 + subíndice.
#
# El indice visible del GUI (0x52xx:sss) no es el subíndice: el prefijo vale
# 0x5200 + 4*instancia + bloque (bloque = subíndice >> 8) y la parte sss es el
# byte bajo en decimal. Los parámetros geométricos están en el BLOQUE 3, asi
# que su subíndice real es 0x300 + n (n = numero tras los dos puntos):
#   Arm Length L1 de Delta  se ve como 0x5203:002  ->  sub 0x302  ->  Id 0x10000302
# Confirmado con Export_KinematicsParameters.py sobre un proyecto generado.
# Acepta dos formas, mezclables: global {"arm_length_l1": 62, ...} o por tipo
# {"DELTA": {"arm_length_l1": 62, ...}} (una clave cuyo valor es un dict = tipo).
ROBOT_PARAMETER_IDS = {
    "DELTA_2DOF": {
        "arm_length_l1": 0x302,
        "arm_length_l2": 0x303,
        "base_radius_rbase": 0x304,
        "end_effector_radius_rtcp": 0x305,
    },
    "DELTA": {
        "arm_length_l1": 0x302,
        "arm_length_l2": 0x303,
        "base_radius_rbase": 0x304,
        "end_effector_radius_rtcp": 0x305,
        "parallelogram_width_d": 0x306,
    },
    "DELTA_4DOF": {
        "arm_length_l1": 0x302,
        "arm_length_l2": 0x303,
        "base_radius_rbase": 0x304,
        "end_effector_radius_rtcp": 0x305,
        "parallelogram_width_d": 0x306,
    },
    "DELTA_5DOF": {
        "arm_length_l1": 0x302,
        "arm_length_l2": 0x303,
        "base_radius_rbase": 0x304,
        "end_effector_radius_rtcp": 0x305,
        "parallelogram_width_d": 0x306,
        "vertical_tcp_offset_l3": 0x307,
        "horizontal_tcp_offset_l4": 0x308,
        "flange_length_l5": 0x309,
        "axis_offset_a4offx": 0x30A,
        "axis_offset_a4offy": 0x30B,
    },
    "SCARA_3DOF": {
        "arm_length_l1": 0x302,
        "arm_length_l2": 0x303,
    },
    "SCARA": {
        "arm_length_l1": 0x302,
        "arm_length_l2": 0x303,
    },
    "BELT_2DOF": {
        "feed_constant": 0x302,
    },
    "PORTAL_AC_5DOF": {
        "axis_offset_a5offx": 0x302,
        "axis_offset_a5offy": 0x303,
        "axis_offset_a5offz": 0x304,
        "flange_length_l": 0x308,
    },
    "LINEAR_DELTA_3DOF": {
        "linear_angle_a": 0x302,
        "arm_length_l2": 0x303,
        "base_radius_rbase": 0x304,
        "end_effector_radius_rtcp": 0x305,
        "parallelogram_width_d": 0x306,
    },
    "LINEAR_DELTA_4DOF": {
        "linear_angle_a": 0x302,
        "arm_length_l2": 0x303,
        "base_radius_rbase": 0x304,
        "end_effector_radius_rtcp": 0x305,
        "parallelogram_width_d": 0x306,
    },
    "ARTICULATED_4DOF": {
        "arm_length_l1": 0x303,
        "arm_length_l2": 0x305,
        "axis_offset_a2off": 0x302,
        "axis_offset_a3off": 0x304,
        "axis_offset_a4off": 0x306,
        "mounting_a3": 0x30A,
    },
    "ARTICULATED_LINEAR_A1_4DOF": {
        "arm_length_l1": 0x303,
        "arm_length_l2": 0x305,
        "axis_offset_a2off": 0x302,
        "axis_offset_a4off": 0x306,
        "mounting_a3": 0x30A,
    },
}


def _robot_parameter_id_map(kind):
    """Ids aplicables a un tipo de grupo: mezcla los globales con los del tipo."""
    merged = {}
    per_kind = None
    for key, value in ROBOT_PARAMETER_IDS.items():
        if isinstance(value, dict):
            if key == kind:
                per_kind = value
            continue
        merged[key] = value
    if per_kind:
        merged.update(per_kind)
    return merged


def robot_parameter_ids(kind, group_parameters=None):
    """{clave: subíndice} de los parámetros conocidos para un grupo."""
    known = _robot_parameter_id_map(kind)
    ids = {}
    for key in (group_parameters or {}):
        try:
            ids[key] = int(known[key])
        except (KeyError, TypeError, ValueError):
            continue
    return ids


def robot_parameter_labels(kind):
    """{clave: etiqueta PLC Designer} para escribir el parámetro por nombre."""
    return {
        definition["key"]: definition["label"]
        for definition in robot_parameter_definitions(kind)
    }


# Tipos que tenían versiones anteriores de la herramienta y no tienen cinemática
# Lenze equivalente: se avisa en vez de crear algo que no es.
UNSUPPORTED_ROBOT_TYPES = ("GANTRY", "ARTICULATED_6_AXIS", "CUSTOM")

# Identificación EtherCAT de los drives, en el maestro. Por defecto NINGUNA: con la
# comprobación activa, un drive que no lleve ese alias grabado no arranca en el bus.
IDENTIFICATION_MODES = {
    "NONE": 0,                  # sin comprobación
    "STATION_ALIAS": 1,         # Configured Station Alias (ADO 0x0012)
    "EXPLICIT_DEVICE_ID": 2,    # Explicit Device Identification (ADO 0x0134)
}


def group_axis_order(group):
    """Los nombres de eje del grupo en el orden A1..An de su cinemática.

    Compatibilidad: un CARTESIAN_2D guardado con X/Y (versiones anteriores) usa la
    Y como segundo eje, que en Portal_2dof es la Z."""
    kind = group.get("type")
    mapping = dict(group.get("axes") or {})
    if kind == "CARTESIAN_2D" and "Z" not in mapping and "Y" in mapping:
        mapping["Z"] = mapping["Y"]
    return [mapping.get(role, "") for role in ROBOT_TYPES.get(kind, [])]


@dataclass
class AxisConfig:
    enabled: bool = True
    name: str = "Axis_01"
    drive_type: str = "i950"
    safety_variant: str = "Basic Safety"
    i950_variant: str = "Normal"
    descriptor_label: str = ""
    device_id: str = ""
    station_alias: int = 1001
    second_station_alias: int = 2001
    motor_code_c86: str = ""
    motor_template: bool = False
    kinematics: str = "ROTARY"
    kinematic_parameter: float = 360.0
    z1: int = 1
    z2: int = 1
    z3: int = 1
    z4: int = 1
    traversing_range: str = "MODULO"
    feed_constant: float = 360.0
    cycle_length: float = 360.0


# ============================================================ números y nombres

def normalize_number(value):
    return float(str(value).strip().replace(" ", "").replace(",", "."))


def format_decimal(value):
    """Un número como texto, sin ceros de sobra y siempre con parte decimal."""
    try:
        number = normalize_number(value)
    except Exception:
        return str(value)
    text = ("%.12f" % number).rstrip("0").rstrip(".")
    return text if "." in text else text + ".0"


# Nombre IEC válido y ASCII: el objeto de eje y el drive se llaman así en el
# proyecto, y el script lo ejecuta IronPython 2.7.
IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,50}$")


def calculate_feed_constant(kinematics, kinematic_parameter):
    """Avance por vuelta de la SALIDA de la reductora (unidad de posición / vuelta).

    ROTARY: 360 (grados). LEADSCREW: el paso del husillo. BELT y RACK_PINION: pi por
    el diámetro efectivo. La relación de la reductora (Z1..Z4) NO entra aquí: va en
    sus propios parámetros del eje."""
    value = normalize_number(kinematic_parameter)
    if value <= 0:
        raise ValueError("El parámetro cinemático debe ser mayor que cero.")
    mode = str(kinematics).upper()
    if mode == "ROTARY":
        return 360.0
    if mode == "LEADSCREW":
        return value
    if mode in ("BELT", "RACK_PINION"):
        return math.pi * value
    raise ValueError("Cinemática no reconocida: " + mode)


# ============================================================ normalización

def normalize_safety(value, drive_type=None):
    text = str(value or "").lower()
    if drive_type == "i550":
        return "Basic Safety"
    if "extended" in text or "advanced" in text:
        return "Extended Safety"
    return "Basic Safety"


def normalize_i950_variant(value, drive_type=None):
    if drive_type not in (None, "i950"):
        return "Normal"
    text = str(value or "").lower().replace(" ", "").replace("-", "")
    return "DC-Link" if "dclink" in text else "Normal"


def normalize_traversing_range(value):
    text = str(value or "").upper()
    if text in ("LIMITED", "LINEAR", "LIMITADO"):
        return "LIMITED"
    return "MODULO"


def normalize_axis(axis, index=1):
    """Un eje con todos sus campos y con valores que la aplicación admite."""
    base = asdict(AxisConfig(name=f"Axis_{index:02d}", station_alias=1000 + index,
                             second_station_alias=2000 + index))
    if isinstance(axis, dict):
        for key in base:
            if key in axis and axis[key] is not None:
                base[key] = axis[key]
    base["enabled"] = bool(base["enabled"])
    base["name"] = str(base["name"]).strip() or f"Axis_{index:02d}"
    if base["drive_type"] not in DRIVES:
        base["drive_type"] = "i950"
    base["safety_variant"] = normalize_safety(base["safety_variant"], base["drive_type"])
    base["i950_variant"] = normalize_i950_variant(base["i950_variant"], base["drive_type"])
    base["kinematics"] = str(base["kinematics"]).upper()
    if base["kinematics"] not in KINEMATICS:
        base["kinematics"] = "ROTARY"
    base["traversing_range"] = normalize_traversing_range(base["traversing_range"])
    for key in ("station_alias", "second_station_alias"):
        try:
            base[key] = int(float(base[key]))
        except Exception:
            base[key] = 0
    for key in ("z1", "z2", "z3", "z4"):
        try:
            base[key] = max(1, int(round(float(base[key]))))
        except Exception:
            base[key] = 1
    for key in ("kinematic_parameter", "feed_constant", "cycle_length"):
        try:
            base[key] = normalize_number(base[key])
        except Exception:
            pass
    base["motor_code_c86"] = str(base["motor_code_c86"] or "")
    base["motor_template"] = bool(base.get("motor_template", False))
    return base


# ============================================================ catálogo

def version_key(value: str):
    nums = [int(x) for x in re.split(r"[^0-9]+", str(value)) if x]
    return tuple(nums or [0])


def load_repository(path: str | Path = "device_repository.json") -> dict:
    p = Path(path)
    if not p.exists():
        return {"devices": []}
    return json.loads(p.read_text(encoding="utf-8"))


def _devices(repo):
    return repo.get("devices", []) if isinstance(repo, dict) else []


def _device_id(d):
    return str(d.get("device_id", d.get("type", "")))


def cpu_options(repo, model):
    exact = f"Controller {model}".lower()
    values = [{**d, "device_id": _device_id(d)} for d in _devices(repo)
              if str(d.get("name", "")).lower() == exact]
    return sorted(values, key=lambda d: version_key(d.get("version", "")), reverse=True)


# Versiones del EtherCAT Master que se ofrecen. Las 4.x existen en el catálogo pero
# quedan fuera hasta confirmar que el resto del proyecto las admite.
VALID_ETHERCAT_MASTER_VERSIONS = {
    "3.0.0.10", "3.1.0.0", "3.2.0.0", "3.3.0.0", "3.4.0.0", "3.6.0.0", "3.9.0.0",
    "3.10.0.1", "3.12.0.1", "3.14.0.0", "3.14.0.1", "3.15.0.0", "3.15.0.1", "3.16.0.0",
    "3.17.0.0", "3.18.0.0", "3.18.1.0", "3.18.2.0", "3.18.3.0", "3.18.4.0", "3.28.0.0",
    "3.32.0.1",
}


def master_options(repo):
    values = []
    for d in _devices(repo):
        name = str(d.get("name", "")).lower()
        if "ethercat master" not in name or "slave" in name:
            continue
        if str(d.get("version", "")) not in VALID_ETHERCAT_MASTER_VERSIONS:
            continue
        values.append({**d, "device_id": _device_id(d)})
    return sorted(values, key=lambda d: version_key(d.get("version", "")), reverse=True)


def _is_extended_safety(low_name):
    # "(ES)" o "Extended Safety". "(AS)" es Advanced/Basic en i750 y "Extended for
    # customer specific devices" no es una variante de safety.
    if "customer specific" in low_name:
        return False
    return "extended" in low_name or "(es" in low_name


def drive_options(repo, drive, safety="Basic Safety", i950_variant="Normal"):
    out = []
    for d in _devices(repo):
        name = str(d.get("name", ""))
        low = name.lower()
        did = _device_id(d)
        if drive.lower() not in low:
            continue
        if not did.startswith("DeviceID(type=65,"):
            continue
        if drive in ("i750", "i950"):
            ext = _is_extended_safety(low)
            if safety == "Extended Safety" and not ext:
                continue
            if safety == "Basic Safety" and ext:
                continue
        if drive == "i950":
            dc = "dc-link" in low or "dc link" in low or "dclink" in low
            if i950_variant == "DC-Link" and not dc:
                continue
            if i950_variant != "DC-Link" and dc:
                continue
        out.append({**d, "device_id": did})
    return sorted(out, key=lambda d: version_key(d.get("version", "")), reverse=True)


# ============================================================ validación

def validate_config(cfg):
    errors = []
    names = set()
    aliases = set()
    aliases2 = set()
    axes = [normalize_axis(a, i) for i, a in enumerate(cfg.get("axes", []), 1)]
    active = [a for a in axes if a["enabled"]]
    if not active:
        errors.append("Debe existir al menos un eje activo.")
    if not str(cfg.get("cpu_device_id", "")).startswith("DeviceID("):
        errors.append("Falta el descriptor de la CPU.")
    if not str(cfg.get("ethercat_master_device_id", "")).startswith("DeviceID("):
        errors.append("Falta el descriptor del EtherCAT Master.")
    path = str(cfg.get("project_path", "")).strip()
    if not path.lower().endswith(".project"):
        errors.append("La ruta del proyecto debe terminar en .project.")
    for a in active:
        name = a["name"]
        if not IDENTIFIER.match(name):
            errors.append(f"{name}: el nombre debe empezar por letra o _, y solo llevar letras "
                          f"sin tilde, números y _ (es el nombre del eje en el proyecto).")
        if name.lower() in names:
            errors.append(f"Nombre duplicado: {name}.")
        names.add(name.lower())
        if not str(a.get("device_id", "")).startswith("DeviceID("):
            errors.append(f"{name}: falta el descriptor del drive.")
        for key, seen, label in (("station_alias", aliases, "Alias"),
                                 ("second_station_alias", aliases2, "Second Alias")):
            value = int(a[key])
            if value in seen:
                errors.append(f"{label} duplicado: {value}.")
            seen.add(value)
        if a["station_alias"] and a["station_alias"] in aliases2:
            errors.append(f"{name}: el Alias {a['station_alias']} coincide con un Second Alias.")
        try:
            if normalize_number(a["feed_constant"]) <= 0:
                errors.append(f"{name}: el Feed Constant debe ser mayor que cero.")
        except Exception:
            errors.append(f"{name}: el Feed Constant no es un número.")
        if a["traversing_range"] == "MODULO":
            try:
                if normalize_number(a["cycle_length"]) <= 0:
                    errors.append(f"{name}: el Cycle Length debe ser mayor que cero en un eje módulo.")
            except Exception:
                errors.append(f"{name}: el Cycle Length no es un número.")
    group_names = set()
    for group_index, raw_group in enumerate(cfg.get("robot_groups", []) or [], 1):
        group = normalize_robot_group(raw_group, group_index)
        label = str(group.get("name", "Grupo"))
        if not IDENTIFIER.match(label):
            errors.append(f"{label}: el nombre del grupo debe ser un identificador sin tildes ni espacios.")
        if label.lower() in names or label.lower() in group_names:
            errors.append(f"{label}: el nombre del grupo coincide con otro eje o grupo.")
        group_names.add(label.lower())
        if group.get("type") not in ROBOT_TYPES:
            errors.append(f"{label}: el tipo {group.get('type')} no tiene cinemática Lenze equivalente.")
            continue
        used = [a for a in group_axis_order(group)]
        if "" in used:
            errors.append(f"{label}: falta asignar algún eje.")
        if len(used) != len(set(used)):
            errors.append(f"{label}: hay ejes repetidos.")
        for axis_name in used:
            if axis_name and axis_name.lower() not in names:
                errors.append(f"{label}: el eje {axis_name} no existe o no está activo.")
        for parameter_error in robot_parameter_errors(group):
            errors.append(f"{label}: {parameter_error}")
    if str(cfg.get("ethercat_identification", "NONE")) not in IDENTIFICATION_MODES:
        errors.append("Modo de identificación EtherCAT no válido.")
    return errors


def config_json(cfg):
    return json.dumps(cfg, indent=2, ensure_ascii=False)


# ============================================================ script de PLC Designer

# Datos de máquina del objeto de eje (L_MC1P / AXIS_REF). Se buscan por Id de
# parámetro, 0x10000000 + subíndice: el Id no depende del eje, mientras que el
# índice visible (0x51xx:sss) lo reparte PLC Designer y no se puede prever.
AXIS_PARAMETERS = {
    "MOTION_KIND": 20,        # 1 traslación, 2 rotación
    "ADD_GEAR_NUMERATOR": 25,
    "ADD_GEAR_DENOMINATOR": 26,
    "TRAVERSING_RANGE": 30,   # 0 módulo, 1 limitado
    "CYCLE_LENGTH": 31,
    "FEED_CONSTANT": 32,
    "GEAR_NUMERATOR": 33,
    "GEAR_DENOMINATOR": 34,
}


def axis_machine_data(a):
    """Los parámetros del objeto de eje, como pares (clave, valor en texto IEC).

    Reductora: se conserva la correspondencia que usaba L_MC1P_ChangeMachineData en
    las versiones anteriores de esta herramienta: Z1 denominador y Z2 numerador de la
    reductora; Z3 denominador y Z4 numerador de la reductora adicional."""
    modulo = a["traversing_range"] == "MODULO"
    data = [
        ("MOTION_KIND", "2" if a["kinematics"] == "ROTARY" else "1"),
        ("TRAVERSING_RANGE", "0" if modulo else "1"),
        ("FEED_CONSTANT", format_decimal(a["feed_constant"])),
        ("GEAR_NUMERATOR", str(int(a["z2"]))),
        ("GEAR_DENOMINATOR", str(int(a["z1"]))),
        ("ADD_GEAR_NUMERATOR", str(int(a["z4"]))),
        ("ADD_GEAR_DENOMINATOR", str(int(a["z3"]))),
    ]
    if modulo:
        data.append(("CYCLE_LENGTH", format_decimal(a["cycle_length"])))
    return data


def _ascii_literal(value):
    """Literal Python aceptado por IronPython 2.7 con el fichero en ASCII."""
    return ascii(value)


SCRIPT_TEMPLATE = r'''# -*- coding: ascii -*-
# Generated by Lenze Machine Builder Web.
# Run it in PLC Designer 4.2: Tools > Scripting > Execute Script File.
#
# It creates the project with the controller, the EtherCAT Master and one drive
# per axis. PLC Designer adds the motion axis of each drive under Functions (the
# project option that asks about it is set first, so there is no dialog); the
# application is built, which is what creates the axis parameters, and then each
# axis's MACHINE DATA (motion kind, traversing range, cycle length, feed constant
# and gear factors) is written into the PROJECT as axis parameters and read back.
# No function block is needed in the controller.
import os
import traceback

try:
    # The documented way; "Execute Script File" also injects these names.
    from scriptengine import *  # noqa: F401,F403
except ImportError:
    pass

PROJECT_PATH = __PROJECT_PATH__
REPORT_PATH = PROJECT_PATH + ".log"
CPU_MODEL = __CPU_MODEL__
CPU_DEVICE_ID = __CPU_DEVICE_ID__
ETHERCAT_MASTER_DEVICE_ID = __MASTER_DEVICE_ID__
AXES = __AXES__
ROBOT_GROUPS = __ROBOT_GROUPS__
UNSUPPORTED_GROUPS = __UNSUPPORTED_GROUPS__
HOT_CONNECT_GROUPS = __HOT_CONNECT_GROUPS__
# 0 none, 1 Configured Station Alias (ADO 0x0012), 2 Explicit Device ID (ADO 0x0134)
IDENTIFICATION_MODE = __IDENTIFICATION_MODE__

# Universal motion axis object (L_MC1P). Its machine data are found by parameter
# Id = 0x10000000 + subindex, which does not depend on the axis.
AXIS_TYPE = 33601
AXIS_ID = "1028 0100"
AXIS_VERSION_FALLBACK = "4.0.0.0"
PARAMETER_BASE = 0x10000000
PARAMETERS = __PARAMETERS__

# Robot group: parameter "Connected drive An" = CONNECTED_DRIVE + (n - 1).
CONNECTED_DRIVE = PARAMETER_BASE + 51

# EtherCAT slave identification: host parameters of the slave connector. The
# slave editor creates them the first time its page is opened, so the script
# creates them if they are not there.
ETC_STATION_ALIAS = 0x40110002
ETC_IDENT_ADO = 0x40110005
ETC_IDENT_MODE = 0x40110006

# Axis connection parameters that link it to its EtherCAT drive.
LINK_ECAT_REFERENCE = 20
LINK_SLOT = 21
LINK_ADDRESS = 22
LINK_NAME = 24

WARNINGS = []
DONE = []
LINES = []


def log(text):
    text = "[Machine Builder] " + str(text)
    LINES.append(text)
    print(text)


def warn(text):
    WARNINGS.append(text)
    log("WARNING: " + text)


def safe(function, default=""):
    try:
        return function()
    except Exception:
        return default


def child_nodes(node):
    """Best effort list of the children of a node (the API differs per object)."""
    for attribute in ("children", "get_children", "get_all_children",
                      "nodes", "items"):
        items = safe(lambda a=attribute: list(getattr(node, a)()), None)
        if not items:
            items = safe(lambda a=attribute: list(getattr(node, a)), None)
        if items:
            return items
    return safe(lambda: list(node), [])


def object_name(obj):
    for attr in ("get_name", "name", "Name"):
        val = safe(lambda a=attr: getattr(obj, a))
        if val:
            if callable(val):
                try:
                    val = val()
                except Exception:
                    continue
            if val:
                return str(val)
    return ""


def write_report():
    """Writes the whole script log next to the project (PROJECT_PATH + '.log')."""
    try:
        report = open(REPORT_PATH, "w")
        try:
            report.write("\n".join(LINES) + "\n")
        finally:
            report.close()
        print("[Machine Builder] Report: " + REPORT_PATH)
    except Exception:
        pass


def exact_device(search_text, expected_id):
    for d in device_repository.get_all_devices(search_text) or []:
        if str(d.device_id) == str(expected_id):
            return d
    raise Exception("Device not found in the repository: " + str(expected_id))


def version_key(text):
    parts = []
    for piece in str(text).replace("-", ".").split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return parts


def axis_version():
    """Newest universal axis installed; the fallback if it cannot be asked."""
    best = None
    try:
        for d in device_repository.get_all_devices() or []:
            did = d.device_id
            if int(did.type) == AXIS_TYPE and str(did.id) == AXIS_ID:
                if best is None or version_key(did.version) > version_key(best):
                    best = str(did.version)
    except Exception:
        pass
    return best or AXIS_VERSION_FALLBACK


def find_one(parent, name):
    found = parent.find(name, True)
    return found[0] if found else None


def axis_insert_without_dialog():
    """Project option of the Lenze motion plugin: when a drive is added, PLC
    Designer adds its motion axis under Functions and does not ask.
    InsertFunctionNodeSettings(functionBelowHardwareNode, insertHardwareNodeOnly,
    alwaysAsk). Returns False if this PLC Designer does not offer it."""
    try:
        projects.primary.InsertFunctionNodeSettings(False, False, False)
        return True
    except Exception as error:
        warn("Could not set the 'insert motion axis' option (" + str(error)
             + "); the axes are added by the script instead.")
        return False


def functions_node(controller):
    node = find_one(controller, "Functions")
    if node is None:
        raise Exception("The controller has no 'Functions' node to add the axes to.")
    return node


def axis_of(project, controller, a, drive_name, automatic):
    """The motion axis of a drive, named as the axis in the configuration."""
    axis = find_one(project, "Axis_" + drive_name) if automatic else None
    if axis is None:
        if automatic:
            warn(a["name"] + ": PLC Designer did not add the axis; adding it by script.")
        functions_node(controller).add(a["name"], AXIS_TYPE, AXIS_ID, axis_version())
        axis = find_one(project, a["name"])
        if axis is None:
            raise Exception("Axis object not found after adding it: " + a["name"])
        link_axis(axis, drive_name)
        return axis
    if str(axis.get_name()) != a["name"]:
        axis.rename(a["name"])
    return axis


def add_groups(controller, project):
    """Adds the robot groups under Kinematics. Their cartesian axes come with them;
    their parameters appear with the build, like the axis ones."""
    created = []
    if not ROBOT_GROUPS:
        return created
    kinematics = find_one(controller, "Kinematics")
    if kinematics is None:
        warn("The controller has no 'Kinematics' node: robot groups not created.")
        return created
    for g in ROBOT_GROUPS:
        kind = g["device"]
        kinematics.add(g["name"], kind[0], kind[1], kind[2])
        group = find_one(project, g["name"])
        if group is None:
            warn("Robot group " + g["name"] + " was not created.")
            continue
        created.append((g, group))
    return created


def connect_groups(created):
    """Writes each role's axis into the group's "Connected drive An" parameters."""
    for g, group in created:
        ok = 0
        for n, axis_name in enumerate(g["order"]):
            try:
                parameter = group.device_parameters.by_id(CONNECTED_DRIVE + n)
            except Exception:
                parameter = None
            if parameter is None:
                warn(g["name"] + ": parameter 'Connected drive A%d' does not exist" % (n + 1))
                continue
            try:
                parameter.value = axis_name
                now = str(parameter.value).strip().strip("'")
            except Exception as error:
                warn(g["name"] + ": could not connect A%d = %s (%s)" % (n + 1, axis_name, error))
                continue
            if now == axis_name:
                ok += 1
            else:
                warn(g["name"] + ": A%d was written as %s but reads %s" % (n + 1, axis_name, now))
        DONE.append("%s (%s): %d/%d axes connected" % (g["name"], g["type"], ok, len(g["order"])))


def object_manager():
    import System
    from System.Reflection import BindingFlags
    flags = BindingFlags.Instance | BindingFlags.Static | BindingFlags.Public | BindingFlags.NonPublic
    for assembly in System.AppDomain.CurrentDomain.GetAssemblies():
        if assembly.GetName().Name == "ScriptDriverDeviceObject.plugin":
            env = assembly.GetType("_3S.CoDeSys.ScriptDriverDeviceObject.APEnvironment")
            return env.GetProperty("ObjectMgr", flags).GetValue(None, None)
    raise Exception("ObjectMgr not found")


def set_identification(drive, mode, value):
    """Sets the EtherCAT identification of a slave (what the slave editor writes),
    on a writable copy of the device object that is then saved."""
    import clr
    clr.AddReference("DeviceObject")
    from _3S.CoDeSys.DeviceObject import IParameterSet, IParameter4, IDataElement, AccessRight, ChannelType

    def parameter(pset, pid, name, kind):
        if not IParameterSet.Contains(pset, pid):
            IParameterSet.AddParameter(pset, pid, name, AccessRight.ReadWrite, AccessRight.ReadWrite,
                                       getattr(ChannelType, "None"), kind)
        return IParameterSet.GetParameter(pset, pid)

    def put(p, text, download):
        try:
            p.Value = text
        except Exception:
            IDataElement.Value.SetValue(p, text)
        IParameter4.SetDownload(p, download)

    manager = object_manager()
    writable = manager.GetObjectToModify(drive.handle, drive.guid)
    saved = False
    try:
        pset = writable.Object.Connectors[0].HostParameterSet
        put(parameter(pset, ETC_IDENT_MODE, "DeviceIdenticationMode", "std:USINT"), str(mode), mode != 0)
        put(parameter(pset, ETC_STATION_ALIAS, "StationAlias", "std:WORD"), str(value), mode != 0)
        ado = {1: 0x12, 2: 0x134}.get(mode, 0)
        put(parameter(pset, ETC_IDENT_ADO, "DeviceIdenticationADO", "std:UINT"), str(ado), False)
        saved = True
    finally:
        manager.SetObject(writable, saved, None)
    host = drive.connectors[0].host_parameters
    return str(host.by_id(ETC_IDENT_MODE).value) == str(mode) and \
        str(host.by_id(ETC_STATION_ALIAS).value) == str(value)


def build(application):
    """Builds the application. It is the build that creates the axis parameters."""
    try:
        application.build()
    except Exception as error:
        warn("The build reported a problem (" + str(error) + ")")


def write_parameter(parameter, label, key, value):
    """Writes a parameter object and reads it back. Returns True if it holds."""
    text = str(value)
    try:
        number = float(text)
        if number == int(number) and abs(number) < 1e15:
            text = str(int(number))
    except ValueError:
        pass
    try:
        parameter.value = text
        now = str(parameter.value)
    except Exception as error:
        warn(label + ": could not write " + key + " = " + text + " (" + str(error) + ")")
        return False
    try:
        same = abs(float(now) - float(text)) < 1e-9
    except ValueError:
        same = now.strip().upper() == text.strip().upper()
    if not same:
        warn(label + ": " + key + " was written as " + text + " but reads " + now)
        return False
    return True


def set_parameter(device, label, key, value, pid=None):
    """Writes a parameter by Id and reads it back. Returns True if it holds."""
    if pid is None:
        pid = PARAMETER_BASE + PARAMETERS[key]
    try:
        parameter = device.device_parameters.by_id(pid)
    except Exception:
        parameter = None
    if parameter is None:
        warn(label + ": parameter " + key + " (Id 0x%08X) does not exist" % pid)
        return False
    return write_parameter(parameter, label, key, value)


def group_parameter_by_name(group, label):
    """A group parameter by its name, used while its Id is unknown."""
    try:
        for parameter in group.device_parameters:
            for attribute in ("name", "label", "display_name", "Name", "Description"):
                try:
                    value = getattr(parameter, attribute)
                except Exception:
                    continue
                if value not in (None, "") and str(value).lower() == label.lower():
                    return parameter
    except Exception:
        return None
    return None


def write_group_parameters(created):
    """Writes the geometric parameters of each robot group (Arm Length L1, ...).

    Their parameters appear with the build, like the axis ones, so this runs
    after it. A parameter whose Id is unknown is matched by name; if that fails
    too, it is reported as a warning."""
    for g, group in created:
        values = g.get("group_parameters") or {}
        if not values:
            continue
        ids = g.get("parameter_ids") or {}
        labels = g.get("parameter_labels") or {}
        ok = 0
        for key in sorted(values.keys()):
            value = values[key]
            text = "TRUE" if value is True else ("FALSE" if value is False else str(value))
            try:
                number = float(text)
                if number == int(number) and abs(number) < 1e15:
                    text = str(int(number))
            except ValueError:
                pass
            if key in ids:
                pid = PARAMETER_BASE + ids[key]
                written = set_parameter(group, g["name"], key, text, pid)
                log("%s: %s (Id 0x%08X) = %s -> %s"
                    % (g["name"], key, pid, text, "OK" if written else "FAILED"))
            else:
                label = labels.get(key, key)
                parameter = group_parameter_by_name(group, label)
                if parameter is None:
                    warn(g["name"] + ": parameter '" + key + "' has no known Id and "
                         "no parameter named '" + str(label) + "'")
                    written = False
                else:
                    written = write_parameter(parameter, g["name"], key, text)
                log("%s: %s (by name '%s') = %s -> %s"
                    % (g["name"], key, label, text, "OK" if written else "FAILED"))
            if written:
                ok += 1
        DONE.append("%s: %d/%d geometric parameters written"
                    % (g["name"], ok, len(values)))


def create_hot_connect_groups(master, project):
    """Creates Hot Connect groups in the EtherCAT Master and configures Second Station Address."""
    if not HOT_CONNECT_GROUPS:
        return []

    created = []
    for group in HOT_CONNECT_GROUPS:
        group_name = group.get("name", "")
        axis_names = group.get("axes", [])
        if not group_name or not axis_names:
            continue

        # Create the Hot Connect group in the EtherCAT Master
        try:
            # Try multiple possible names for Hot Connect node
            hot_connect = None
            hc_names = ["Hot Connect", "HotConnect", "Hot Connect Groups", "HC Groups", "Hot_Connect"]
            for hc_name in hc_names:
                hot_connect = find_one(master, hc_name)
                if hot_connect is not None:
                    log("Found Hot Connect node: " + hc_name)
                    break

            # If not found, try to create it
            if hot_connect is None:
                for hc_name in hc_names:
                    try:
                        master.add(hc_name, "Hot Connect")
                        hot_connect = find_one(master, hc_name)
                        if hot_connect is not None:
                            log("Created Hot Connect node: " + hc_name)
                            break
                    except Exception:
                        pass

            # Debug: list all children of master if still not found
            if hot_connect is None:
                children = child_nodes(master)
                child_names = [object_name(c) for c in children]
                warn("Hot Connect node not found in EtherCAT Master. Available children: " + str(child_names))
                continue

            # Add the group to Hot Connect
            hc_group = hot_connect.add(group_name)
            if hc_group is None:
                warn("Could not create Hot Connect group: " + group_name)
                continue

            created.append((group_name, axis_names))

            # Configure Second Station Address for each axis in the group
            for axis_name in axis_names:
                drive_name = "Drv_" + axis_name
                drive = find_one(projects.primary, drive_name)
                if drive is None:
                    continue

                # Find the axis in AXES to get its second_station_alias
                second_alias = 0
                for a in AXES:
                    if a["name"] == axis_name:
                        second_alias = a.get("second_station_alias", 0)
                        break

                if second_alias > 0:
                    # Set Second Station Address on the drive
                    try:
                        param = drive.device_parameters.by_id(0x40110002)  # ETC_STATION_ALIAS
                        if param:
                            param.value = second_alias
                            log("%s: Second Station Address set to %d" % (drive_name, second_alias))
                    except Exception as error:
                        warn("%s: could not set Second Station Address (%s)" % (drive_name, error))

        except Exception as error:
            warn("Error creating Hot Connect group %s: %s" % (group_name, error))

    return created
    """Links the axis object to its drive (connection parameters of the axis)."""
    values = {
        LINK_ECAT_REFERENCE: "'" + drive_name + "'",
        LINK_SLOT: "0",
        LINK_ADDRESS: "ADR(" + drive_name + ".etcslave.m_pioconfigconnector)",
        LINK_NAME: "'" + drive_name + ".etcslave.m_pioconfigconnector'",
    }
    for connector in axis.connectors:
        try:
            host = connector.host_parameters
        except Exception:
            continue
        if LINK_ECAT_REFERENCE not in host:
            continue
        try:
            for pid, value in values.items():
                host.by_id(pid).value = value
            return True
        except Exception as error:
            warn(axis.get_name() + ": could not link it to " + drive_name + " (" + str(error)
                 + "). Link it by hand in the axis editor.")
            return False
    warn(axis.get_name() + ": no connection parameters found. Link it by hand to " + drive_name + ".")
    return False


def create_task(application):
    task_cfg = find_one(application, "Task Configuration")
    if task_cfg is None:
        task_cfg = application.create_task_configuration()
    task = find_one(task_cfg, "MainTask")
    if task is None:
        task = task_cfg.create_task("MainTask")
    try:
        task.kind_of_task = KindOfTask.Cyclic
    except Exception as error:
        warn("MainTask: could not make it cyclic (" + str(error) + ")")
    written = False
    for value in ("t#10ms", "T#10ms", "10"):
        try:
            task.interval = value
            written = True
            break
        except Exception:
            pass
    if not written:
        warn("MainTask: could not set the 10 ms interval")
    try:
        task.priority = "1"
    except Exception as error:
        warn("MainTask: could not set the priority (" + str(error) + ")")
    try:
        task.pous.add("PLC_PRG")
    except Exception as error:
        warn("MainTask: could not call PLC_PRG (" + str(error) + ")")


def main():
    if os.path.exists(PROJECT_PATH):
        raise Exception("The project already exists: " + PROJECT_PATH
                        + ". Choose another path or delete it first.")
    folder = os.path.dirname(PROJECT_PATH)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    project = projects.create(PROJECT_PATH, True)
    log("Project created: " + PROJECT_PATH)

    cpu = exact_device("Controller " + CPU_MODEL, CPU_DEVICE_ID)
    cpu_name = str(cpu.device_info.default_instance_name) or "Device"
    project.add(cpu_name, cpu.device_id)
    controller = find_one(project, cpu_name)
    if controller is None:
        raise Exception("The controller was not found after adding it: " + cpu_name)

    application = find_one(project, "Application")
    if application is None:
        raise Exception("No Application after adding the controller.")
    plc_prg = find_one(application, "PLC_PRG")
    if plc_prg is None:
        plc_prg = application.create_pou("PLC_PRG", PouType.Program)
    plc_prg.textual_declaration.replace("PROGRAM PLC_PRG\nVAR\nEND_VAR\n")
    plc_prg.textual_implementation.replace(
        "// The axis machine data are project parameters of each axis object.\n")
    create_task(application)

    master_desc = exact_device("EtherCAT Master", ETHERCAT_MASTER_DEVICE_ID)
    controller.add("EtherCAT_Master", master_desc.device_id)
    master = find_one(project, "EtherCAT_Master")
    sync_desc = None
    for d in device_repository.get_all_devices("Controller Sync Device") or []:
        name = str(d.device_info.name).lower()
        if "controller" in name and "sync" in name:
            sync_desc = d
            break
    if sync_desc is None:
        raise Exception("Controller Sync Device not found in the repository.")
    master.add("Controller_Sync_Device", sync_desc.device_id)

    # Create Hot Connect groups in the EtherCAT Master
    hot_connect_groups_created = create_hot_connect_groups(master, project)

    automatic = axis_insert_without_dialog()
    axes = []
    for a in AXES:
        drive_name = "Drv_" + a["name"]
        desc = exact_device(a["drive_type"], a["device_id"])
        master.add(drive_name, desc.device_id)
        axes.append((a, drive_name, axis_of(project, controller, a, drive_name, automatic)))
        if IDENTIFICATION_MODE:
            drive = find_one(project, drive_name)
            try:
                if set_identification(drive, IDENTIFICATION_MODE, a["station_alias"]):
                    DONE.append("%s: EtherCAT identification %d = %d"
                                % (drive_name, IDENTIFICATION_MODE, a["station_alias"]))
                else:
                    warn(drive_name + ": the EtherCAT identification did not read back as written")
            except Exception as error:
                warn(drive_name + ": could not set the EtherCAT identification (" + str(error) + ")")

    groups = add_groups(controller, project)

    build(application)
    connect_groups(groups)
    write_group_parameters(groups)

    for a, drive_name, axis in axes:
        try:
            count = len(axis.device_parameters)
        except Exception:
            count = 0
        if count == 0:
            warn(a["name"] + ": the axis has no parameters after the build; "
                 "its machine data could not be written")
            continue
        ok = 0
        for key, value in a["machine_data"]:
            if set_parameter(axis, a["name"], key, value):
                ok += 1
        DONE.append("%s: drive %s, %d/%d machine data written"
                    % (a["name"], drive_name, ok, len(a["machine_data"])))

    for g in UNSUPPORTED_GROUPS:
        warn("Robot group " + g + " not created: no Lenze kinematics for its type.")

    project.save()
    log("-" * 60)
    for line in DONE:
        log(line)
    log("RESULT: " + ("OK" if not WARNINGS else "DONE WITH %d WARNING(S)" % len(WARNINGS)))
    for line in WARNINGS:
        log("  - " + line)
    write_report()


try:
    main()
except Exception as error:
    log("ERROR: " + str(error))
    traceback.print_exc()
    write_report()
    raise
'''


def generate_plc_script(cfg):
    errors = validate_config(cfg)
    if errors:
        raise ValueError("\n".join(errors))
    axes = []
    for i, raw in enumerate(cfg["axes"], 1):
        a = normalize_axis(raw, i)
        if not a["enabled"]:
            continue
        axes.append({
            "name": a["name"],
            "drive_type": a["drive_type"],
            "device_id": a["device_id"],
            "station_alias": int(a["station_alias"]),
            "second_station_alias": int(a["second_station_alias"]),
            "machine_data": axis_machine_data(a),
            "motor_code_c86": a.get("motor_code_c86", ""),
        })
    groups = []
    unsupported = []
    for g in cfg.get("robot_groups", []) or []:
        kind = str(g.get("type", ""))
        if kind not in ROBOT_DEVICES:
            unsupported.append("%s (%s)" % (g.get("name", ""), kind))
            continue
        normalized_group = normalize_robot_group(g, len(groups) + 1)
        groups.append({"name": normalized_group["name"], "type": kind,
                       "device": list(ROBOT_DEVICES[kind]),
                       "order": group_axis_order(normalized_group),
                       "group_parameters": normalized_group["group_parameters"],
                       "parameter_ids": robot_parameter_ids(
                           kind, normalized_group["group_parameters"]),
                       "parameter_labels": robot_parameter_labels(kind)})
    mode = IDENTIFICATION_MODES.get(str(cfg.get("ethercat_identification", "NONE")), 0)
    script = SCRIPT_TEMPLATE
    hot_connect_groups = cfg.get("hot_connect_groups", [])
    for token, value in (
        ("__PROJECT_PATH__", str(cfg["project_path"]).strip()),
        ("__CPU_MODEL__", cfg["cpu_model"]),
        ("__CPU_DEVICE_ID__", cfg["cpu_device_id"]),
        ("__MASTER_DEVICE_ID__", cfg["ethercat_master_device_id"]),
        ("__AXES__", axes),
        ("__ROBOT_GROUPS__", groups),
        ("__UNSUPPORTED_GROUPS__", unsupported),
        ("__HOT_CONNECT_GROUPS__", hot_connect_groups),
        ("__IDENTIFICATION_MODE__", mode),
        ("__PARAMETERS__", AXIS_PARAMETERS),
    ):
        script = script.replace(token, _ascii_literal(value))
    return script
