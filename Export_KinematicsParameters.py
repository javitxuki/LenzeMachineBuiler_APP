# -*- coding: ascii -*-
# Run INSIDE PLC Designer 4.2: Tools > Scripting > Execute Script File.
#
# Dumps the parameters of every Robot Group (Device > Kinematics) of the open
# project, so Lenze Machine Builder can learn the parameter Ids of the geometric
# data (Arm Length L1, Base Radius Rbase, ...). Keep this file ASCII (the script
# engine is IronPython 2.7).
#
# Steps:
#   1. Open a project that contains at least one Robot Group (create it with
#      Machine Builder or by hand in PLC Designer).
#   2. Open each Robot Group page once and save the project: PLC Designer creates
#      the parameters the first time the page is opened.
#   3. Run this script. The result is printed below and also saved next to this
#      file as KinematicsDump.txt. Paste that file (or the printed lines) back
#      to Machine Builder to fill ROBOT_PARAMETER_IDS.
#
# If the groups cannot be listed automatically, write their names below:
GROUP_NAMES = []

import os
import traceback

PARAMETER_BASE = 0x10000000
SCAN_FROM = 1
SCAN_TO = 160
OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "KinematicsDump.txt"
)

LINES = []


def log(text):
    text = str(text)
    LINES.append(text)
    print("[KinematicsDump] " + text)


def safe(function, default=""):
    try:
        return function()
    except Exception:
        return default


def find_one(parent, name):
    found = parent.find(name, True)
    return found[0] if found else None


def node_name(node):
    for attribute in ("get_name",):
        value = safe(lambda: getattr(node, attribute)())
        if value:
            return str(value)
    value = safe(lambda: node.name)
    if value:
        return str(value)
    return ""


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


def parameter_name(parameter):
    """Best effort label of a parameter: 'Arm Length L1', 'Station Alias'..."""
    for attribute in ("name", "label", "display_name", "displayname",
                      "title", "description", "Description", "Name"):
        value = safe(lambda a=attribute: getattr(parameter, a))
        if value not in (None, ""):
            return str(value)
    return ""


def parameter_id(parameter):
    for attribute in ("id", "parameter_id", "Id", "PID", "pid"):
        value = safe(lambda a=attribute: getattr(parameter, a))
        try:
            return int(value)
        except Exception:
            continue
    return None


def parameter_value(parameter):
    return safe(lambda: parameter.value, "<unreadable>")


def dump_group(group):
    name = node_name(group) or "<unnamed group>"
    device_id = safe(lambda: str(group.device_id), "")
    log("")
    log("GROUP: " + name + "    DEVICE: " + device_id)

    # 1) Parameters of the group, discovered by scanning the Id range. This is
    #    the source of truth: by_id is the same API Machine Builder uses.
    found = {}
    for offset in range(SCAN_FROM, SCAN_TO + 1):
        pid = PARAMETER_BASE + offset
        parameter = safe(lambda p=pid: group.device_parameters.by_id(p), None)
        if parameter is None:
            continue
        found[offset] = parameter
        log("  SUB=0x%03X  PID=0x%08X  NAME=%s  VALUE=%s"
            % (offset, pid, parameter_name(parameter),
               parameter_value(parameter)))

    if not found:
        log("  (no parameters found: open this Robot Group page in PLC Designer "
            "and save the project, then run the script again)")

    # 2) Cross-check by enumerating the collection: parameters outside the scan
    #    range and the names of the ones already found.
    try:
        for parameter in group.device_parameters:
            offset = None
            pid = parameter_id(parameter)
            if pid is not None and pid >= PARAMETER_BASE:
                offset = pid - PARAMETER_BASE
            if offset is None or offset in found:
                continue
            log("  EXTRA SUB=0x%03X PID=%s NAME=%s VALUE=%s"
                % (offset, pid, parameter_name(parameter),
                   parameter_value(parameter)))
    except Exception as error:
        log("  (parameter enumeration not available: %s)" % error)


def group_list(project, kinematics):
    groups = child_nodes(kinematics)
    known = [g for g in groups if node_name(g)]
    if known:
        return known
    for name in GROUP_NAMES:
        group = find_one(project, str(name))
        if group is not None:
            known.append(group)
    return known


def main():
    project = projects.primary
    log("Project: " + str(safe(lambda: project.path, "?")))
    kinematics = find_one(project, "Kinematics")
    if kinematics is None:
        log("No 'Kinematics' node found. Open a project with Robot Groups first.")
        return
    groups = group_list(project, kinematics)
    if not groups:
        log("No Robot Groups found. Create one, open its page, save the project,")
        log("or write its name in GROUP_NAMES at the top of this script.")
        return
    for group in groups:
        dump_group(group)


try:
    main()
    log("")
    log("Done.")
except Exception as error:
    log("ERROR: " + str(error))
    traceback.print_exc()

try:
    with open(OUTPUT_FILE, "w") as output:
        output.write("\n".join(LINES) + "\n")
    print("[KinematicsDump] Saved: " + OUTPUT_FILE)
except Exception as error:
    print("[KinematicsDump] Could not save the file: " + str(error))
