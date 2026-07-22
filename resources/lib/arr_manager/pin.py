# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib
import hmac
import os

from .messages import message


def _m(source, key, **values):
    return message(source, key, **values)

def hash_pin(pin: str, salt: bytes = None) -> (bytes, bytes):
    if not salt:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac(
        'sha256',
        pin.encode('utf-8'),
        salt,
        100000
    )
    return key, salt

def verify_pin(pin: str, stored_hash: bytes, salt: bytes) -> bool:
    new_hash, _ = hash_pin(pin, salt)
    return hmac.compare_digest(stored_hash, new_hash)

def authorize_action(action_id: str, settings, ui) -> bool:
    from .registry import get_action_by_id, get_action_by_mode
    action = get_action_by_id(action_id) or get_action_by_mode(action_id)
    if not action or not action.get("destructive"):
        return True

    if not settings.pin_enabled:
        return True

    for attempt in range(3):
        pin = ui.numeric_input(_m(settings.addon, "pin_prompt", fallback="Enter PIN for destructive action"))
        if not pin:
            return False # Cancelled
        if verify_pin(pin, settings.pin_hash, settings.pin_salt):
            return True
        ui.notification(_m(settings.addon, "pin_incorrect", fallback="Incorrect PIN"))

    return False
