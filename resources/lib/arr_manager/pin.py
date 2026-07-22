# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import hmac
import os

from .messages import message

PIN_MIN_LENGTH = 4
PIN_MAX_LENGTH = 8
PBKDF2_ITERATIONS = 100000


def _m(source, key, **values):
    return message(source, key, **values)


def validate_pin(pin):
    value = str(pin or "")
    if not value.isdigit() or not PIN_MIN_LENGTH <= len(value) <= PIN_MAX_LENGTH:
        raise ValueError("PIN must contain 4 to 8 digits")
    return value


def hash_pin(pin, salt=None):
    pin = validate_pin(pin)
    salt = salt or os.urandom(16)
    if not isinstance(salt, bytes) or len(salt) != 16:
        raise ValueError("PIN salt is invalid")
    key = hashlib.pbkdf2_hmac(
        "sha256",
        pin.encode("utf-8"),
        salt,
        PBKDF2_ITERATIONS,
    )
    return key, salt


def verify_pin(pin, stored_hash, salt):
    try:
        pin = validate_pin(pin)
        if not isinstance(stored_hash, bytes) or len(stored_hash) != 32:
            return False
        if not isinstance(salt, bytes) or len(salt) != 16:
            return False
        new_hash, _ = hash_pin(pin, salt)
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(stored_hash, new_hash)


def authorize_action(action_id, settings, ui):
    from .registry import get_action_by_id, get_action_by_mode

    action = get_action_by_id(action_id) or get_action_by_mode(action_id)
    if not action or not action.get("destructive"):
        return True
    if getattr(settings, "pin_invalid", False):
        ui.notification(_m(settings.addon, "pin_configuration_invalid"), error=True)
        return False
    if not settings.pin_enabled:
        return True

    for _attempt in range(3):
        pin = ui.numeric_input(_m(settings.addon, "pin_prompt"))
        if not pin:
            return False
        if verify_pin(pin, settings.pin_hash, settings.pin_salt):
            return True
        ui.notification(_m(settings.addon, "pin_incorrect"), error=True)
    ui.notification(_m(settings.addon, "pin_retry_exhausted"), error=True)
    return False
