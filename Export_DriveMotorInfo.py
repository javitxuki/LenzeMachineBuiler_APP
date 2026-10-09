# -*- coding: ascii -*-
# Run INSIDE PLC Designer 4.2: Tools > Scripting > Execute Script File.
#
# Introspecta los Drives del proyecto abierto para encontrar como configurar
# el motor (C86, sonda temperatura, i2xt, asistente).
# IronPython 2.7: mantener ASCII.
#
# Pasos:
#   1. Abre un proyecto que tenga al menos un Drive en el EtherCAT Master.
#   2. Ejecuta este script. La salida se imprime en la consola de Scripting
#      y se guarda en DriveMotorInfo.txt junto a este script.

import os
import json

OUTPUT_FILE = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "DriveMotorInfo.txt"
)

LINES = []


def log(text):
    text = str(text)
    LINES.append(text)
    print("[DriveMotorInfo] " + text)


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
            # Si es un metodo (callable), llamarlo
            if callable(val):
                try:
                    val = val()
                except Exception:
                    continue
            if val:
                return str(val)
    return ""


def introspect_object(obj, prefix=""):
    """Lista metodos/propiedades relevantes de un objeto."""
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


def filter_motor_related(attrs):
    keywords = ("motor", "temperature", "temp", "i2xt", "i2t", "sensor",
                "assistant", "dialog", "configure", "c86", "code",
                "accept", "apply", "confirm", "motor")
    filtered = []
    for name, t, val in attrs:
        low = name.lower()
        if any(k in low for k in keywords):
            filtered.append((name, t, val))
    return filtered


def dump_drive(drive):
    name = object_name(drive) or "<unnamed>"
    device_id = safe(lambda: str(drive.device_id), "")
    log("")
    log("=" * 60)
    log("DRIVE: " + name + "    DEVICE: " + device_id)
    log("=" * 60)

    # 1) Propiedades/metodos del drive relacionados con motor
    all_attrs = introspect_object(drive)
    motor_attrs = filter_motor_related(all_attrs)
    if motor_attrs:
        log("--- Atributos/metodos relacionados con motor/temperatura/i2xt ---")
        for name, t, val in motor_attrs:
            log("  %s (%s) = %s" % (name, t, safe(lambda: str(val), "<unreadable>")))
    else:
        log("  (ningun atributo con motor/temp/i2xt/assistant/c86 en el nombre)")

    # 2) Intentar ver si hay un metodo para abrir asistente
    for method_name in ("configure_motor", "motor_assistant", "motor_dialog",
                        "open_motor_assistant", "show_motor_dialog",
                        "motor_configuration", "configure_drive_motor"):
        if hasattr(drive, method_name):
            log("  *** METODO ENCONTRADO: drive.%s()" % method_name)

    # 3) Propiedades directas tipicas
    for prop in ("motor_code", "motor_c86", "c86", "temperature_sensor",
                 "temp_sensor", "motor_temp_sensor", "i2xt_monitoring",
                 "i2xt", "i2t_monitoring", "motor_temperature_sensor",
                 "motor_temperature_sensor_type", "i2t_mode"):
        val = safe(lambda p=prop: getattr(drive, p), None)
        if val is not None:
            log("  *** PROPIEDAD DIRECTA: drive.%s = %s" % (prop, val))

    # 4) Device parameters (subindices) - escanear rango amplio
    log("--- Device parameters (scan subindex 1..2000) ---")
    found_params = []
    for offset in range(1, 2001):
        try:
            param = drive.device_parameters.by_id(0x10000000 + offset)
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
        low = pname.lower()
        if any(k in low for k in ("motor", "temp", "i2xt", "i2t", "c86", "code", "sensor")):
            found_params.append((offset, pname, pval))
    if found_params:
        for offset, pname, pval in found_params:
            log("  SUB=0x%03X  NAME=%s  VALUE=%s" % (offset, pname, pval))
    else:
        log("  (ningun parametro con motor/temp/i2xt/c86 en el nombre)")

    # 5) Si tiene hijos (objetos anidados), inspeccionarlos
    children = child_nodes(drive)
    for child in children:
        cname = object_name(child)
        if any(k in cname.lower() for k in ("motor", "temperature", "i2xt", "sensor")):
            log("  -> HIJO RELEVANTE: %s" % cname)
            cattrs = filter_motor_related(introspect_object(child))
            for name, t, val in cattrs:
                log("     %s (%s) = %s" % (name, t, safe(lambda: str(val), "<unreadable>")))


def main():
    project = projects.primary
    log("Project: " + str(safe(lambda: project.path, "?")))

    # Buscar EtherCAT Master y sus drives
    master = find_one(project, "EtherCAT_Master")
    if master is None:
        # Intentar nombres alternativos
        for name in ("EtherCAT Master", "EtherCAT_Master", "EtherCAT"):
            master = find_one(project, name)
            if master:
                break
    if master is None:
        log("No se encontro EtherCAT Master. Asegurate de que el proyecto tenga uno.")
        return

    drives = child_nodes(master)
    if not drives:
        log("No hay drives bajo el EtherCAT Master.")
        return

    log("Drives encontrados: %d" % len(drives))
    for drive in drives:
        dump_drive(drive)

    # Tambien buscar drives sueltos en el proyecto
    all_drives = []
    for node in child_nodes(project):
        if "drive" in object_name(node).lower() or "drive" in str(node).lower():
            all_drives.append(node)
    if all_drives:
        log("")
        log("Otros objetos con 'drive' en el nombre a nivel de proyecto:")
        for d in all_drives:
            log("  - %s" % object_name(d))


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
    print("[DriveMotorInfo] Saved: " + OUTPUT_FILE)
except Exception as error:
    print("[DriveMotorInfo] Could not save the file: " + str(error))