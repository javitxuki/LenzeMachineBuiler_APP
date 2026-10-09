# -*- coding: ascii -*-
# Run INSIDE PLC Designer 4.2: Tools > Scripting > Execute Script File.
#
# Descubrimiento EXHAUSTIVO de parametros de motor en Drives y Axes.
# IronPython 2.7: mantener ASCII.

import os

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "DriveMotorFullDump.txt"
)

LINES = []


def log(text):
    text = str(text)
    LINES.append(text)
    print("[FullDump] " + text)


def safe(function, default=""):
    try:
        return function()
    except Exception:
        return default


def find_one(parent, name):
    found = parent.find(name, True)
    return found[0] if found else None


def child_nodes(node):
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


def dump_all_params(obj, label, max_sub=5000):
    """Vuelca TODOS los parametros del objeto (hasta max_sub)."""
    log("")
    log("=" * 60)
    log("FULL PARAM DUMP: " + label)
    log("=" * 60)
    count = 0
    for offset in range(1, max_sub + 1):
        try:
            param = obj.device_parameters.by_id(0x10000000 + offset)
        except Exception:
            param = None
        if param is None:
            continue
        pname = ""
        for attr in ("name", "label", "display_name", "Name", "Description"):
            try:
                v = getattr(param, attr)
                if v not in (None, ""):
                    pname = str(v)
                    break
            except Exception:
                pass
        pval = safe(lambda: str(param.value), "<unreadable>")
        count += 1
        log("  SUB=0x%04X  NAME=%s  VALUE=%s" % (offset, pname, pval))
    log("Total params found: %d" % count)


def introspect_object(obj):
    attrs = []
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            val = getattr(obj, name)
        except Exception:
            continue
        t = type(val).__name__
        attrs.append((name, t, val))
    return attrs


def dump_object(obj, label):
    name = object_name(obj) or "<unnamed>"
    log("")
    log("=" * 60)
    log("OBJECT: " + label + "  (" + name + ")")
    log("=" * 60)
    attrs = introspect_object(obj)
    # Filtrar cosas interesantes
    keywords = ("motor", "temperature", "temp", "i2xt", "i2t", "sensor",
                "assistant", "dialog", "configure", "c86", "code",
                "accept", "apply", "confirm", "motor", "encoder",
                "brake", "brake", "holding", "current", "torque",
                "pole", "induct", "resist", "flux", "flux", "rated",
                "nominal", "max", "limit", "protect", "monitor")
    found = False
    for name, t, val in attrs:
        low = name.lower()
        if any(k in low for k in keywords):
            if not found:
                log("--- Atributos interesantes ---")
                found = True
            log("  %s (%s) = %s" % (name, t, safe(lambda: str(val), "<unreadable>")))
    if not found:
        log("  (ningun atributo con palabras clave de motor)")


def child_nodes(node):
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


def safe(function, default=""):
    try:
        return function()
    except Exception:
        return default


def find_one(parent, name):
    found = parent.find(name, True)
    return found[0] if found else None


def main():
    project = projects.primary
    log("Project: " + str(safe(lambda: project.path, "?")))

    # 1. Buscar EtherCAT Master
    master = find_one(project, "EtherCAT_Master")
    if master is None:
        for name in ("EtherCAT Master", "EtherCAT_Master", "EtherCAT"):
            master = find_one(project, name)
            if master:
                break
    if master is None:
        log("No EtherCAT Master found.")
        return

    # 2. Encontrar drives bajo el master
    drives = child_nodes(master)
    log("Drives bajo master: %d" % len(drives))
    for i, drive in enumerate(drives):
        dump_object(drive, "Drive_%d" % i)
        # Volcar TODOS los parametros del primer drive real (no Controller_Sync)
        if i == 1:  # Drv_Axis_01
            dump_all_params(drive, "Drive_1_FULL", max_sub=5000)
        # Inspeccionar hijos del drive
        children = child_nodes(drive)
        if children:
            log("  Hijos del drive: %d" % len(children))
            for child in children:
                cname = object_name(child)
                log("    -> Hijo: %s" % cname)
                dump_object(child, "DriveChild_" + cname)
                dump_all_params(child, "Child_" + cname, max_sub=2000)

    # 3. Buscar objetos Axis en la Application
    app = find_one(project, "Application")
    if app:
        axes = child_nodes(app)
        log("")
        log("Objetos bajo Application: %d" % len(axes))
        for axis in axes:
            aname = object_name(axis)
            if "axis" in aname.lower() or "Axis" in aname:
                dump_object(axis, "Axis_" + aname)
                dump_all_params(axis, "Axis_" + aname, max_sub=3000)

    # 4. Buscar cualquier objeto con "motor" en el nombre en todo el proyecto
    log("")
    log("=" * 60)
    log("BUSQUEDA GLOBAL DE OBJETOS CON 'MOTOR'")
    log("=" * 60)
    all_nodes = child_nodes(project)
    for node in all_nodes:
        n = object_name(node)
        if "motor" in n.lower():
            log("ENCONTRADO: %s" % n)
            dump_object(node, "GlobalMotor_" + n)
            dump_all_params(node, "GlobalMotor_" + n, max_sub=2000)


try:
    main()
    log("")
    log("Done.")
except Exception as error:
    log("ERROR: " + str(error))
    import traceback
    traceback.print_exc()

try:
    with open(OUTPUT_FILE, "w") as output:
        output.write("\n".join(LINES) + "\n")
    print("[FullDump] Saved: " + OUTPUT_FILE)
except Exception as error:
    print("[FullDump] Could not save: " + str(error))