import base64
import json
from dataclasses import asdict
from pathlib import Path

import streamlit as st

from machine_builder_core import (
    AxisConfig, CPU_MODELS, DRIVES, I950_VARIANTS, IDENTIFICATION_MODES, KINEMATICS, ROBOT_TYPES, SAFETY,
    TRAVERSING, calculate_feed_constant, config_json, cpu_options, drive_options,
    format_decimal, generate_plc_script, load_repository, master_options,
    normalize_axis, normalize_number, validate_config,
)
from auth import (
    authenticate, change_password, init_auth_state, load_users, login_wait_seconds,
    logout, plaintext_users,
)

st.set_page_config(
    page_title="Lenze Machine Builder Web",
    page_icon="⚙️",
    layout="wide",
)

st.markdown(
    """
<style>
:root {
    --lenze-blue: #3155f5;
    --lenze-navy: #14213d;
    --lenze-muted: #5b6475;
    --lenze-border: #d8dee9;
}
[data-testid="stHeader"], #MainMenu, footer { display: none; }
.block-container {
    padding-top: .6rem !important;
    max-width: 1500px !important;
    padding-left: 1rem !important;
    padding-right: 1rem !important;
}
/* Cabecera */
.lenze-head {
    background: #ffffff;
    border: 1px solid var(--lenze-border);
    border-bottom: 3px solid var(--lenze-blue);
    border-radius: 12px;
    padding: 12px 18px;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 18px;
}
.lenze-head img { width: 130px; max-height: 46px; object-fit: contain; }
.lenze-title { border-left: 1px solid var(--lenze-border); padding-left: 18px; }
.lenze-title b { font-size: 20px; color: var(--lenze-navy); }
.lenze-title span { display: block; color: var(--lenze-muted); font-size: 12px; }
/* Metricas del resumen como tarjetas */
[data-testid="stMetric"] {
    background: #ffffff;
    border: 1px solid var(--lenze-border);
    border-radius: 12px;
    padding: 10px 14px;
}
[data-testid="stMetricLabel"] p { color: var(--lenze-muted) !important; font-size: 12px; }
[data-testid="stMetricValue"] { color: var(--lenze-navy) !important; font-size: 22px; }
/* Pestanas */
.stTabs [data-baseweb="tab-list"] { gap: 6px; border-bottom: 2px solid var(--lenze-border); }
.stTabs [data-baseweb="tab"] {
    background: #ffffff;
    border: 1px solid var(--lenze-border);
    border-bottom: none;
    border-radius: 10px 10px 0 0;
    padding: 8px 16px;
    font-weight: 600;
}
.stTabs [aria-selected="true"] { color: var(--lenze-blue) !important; border-color: var(--lenze-blue); }
/* Desplegables */
[data-testid="stExpander"] details {
    border: 1px solid var(--lenze-border) !important;
    border-radius: 12px !important;
    background: #ffffff;
}
[data-testid="stExpander"] summary p { font-weight: 600; color: var(--lenze-navy); }
.stButton button, .stDownloadButton button { border-radius: 8px; font-weight: 600; }

@media (max-width: 768px) {
    .block-container { padding-left: 0.4rem !important; padding-right: 0.4rem !important; }
    .lenze-head { flex-direction: column !important; align-items: flex-start !important; gap: 8px !important; }
    .lenze-head img { width: 100px !important; max-height: 36px !important; }
    .lenze-title { border-left: none !important; padding-left: 0 !important; }
    [data-testid="column"] { width: 100% !important; min-width: 100% !important; flex: 1 1 100% !important; }
}
</style>
""",
    unsafe_allow_html=True,
)

