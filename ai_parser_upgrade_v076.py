# -*- coding: utf-8 -*-
"""Lenze Machine Builder parser V0.7.6.

Amplía V0.7.2 con todos los Robot Groups Lenze configurados en
machine_builder_core.py y conserva las plantillas globales de ejes de V0.7.1.
"""
from copy import deepcopy
import re

import ai_assistant as _base
import ai_parser_upgrade_v07 as _v07
import ai_parser_upgrade_v071 as _v071
from machine_builder_core import ROBOT_TYPES


NUMBER_WORDS = {
    "uno": 1, "una": 1, "un": 1,
    "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5,
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
}

DEFAULT_GROUP_NAMES = {
    "CARTESIAN_2D": "Robot_XZ",
    "CARTESIAN_3D": "Robot_XYZ",
    "CARTESIAN_4D": "Robot_XYZC",
    "PORTAL_AC_5DOF": "Portal_AC_01",
    "BELT_2DOF": "Belt_01",
    "SCARA_3DOF": "SCARA_3DOF_01",
    "SCARA": "SCARA_01",
    "DELTA_2DOF": "Delta_2DOF_01",
    "DELTA": "Delta_01",
    "DELTA_4DOF": "Delta_4DOF_01",
    "DELTA_5DOF": "Delta_5DOF_01",
    "LINEAR_DELTA_3DOF": "LinearDelta_3DOF_01",
    "LINEAR_DELTA_4DOF": "LinearDelta_4DOF_01",
    "ARTICULATED_4DOF": "Articulated_4DOF_01",
    "ARTICULATED_LINEAR_A1_4DOF": "ArticulatedLinearA1_01",
}


def _normal(prompt):
    return _base._normalize(prompt).replace("_", " ")


def _axis_count_in_prompt(prompt):
    match = re.search(
        r"\b(\d+|uno|una|un|dos|tres|cuatro|cinco|one|two|three|four|five)"
        r"\s*(?:ejes?|axes?|dof|grados?\s+de\s+libertad)\b",
        _normal(prompt), re.IGNORECASE,
    )
    if not match:
        return None
    value = match.group(1).lower()
    return int(value) if value.isdigit() else NUMBER_WORDS.get(value)


