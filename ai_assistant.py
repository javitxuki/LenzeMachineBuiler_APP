# -*- coding: utf-8 -*-
"""Lenze Machine Builder Assistant.
Asistente híbrido:
1. OpenAI interpreta instrucciones en lenguaje natural.
2. El parser local queda como respaldo si OpenAI no está disponible.
3. La configuración nunca se aplica automáticamente.
   app.py muestra la propuesta y el usuario decide si aplicarla.
"""

import io
import math
import os
import re
import unicodedata
from copy import deepcopy

from machine_builder_core import (
    CPU_MODELS, DRIVES, KINEMATICS, SAFETY, I950_VARIANTS, TRAVERSING,
    calculate_feed_constant, normalize_safety, normalize_i950_variant,
    normalize_traversing_range,
)

# Los proxies corporativos (Zscaler) interceptan HTTPS con su propio CA, que no
# esta en certifi: sin esto, descargar los modelos Whisper y llamar a OpenAI
# fallan con "SSL: CERTIFICATE_VERIFY_FAILED". Truststore usa el almacenes de
# certificados de Windows, que si confia en ese CA.
try:
    import truststore
    truststore.inject_into_ssl()
except Exception:
    pass

# Los mismos valores que la aplicacion: una propuesta con otros nombres ("Advanced
# Safety", "Compact", "LINEAR") no casaba con los desplegables y reventaba la pantalla.
SUPPORTED_CPUS = tuple(CPU_MODELS)
SUPPORTED_DRIVES = tuple(DRIVES)
SUPPORTED_KINEMATICS = tuple(KINEMATICS)


# ============================================================
# UTILIDADES
# ============================================================

def _normalize(value):
    text = str(value or "").strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text


def _number(value, default=None):
    try:
        return float(str(value).replace(",", "."))
    except Exception:
        return default


def _formatted_number(value):
    if value is None:
        return ""
    try:
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:.4f}".rstrip("0").rstrip(".")
    except Exception:
        return str(value)


def _feed(kinematics, parameter, z1=1, z2=1, z3=1, z4=1):
    """Feed constant con la MISMA formula que la aplicacion.

    La relacion de la reductora (Z1..Z4) va en sus propios parametros del eje y no
    se mezcla aqui. Los Z se aceptan por compatibilidad y no se usan."""
    try:
        return calculate_feed_constant(kinematics, _number(parameter, 360.0))
    except Exception:
        return 360.0


def _new_axis(index):
    return {
        "enabled": True,
        "name": f"Axis_{index:02d}",
        "drive_type": "i950",
        "safety_variant": "Basic Safety",
        "i950_variant": "Normal",
        "descriptor_label": "",
        "device_id": "",
        "station_alias": 1000 + index,
        "second_station_alias": 2000 + index,
        "motor_code_c86": "",
        "kinematics": "ROTARY",
        "kinematic_parameter": 360.0,
        "z1": 1,
        "z2": 1,
        "z3": 1,
        "z4": 1,
        "traversing_range": "MODULO",
        "feed_constant": 360.0,
        "cycle_length": 360.0,
    }


def _ensure_axes(current_axes):
    axes = deepcopy(current_axes or [])

    if not axes:
        axes = [_new_axis(1)]

    return axes


# ============================================================
# PARSER LOCAL
# ============================================================

def _detect_cpu(prompt):
    text = _normalize(prompt)

    for cpu in SUPPORTED_CPUS:
        if re.search(rf"\b{re.escape(cpu)}\b", text):
            return cpu

    return None


