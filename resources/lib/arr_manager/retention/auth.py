# SPDX-License-Identifier: GPL-3.0-or-later
import hashlib


def pin_generation(settings):
    if getattr(settings, "pin_invalid", False):
        return "invalid"
    if not getattr(settings, "pin_enabled", False):
        return "none"
    digest = hashlib.sha256()
    digest.update(getattr(settings, "pin_hash", b""))
    digest.update(getattr(settings, "pin_salt", b""))
    return digest.hexdigest()
