# -*- coding: ascii -*-
# Run INSIDE PLC Designer 4.2: Tools > Scripting > Execute Script File.
# Captura TODOS los parametros de un drive seleccionado para usar como plantilla de motor.
# El resultado se imprime en la consola y se guarda en MotorTemplate_<C86>.json

import os
import json

# CONFIG: nombre del drive a capturar (ej. "Drv_Axis_01")
TARGET_DRIVE_NAME = "Drv_Axis_01"

# C86 del motor (para nombrar el archivo). Si no se sabe, se usa "UNKNOWN"
MOTOR_C86 = "MCS06F41"

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "MotorTemplate_%s.json" % MOTOR_C86
)

LINES = []


def log(text):
    text = str(text)
    print("[CaptureTemplate] " + text)
    LINES.append(text)


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


def capture_drive_params(drive, c86):
    """Captura todos los parametros del drive y devuelve dict {pid: value}."""
    params = {}
    count = 0
    for param in drive.device_parameters:
        try:
            pid = param.id
            if pid is not None:
                val = param.value
                params[str(pid)] = val
                count += 1
        except Exception:
            pass
    log("Capturados %d parametros del drive" % count)
    return params


def main():
    project = projects.primary
    log("Project: " + str(safe(lambda: project.path, "?")))

    # Buscar el drive objetivo
    drive = find_one(project, TARGET_DRIVE_NAME)
    if drive is None:
        log("ERROR: No se encontro el drive '%s'" % TARGET_DRIVE_NAME)
        return

    log("Drive encontrado: %s" % TARGET_DRIVE_NAME)
    device_id = safe(lambda: str(drive.device_id), "")
    log("Device ID: %s" % device_id)

    # Capturar parametros
    params = capture_drive_params(drive, MOTOR_C86)

    # Guardar JSON
    template = {
        "motor_code_c86": MOTOR_C86,
        "source_drive": TARGET_DRIVE_NAME,
        "source_device_id": device_id,
        "parameters": params
    }

    try:
        with open(OUTPUT_FILE, "w") as f:
            json.dump(template, f, indent=2)
        log("Plantilla guardada en: %s" % OUTPUT_FILE)
    except Exception as error:
        log("ERROR guardando: %s" % error)

    log("Done.")


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
        os.path.dirname(os.path.abspath(__file__)), "CaptureTemplateLog.txt"), "w") as f:
        f.write("\n".join(LINES) + "\n")
    print("[CaptureTemplate] Saved: CaptureTemplateLog.txt")
except Exception as error:
    print("[CaptureTemplate] Could not save: " + str(error))