# -*- coding: utf-8 -*-
"""Usuarios y sesion de Machine Builder.

Los usuarios vienen SIEMPRE de la variable de entorno MB_USERS_JSON; en el codigo
no hay ninguno. Formato:

    {"persona@empresa.com": {"password": "pbkdf2_sha256$...", "role": "admin",
                             "name": "Nombre Apellido"}}

La contrasena va con hash. Para generarlo:

    python auth.py hash            (la pide sin mostrarla)

Una contrasena en claro todavia se acepta, para no dejar fuera a nadie al migrar,
pero la aplicacion avisa de que hay que cambiarla por su hash.
"""

import base64
import getpass
import hashlib
import hmac
import json
import os
import secrets
import sys
import time

_HASH_PREFIX = "pbkdf2_sha256"
_HASH_ITERATIONS = 390000

# Intentos fallidos seguidos antes de hacer esperar, y cuanto.
_MAX_ATTEMPTS = 5
_LOCK_SECONDS = 60

# Cambios de contrasena hechos desde la aplicacion. Viven en memoria: se pierden al
# reiniciar el servicio, y la aplicacion lo dice (hay que actualizar MB_USERS_JSON).
_RUNTIME_PASSWORDS = {}


# ------------------------------------------------------------------ hashes

def hash_password(password, iterations=_HASH_ITERATIONS):
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"), salt, iterations)
    return "{0}${1}${2}${3}".format(
        _HASH_PREFIX, iterations,
        base64.b64encode(salt).decode("ascii"),
        base64.b64encode(digest).decode("ascii"))


def is_hashed(stored):
    return str(stored).startswith(_HASH_PREFIX + "$")


def verify_password(password, stored):
    stored = str(stored or "")
    if not stored:
        return False
    if not is_hashed(stored):
        # Contrasena en claro (heredada): se compara sin filtrar tiempos.
        return hmac.compare_digest(str(password).encode("utf-8"), stored.encode("utf-8"))
    try:
        _, iterations, salt, digest = stored.split("$", 3)
        expected = base64.b64decode(digest)
        actual = hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"),
                                     base64.b64decode(salt), int(iterations))
    except Exception:
        return False
    return hmac.compare_digest(actual, expected)


# ------------------------------------------------------------------ usuarios

def load_users():
    """import os
    print("DEBUG MB_USERS_JSON =", os.getenv("MB_USERS_JSON"))"""
    """Devuelve (usuarios, problema). Sin MB_USERS_JSON no hay usuarios."""
    raw = os.getenv("MB_USERS_JSON", "").strip()
    if not raw:
        return {}, "MB_USERS_JSON no está configurada: no hay ningún usuario."
    try:
        data = json.loads(raw)
    except ValueError as error:
        return {}, "MB_USERS_JSON no es un JSON válido: " + str(error)
    if not isinstance(data, dict):
        return {}, "MB_USERS_JSON debe ser un objeto {correo: {...}}."
    users = {}
    for email, profile in data.items():
        if not isinstance(profile, dict):
            continue
        key = str(email).strip().lower()
        users[key] = {
            "password": str(profile.get("password", "")),
            "role": str(profile.get("role", "user")),
            "name": str(profile.get("name", email)),
        }
    return users, ""


def plaintext_users(users=None):
    """Correos cuya contrasena sigue en claro en MB_USERS_JSON."""
    if users is None:
        users, _ = load_users()
    return sorted(k for k, v in users.items() if v.get("password") and not is_hashed(v["password"]))


def _stored_password(key, profile):
    return _RUNTIME_PASSWORDS.get(key, profile.get("password", ""))


# ------------------------------------------------------------------ sesion

def _st():
    import streamlit as st
    return st


def init_auth_state():
    st = _st()
    defaults = {"authenticated": False, "user_email": "", "user_role": "", "user_name": "",
                "language": "ES", "login_failures": 0, "login_locked_until": 0.0}
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def login_wait_seconds():
    """Segundos que faltan para poder volver a intentarlo (0 si ya se puede)."""
    st = _st()
    return max(0, int(st.session_state.get("login_locked_until", 0.0) - time.time() + 0.999))


def authenticate(email, password):
    """Devuelve (correcto, problema). problema explica por que no se entra."""
    st = _st()
    wait = login_wait_seconds()
    if wait > 0:
        return False, "locked"
    users, problem = load_users()
    if problem:
        return False, problem
    key = str(email).strip().lower()
    profile = users.get(key)
    # Se verifica aunque el usuario no exista, para no delatar por el tiempo de
    # respuesta que correos estan dados de alta.
    stored = _stored_password(key, profile) if profile else hash_password("x", 1000)
    if not profile or not verify_password(password, stored):
        st.session_state.login_failures = st.session_state.get("login_failures", 0) + 1
        if st.session_state.login_failures >= _MAX_ATTEMPTS:
            st.session_state.login_locked_until = time.time() + _LOCK_SECONDS
            st.session_state.login_failures = 0
        return False, ""
    st.session_state.login_failures = 0
    st.session_state.authenticated = True
    st.session_state.user_email = key
    st.session_state.user_role = profile.get("role", "user")
    st.session_state.user_name = profile.get("name", key)
    return True, ""


def logout():
    st = _st()
    st.session_state.authenticated = False
    for key in ("user_email", "user_role", "user_name"):
        st.session_state[key] = ""
    st.rerun()


def change_password(email, current, new):
    users, _ = load_users()
    key = str(email).strip().lower()
    profile = users.get(key, {})
    if not verify_password(current, _stored_password(key, profile)):
        return False, "La contraseña actual no es correcta.", ""
    if len(str(new)) < 8:
        return False, "La nueva contraseña debe tener al menos 8 caracteres.", ""
    if str(new) == str(current):
        return False, "La nueva contraseña debe ser diferente.", ""
    new_hash = hash_password(new)
    _RUNTIME_PASSWORDS[key] = new_hash
    # Se devuelve el hash para que el administrador pueda copiarlo a MB_USERS_JSON.
    return True, "Contraseña modificada correctamente.", new_hash


# ------------------------------------------------------------------ linea de ordenes

if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "hash":
        first = getpass.getpass("Contraseña: ")
        second = getpass.getpass("Repítela: ")
        if first != second:
            print("No coinciden.")
            sys.exit(1)
        print(hash_password(first))
    else:
        print("Uso: python auth.py hash")