TEXTS = {
    "ES": {
        "title": "Lenze Machine Builder Web",
        "subtitle": "Generación automática de proyectos PLC Designer",
        "login": "Acceso a Machine Builder",
        "email": "Correo electrónico",
        "password": "Contraseña",
        "signin": "Iniciar sesión",
        "invalid": "Correo o contraseña incorrectos",
        "locked": "Demasiados intentos fallidos. Espera {0} s y vuelve a probar.",
        "no_users": "No hay usuarios configurados: {0}",
        "plaintext": "Hay contraseñas en claro en MB_USERS_JSON ({0}). Sustitúyelas por su hash (python auth.py hash).",
        "role": "Permiso",
        "change": "Cambiar contraseña",
        "logout": "Cerrar sesión",
        "current": "Contraseña actual",
        "new": "Nueva contraseña",
        "repeat": "Repetir nueva contraseña",
        "save": "Guardar contraseña",
        "nomatch": "Las contraseñas no coinciden",
        "persist": "El cambio dura hasta que se reinicie el servicio. Para que sea permanente, pon este hash en MB_USERS_JSON:",
        "config": "Configuración",
        "load": "Recuperar configuración",
        "apply": "Aplicar configuración cargada",
        "loaded": "Configuración cargada correctamente.",
        "load_error": "No se pudo cargar la configuración: ",
        "cpu": "CPU",
        "cpu_desc": "Descriptor CPU",
        "master": "EtherCAT Master",
        "path": "Ruta destino del proyecto PLC Designer",
        "ident": "Identificación EtherCAT de los drives",
        "ident_NONE": "Ninguna",
        "ident_STATION_ALIAS": "Station Alias (ADO 0x0012)",
        "ident_EXPLICIT_DEVICE_ID": "Explicit Device ID (ADO 0x0134)",
        "ident_help": "El maestro comprobará que cada drive lleva el valor del campo Alias. Si un drive no lo tiene grabado, NO arranca en el bus. El Second Alias no se escribe en el proyecto.",
        "axes_n": "Número de ejes",
        "axes": "Ejes",
        "active": "Activo",
        "name": "Nombre",
        "drive": "Drive",
        "safety": "Safety",
        "i950": "Tipo i950",
        "desc": "Descriptor",
        "alias2": "Second Alias",
        "kinematics": "Cinemática",
        "kin_param": "Parámetro cinemático",
        "kin_help": "ROTARY: 360. LEADSCREW: paso del husillo (mm). BELT / RACK_PINION: diámetro efectivo (mm).",
        "traversing": "Rango de desplazamiento",
        "feed": "Feed Constant",
        "feed_help": "Avance por vuelta de la salida de la reductora. La relación Z1..Z4 va aparte.",
        "cycle": "Cycle Length",
        "calc": "Calcular Feed Constant",
        "no_desc": "Sin descriptor",
        "groups": "Robot Groups",
        "groups_n": "Número de grupos",
        "group": "Grupo",
        "group_name": "Nombre del grupo",
        "group_type": "Tipo de robot",
        "group_dup": "Hay ejes repetidos dentro del grupo.",
        "gen": "Configuración y generación",
        "download": "Descargar script PLC Designer",
        "download_help": "Corrige los errores de validación antes de generar el script.",
        "save_json": "Guardar configuración JSON",
        "warnings": "Avisos",
        "assistant": "Asistente Machine Builder",
        "assistant_help": "Describe la máquina por escrito o por voz. El asistente prepara una propuesta; los campos solo cambian al pulsar Aplicar propuesta.",
        "assistant_hint": "Ejemplo: 3 ejes; eje 1 i950 rotary; eje 2 belt 120; eje 3 leadscrew 10",
        "engine": "Motor de transcripción",
        "engine_local": "Local gratuito (Faster-Whisper)",
        "engine_help": "El modo local procesa el audio en el servidor. OpenAI requiere OPENAI_API_KEY.",
        "engine_first": "La primera transcripción puede tardar más mientras se descarga y carga el modelo local. Después se reutiliza en memoria.",
        "dictate": "🎤 Dictar configuración",
        "transcribing": "Transcribiendo audio...",
        "transcription": "Transcripción: ",
        "proposal_ready": "**Propuesta preparada**",
        "preview": "Vista previa",
        "apply_proposal": "✅ Aplicar propuesta",
        "discard": "❌ Descartar",
        "applied": "Configuración aplicada.",
        "openai_fallback": "No se pudo usar OpenAI ({0}); se ha usado el intérprete local.",
        "col_axis": "Eje",
        "col_param": "Parámetro",
        'tab_ctrl': 'Controlador',
        'path_help': 'Ruta en el PC de ingeniería donde PLC Designer creará el proyecto. Si ya existe, el script se para sin tocarlo.',
        'name_help': 'Nombre del eje en el proyecto: letras sin tilde, números y _.',
        'sec_mech': 'Mecánica',
        'sec_gear': 'Reductora',
        'sec_bus': 'EtherCAT y motor',
        'trav_MODULO': 'Módulo (sin fin)',
        'trav_LIMITED': 'Limitado',
        'gear_den': 'Z1: denominador de la reductora',
        'gear_num': 'Z2: numerador de la reductora',
        'add_den': 'Z3: denominador de la reductora adicional',
        'add_num': 'Z4: numerador de la reductora adicional',
        'alias2_help': 'Se guarda en la configuración, pero no se escribe en el proyecto: el maestro EtherCAT solo guarda una identificación por drive.',
        'groups_help': 'Cada grupo es una cinemática Lenze bajo Device > Kinematics. Asigna un eje a cada rol (A1..An).',
        'robot_CARTESIAN_2D': 'Cartesiano 2D (plano X-Z) · Portal_2dof',
        'robot_CARTESIAN_3D': 'Cartesiano 3D · Portal_3dof',
        'robot_CARTESIAN_4D': 'Cartesiano 4D (X, Y, Z, C) · Portal_4dof',
        'robot_SCARA': 'SCARA · Scara_4dof',
        'robot_DELTA': 'Delta 3 brazos · Delta3_3dof',
        'status': 'Estado',
        'ready': 'Listo',
        'n_errors': '{0} error(es)',
        'fix_first': 'Corrige estos puntos antes de generar el script:',
        'ready_long': 'Configuración válida: ya puedes descargar el script.',
        'how_to_run': 'Ejecútalo en PLC Designer 4.2: Tools › Scripting › Execute Script File. Al terminar, el resumen dice RESULT: OK o lista los avisos.',
        'preview_script': 'Ver el script generado',
    },
    "EN": {
        "title": "Lenze Machine Builder Web",
        "subtitle": "Automatic PLC Designer project generation",
        "login": "Machine Builder access",
        "email": "Email",
        "password": "Password",
        "signin": "Sign in",
        "invalid": "Incorrect email or password",
        "locked": "Too many failed attempts. Wait {0} s and try again.",
        "no_users": "No users configured: {0}",
        "plaintext": "There are plain-text passwords in MB_USERS_JSON ({0}). Replace them with their hash (python auth.py hash).",
        "role": "Role",
        "change": "Change password",
        "logout": "Sign out",
        "current": "Current password",
        "new": "New password",
        "repeat": "Repeat new password",
        "save": "Save password",
        "nomatch": "Passwords do not match",
        "persist": "The change lasts until the service restarts. To make it permanent, put this hash in MB_USERS_JSON:",
        "config": "Configuration",
        "load": "Load configuration",
        "apply": "Apply uploaded configuration",
        "loaded": "Configuration loaded.",
        "load_error": "The configuration could not be loaded: ",
        "cpu": "CPU",
        "cpu_desc": "CPU descriptor",
        "master": "EtherCAT Master",
        "path": "PLC Designer project destination path",
        "ident": "EtherCAT identification of the drives",
        "ident_NONE": "None",
        "ident_STATION_ALIAS": "Station Alias (ADO 0x0012)",
        "ident_EXPLICIT_DEVICE_ID": "Explicit Device ID (ADO 0x0134)",
        "ident_help": "The master will check that each drive carries the value of its Alias field. A drive without it does NOT start on the bus. The Second Alias is not written to the project.",
        "axes_n": "Number of axes",
        "axes": "Axes",
        "active": "Enabled",
        "name": "Name",
        "drive": "Drive",
        "safety": "Safety",
        "i950": "i950 type",
        "desc": "Descriptor",
        "alias2": "Second Alias",
        "kinematics": "Kinematics",
        "kin_param": "Kinematic parameter",
        "kin_help": "ROTARY: 360. LEADSCREW: screw pitch (mm). BELT / RACK_PINION: effective diameter (mm).",
        "traversing": "Traversing range",
        "feed": "Feed Constant",
        "feed_help": "Travel per revolution of the gearbox output. The Z1..Z4 ratio is set separately.",
        "cycle": "Cycle Length",
        "calc": "Calculate Feed Constant",
        "no_desc": "No descriptor",
        "groups": "Robot Groups",
        "groups_n": "Number of groups",
        "group": "Group",
        "group_name": "Group name",
        "group_type": "Robot type",
        "group_dup": "The same axis is used twice in the group.",
        "gen": "Configuration and generation",
        "download": "Download PLC Designer script",
        "download_help": "Fix the validation errors before generating the script.",
        "save_json": "Save configuration JSON",
        "warnings": "Warnings",
        "assistant": "Machine Builder assistant",
        "assistant_help": "Describe the machine in writing or by voice. The assistant prepares a proposal; nothing changes until you press Apply proposal.",
        "assistant_hint": "Example: 3 axes; axis 1 i950 rotary; axis 2 belt 120; axis 3 leadscrew 10",
        "engine": "Transcription engine",
        "engine_local": "Free local (Faster-Whisper)",
        "engine_help": "Local mode processes the audio on the server. OpenAI needs OPENAI_API_KEY.",
        "engine_first": "The first transcription can take longer while the local model is downloaded and loaded. It is reused afterwards.",
        "dictate": "🎤 Dictate configuration",
        "transcribing": "Transcribing audio...",
        "transcription": "Transcription: ",
        "proposal_ready": "**Proposal ready**",
        "preview": "Preview",
        "apply_proposal": "✅ Apply proposal",
        "discard": "❌ Discard",
        "applied": "Configuration applied.",
        "openai_fallback": "OpenAI could not be used ({0}); the local interpreter was used.",
        "col_axis": "Axis",
        "col_param": "Parameter",
        'tab_ctrl': 'Controller',
        'path_help': 'Path on the engineering PC where PLC Designer will create the project. If it exists, the script stops without touching it.',
        'name_help': 'Axis name in the project: letters without accents, digits and _.',
        'sec_mech': 'Mechanics',
        'sec_gear': 'Gearbox',
        'sec_bus': 'EtherCAT and motor',
        'trav_MODULO': 'Modulo (endless)',
        'trav_LIMITED': 'Limited',
        'gear_den': 'Z1: gearbox denominator',
        'gear_num': 'Z2: gearbox numerator',
        'add_den': 'Z3: additional gearbox denominator',
        'add_num': 'Z4: additional gearbox numerator',
        'alias2_help': 'Kept in the configuration but not written to the project: the EtherCAT master stores one identification per drive.',
        'groups_help': 'Each group is a Lenze kinematics under Device > Kinematics. Assign one axis per role (A1..An).',
        'robot_CARTESIAN_2D': 'Cartesian 2D (X-Z plane) · Portal_2dof',
        'robot_CARTESIAN_3D': 'Cartesian 3D · Portal_3dof',
        'robot_CARTESIAN_4D': 'Cartesian 4D (X, Y, Z, C) · Portal_4dof',
        'robot_SCARA': 'SCARA · Scara_4dof',
        'robot_DELTA': 'Delta, 3 arms · Delta3_3dof',
        'status': 'Status',
        'ready': 'Ready',
        'n_errors': '{0} error(s)',
        'fix_first': 'Fix these points before generating the script:',
        'ready_long': 'Valid configuration: the script can be downloaded.',
        'how_to_run': 'Run it in PLC Designer 4.2: Tools › Scripting › Execute Script File. At the end, the summary says RESULT: OK or lists the warnings.',
        'preview_script': 'Show the generated script',
    },
}


