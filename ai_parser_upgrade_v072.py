# -*- coding: utf-8 -*-
"""Lenze Machine Builder parser V0.7.2.

Corrige la inferencia de cartesianos por número de ejes:
- cartesiana de 2 ejes -> CARTESIAN_2D
- cartesiana de 3 ejes -> CARTESIAN_3D
- cartesiana de 4 ejes -> CARTESIAN_4D
Mantiene las plantillas globales de V0.7.1.
"""
import re

import ai_assistant as _base
import ai_parser_upgrade_v07 as _v07
import ai_parser_upgrade_v071 as _v071
from machine_builder_core import ROBOT_TYPES


NUMBER_WORDS = {
    "uno": 1, "una": 1, "un": 1,
    "dos": 2, "tres": 3, "cuatro": 4,
    "one": 1, "two": 2, "three": 3, "four": 4,
}


def _axis_count_in_prompt(prompt):
    text = _base._normalize(prompt)
    match = re.search(
        r"\b(\d+|uno|una|un|dos|tres|cuatro|one|two|three|four)\s+(?:ejes?|axes?)\b",
        text,
        re.IGNORECASE,
    )
    if not match:
        return None
    value = match.group(1).lower()
    return int(value) if value.isdigit() else NUMBER_WORDS.get(value)


def robot_type_v072(prompt):
    """Prioriza dimensión explícita y número de ejes antes del cartesiano genérico."""
    text = _base._normalize(prompt).replace("_", " ")
    canonical = text.upper().replace(" ", "_")

    for kind in ROBOT_TYPES:
        if kind in canonical:
            return kind

    if re.search(r"\bscara\b", text):
        return "SCARA"
    if re.search(r"\bdelta(?:\s*3d)?\b", text):
        return "DELTA"

    cartesian = bool(re.search(r"\b(cartesian[oa]?|portal|robot\s*xz|robot\s*xyz|robot\s*xyzc)\b", text))
    if not cartesian:
        return None

    # Dimensiones y nombres de coordenadas tienen prioridad absoluta.
    if re.search(r"\b(4d|xyzc)\b", text):
        return "CARTESIAN_4D"
    if re.search(r"\b(2d|xz)\b", text):
        return "CARTESIAN_2D"
    if re.search(r"\b(3d|xyz)\b", text):
        return "CARTESIAN_3D"

    count = _axis_count_in_prompt(prompt)
    if count == 4:
        return "CARTESIAN_4D"
    if count == 2:
        return "CARTESIAN_2D"
    if count == 3:
        return "CARTESIAN_3D"

    # Solo si no hay ninguna pista dimensional se usa 3D como valor por defecto.
    return "CARTESIAN_3D"


def upgraded_axis_count(prompt):
    count = _axis_count_in_prompt(prompt)
    if count:
        return count
    clauses = _v07.upgraded_axis_clauses(prompt)
    if clauses:
        return max(index for index, _ in clauses)
    kind = robot_type_v072(prompt)
    return len(ROBOT_TYPES[kind]) if kind else None


def automatic_robot_groups(prompt, axes, current_config=None):
    """Usa la lógica V0.7, inyectando temporalmente la inferencia corregida."""
    old_robot_type = _v07._robot_type
    try:
        _v07._robot_type = robot_type_v072
        return _v07.automatic_robot_groups(prompt, axes, current_config)
    finally:
        _v07._robot_type = old_robot_type


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
    result["source"] = "local-v4.2-cartesian-dimension-fix"
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
        result["source"] = "openai+cartesian-dimension-fix"
        return _v071._fix_summary(result, axis_changes, group_changes)
    except Exception as error:
        result = local_parse(prompt, current_axes, current_config)
        result.setdefault("warnings", []).insert(
            0, "OpenAI no estuvo disponible; se usó el parser local V0.7.2."
        )
        result["openai_error"] = str(error)
        return result


transcribe_audio = _base.transcribe_audio
