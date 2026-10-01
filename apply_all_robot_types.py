# -*- coding: utf-8 -*-
"""Actualiza machine_builder_core.py y robot_groups_tab.py con todos los robots.
Ejecutar desde la raiz del proyecto: python apply_all_robot_types.py
"""
from pathlib import Path
import re
import shutil

ROOT = Path.cwd()
CORE = ROOT / "machine_builder_core.py"
TAB = ROOT / "ui" / "robot_groups_tab.py"
if not CORE.is_file():
    raise SystemExit("No se encuentra machine_builder_core.py en la carpeta actual.")
if not TAB.is_file():
    raise SystemExit("No se encuentra ui/robot_groups_tab.py.")

ROBOT_TYPES = '''ROBOT_TYPES = {
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
}'''

ROBOT_DEVICES = '''ROBOT_DEVICES = {
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
}'''

ROBOT_LABELS = '''ROBOT_LABELS = {
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
}'''

def replace_dict(text, name, replacement):
    pattern = rf"{name}\s*=\s*\{{.*?^\}}"
    updated, count = re.subn(pattern, replacement, text, count=1, flags=re.S | re.M)
    if count != 1:
        raise RuntimeError("No se pudo localizar " + name)
    return updated

core_text = CORE.read_text(encoding="utf-8")
tab_text = TAB.read_text(encoding="utf-8")
core_new = replace_dict(core_text, "ROBOT_TYPES", ROBOT_TYPES)
core_new = replace_dict(core_new, "ROBOT_DEVICES", ROBOT_DEVICES)
tab_new = replace_dict(tab_text, "ROBOT_LABELS", ROBOT_LABELS)
compile(core_new, str(CORE), "exec")
compile(tab_new, str(TAB), "exec")
shutil.copy2(CORE, CORE.with_name("machine_builder_core_pre_all_robots.py"))
shutil.copy2(TAB, TAB.with_name("robot_groups_tab_pre_all_robots.py"))
CORE.write_text(core_new, encoding="utf-8")
TAB.write_text(tab_new, encoding="utf-8")
print("OK: archivos actualizados y copias de seguridad creadas.")
