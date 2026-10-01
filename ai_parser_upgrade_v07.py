# -*- coding: utf-8 -*-
"""Parser IA V0.7: Robot Groups automáticos para Lenze Machine Builder."""
from copy import deepcopy
import re

import ai_assistant as _base
from machine_builder_core import ROBOT_TYPES

ROBOT_ALIASES = {
    "CARTESIAN_2D": (r"cartesian[oa]?\s*(?:2d|xz)", r"portal\s*2d", r"robot\s*xz"),
    "CARTESIAN_3D": (r"cartesian[oa]?\s*(?:3d|xyz)", r"portal\s*3d", r"robot\s*xyz", r"maquina\s+cartesiana"),
    "CARTESIAN_4D": (r"cartesian[oa]?\s*(?:4d|xyzc)", r"portal\s*4d", r"robot\s*xyzc"),
    "SCARA": (r"\bscara\b",),
    "DELTA": (r"\bdelta(?:\s*3d)?\b",),
}

DEFAULT_GROUP_NAMES = {
    "CARTESIAN_2D": "Robot_XZ",
    "CARTESIAN_3D": "Robot_XYZ",
    "CARTESIAN_4D": "Robot_XYZC",
    "SCARA": "SCARA_01",
    "DELTA": "Delta_01",
}

NUMBER_WORDS = {
    "uno": 1, "una": 1, "un": 1,
    "dos": 2, "tres": 3, "cuatro": 4,
    "one": 1, "two": 2, "three": 3, "four": 4,
}


def upgraded_axis_clauses(prompt):
    text = str(prompt or "").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[;]+", "\n", text)
    pattern = re.compile(
        r"(?:^|\n|(?<=[.!?]))\s*(?:eje|axis)\s*#?\s*(\d+)\s*[:=\-]?\s*"
        r"(.*?)(?=(?:\n|(?<=[.!?]))\s*(?:eje|axis)\s*#?\s*\d+\b|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    return [(int(m.group(1)), m.group(2).strip(" \t\n.,;")) for m in pattern.finditer(text)]


def _robot_type(prompt):
    text = _base._normalize(prompt).replace("_", " ")
    canonical = text.upper().replace(" ", "_")
    for kind in ROBOT_TYPES:
        if kind in canonical:
            return kind
    # El orden evita que "cartesiana 4D" coincida antes con el patrón genérico 3D.
    for kind in ("CARTESIAN_4D", "CARTESIAN_2D", "SCARA", "DELTA", "CARTESIAN_3D"):
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in ROBOT_ALIASES[kind]):
            return kind
    return None


def _number_from_text(value):
    value = str(value).lower()
    if value.isdigit():
        return int(value)
    return NUMBER_WORDS.get(value)


def upgraded_axis_count(prompt):
    text = _base._normalize(prompt)
    match = re.search(r"\b(\d+|uno|una|un|dos|tres|cuatro|one|two|three|four)\s+(?:ejes?|axes?)\b", text)
    if match:
        return max(1, _number_from_text(match.group(1)))
    clauses = upgraded_axis_clauses(prompt)
    if clauses:
        return max(index for index, _ in clauses)
    kind = _robot_type(prompt)
    return len(ROBOT_TYPES[kind]) if kind else None


def _robot_requested(prompt):
    text = _base._normalize(prompt)
    kind = _robot_type(prompt)
    action = re.search(r"\b(crea|crear|configura|configurar|anade|añade|quiero|necesito|create|add|configure)\b", text)
    noun = re.search(r"\b(robot|maquina|máquina|grupo|group|cinematica|cinemática|portal|scara|delta|cartesiana)\b", text)
    return bool(kind and (action or noun))


def _robot_name(prompt, kind):
    text = str(prompt or "")
    patterns = (
        r"(?:robot\s*group|grupo\s+de\s+robot|grupo\s+robot)\s+(?:llamado|named|nombre)?\s*[:=]?\s*([A-Za-z_][A-Za-z0-9_]*)",
        r"(?:llamado|named)\s+([A-Za-z_][A-Za-z0-9_]*)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)
    return DEFAULT_GROUP_NAMES[kind]


def _enabled_axis_names(axes):
    return [str(a.get("name", f"Axis_{i:02d}")) for i, a in enumerate(axes or [], 1) if a.get("enabled", True)]


def _explicit_assignments(prompt, roles, axis_names):
    known = {name.lower(): name for name in axis_names}
    mapping = {}
    for role in roles:
        match = re.search(
            rf"\b{re.escape(role)}\s*(?:=|:|->|→|es|usa|con)\s*([A-Za-z_][A-Za-z0-9_]*)",
            str(prompt or ""), re.IGNORECASE,
        )
        if match:
            raw = match.group(1)
            mapping[role] = known.get(raw.lower(), raw)
    return mapping


def automatic_robot_groups(prompt, axes, current_config=None):
    existing = deepcopy((current_config or {}).get("robot_groups") or [])
    if not _robot_requested(prompt):
        return existing, [], []

    kind = _robot_type(prompt)
    roles = ROBOT_TYPES[kind]
    axis_names = _enabled_axis_names(axes)
    explicit = _explicit_assignments(prompt, roles, axis_names)
    mapping = {
        role: explicit.get(role, axis_names[index] if index < len(axis_names) else "")
        for index, role in enumerate(roles)
    }
    name = _robot_name(prompt, kind)
    new_group = {"name": name, "type": kind, "axes": mapping}

    # Evita duplicados: reemplaza por nombre o por tipo si es un grupo autogenerado.
    target = None
    for index, group in enumerate(existing):
        if str(group.get("name", "")).lower() == name.lower():
            target = index
            break
    if target is None:
        existing.append(new_group)
    else:
        existing[target] = new_group

    changes = [f"Robot Group automático: {name} ({kind})"]
    changes += [f"{role} → {mapping[role]}" for role in roles if mapping[role]]
    warnings = []
    if len(axis_names) < len(roles):
        warnings.append(f"{name} requiere {len(roles)} ejes activos y solo hay {len(axis_names)}.")
    return existing, changes, warnings


def local_parse(prompt, current_axes, current_config=None):
    old_clauses, old_count = _base._axis_clauses, _base._detect_axis_count
    try:
        _base._axis_clauses = upgraded_axis_clauses
        _base._detect_axis_count = upgraded_axis_count
        result = _base.local_parse(prompt, current_axes, current_config)
    finally:
        _base._axis_clauses, _base._detect_axis_count = old_clauses, old_count

    groups, changes, warnings = automatic_robot_groups(prompt, result.get("axes", []), current_config)
    result["robot_groups"] = groups
    result.setdefault("changes", []).extend(changes)
    result.setdefault("warnings", []).extend(warnings)
    result["source"] = "local-v4-automatic-groups"
    return result


def interpret(prompt, current_axes, current_config=None):
    prompt = str(prompt or "").strip()
    if not prompt:
        return local_parse(prompt, current_axes, current_config)
    try:
        result = _base._openai_interpret(prompt, current_axes, current_config)
        groups, changes, warnings = automatic_robot_groups(prompt, result.get("axes", []), current_config)
        result["robot_groups"] = groups
        result.setdefault("changes", []).extend(changes)
        result.setdefault("warnings", []).extend(warnings)
        result["source"] = "openai+automatic-groups"
        return result
    except Exception as error:
        result = local_parse(prompt, current_axes, current_config)
        result.setdefault("warnings", []).insert(0, "OpenAI no estuvo disponible; se usó el parser local con Robot Groups automáticos.")
        result["openai_error"] = str(error)
        return result


transcribe_audio = _base.transcribe_audio