def t(key):
    return TEXTS[st.session_state.get("language", "ES")].get(key, key)


def logo_html():
    logo_path = Path(__file__).parent / "Lenze.png"
    if not logo_path.exists():
        return '<b style="color:#3155f5;font-size:25px">Lenze</b>'
    payload = base64.b64encode(logo_path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{payload}" alt="Lenze">'


def language_selector(key):
    choice = st.selectbox(
        "Language",
        ["🇪🇸", "🇬🇧"],
        index=0 if st.session_state.language == "ES" else 1,
        key=key,
        label_visibility="collapsed",
    )
    language = "ES" if choice == "🇪🇸" else "EN"
    if language != st.session_state.language:
        st.session_state.language = language
        st.rerun()


# ============================================================ login

def login_view():
    _, center, _ = st.columns([1, 1.2, 1])
    with center:
        st.markdown(
            f'<div class="lenze-head" style="justify-content:center">{logo_html()}</div>',
            unsafe_allow_html=True,
        )
        language_selector("login_language")
        st.title(t("login"))
        _, problem = load_users()
        if problem:
            st.error(t("no_users").format(problem))
        with st.form("login_form"):
            email = st.text_input(t("email"))
            password = st.text_input(t("password"), type="password")
            submitted = st.form_submit_button(t("signin"), width="stretch", type="primary")
        if submitted:
            success, reason = authenticate(email, password)
            if success:
                st.rerun()
            elif reason == "locked":
                st.error(t("locked").format(login_wait_seconds()))
            elif reason:
                st.error(reason)
            else:
                st.error(t("invalid"))


def user_menu():
    name = st.session_state.user_name or st.session_state.user_email
    initials = "".join(part[0].upper() for part in name.split() if part)[:2] or "US"
    with st.popover(f"{initials}  {name}  ▾", width="stretch"):
        st.caption(st.session_state.user_email)
        st.caption(f'{t("role")}: {st.session_state.user_role}')
        action = st.selectbox(
            "action", [t("change"), t("logout")], label_visibility="collapsed", key="user_action"
        )
        if action == t("change"):
            with st.form("password_form", clear_on_submit=True):
                current = st.text_input(t("current"), type="password")
                new = st.text_input(t("new"), type="password")
                repeated = st.text_input(t("repeat"), type="password")
                submitted = st.form_submit_button(t("save"), width="stretch", type="primary")
            if submitted:
                if new != repeated:
                    st.error(t("nomatch"))
                else:
                    success, message, new_hash = change_password(st.session_state.user_email, current, new)
                    (st.success if success else st.error)(message)
                    if success:
                        st.info(t("persist"))
                        st.code(new_hash, language=None)
        elif st.button(t("logout"), width="stretch", type="primary"):
            logout()


def header():
    st.markdown(
        f'<div class="lenze-head">{logo_html()}'
        f'<div class="lenze-title"><b>{t("title")}</b>'
        f'<span>{t("subtitle")}</span></div></div>',
        unsafe_allow_html=True,
    )
    language_col, _, user_col = st.columns([0.7, 5.5, 2.5])
    with language_col:
        language_selector("header_language")
    with user_col:
        user_menu()
    if st.session_state.get("user_role") == "admin":
        weak = plaintext_users()
        if weak:
            st.warning(t("plaintext").format(", ".join(weak)))


# ============================================================ estado de los ejes
#
# Cada control de un eje tiene su clave en st.session_state y se crea SOLO con esa
# clave (sin value/index). Asi hay una unica fuente de verdad: cuando se carga un
# JSON o se aplica una propuesta del asistente, se escriben las claves con
# seed_axis_widgets() y la pantalla las muestra tal cual, variante de safety y
# descriptor incluidos.

AXIS_WIDGET_PREFIXES = (
    "en_", "name_", "drv_", "safe_", "i950_", "desc_", "alias_", "alias2_", "c86_",
    "kin_", "kp_", "trav_", "z1_", "z2_", "z3_", "z4_", "feed_", "cycle_",
)
GROUP_WIDGET_PREFIXES = ("group_",)


def clear_widget_state(prefixes):
    for key in list(st.session_state.keys()):
        if str(key).startswith(prefixes):
            del st.session_state[key]


def descriptor_label(item):
    return f"{item['name']} [{item.get('version', '')}]"


def seed_axis_widgets(index, axis):
    """Escribe en session_state el valor de cada control del eje index."""
    axis = normalize_axis(axis, index + 1)
    s = st.session_state
    s[f"en_{index}"] = bool(axis["enabled"])
    s[f"name_{index}"] = axis["name"]
    s[f"drv_{index}"] = axis["drive_type"]
    s[f"safe_{index}"] = axis["safety_variant"]
    s[f"i950_{index}"] = axis["i950_variant"]
    descriptors = drive_options(REPO, axis["drive_type"], axis["safety_variant"], axis["i950_variant"])
    labels = [descriptor_label(d) for d in descriptors]
    by_id = {d["device_id"]: descriptor_label(d) for d in descriptors}
    label = by_id.get(axis.get("device_id")) or (
        axis.get("descriptor_label") if axis.get("descriptor_label") in labels else (labels[0] if labels else t("no_desc"))
    )
    s[f"desc_{index}"] = label
    s[f"alias_{index}"] = int(axis["station_alias"])
    s[f"alias2_{index}"] = int(axis["second_station_alias"])
    s[f"c86_{index}"] = axis["motor_code_c86"]
    s[f"kin_{index}"] = axis["kinematics"]
    s[f"kp_{index}"] = format_decimal(axis["kinematic_parameter"])
    s[f"trav_{index}"] = axis["traversing_range"]
    for z in ("z1", "z2", "z3", "z4"):
        s[f"{z}_{index}"] = int(axis[z])
    s[f"feed_{index}"] = format_decimal(axis["feed_constant"])
    s[f"cycle_{index}"] = format_decimal(axis["cycle_length"])
    return axis


def apply_axes(axes):
    """Sustituye todos los ejes y sus controles."""
    clear_widget_state(AXIS_WIDGET_PREFIXES)
    st.session_state.axes = [seed_axis_widgets(i, a) for i, a in enumerate(axes)]
    st.session_state.axis_count = max(1, len(st.session_state.axes))


def new_axis(index):
    return asdict(AxisConfig(name=f"Axis_{index:02d}", station_alias=1000 + index,
                             second_station_alias=2000 + index))


def request_feed_update(index):
    try:
        value = calculate_feed_constant(st.session_state[f"kin_{index}"], st.session_state[f"kp_{index}"])
        st.session_state[f"feed_{index}"] = format_decimal(value)
    except Exception as error:
        st.session_state["feed_error"] = str(error)


# ============================================================ asistente

from ai_assistant import interpret as ai_interpret, transcribe_audio as ai_transcribe_audio


def render_machine_assistant():
    st.session_state.setdefault("assistant_messages", [])
    st.session_state.setdefault("assistant_proposal", None)
    st.session_state.setdefault("last_audio_id", None)

    with st.expander("💬 " + t("assistant"), expanded=False):
        st.caption(t("assistant_help"))
        for message in st.session_state.assistant_messages[-8:]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        prompt = st.chat_input(t("assistant_hint"), key="machine_assistant_chat")

        engine = st.radio(
            t("engine"), options=("local", "openai"),
            format_func=lambda v: t("engine_local") if v == "local" else "OpenAI API",
            horizontal=True, key="transcription_engine", help=t("engine_help"),
        )
        if engine == "local":
            st.caption(t("engine_first"))
        audio = st.audio_input(t("dictate"), key="machine_assistant_audio")
        if audio is not None:
            audio_bytes = audio.getvalue()
            # Por contenido y no por tamaño: dos grabaciones distintas pueden medir lo mismo.
            import hashlib
            audio_id = engine + ":" + hashlib.sha1(audio_bytes).hexdigest()
            if audio_id != st.session_state.last_audio_id:
                st.session_state.last_audio_id = audio_id
                try:
                    with st.spinner(t("transcribing")):
                        prompt = ai_transcribe_audio(audio_bytes, getattr(audio, "name", "voice.wav"), engine=engine)
                    st.info(t("transcription") + prompt)
                except Exception as error:
                    st.error(str(error))

        if prompt:
            st.session_state.assistant_messages.append({"role": "user", "content": prompt})
            proposal = ai_interpret(prompt, st.session_state.axes, {"cpu_model": st.session_state.get("cpu_model")})
            st.session_state.assistant_proposal = proposal
            response = t("proposal_ready") + "\n\n" + proposal.get("summary", "")
            st.session_state.assistant_messages.append({"role": "assistant", "content": response})
            st.rerun()

        proposal = st.session_state.assistant_proposal
        if not proposal:
            return
        if proposal.get("openai_error"):
            st.warning(t("openai_fallback").format(proposal["openai_error"]))
        for warning in proposal.get("warnings", []):
            if "OpenAI" not in warning:
                st.warning(warning)
        st.markdown("#### " + t("preview"))
        # Todo como texto: una columna con números y textos mezclados no se puede pintar.
        preview = [{
            t("col_axis"): str(a.get("name", "")), "Drive": str(a.get("drive_type", "")),
            "Safety": str(a.get("safety_variant", "")), "Kinematics": str(a.get("kinematics", "")),
            t("col_param"): format_decimal(a.get("kinematic_parameter", "")),
            "Feed Constant": format_decimal(a.get("feed_constant", "")),
            "Z1:Z2 / Z3:Z4": f"{a.get('z1')}:{a.get('z2')} / {a.get('z3')}:{a.get('z4')}",
            "Alias": str(a.get("station_alias", "")),
        } for a in proposal.get("axes", [])]
        st.dataframe(preview, width="stretch", hide_index=True)
        apply_col, discard_col = st.columns(2)
        if apply_col.button(t("apply_proposal"), width="stretch", type="primary"):
            apply_axes(proposal.get("axes", []))
            if proposal.get("cpu_model") in CPU_MODELS:
                st.session_state["cpu_model"] = proposal["cpu_model"]
            st.session_state.assistant_proposal = None
            st.session_state.assistant_messages.append({"role": "assistant", "content": t("applied")})
            st.rerun()
        if discard_col.button(t("discard"), width="stretch"):
            st.session_state.assistant_proposal = None
            st.rerun()


# ============================================================ inicio

init_auth_state()
if not st.session_state.authenticated:
    login_view()
    st.stop()

header()


@st.cache_data
def repo_data():
    return load_repository(Path(__file__).parent / "device_repository.json")


REPO = repo_data()

if "axes" not in st.session_state:
    apply_axes([new_axis(i) for i in range(1, 3)])
st.session_state.setdefault("robot_groups", [])
st.session_state.setdefault("cpu_model", "c550")
st.session_state.setdefault("project_path", r"C:\Temp\LenzeMachine_Auto.project")
st.session_state.setdefault("ethercat_identification", "NONE")

# Una configuracion cargada se aplica al principio del rerun, antes de crear controles.
loaded = st.session_state.pop("pending_loaded_configuration", None)
if loaded is not None:
    apply_axes(loaded.get("axes") or [new_axis(1)])
    clear_widget_state(GROUP_WIDGET_PREFIXES)
    st.session_state.robot_groups = [g for g in loaded.get("robot_groups", []) if isinstance(g, dict)]
    st.session_state.robot_group_count = len(st.session_state.robot_groups)
    if loaded.get("cpu_model") in CPU_MODELS:
        st.session_state["cpu_model"] = loaded["cpu_model"]
    if loaded.get("project_path"):
        st.session_state["project_path"] = str(loaded["project_path"])
    if loaded.get("ethercat_identification") in IDENTIFICATION_MODES:
        st.session_state["ethercat_identification"] = loaded["ethercat_identification"]
    st.session_state["loaded_cpu_device_id"] = loaded.get("cpu_device_id", "")
    st.session_state["loaded_master_device_id"] = loaded.get("ethercat_master_device_id", "")
    st.session_state["configuration_load_message"] = True

render_machine_assistant()

if st.session_state.pop("configuration_load_message", None):
    st.success(t("loaded"))


def select_by_device_id(label_key, values, device_id_key):
    """Deja elegido en un desplegable el descriptor que traia el JSON cargado."""
    wanted = st.session_state.pop(device_id_key, "")
    if wanted:
        for item in values:
            if item.get("device_id") == wanted:
                st.session_state[label_key] = descriptor_label(item)


def keep_valid(key, options):
    """Si el valor guardado ya no esta entre las opciones, se pasa a la primera."""
    if st.session_state.get(key) not in options:
        st.session_state[key] = options[0]


def normalize_decimal_field(key):
    """Al salir de un campo decimal: coma o punto, y el numero bien escrito."""
    value = st.session_state.get(key, "")
    try:
        st.session_state[key] = format_decimal(normalize_number(value))
    except Exception:
        pass


def axis_label(i):
    name = st.session_state.get(f"name_{i}", "")
    kin = st.session_state.get(f"kin_{i}", "")
    drive = st.session_state.get(f"drv_{i}", "")
    return f"{i + 1} · {name} — {drive} · {kin}"


# La barra de resumen va arriba, pero se rellena al final, cuando ya se sabe si la
# configuracion es valida.
summary = st.container()

tab_ctrl, tab_axes, tab_groups, tab_gen = st.tabs(
    ["⚙️ " + t("tab_ctrl"), "🔧 " + t("axes"), "🤖 " + t("groups"), "💾 " + t("gen")]
)

# ------------------------------------------------------------ controlador
with tab_ctrl:
    col1, col2 = st.columns(2)
    cpu = col1.selectbox(t("cpu"), CPU_MODELS, key="cpu_model")
    cpu_values = cpu_options(REPO, cpu)
    cpu_labels = [descriptor_label(item) for item in cpu_values] or [t("no_desc")]
    select_by_device_id("cpu_desc", cpu_values, "loaded_cpu_device_id")
    keep_valid("cpu_desc", cpu_labels)
    cpu_label = col2.selectbox(t("cpu_desc"), cpu_labels, key="cpu_desc")
    cpu_selected = cpu_values[cpu_labels.index(cpu_label)] if cpu_values else {}

    col1, col2 = st.columns(2)
    master_values = master_options(REPO)
    master_labels = [descriptor_label(item) for item in master_values] or [t("no_desc")]
    select_by_device_id("master_desc", master_values, "loaded_master_device_id")
    keep_valid("master_desc", master_labels)
    master_label = col1.selectbox(t("master"), master_labels, key="master_desc")
    master_selected = master_values[master_labels.index(master_label)] if master_values else {}
    identification = col2.selectbox(
        t("ident"), list(IDENTIFICATION_MODES), key="ethercat_identification",
        format_func=lambda mode: t("ident_" + mode), help=t("ident_help"),
    )
    if identification != "NONE":
        st.warning(t("ident_help"))

    project_path = st.text_input(t("path"), key="project_path", help=t("path_help"))

# ------------------------------------------------------------ ejes
with tab_axes:
    st.session_state.setdefault("axis_count", len(st.session_state.axes))
    axis_count = st.number_input(t("axes_n"), 1, 32, step=1, key="axis_count")
    while len(st.session_state.axes) < axis_count:
        index = len(st.session_state.axes)
        st.session_state.axes.append(seed_axis_widgets(index, new_axis(index + 1)))
    st.session_state.axes = st.session_state.axes[:axis_count]

    overview = st.container()

    for i, axis in enumerate(st.session_state.axes):
        if f"name_{i}" not in st.session_state:
            seed_axis_widgets(i, axis)
        box = st.expander(axis_label(i), expanded=(i == 0))
        with box:
            col1, col2, col3, col4 = st.columns(4)
            axis["enabled"] = col1.checkbox(t("active"), key=f"en_{i}")
            axis["name"] = col2.text_input(t("name"), key=f"name_{i}", help=t("name_help"))
            axis["drive_type"] = col3.selectbox(t("drive"), DRIVES, key=f"drv_{i}")
            safety_options = SAFETY if axis["drive_type"] in ("i750", "i950") else ["Basic Safety"]
            keep_valid(f"safe_{i}", safety_options)
            axis["safety_variant"] = col4.selectbox(t("safety"), safety_options, key=f"safe_{i}")

            col1, col2 = st.columns([1, 3])
            if axis["drive_type"] == "i950":
                keep_valid(f"i950_{i}", I950_VARIANTS)
                axis["i950_variant"] = col1.selectbox(t("i950"), I950_VARIANTS, key=f"i950_{i}")
            else:
                axis["i950_variant"] = "Normal"
                col1.text_input(t("i950"), "—", disabled=True, key=f"i950_off_{i}")
            descriptors = drive_options(REPO, axis["drive_type"], axis["safety_variant"], axis["i950_variant"])
            labels = [descriptor_label(item) for item in descriptors] or [t("no_desc")]
            keep_valid(f"desc_{i}", labels)
            label = col2.selectbox(t("desc"), labels, key=f"desc_{i}")
            selected = descriptors[labels.index(label)] if descriptors else {}
            axis["descriptor_label"] = label
            axis["device_id"] = selected.get("device_id", "")

            st.markdown(f"**{t('sec_mech')}**")
            col1, col2, col3 = st.columns(3)
            axis["kinematics"] = col1.selectbox(t("kinematics"), KINEMATICS, key=f"kin_{i}")
            axis["kinematic_parameter"] = col2.text_input(
                t("kin_param"), key=f"kp_{i}", help=t("kin_help"),
                on_change=normalize_decimal_field, args=(f"kp_{i}",))
            axis["traversing_range"] = col3.selectbox(
                t("traversing"), TRAVERSING, key=f"trav_{i}",
                format_func=lambda v: t("trav_" + v))

            col1, col2, col3 = st.columns(3, vertical_alignment="bottom")
            axis["feed_constant"] = col1.text_input(
                t("feed"), key=f"feed_{i}", help=t("feed_help"),
                on_change=normalize_decimal_field, args=(f"feed_{i}",))
            col2.button("🧮 " + t("calc"), key=f"calculate_feed_{i}", width="stretch",
                        on_click=request_feed_update, args=(i,))
            if axis["traversing_range"] == "MODULO":
                axis["cycle_length"] = col3.text_input(
                    t("cycle"), key=f"cycle_{i}", on_change=normalize_decimal_field, args=(f"cycle_{i}",))
            else:
                axis["cycle_length"] = st.session_state.get(f"cycle_{i}", "0")
                col3.text_input(t("cycle"), "—", disabled=True, key=f"cycle_off_{i}")

            st.markdown(f"**{t('sec_gear')}**")
            gear = st.columns(4)
            for column, z_name, hint in zip(gear, ("z1", "z2", "z3", "z4"),
                                            ("gear_den", "gear_num", "add_den", "add_num")):
                axis[z_name] = column.number_input(z_name.upper(), 1, 1000000, step=1,
                                                   key=f"{z_name}_{i}", help=t(hint))

            st.markdown(f"**{t('sec_bus')}**")
            col1, col2, col3 = st.columns(3)
            axis["station_alias"] = col1.number_input("Alias", 0, 65535, key=f"alias_{i}")
            axis["second_station_alias"] = col2.number_input(t("alias2"), 0, 65535, key=f"alias2_{i}",
                                                             help=t("alias2_help"))
            axis["motor_code_c86"] = col3.text_input("C86", key=f"c86_{i}")
            errors_here = st.container()
            axis["_errors_box"] = errors_here

    if st.session_state.get("feed_error"):
        st.error(st.session_state.pop("feed_error"))

# ------------------------------------------------------------ grupos
with tab_groups:
    st.caption(t("groups_help"))
    st.session_state.setdefault("robot_group_count", len(st.session_state.robot_groups))
    group_count = st.number_input(t("groups_n"), min_value=0, max_value=16, step=1, key="robot_group_count")
    while len(st.session_state.robot_groups) < group_count:
        st.session_state.robot_groups.append({
            "name": f"RobotGroup_{len(st.session_state.robot_groups) + 1:02}",
            "type": "CARTESIAN_3D",
            "axes": {},
        })
    st.session_state.robot_groups = st.session_state.robot_groups[:group_count]

    axis_names = [a["name"] for a in st.session_state.axes if a.get("enabled", True)]
    robot_types = list(ROBOT_TYPES.keys())

    for group_index, group in enumerate(st.session_state.robot_groups):
        with st.expander(f"{group_index + 1} · {group.get('name', '')}", expanded=(group_index == 0)):
            col1, col2 = st.columns(2)
            name_key = f"group_name_{group_index}"
            st.session_state.setdefault(name_key, group.get("name", f"RobotGroup_{group_index + 1:02}"))
            group["name"] = col1.text_input(t("group_name"), key=name_key)
            type_key = f"group_type_{group_index}"
            st.session_state.setdefault(type_key, group.get("type", "CARTESIAN_3D"))
            keep_valid(type_key, robot_types)
            group["type"] = col2.selectbox(t("group_type"), robot_types, key=type_key,
                                           format_func=lambda k: t("robot_" + k))
            roles = ROBOT_TYPES[group["type"]]
            mapping = {}
            if axis_names:
                columns = st.columns(len(roles))
                for role_index, role in enumerate(roles):
                    role_key = f"group_{group_index}_{role}"
                    st.session_state.setdefault(role_key, group.get("axes", {}).get(role, axis_names[0]))
                    keep_valid(role_key, axis_names)
                    mapping[role] = columns[role_index].selectbox(
                        f"A{role_index + 1} · {role}", axis_names, key=role_key)
            group["axes"] = mapping
            if len(mapping.values()) != len(set(mapping.values())):
                st.error(t("group_dup"))

# ------------------------------------------------------------ configuracion y validacion
axes_clean = [{k: v for k, v in a.items() if not k.startswith("_")} for a in st.session_state.axes]
configuration = {
    "format": "LenzeMachineBuilderWeb",
    "format_version": 3,
    "cpu_model": cpu,
    "cpu_version": cpu_selected.get("version", ""),
    "cpu_device_id": cpu_selected.get("device_id", ""),
    "ethercat_master_label": master_label,
    "ethercat_master_version": master_selected.get("version", ""),
    "ethercat_master_device_id": master_selected.get("device_id", ""),
    "project_path": project_path,
    "ethercat_identification": identification,
    "axes": axes_clean,
    "robot_groups": st.session_state.robot_groups,
}

validation_errors = validate_config(configuration)
generated_script = None if validation_errors else generate_plc_script(configuration)

# Los errores de cada eje, dentro de su desplegable.
for axis in st.session_state.axes:
    box = axis.pop("_errors_box", None)
    mine = [e for e in validation_errors if e.startswith(str(axis.get("name")) + ":")]
    if box is not None:
        for error in mine:
            box.error(error)

with overview:
    rows = []
    for a in axes_clean:
        bad = any(e.startswith(str(a.get("name")) + ":") for e in validation_errors)
        rows.append({
            "": "⚠️" if bad else ("✅" if a.get("enabled") else "⏸️"),
            t("name"): a.get("name"),
            t("drive"): a.get("drive_type"),
            t("kinematics"): a.get("kinematics"),
            t("traversing"): t("trav_" + str(a.get("traversing_range"))),
            t("feed"): format_decimal(a.get("feed_constant")),
            "Z1:Z2": f"{a.get('z1')}:{a.get('z2')}",
            "Z3:Z4": f"{a.get('z3')}:{a.get('z4')}",
            "Alias": str(a.get("station_alias")),
        })
    st.dataframe(rows, width="stretch", hide_index=True)

with summary:
    active = sum(1 for a in axes_clean if a.get("enabled"))
    cols = st.columns(5)
    cols[0].metric(f'{t("cpu")} · {cpu_selected.get("version", "—")}', cpu)
    cols[1].metric("EtherCAT", master_selected.get("version", "—"))
    cols[2].metric(t("axes"), f"{active} / {len(axes_clean)}")
    cols[3].metric(t("groups"), str(len(st.session_state.robot_groups)))
    cols[4].metric(t("status"), "✅ " + t("ready") if not validation_errors
                   else "⚠️ " + t("n_errors").format(len(validation_errors)))

# ------------------------------------------------------------ generar
with tab_gen:
    if validation_errors:
        st.error(t("fix_first"))
        for validation_error in validation_errors:
            st.markdown("- " + validation_error)
    else:
        st.success(t("ready_long"))

    load_col, save_col, script_col = st.columns(3, vertical_alignment="bottom")
    with load_col:
        uploaded_configuration = st.file_uploader(t("load"), type=["json"], key="bottom_configuration_uploader")
        if st.button(t("apply"), key="bottom_apply_configuration", width="stretch",
                     disabled=uploaded_configuration is None):
            try:
                loaded_configuration = json.load(uploaded_configuration)
                if not isinstance(loaded_configuration, dict):
                    raise ValueError("JSON")
                st.session_state["pending_loaded_configuration"] = loaded_configuration
                st.rerun()
            except Exception as error:
                st.error(t("load_error") + str(error))

    project_stem = Path(str(project_path).replace("\\", "/")).stem or "machine"
    with save_col:
        st.download_button("💾 " + t("save_json"), config_json(configuration),
                           f"{project_stem}_configuration.json", "application/json", width="stretch")
    with script_col:
        if generated_script is not None:
            st.download_button("⬇️ " + t("download"), generated_script, f"Create_{project_stem}.py",
                               "text/x-python", width="stretch", type="primary")
        else:
            st.button("⬇️ " + t("download"), width="stretch", disabled=True, help=t("download_help"))

    if generated_script is not None:
        st.caption(t("how_to_run"))
        with st.expander(t("preview_script")):
            st.code(generated_script, language="python")