def robot_type_v075(prompt):
    """Reconoce nombres técnicos, abreviaturas y expresiones naturales."""
    text = _normal(prompt)
    canonical = text.upper().replace("-", " ").replace("/", " ").replace(" ", "_")
    count = _axis_count_in_prompt(prompt)

    # Claves internas exactas, priorizando las más largas. SCARA y DELTA
    # se dejan para después porque necesitan resolver el número de DOF.
    specific_internal_types = sorted(
        (kind for kind in ROBOT_TYPES if kind not in ("SCARA", "DELTA")),
        key=len,
        reverse=True,
    )
    for kind in specific_internal_types:
        if kind in canonical:
            return kind

    # ArticulatedPlinA1_4dof y variantes naturales.
    if re.search(
        r"\b(articulated\s*p?lin\s*a1|articulated\s+linear\s+a1|"
        r"articulado\s+lineal\s+a1|brazo\s+articulado\s+con\s+eje\s+lineal|"
        r"robot\s+articulado\s+con\s+a1)\b", text
    ):
        return "ARTICULATED_LINEAR_A1_4DOF"
    if re.search(
        r"\b(articulated\s*p|articulated|articulado|brazo\s+articulado|"
        r"robot\s+antropomorfico|robot\s+antropomórfico)\b", text
    ):
        return "ARTICULATED_4DOF"

    # Portal AC y Belt Kinematic.
    if re.search(
        r"\b(portal\s*ac|portal\s+a\s*c|gantry\s*ac|gantry\s+5|"
        r"portal\s+de\s+5|portal\s+cinco|xyza?c)\b", text
    ):
        return "PORTAL_AC_5DOF"
    if re.search(
        r"\b(belt\s*kinematic|beltkinematic|cinematica\s+de\s+correa|"
        r"cinemática\s+de\s+correa|robot\s+de\s+correa|portal\s+de\s+correa|"
        r"corexy|h\s*bot)\b", text
    ):
        return "BELT_2DOF"

    # Linear Delta debe comprobarse antes que Delta.
    if re.search(
        r"\b(linear\s*delta|lineardelta|delta\s+lineal|delta\s+linear|"
        r"delta\s+de\s+actuadores\s+lineales)\b", text
    ):
        if count == 4 or re.search(r"\b(4\s*dof|cuatro\s+ejes|four\s+axes)\b", text):
            return "LINEAR_DELTA_4DOF"
        return "LINEAR_DELTA_3DOF"

    # SCARA 3/4 DOF. Sin número se conserva SCARA 4DOF.
    if re.search(r"\b(scara|selective\s+compliance)\b", text):
        if count == 3 or re.search(r"\b(3\s*dof|tres\s+ejes|three\s+axes)\b", text):
            return "SCARA_3DOF"
        return "SCARA"

    # Delta2_2dof, Delta3_3dof, Delta3_4dof y Delta3_5dof.
    if re.search(r"\b(delta2|delta3|robot\s+delta|delta)\b", text):
        if re.search(r"\bdelta2\b", text) or count == 2 or re.search(r"\b2\s*dof\b", text):
            return "DELTA_2DOF"
        if count == 5 or re.search(r"\b(delta3[_\s-]*5dof|5\s*dof)\b", text):
            return "DELTA_5DOF"
        if count == 4 or re.search(r"\b(delta3[_\s-]*4dof|4\s*dof)\b", text):
            return "DELTA_4DOF"
        return "DELTA"

    # Portales cartesianos. La nomenclatura Portal_2/3/4dof también se acepta.
    cartesian = bool(re.search(
        r"\b(cartesian[oa]?|portal|gantry|portico|pórtico|robot\s*xz|"
        r"robot\s*xyz|robot\s*xyzc|mesa\s+cartesiana)\b", text
    ))
    if not cartesian:
        return None
    if re.search(r"\b(4d|4\s*dof|xyzc|portal[_\s-]*4dof)\b", text) or count == 4:
        return "CARTESIAN_4D"
    if re.search(r"\b(2d|2\s*dof|xz|portal[_\s-]*2dof)\b", text) or count == 2:
        return "CARTESIAN_2D"
    return "CARTESIAN_3D"

def upgraded_axis_count(prompt):
    count = _axis_count_in_prompt(prompt)
    if count:
        return count
    clauses = _v07.upgraded_axis_clauses(prompt)
    if clauses:
        return max(index for index, _ in clauses)
    kind = robot_type_v075(prompt)
    return len(ROBOT_TYPES[kind]) if kind else None


def _robot_requested(prompt):
    text = _normal(prompt)
    return bool(
        robot_type_v075(prompt)
        and re.search(
            r"\b(crea|crear|configura|configurar|anade|añade|quiero|necesito|"
            r"create|add|configure|robot|portal|gantry|portico|pórtico|scara|delta|"
            r"articulated|articulado|belt|correa|cinematica|cinemática)\b",
            text,
        )
    )


