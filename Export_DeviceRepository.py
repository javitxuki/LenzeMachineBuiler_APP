# -*- coding: ascii -*-
# Run INSIDE PLC Designer 4.2: Tools > Scripting > Execute Script File.
#
# Exports the installed device descriptions that Lenze Machine Builder offers
# (controllers, EtherCAT master, controller sync device, drives and axis
# objects) to device_repository.json, next to this script.
#
# IronPython 2.7: keep this file ASCII.

import json
import os

OUTPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "device_repository.json")

SEARCH_TERMS = [
    "c430", "c520", "c550",
    "EtherCAT Master", "Controller Sync Device",
    "i550", "i750", "i950",
]

# Universal motion axis (L_MC1P): the generated script adds one per drive.
AXIS_TYPE = 33601
AXIS_ID = "1028 0100"


def version_text(device):
    try:
        return str(device.device_id.version)
    except Exception:
        text = str(device.device_id)
        marker = "Version='"
        try:
            start = text.index(marker) + len(marker)
            return text[start:text.index("'", start)]
        except Exception:
            return ""


def device_name(device):
    try:
        return str(device.device_info.name)
    except Exception:
        try:
            return str(device.name)
        except Exception:
            return ""


def entry(device):
    key = str(device.device_id)
    # "type" repeats device_id: older versions of the web app read it from there.
    return {"name": device_name(device), "version": version_text(device),
            "device_id": key, "type": key}


def main():
    result = []
    known = set()

    for term in SEARCH_TERMS:
        for device in device_repository.get_all_devices(term) or []:
            key = str(device.device_id)
            if key not in known:
                known.add(key)
                result.append(entry(device))

    # The axis objects are not found by a drive name, so they go by type and id.
    try:
        for device in device_repository.get_all_devices() or []:
            did = device.device_id
            if int(did.type) == AXIS_TYPE and str(did.id) == AXIS_ID:
                key = str(did)
                if key not in known:
                    known.add(key)
                    result.append(entry(device))
    except Exception as error:
        print("Axis objects not exported: " + str(error))

    with open(OUTPUT_FILE, "w") as output:
        output.write(json.dumps({"devices": result}, indent=2))

    print("Exported: " + OUTPUT_FILE)
    print("Device descriptions: " + str(len(result)))


main()
