# SPDX-License-Identifier: GPL-3.0-or-later
"""Fail-closed normalisation for persisted replacement transaction evidence."""


def normalise_transaction_candidate(candidate):
    """Return independently normalised non-secret fields without dropping the record."""
    if not isinstance(candidate, dict):
        return candidate
    output = dict(candidate)
    stages = candidate.get("stages")
    output["stages"] = [value for value in stages if isinstance(value, str)][:20] if isinstance(stages, list) else []

    command_id = candidate.get("commandId")
    if isinstance(command_id, bool):
        output["commandId"] = 0
    elif isinstance(command_id, int):
        output["commandId"] = command_id if command_id > 0 else 0
    elif isinstance(command_id, str) and command_id.strip().isdigit():
        parsed = int(command_id.strip())
        output["commandId"] = parsed if parsed > 0 else 0
    else:
        output["commandId"] = 0
    return output


def install(entrypoints_module):
    """Wrap the diagnostics reader before ``run_script`` can dispatch diagnostics."""
    if getattr(entrypoints_module, "_transaction_normalisation_installed", False):
        return
    original = entrypoints_module._write_diagnostics

    def hardened_write_diagnostics(addon, settings, logger):
        original_load = entrypoints_module.json.load

        def safe_load(handle):
            return normalise_transaction_candidate(original_load(handle))

        entrypoints_module.json.load = safe_load
        try:
            return original(addon, settings, logger)
        finally:
            entrypoints_module.json.load = original_load

    entrypoints_module._write_diagnostics = hardened_write_diagnostics
    entrypoints_module._transaction_normalisation_installed = True
