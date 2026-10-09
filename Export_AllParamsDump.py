# -*- coding: ascii -*-
# Run INSIDE PLC Designer 4.2: Tools > Scripting > Execute Script File.
# Lista TODOS los parametros (sin filtro) de Drives, hijos y Axes.

import os

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "AllParamsDump.txt"
)

LINES = []


def log(text):
    text = str(text)
    LINES.append(text)
    print("[AllParams] " + text)


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


def dump_all_params_collection(obj, label):
    """Enumera device_parameters collection completa."""
    log("")
    log("=" * 60)
    log("COLLECTION: " + label)
    log("=" * 60)
    count = 0
    try:
        for param in obj.device_parameters:
            count += 1
            pid = safe(lambda: str(param.id), "?")
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
            log("  ID=%s  NAME=%s  VALUE=%s" % (pid, pname, pval))
    except Exception as e:
        log("  (error enumerando collection: %s)" % e)
    log("Total en collection: %d" % count)


def dump_by_id_scan(obj, label, max_sub=3000):
    """Escanea por ID 0x10000000+offset."""
    log("")
    log("-" * 60)
    log("ID SCAN: " + label + "  (sub 1..3000)")
    log("-" * 60)
    count = 0
    for offset in range(1, 3001):
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
        log("  SUB=0x%04X  ID=0x%08X  NAME=%s  VALUE=%s" %
            (offset, 0x10000000 + offset, pname, safe(lambda: str(param.value), "?")))
    log("Total encontrados por ID: %d" % count)


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


def main():
    project = projects.primary
    log("Project: " + str(safe(lambda: project.path, "?")))

    master = find_one(project, "EtherCAT_Master")
    if master is None:
        for name in ("EtherCAT Master", "EtherCAT_Master", "EtherCAT"):
            master = find_one(project, name)
            if master:
                break
    if master is None:
        log("No EtherCAT Master")
        return

    drives = child_nodes(master)
    log("Drives bajo master: %d" % len(drives))

    for i, drive in enumerate(drives):
        name = object_name(drive)
        log("")
        log("=" * 60)
        log("DRIVE %d: %s" % (i, name))
        log("=" * 60)

        # 1. Enumerar collection completa
        dump_all_params_collection(drive, "Drive_%d" % i)

        # 2. Scan por ID
        dump_by_id_scan(drive, "Drive_%d" % i, max_sub=3000)

        # Hijos
        children = child_nodes(drive)
        if children:
            log("  Hijos: %d" % len(children))
            for child in children:
                cname = object_name(child)
                log("  -> Hijo: %s" % cname)
                dump_all_params_collection(child, "Child_%s" % cname)
                dump_by_id_scan(child, "Child_%s" % cname, max_sub=2000)

    # Buscar ejes en Application
    app = find_one(project, "Application")
    if app:
        log("")
        log("=" * 60)
        log("APPLICATION OBJECTS")
        log("=" * 60)
        axes = child_nodes(app)
        log("Objetos bajo Application: %d" % len(axes))
        for axis in axes:
            aname = object_name(axis)
            log("  Objeto: %s" % aname)
            dump_all_params_collection(axis, "Axis_%s" % aname)
            dump_by_id_scan(axis, "Axis_%s" % aname, max_sub=3000)

    # Buscar objetos sueltos con parametros
    log("")
    log("=" * 60)
    log("TODOS LOS OBJETOS CON PARAMETROS (scan rapido)")
    log("=" * 60)
    all_nodes = child_nodes(project)
    for node in all_nodes:
        n = object_name(node)
        try:
            count = 0
            for p in node.device_parameters:
                count += 1
                break
            if count > 0:
                log("OBJETO CON PARAMS: %s" % n)
        except Exception:
            pass


try:
    main()
    log("")
    log("Done.")
except Exception as error:
    log("ERROR: " + str(error))
    import traceback
    traceback.print_exc()

try:
    with open(os.path.join(
        os.path.dirname(os.path.abspath(__file__)), "AllParamsDump.txt"), "w") as f:
        f.write("\n".join(LINES) + "\n")
    print("[AllParams] Saved: AllParamsDump.txt")
except Exception as error:
    print("[AllParams] Could not save: " + str(error))