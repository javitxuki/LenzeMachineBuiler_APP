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
    for group in cfg.get("robot_groups", []) or []:
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
CPU_MODEL = __CPU_MODEL__
CPU_DEVICE_ID = __CPU_DEVICE_ID__
ETHERCAT_MASTER_DEVICE_ID = __MASTER_DEVICE_ID__
AXES = __AXES__
ROBOT_GROUPS = __ROBOT_GROUPS__
UNSUPPORTED_GROUPS = __UNSUPPORTED_GROUPS__
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


def log(text):
    print("[Machine Builder] " + str(text))


def warn(text):
    WARNINGS.append(text)
    log("WARNING: " + text)


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


def set_parameter(device, label, key, value):
    """Writes a parameter by Id and reads it back. Returns True if it holds."""
    pid = PARAMETER_BASE + PARAMETERS[key]
    try:
        parameter = device.device_parameters.by_id(pid)
    except Exception:
        parameter = None
    if parameter is None:
        warn(label + ": parameter " + key + " (Id 0x%08X) does not exist" % pid)
        return False
    try:
        parameter.value = value
        now = str(parameter.value)
    except Exception as error:
        warn(label + ": could not write " + key + " = " + value + " (" + str(error) + ")")
        return False
    try:
        same = abs(float(now) - float(value)) < 1e-9
    except ValueError:
        same = now.strip().upper() == value.strip().upper()
    if not same:
        warn(label + ": " + key + " was written as " + value + " but reads " + now)
        return False
    return True


def link_axis(axis, drive_name):
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


try:
    main()
except Exception as error:
    log("ERROR: " + str(error))
    traceback.print_exc()
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
        })
    groups = []
    unsupported = []
    for g in cfg.get("robot_groups", []) or []:
        kind = str(g.get("type", ""))
        if kind not in ROBOT_DEVICES:
            unsupported.append("%s (%s)" % (g.get("name", ""), kind))
            continue
        groups.append({"name": str(g.get("name", "")), "type": kind,
                       "device": list(ROBOT_DEVICES[kind]), "order": group_axis_order(g)})
    mode = IDENTIFICATION_MODES.get(str(cfg.get("ethercat_identification", "NONE")), 0)
    script = SCRIPT_TEMPLATE
    for token, value in (
        ("__PROJECT_PATH__", str(cfg["project_path"]).strip()),
        ("__CPU_MODEL__", cfg["cpu_model"]),
        ("__CPU_DEVICE_ID__", cfg["cpu_device_id"]),
        ("__MASTER_DEVICE_ID__", cfg["ethercat_master_device_id"]),
        ("__AXES__", axes),
        ("__ROBOT_GROUPS__", groups),
        ("__UNSUPPORTED_GROUPS__", unsupported),
        ("__IDENTIFICATION_MODE__", mode),
        ("__PARAMETERS__", AXIS_PARAMETERS),
    ):
        script = script.replace(token, _ascii_literal(value))
    return script
