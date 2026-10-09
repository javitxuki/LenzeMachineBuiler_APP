# -*- coding: ascii -*-
# Run INSIDE PLC Designer 4.2: Tools > Scripting > Execute Script File.
# Busca el metodo que abre el asistente "Select Motor" en el Drive.

import os

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "FindSelectMotorMethod.txt"
)

LINES = []


def log(text):
    text = str(text)
    LINES.append(text)
    print("[FindSelectMotor] " + text)


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


def dump_all_methods(obj, label):
    log("")
    log("=" * 60)
    log("METODOS DE: " + label)
    log("=" * 60)
    keywords = ("select", "motor", "dialog", "wizard", "assistant", "configure",
                "setup", "choose", "pick", "browse", "open", "show", "launch",
                "motor", "temperature", "temp", "i2xt", "i2t", "sensor",
                "accept", "apply", "confirm", "code", "c86", "c87", "c88")
    found_any = False
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            val = getattr(obj, name)
        except Exception:
            continue
        if not callable(val):
            continue
        low = name.lower()
        if any(k in low for k in keywords):
            log("  *** METODO CANDIDATO: %s" % name)
            found_any = True
            # Intentar ver firma
            try:
                import inspect
                sig = inspect.getargspec(val)
                log("      args: %s" % str(sig))
            except Exception:
                pass
    if not found_any:
        log("  (ningun metodo con palabras clave)")


def dump_properties(obj, label):
    log("")
    log("-" * 60)
    log("PROPIEDADES DE: " + label)
    log("-" * 60)
    keywords = ("motor", "temperature", "temp", "i2xt", "i2t", "sensor",
                "assistant", "dialog", "configure", "c86", "code",
                "temperature_sensor", "i2xt_monitoring", "motor_code",
                "motor_c86", "c86", "c87", "c88", "motor_type")
    found = False
    for name in dir(obj):
        if name.startswith("_"):
            continue
        try:
            val = getattr(obj, name)
        except Exception:
            continue
        if callable(val):
            continue
        low = name.lower()
        if any(k in low for k in keywords):
            log("  *** PROP: %s = %s" % (name, safe(lambda: str(val), "<unreadable>")))


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
    log("Drives: %d" % len(drives))

    for i, drive in enumerate(drives):
        name = object_name(drive)
        log("")
        log("=" * 60)
        log("DRIVE %d: %s" % (i, name))
        log("=" * 60)

        # 1. Buscar metodos relacionados con motor/select
        dump_all_methods(drive, "Drive_%d" % i)

        # 2. Propiedades relacionadas
        dump_properties(drive, "Drive_%d" % i)

        # 3. Inspeccionar hijos (puede haber un objeto UI)
        children = child_nodes(drive)
        if children:
            log("  Hijos: %d" % len(children))
            for child in children:
                cname = object_name(child)
                log("  -> Hijo: %s" % cname)
                dump_all_methods(child, "Child_%s" % cname)
                dump_properties(child, "Child_%s" % cname)

    # Tambien buscar en el proyecto objetos UI
    log("")
    log("=" * 60)
    log("BUSQUEDA GLOBAL DE METODOS 'SELECT MOTOR'")
    log("=" * 60)
    all_nodes = child_nodes(projects.primary)
    for node in all_nodes:
        n = object_name(node)
        if "select" in n.lower() and "motor" in n.lower():
            log("OBJETO UI ENCONTRADO: %s" % n)
            dump_all_methods(node, "UI_" + n)


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
        os.path.dirname(os.path.abspath(__file__)), "FindSelectMotorMethod.txt"), "w") as f:
        f.write("\n".join(LINES) + "\n")
    print("[FindSelectMotor] Saved: FindSelectMotorMethod.txt")
except Exception as error:
    print("[FindSelectMotor] Could not save: " + str(error))