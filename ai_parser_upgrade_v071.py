# -*- coding: utf-8 -*-
"""Lenze Machine Builder parser V0.7.1.

Adds global axis templates to V0.7 automatic Robot Groups. A phrase such as
"three i750 axes with Extended Safety" applies the common drive/safety template
to every created or existing target axis, while explicit "Axis N ..." clauses
still override the global values for that axis.
"""
from copy import deepcopy
import re

import ai_assistant as _base
from machine_builder_core import (
    DRIVES,
    KINEMATICS,
    ROBOT_TYPES,
    calculate_feed_constant,
    normalize_i950_variant,
    normalize_safety,
    normalize_traversing_range,
)
from ai_parser_upgrade_v07 import (
    automatic_robot_groups,
    upgraded_axis_clauses,
    upgraded_axis_count,
)


GLOBAL_FIELDS = (
    "drive_type", "safety_variant", "i950_variant", "kinematics",
    "kinematic_parameter", "feed_constant", "traversing_range",
    "cycle_length", "z1", "z2", "z3", "z4", "motor_code_c86",
)


def _normal(text):
    return _base._normalize(text)


def _number(text, patterns, default=None):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                return float(match.group(1).replace(",", "."))
            except Exception:
                return default
    return default


def _global_drive(text):
    found = [drive for drive in DRIVES if re.search(rf"\b{re.escape(drive)}\b", text)]
    return found[0] if len(found) == 1 else None


def _global_safety(text):
    if re.search(r"\b(extended\s+safety|extended|advanced\s+safety|avanzada|extendida)\b", text):
        return "Extended Safety"
    if re.search(r"\b(basic\s+safety|basic|basica|básica)\b", text):
        return "Basic Safety"
    return None


def _global_kinematics(text):
    if re.search(r"\b(husillo|tornillo|lead\s*screw|leadscrew)\b", text):
        return "LEADSCREW"
    if re.search(r"\b(correa|belt)\b", text):
        return "BELT"
    if re.search(r"\b(cremallera|pinon|piñon|pinion|rack)\b", text):
        return "RACK_PINION"
    if re.search(r"\b(rotativo|rotativa|rotary|giro)\b", text):
        return "ROTARY"
    return None


def parse_global_axis_template(prompt):
    """Returns common values explicitly requested for all axes."""
    text = _normal(prompt)
    template = {}

    drive = _global_drive(text)
    if drive:
        template["drive_type"] = drive

    safety = _global_safety(text)
    if safety:
        template["safety_variant"] = safety

    if re.search(r"\bdc[\s-]*link\b", text):
        template["i950_variant"] = "DC-Link"
    elif re.search(r"\bi950\s+normal\b", text):
        template["i950_variant"] = "Normal"

    kinematics = _global_kinematics(text)
    if kinematics:
        template["kinematics"] = kinematics

    parameter = _number(text, (
        r"(?:paso|pitch)\s*(?:de|=|:)?\s*(-?\d+(?:[.,]\d+)?)",
        r"(?:diametro|diámetro|diameter)\s*(?:de|=|:)?\s*(-?\d+(?:[.,]\d+)?)",
        r"(?:parametro\s+cinematico|parámetro\s+cinemático)\s*(?:=|:)?\s*(-?\d+(?:[.,]\d+)?)",
    ))
    if parameter is not None:
        template["kinematic_parameter"] = parameter

    feed = _number(text, (
        r"(?:feed\s*constant|feed|avance)\s*(?:=|:|de)?\s*(-?\d+(?:[.,]\d+)?)",
    ))
    if feed is not None:
        template["feed_constant"] = feed

    if re.search(r"\b(modulo|módulo|sin\s+fin|endless|infinite)\b", text):
        template["traversing_range"] = "MODULO"
    elif re.search(r"\b(limited|limitado|limitada|lineal|linear|con\s+topes)\b", text):
        template["traversing_range"] = "LIMITED"

    cycle = _number(text, (
        r"(?:cycle\s*length|longitud\s+de\s+ciclo|ciclo)\s*(?:=|:|de)?\s*(-?\d+(?:[.,]\d+)?)",
    ))
    if cycle is not None:
        template["cycle_length"] = cycle

    for key in ("z1", "z2", "z3", "z4"):
        value = _number(text, (rf"\b{key}\s*(?:=|:)?\s*(\d+(?:[.,]\d+)?)",))
        if value is not None:
            template[key] = max(1, int(round(value)))

    c86 = re.search(r"\b(?:c86|codigo\s+motor|código\s+motor)\s*(?:=|:)?\s*([a-z0-9._/-]+)", text)
    if c86:
        template["motor_code_c86"] = c86.group(1)

    return template