def _robot_name(prompt, kind):
    text = str(prompt or "")
    patterns = (
        r"(?:robot\s*group|grupo\s+de\s+robot|grupo\s+robot)\s+"
        r"(?:llamado|named|nombre)?\s*[:=]?\s*([A-Za-z_][A-Za-z0-9_]*)",
        r"(?:llamado|named)\s+([A-Za-z_][A-Za-z0-9_]*)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return DEFAULT_GROUP_NAMES.get(kind, "RobotGroup_01")


def _enabled_axis_names(axes):
    return [
        str(axis.get("name", "Axis_%02d" % index))
        for index, axis in enumerate(axes or [], 1)
        if axis.get("enabled", True)
    ]


def _explicit_assignments(prompt, roles, axis_names):
    known = {name.lower(): name for name in axis_names}
    result = {}
    for role in roles:
        match = re.search(
            r"\b%s\s*(?:=|:|->|→|es|usa|con)\s*([A-Za-z_][A-Za-z0-9_]*)"
            % re.escape(role),
            str(prompt or ""), re.IGNORECASE,
        )
        if match:
            raw = match.group(1)
            result[role] = known.get(raw.lower(), raw)
    return result


def automatic_robot_groups(prompt, axes, current_config=None):
    groups = deepcopy((current_config or {}).get("robot_groups") or [])
    if not _robot_requested(prompt):
        return groups, [], []

    kind = robot_type_v075(prompt)
    roles = ROBOT_TYPES.get(kind, [])
    names = _enabled_axis_names(axes)
    explicit = _explicit_assignments(prompt, roles, names)
    mapping = {
        role: explicit.get(role, names[index] if index < len(names) else "")
        for index, role in enumerate(roles)
    }
    name = _robot_name(prompt, kind)
    new_group = {"name": name, "type": kind, "axes": mapping}

    replaced = False
    for index, group in enumerate(groups):
        if str(group.get("name", "")).lower() == name.lower():
            groups[index] = new_group
            replaced = True
            break
    if not replaced:
        groups.append(new_group)

    changes = ["Robot Group automático: %s (%s)" % (name, kind)]
    changes.extend(
        "%s → %s" % (role, mapping[role])
        for role in roles if mapping[role]
    )
    warnings = []
    missing = [role for role in roles if not mapping[role]]
    if missing:
        warnings.append(
            "%s requiere %d ejes activos; faltan: %s."
            % (name, len(roles), ", ".join(missing))
        )
    return groups, changes, warnings


def local_parse(prompt, current_axes, current_config=None):
    old_clauses = _base._axis_clauses
    old_count = _base._detect_axis_count
    try:
        _base._axis_clauses = _v07.upgraded_axis_clauses
        _base._detect_axis_count = upgraded_axis_count
        result = _base.local_parse(prompt, current_axes, current_config)
    finally:
        _base._axis_clauses = old_clauses
        _base._detect_axis_count = old_count

    result["axes"], axis_changes = _v071.apply_global_template(
        prompt, result.get("axes", [])
    )
    result.setdefault("changes", []).extend(axis_changes)
    groups, group_changes, warnings = automatic_robot_groups(
        prompt, result["axes"], current_config
    )
    result["robot_groups"] = groups
    result["changes"].extend(group_changes)
    result.setdefault("warnings", []).extend(warnings)
    result["source"] = "local-v4.6-expanded-robot-variants"
    return _v071._fix_summary(result, axis_changes, group_changes)


def interpret(prompt, current_axes, current_config=None):
    prompt = str(prompt or "").strip()
    if not prompt:
        return local_parse(prompt, current_axes, current_config)
    try:
        result = _base._openai_interpret(prompt, current_axes, current_config)
        result["axes"], axis_changes = _v071.apply_global_template(
            prompt, result.get("axes", [])
        )
        result.setdefault("changes", []).extend(axis_changes)
        groups, group_changes, warnings = automatic_robot_groups(
            prompt, result["axes"], current_config
        )
        result["robot_groups"] = groups
        result["changes"].extend(group_changes)
        result.setdefault("warnings", []).extend(warnings)
        result["source"] = "openai+expanded-robot-variants"
        return _v071._fix_summary(result, axis_changes, group_changes)
    except Exception as error:
        result = local_parse(prompt, current_axes, current_config)
        result.setdefault("warnings", []).insert(
            0, "OpenAI no estuvo disponible; se usó el parser local V0.7.6."
        )
        result["openai_error"] = str(error)
        return result


transcribe_audio = _base.transcribe_audio