def _detect_axis_count(prompt):
    text = _normalize(prompt)

    patterns = [
        r"\b(\d+)\s+ejes?\b",
        r"\b(\d+)\s+axes?\b",
        r"\bcon\s+(\d+)\s+ejes?\b",
        r"\bcon\s+(\d+)\s+axes?\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            try:
                return max(1, int(match.group(1)))
            except Exception:
                pass

    return None


def _axis_clauses(prompt):
    """
    Detecta expresiones del tipo:

    eje 1 i950
    eje 2 i550
    axis 3 i750
    eje 1 safety advanced
    """

    text = _normalize(prompt)

    pattern = re.compile(
        r"(?:eje|axis)\s*"
        r"(\d+)"
        r"(.*?)(?=(?:\b(?:eje|axis)\s*\d+\b)|$)",
        re.IGNORECASE,
    )

    return [
        (int(match.group(1)), match.group(2).strip())
        for match in pattern.finditer(text)
    ]


def _extract_drive(text):
    text = _normalize(text)

    for drive in SUPPORTED_DRIVES:
        if re.search(rf"\b{re.escape(drive)}\b", text):
            return drive

    return None


def _extract_safety(text):
    text = _normalize(text)

    if re.search(r"\b(extended|advanced|extendida|avanzada)\b", text):
        return "Extended Safety"

    if re.search(r"\b(basic|basica)\b", text):
        return "Basic Safety"

    return None


def _extract_i950_variant(text):
    text = _normalize(text)

    if re.search(r"dc[\s-]?link", text):
        return "DC-Link"

    if "normal" in text:
        return "Normal"

    return None


def _extract_traversing_range(text):
    text = _normalize(text)

    if re.search(r"\b(modulo|infinite|infinito|sin fin|endless)\b", text):
        return "MODULO"

    if re.search(r"\b(limited|limitado|linear|lineal)\b", text):
        return "LIMITED"

    return None


def _extract_kinematics(text):
    text = _normalize(text)

    if any(x in text for x in ["lead screw", "leadscrew", "husillo", "tornillo"]):
        return "LEADSCREW"

    if any(x in text for x in ["belt", "correa"]):
        return "BELT"

    if any(x in text for x in ["rack", "pinion", "cremallera", "pinon"]):
        return "RACK_PINION"

    if any(x in text for x in ["rotary", "rotativo", "rotativa", "giro"]):
        return "ROTARY"

    return None


def _extract_z_values(text):
    text = _normalize(text)

    values = {}

    for z in ("z1", "z2", "z3", "z4"):
        match = re.search(
            rf"\b{z}\s*[:=]?\s*(-?\d+(?:[.,]\d+)?)",
            text,
        )

        if match:
            values[z] = _number(match.group(1), 1)

    return values


def _extract_alias(text):
    text = _normalize(text)

    match = re.search(
        r"(?:alias|station\s+alias|direccion|dirección)"
        r"\s*[:=]?\s*(\d+)",
        text,
    )

    if match:
        return int(match.group(1))

    return None


def _extract_c86(text):
    text = _normalize(text)

    match = re.search(
        r"(?:c86|motor\s+c86|codigo\s+c86|codigo)"
        r"\s*[:=]?\s*([a-z0-9._/-]+)",
        text,
    )

    if match:
        return match.group(1)

    return None


def _describe_axis(axis, index):
    parts = [
        f"Eje {index}",
        axis.get("name", f"Axis_{index:02d}"),
    ]

    if axis.get("drive_type"):
        parts.append(axis["drive_type"])

    if axis.get("kinematics"):
        parts.append(axis["kinematics"])

    return " — ".join(parts)


def local_parse(prompt, current_axes, current_config=None):
    """
    Parser local de respaldo.

    Devuelve siempre la misma estructura que espera app.py.
    """

    axes = _ensure_axes(current_axes)

    original_axes = deepcopy(axes)

    cpu_model = _detect_cpu(prompt)
    axis_count = _detect_axis_count(prompt)

    if axis_count is not None:
        while len(axes) < axis_count:
            axes.append(_new_axis(len(axes) + 1))

        if len(axes) > axis_count:
            axes = axes[:axis_count]

    changes = []
    warnings = []

    # --------------------------------------------------------
    # CPU
    # --------------------------------------------------------

    if cpu_model:
        changes.append(f"CPU → {cpu_model.upper()}")

    # --------------------------------------------------------
    # CAMBIOS POR EJE
    # --------------------------------------------------------

    clauses = _axis_clauses(prompt)

    for index, clause in clauses:

        if index < 1:
            continue

        while len(axes) < index:
            axes.append(_new_axis(len(axes) + 1))

        axis = axes[index - 1]
        text = _normalize(clause)

        # Drive
        drive = _extract_drive(text)

        if drive:
            axis["drive_type"] = drive
            changes.append(f"Eje {index}: drive → {drive}")

        # Safety
        safety = _extract_safety(text)

        if safety:
            axis["safety_variant"] = normalize_safety(safety, axis.get("drive_type"))
            changes.append(f"Eje {index}: safety → {axis['safety_variant']}")

        # i950 variant
        i950_variant = _extract_i950_variant(text)

        if i950_variant and axis.get("drive_type") == "i950":
            axis["i950_variant"] = i950_variant
            changes.append(f"Eje {index}: i950 → {i950_variant}")

        # Kinematics
        kinematics = _extract_kinematics(text)

        if kinematics:
            axis["kinematics"] = kinematics
            changes.append(f"Eje {index}: cinemática → {kinematics}")

        # Traversing range
        traversing = _extract_traversing_range(text)

        if traversing:
            axis["traversing_range"] = traversing
            changes.append(
                f"Eje {index}: traversing range → {traversing}"
            )

        # Z values
        z_values = _extract_z_values(text)

        for key, value in z_values.items():
            value = max(1, int(round(value or 1)))
            z_values[key] = value
            axis[key] = value
            changes.append(f"Eje {index}: {key} → {_formatted_number(value)}")

        # Alias
        alias = _extract_alias(text)

        if alias is not None:
            axis["station_alias"] = alias
            changes.append(f"Eje {index}: station alias → {alias}")

        # C86
        c86 = _extract_c86(text)

        if c86:
            axis["motor_code_c86"] = c86
            changes.append(f"Eje {index}: C86 → {c86}")

        # Feed constant / parámetro cinemático
        feed_match = re.search(
            r"(?:feed|feed\s+constant|avance|paso)"
            r"\s*[:=]?\s*(-?\d+(?:[.,]\d+)?)",
            text,
        )

        if feed_match:
            feed = _number(feed_match.group(1))

            if feed is not None:
                axis["feed_constant"] = feed
                axis["kinematic_parameter"] = feed

                changes.append(
                    f"Eje {index}: feed constant → {_formatted_number(feed)}"
                )

        # Recalcular feed si se modificó la cinemática o engranajes
        if kinematics or z_values:
            axis["feed_constant"] = _feed(
                axis.get("kinematics"),
                axis.get("kinematic_parameter"),
                axis.get("z1"),
                axis.get("z2"),
                axis.get("z3"),
                axis.get("z4"),
            )

    # --------------------------------------------------------
    # CAMBIOS GENERALES QUE NO VIENEN COMO "EJE X"
    # --------------------------------------------------------

    normalized_prompt = _normalize(prompt)

    if not clauses and axis_count == 1:

        axis = axes[0]

        drive = _extract_drive(normalized_prompt)

        if drive:
            axis["drive_type"] = drive
            changes.append(f"Eje 1: drive → {drive}")

        safety = _extract_safety(normalized_prompt)

        if safety:
            axis["safety_variant"] = safety
            changes.append(f"Eje 1: safety → {safety}")

        kinematics = _extract_kinematics(normalized_prompt)

        if kinematics:
            axis["kinematics"] = kinematics
            changes.append(
                f"Eje 1: cinemática → {kinematics}"
            )

    # --------------------------------------------------------
    # ADVERTENCIAS
    # --------------------------------------------------------

    if not changes and not cpu_model and axis_count is None:
        warnings.append(
            "No he detectado ningún cambio concreto en la orden."
        )

    # --------------------------------------------------------
    # RESUMEN
    # --------------------------------------------------------

    if changes:
        summary = "He preparado los siguientes cambios:\n\n"
        summary += "\n".join(f"• {change}" for change in changes)
    else:
        summary = "No se han detectado cambios concretos."

    return {
        "axes": axes,
        "cpu_model": cpu_model,
        "axis_count": len(axes),
        "summary": summary,
        "changes": changes,
        "warnings": warnings,
        "source": "local-v3",
    }


# ============================================================
# OPENAI
# ============================================================

def _openai_client():
    """
    Crea el cliente OpenAI usando exclusivamente la variable
    OPENAI_API_KEY configurada en Railway.
    """

    key = os.getenv("OPENAI_API_KEY", "").strip()

    if not key:
        return None

    from openai import OpenAI

    return OpenAI(api_key=key)


def _openai_model():
    """
    Modelo utilizado para interpretar las órdenes de Machine Builder.

    Se puede cambiar con la variable OPENAI_MODEL sin tocar el código.
    """

    return os.getenv("OPENAI_MODEL", "gpt-5.6-luna").strip() or "gpt-5.6-luna"


def _build_openai_prompt(prompt, current_axes, current_config=None):

    return f"""
Eres un asistente experto en Lenze Machine Builder y automatización industrial.

Tu trabajo es interpretar una orden escrita por el usuario y convertirla en una propuesta de configuración.

IMPORTANTE:
- No ejecutes cambios directamente.
- Devuelve únicamente una propuesta.
- Conserva los valores actuales cuando el usuario no pida modificarlos.
- No inventes valores.
- Si el usuario no menciona un parámetro, mantenlo exactamente como está.
- Puedes entender español e inglés.
- Interpreta expresiones naturales como:
  "pon 3 ejes",
  "el eje 1 que sea i950",
  "eje 2 i550",
  "pon husillo en el eje 1",
  "usa Extended Safety en el eje 3",
  "pon z1 2 y z2 5 en el eje 1",
  "CPU C550",
  etc.

CONFIGURACIÓN ACTUAL DE LOS EJES:

{current_axes}

CONFIGURACIÓN GENERAL ACTUAL:

{current_config}

ORDEN DEL USUARIO:

{prompt}

Devuelve ÚNICAMENTE un objeto JSON válido con esta estructura:

{{
  "axes": [...],
  "cpu_model": null,
  "axis_count": 1,
  "summary": "Resumen breve en español",
  "changes": [
    "Cambio 1",
    "Cambio 2"
  ],
  "warnings": [],
  "source": "openai"
}}

REGLAS PARA "axes":

- Debe contener la configuración COMPLETA de todos los ejes.
- Mantén exactamente los campos existentes.
- No elimines campos.
- No cambies valores que el usuario no haya solicitado cambiar.
- Si el usuario pide cambiar el número de ejes, crea o elimina ejes según corresponda.
- Los nombres por defecto deben seguir Axis_01, Axis_02, Axis_03...
- drive_type solamente puede ser:
  "i550", "i750", "i950"
- safety_variant solamente puede ser:
  "Basic Safety" o "Extended Safety" (i550 solo admite "Basic Safety")
- i950_variant solamente puede ser:
  "Normal" o "DC-Link"
- kinematics solamente puede ser:
  "ROTARY", "LEADSCREW", "BELT", "RACK_PINION"
- traversing_range solamente puede ser:
  "MODULO" (eje sin fin, p. ej. un plato o una cinta) o "LIMITED" (eje con topes)
- kinematic_parameter es: 360 para ROTARY, el paso del husillo en mm para
  LEADSCREW, y el diámetro efectivo en mm para BELT y RACK_PINION.
- feed_constant es el avance por vuelta de la salida de la reductora:
  360 para ROTARY, el paso para LEADSCREW y pi × diámetro para BELT y RACK_PINION.
  Z1..Z4 son la relación de la reductora y NO se multiplican en el feed constant.
- cycle_length solo tiene sentido con traversing_range "MODULO".

No añadas explicaciones fuera del JSON.
"""


def _extract_json(text):
    """
    Extrae JSON aunque el modelo haya añadido accidentalmente
    ```json ... ```
    """

    if not text:
        raise ValueError("Respuesta vacía de OpenAI.")

    text = text.strip()

    # Caso ideal
    try:
        import json
        return json.loads(text)
    except Exception:
        pass

    # Quitar fences
    text = re.sub(
        r"^```(?:json)?\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
        flags=re.IGNORECASE,
    )

    try:
        import json
        return json.loads(text.strip())
    except Exception:
        pass

    # Buscar primer objeto JSON
    start = text.find("{")
    end = text.rfind("}")

    if start >= 0 and end > start:
        import json
        return json.loads(text[start:end + 1])

    raise ValueError("OpenAI no devolvió un JSON válido.")


def _sanitize_axis(axis, index):
    """
    Protege la aplicación frente a valores inesperados
    devueltos por el modelo.
    """

    base = _new_axis(index)

    if not isinstance(axis, dict):
        return base

    result = deepcopy(base)

    # Solo copiamos campos que conocemos
    for key in result.keys():

        if key in axis:
            result[key] = axis[key]

    # Valores seguros
    if result["drive_type"] not in SUPPORTED_DRIVES:
        result["drive_type"] = "i950"

    result["safety_variant"] = normalize_safety(result["safety_variant"], result["drive_type"])
    result["i950_variant"] = normalize_i950_variant(result["i950_variant"], result["drive_type"])

    if str(result["kinematics"]).upper() in SUPPORTED_KINEMATICS:
        result["kinematics"] = str(result["kinematics"]).upper()
    else:
        result["kinematics"] = "ROTARY"

    result["traversing_range"] = normalize_traversing_range(result["traversing_range"])

    # Tipos numéricos
    for key in (
        "station_alias",
        "second_station_alias",
        "z1",
        "z2",
        "z3",
        "z4",
        "kinematic_parameter",
        "feed_constant",
        "cycle_length",
    ):
        if key in result:
            value = _number(result[key], None)

            if value is not None:
                if key in (
                    "station_alias",
                    "second_station_alias",
                ):
                    result[key] = int(value)
                else:
                    result[key] = value

    for key in ("z1", "z2", "z3", "z4"):
        try:
            result[key] = max(1, int(round(float(result[key]))))
        except Exception:
            result[key] = 1

    # Boolean
    result["enabled"] = bool(result.get("enabled", True))

    return result


def _openai_interpret(prompt, current_axes, current_config=None):

    client = _openai_client()

    if client is None:
        raise RuntimeError(
            "OPENAI_API_KEY no está configurada."
        )

    response = client.responses.create(
        model=_openai_model(),
        instructions=(
            "Devuelve exclusivamente JSON válido. "
            "No escribas markdown ni explicaciones fuera del JSON."
        ),
        input=_build_openai_prompt(
            prompt,
            current_axes,
            current_config,
        ),
    )

    raw = getattr(response, "output_text", None)

    if not raw:
        raise ValueError(
            "OpenAI no devolvió texto."
        )

    data = _extract_json(raw)

    if not isinstance(data, dict):
        raise ValueError(
            "La respuesta de OpenAI no es un objeto JSON."
        )

    # --------------------------------------------------------
    # Ejes
    # --------------------------------------------------------

    returned_axes = data.get("axes")

    if not isinstance(returned_axes, list):
        raise ValueError(
            "OpenAI no devolvió una lista de ejes válida."
        )

    axes = []

    for index, axis in enumerate(returned_axes, start=1):
        axes.append(
            _sanitize_axis(axis, index)
        )

    if not axes:
        axes = _ensure_axes(current_axes)

    # --------------------------------------------------------
    # CPU
    # --------------------------------------------------------

    cpu_model = data.get("cpu_model")

    if cpu_model:
        cpu_model = str(cpu_model).lower()

        if cpu_model not in SUPPORTED_CPUS:
            cpu_model = None

    # --------------------------------------------------------
    # Resultado
    # --------------------------------------------------------

    changes = data.get("changes", [])

    if not isinstance(changes, list):
        changes = []

    changes = [
        str(change)
        for change in changes
    ]

    warnings = data.get("warnings", [])

    if not isinstance(warnings, list):
        warnings = []

    warnings = [
        str(warning)
        for warning in warnings
    ]

    summary = str(
        data.get(
            "summary",
            "Propuesta preparada.",
        )
    )

    return {
        "axes": axes,
        "cpu_model": cpu_model,
        "axis_count": len(axes),
        "summary": summary,
        "changes": changes,
        "warnings": warnings,
        "source": "openai",
    }


# ============================================================
# INTERPRETACIÓN PRINCIPAL
# ============================================================

def interpret(prompt, current_axes, current_config=None):
    """
    Primero intenta interpretar con OpenAI.

    Si OpenAI no está disponible, hay un error de API,
    el modelo falla o devuelve algo incorrecto, utiliza
    automáticamente el parser local.
    """

    prompt = str(prompt or "").strip()

    if not prompt:
        return local_parse(
            prompt,
            current_axes,
            current_config,
        )

    try:
        return _openai_interpret(
            prompt,
            current_axes,
            current_config,
        )

    except Exception as exc:

        local_result = local_parse(
            prompt,
            current_axes,
            current_config,
        )

        # Informamos del fallback sin romper la aplicación.
        local_result.setdefault("warnings", [])

        local_result["warnings"].insert(
            0,
            "OpenAI no pudo interpretar la orden; "
            "se ha utilizado el intérprete local."
        )

        local_result["openai_error"] = str(exc)

        return local_result


# ============================================================
# TRANSCRIPCIÓN DE VOZ
# ============================================================

# Información de la última transcripción (motor, modelo, idioma detectado y su
# probabilidad) para que la interfaz la muestre. Se mutate, no se rebinda, así
# que el importador ve siempre el mismo objeto.
LAST_TRANSCRIPTION_INFO = {}

# Modelos Whisper que la interfaz ofrece para el motor local.
WHISPER_MODELS = ("tiny", "base", "small", "medium", "large-v3")


def _transcribe_audio_openai(audio_bytes, filename, language=None):
    """Transcribe el audio mediante la API de OpenAI."""
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("Para usar OpenAI debes configurar OPENAI_API_KEY en Railway.")
    from openai import OpenAI
    stream = io.BytesIO(audio_bytes)
    stream.name = filename
    options = {
        "model": os.getenv("OPENAI_TRANSCRIPTION_MODEL", "gpt-4o-mini-transcribe"),
        "file": stream,
    }
    if language:
        options["language"] = language
    result = OpenAI(api_key=key).audio.transcriptions.create(**options)
    text = str(result.text or "").strip()
    if not text:
        raise ValueError("OpenAI no devolvió ninguna transcripción.")
    LAST_TRANSCRIPTION_INFO.clear()
    LAST_TRANSCRIPTION_INFO.update({
        "engine": "openai",
        "model": options["model"],
        "language": language or "",
        "language_probability": None,
    })
    return text


def _local_whisper_settings(model=None):
    return (
        str(model or os.getenv("WHISPER_MODEL", "small")).strip() or "small",
        os.getenv("WHISPER_DEVICE", "cpu").strip() or "cpu",
        os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip() or "int8",
    )


def _local_whisper_model(model=None):
    """Carga y conserva una única instancia de Whisper (OpenAI) por modelo.

    Los modelos se descargan de openaipublic.azureedge.net (no de Hugging Face,
    que el proxy corporativo bloquea con 403)."""
    settings = _local_whisper_settings(model)
    if getattr(_local_whisper_model, "_settings", None) != settings:
        import whisper
        try:
            _local_whisper_model._model = whisper.load_model(
                settings[0], device=settings[1]
            )
        except Exception as error:
            raise RuntimeError(
                "No se pudo cargar el modelo Whisper '%s' (%s). Comprueba la "
                "conexion: los modelos se descargan de openaipublic.azureedge.net."
                % (settings[0], error)
            )
        _local_whisper_model._settings = settings
    return _local_whisper_model._model


def _wav_to_array(audio_bytes):
    """Decodifica un WAV PCM16 a float32 16 kHz mono sin necesitar ffmpeg.

    La grabación del micrófono siempre produce WAV PCM16; Whisper carga el
    audio con ffmpeg, que no siempre está instalado, así que se decodifica aquí
    con la biblioteca estándar y se le pasa el array a Whisper."""
    import wave as _wave
    import numpy as np
    with _wave.open(io.BytesIO(audio_bytes), "rb") as wav:
        channels = wav.getnchannels()
        width = wav.getsampwidth()
        rate = wav.getframerate()
        frames = wav.readframes(wav.getnframes())
    if width != 2:
        raise ValueError("Formato de audio no soportado (%d bytes por muestra)." % width)
    data = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    if rate != 16000 and data.shape[0] > 1:
        target = int(round(data.shape[0] * 16000.0 / rate))
        if target > 1:
            positions = np.linspace(0, data.shape[0] - 1, target)
            data = np.interp(positions, np.arange(data.shape[0]), data).astype(np.float32)
    return data


def _transcribe_audio_local(audio_bytes, filename, model=None, language=None):
    """Transcribe localmente con Whisper (OpenAI), sin utilizar API.

    language None o vacío → auto-detección de idioma (lo devuelve info)."""
    import tempfile
    from pathlib import Path
    suffix = Path(filename or "audio.wav").suffix or ".wav"
    temp_path = None
    try:
        try:
            audio_input = _wav_to_array(audio_bytes)
        except Exception:
            # Si no es un WAV PCM decodificable, se deja que Whisper lo cargue
            # (requiere ffmpeg) desde el fichero temporal.
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temp_audio:
                temp_audio.write(audio_bytes)
                temp_path = temp_audio.name
            audio_input = temp_path
        selected_language = str(language or "").strip() or None
        device = _local_whisper_settings(model)[1]
        result = _local_whisper_model(model).transcribe(
            audio_input,
            language=selected_language,
            fp16=device != "cpu",
        )
        text = str(result.get("text") or "").strip()
        if not text:
            raise ValueError("No se ha detectado voz en el audio.")
        LAST_TRANSCRIPTION_INFO.clear()
        LAST_TRANSCRIPTION_INFO.update({
            "engine": "local",
            "model": _local_whisper_settings(model)[0],
            "language": str(result.get("language") or ""),
            "language_probability": None,
        })
        return text
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except OSError:
                pass


def transcribe_audio(audio_bytes, filename="audio.wav", engine="local",
                     model=None, language=None):
    """Transcribe con Whisper local o con la API de OpenAI.

    model: modelo Whisper del motor local (None → WHISPER_MODEL o "small").
    language: código ISO ("es", "en", "de") o None para auto-detectar."""
    if not audio_bytes:
        raise ValueError("No se recibió audio.")
    selected_engine = str(engine or "local").strip().lower()
    LAST_TRANSCRIPTION_INFO.clear()
    if selected_engine == "local":
        return _transcribe_audio_local(audio_bytes, filename,
                                       model=model, language=language)
    if selected_engine == "openai":
        return _transcribe_audio_openai(audio_bytes, filename,
                                        language=language)
    raise ValueError("Motor no reconocido. Usa 'local' u 'openai'.")