def _axis_specific_fields(prompt):
    """Maps axis index to the fields explicitly present in each Axis N clause."""
    specific = {}
    for index, clause in upgraded_axis_clauses(prompt):
        text = _normal(clause)
        fields = set()
        if _global_drive(text): fields.add("drive_type")
        if _global_safety(text): fields.add("safety_variant")
        if re.search(r"\bdc[\s-]*link\b|\bi950\s+normal\b", text): fields.add("i950_variant")
        if _global_kinematics(text): fields.add("kinematics")
        if re.search(r"\b(paso|pitch|diametro|diámetro|diameter|parametro\s+cinematico|parámetro\s+cinemático)\b", text): fields.add("kinematic_parameter")
        if re.search(r"\b(feed|avance)\b", text): fields.add("feed_constant")
        if re.search(r"\b(modulo|módulo|limited|limitado|lineal|linear|sin\s+fin|endless)\b", text): fields.add("traversing_range")
        if re.search(r"\b(cycle\s*length|ciclo)\b", text): fields.add("cycle_length")
        for key in ("z1", "z2", "z3", "z4"):
            if re.search(rf"\b{key}\b", text): fields.add(key)
        if re.search(r"\b(c86|codigo\s+motor|código\s+motor)\b", text): fields.add("motor_code_c86")
        specific[index] = fields
    return specific


def _recalculate_axis(axis, template, protected):
    drive = axis.get("drive_type", "i950")
    axis["safety_variant"] = normalize_safety(axis.get("safety_variant"), drive)
    axis["i950_variant"] = normalize_i950_variant(axis.get("i950_variant"), drive)
    axis["traversing_range"] = normalize_traversing_range(axis.get("traversing_range"))

    if "feed_constant" not in protected and "feed_constant" not in template:
        if "kinematics" in template or "kinematic_parameter" in template:
            try:
                axis["feed_constant"] = calculate_feed_constant(
                    axis.get("kinematics", "ROTARY"),
                    axis.get("kinematic_parameter", 360.0),
                )
            except Exception:
                pass
    return axis


def apply_global_template(prompt, axes):
    template = parse_global_axis_template(prompt)
    if not template:
        return deepcopy(axes or []), []

    protected_by_axis = _axis_specific_fields(prompt)
    result = deepcopy(axes or [])
    changes = []

    for index, axis in enumerate(result, 1):
        protected = protected_by_axis.get(index, set())
        applied = []
        for key, value in template.items():
            if key in protected:
                continue
            axis[key] = value
            applied.append(f"{key}={value}")
        _recalculate_axis(axis, template, protected)
        if applied:
            changes.append(f"{axis.get('name', f'Axis_{index:02d}')}: " + ", ".join(applied))
    return result, changes


def _fix_summary(result, axis_changes, group_changes):
    all_changes = list(result.get("changes") or [])
    if all_changes:
        lines = ["Se ha preparado la configuración solicitada:"]
        if axis_changes:
            lines.append(f"• Plantilla global aplicada a {len(axis_changes)} eje(s).")
        if group_changes:
            lines.append("• Robot Group creado y ejes asignados automáticamente.")
        result["summary"] = "\n".join(lines)
    return result


def local_parse(prompt, current_axes, current_config=None):
    old_clauses, old_count = _base._axis_clauses, _base._detect_axis_count
    try:
        _base._axis_clauses = upgraded_axis_clauses
        _base._detect_axis_count = upgraded_axis_count
        result = _base.local_parse(prompt, current_axes, current_config)
    finally:
        _base._axis_clauses, _base._detect_axis_count = old_clauses, old_count

    result["axes"], axis_changes = apply_global_template(prompt, result.get("axes", []))
    result.setdefault("changes", []).extend(axis_changes)
    groups, group_changes, warnings = automatic_robot_groups(prompt, result["axes"], current_config)
    result["robot_groups"] = groups
    result["changes"].extend(group_changes)
    result.setdefault("warnings", []).extend(warnings)
    result["source"] = "local-v4.1-global-templates"
    return _fix_summary(result, axis_changes, group_changes)


def interpret(prompt, current_axes, current_config=None):
    prompt = str(prompt or "").strip()
    if not prompt:
        return local_parse(prompt, current_axes, current_config)
    try:
        result = _base._openai_interpret(prompt, current_axes, current_config)
        result["axes"], axis_changes = apply_global_template(prompt, result.get("axes", []))
        result.setdefault("changes", []).extend(axis_changes)
        groups, group_changes, warnings = automatic_robot_groups(prompt, result["axes"], current_config)
        result["robot_groups"] = groups
        result["changes"].extend(group_changes)
        result.setdefault("warnings", []).extend(warnings)
        result["source"] = "openai+global-templates"
        return _fix_summary(result, axis_changes, group_changes)
    except Exception as error:
        result = local_parse(prompt, current_axes, current_config)
        result.setdefault("warnings", []).insert(0, "OpenAI no estuvo disponible; se usó el parser local V0.7.1.")
        result["openai_error"] = str(error)
        return result


transcribe_audio = _base.transcribe_audio
