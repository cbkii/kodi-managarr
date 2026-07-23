# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import json
import re

from .interactive_messages import INTERACTIVE_MESSAGES
from .messages import MESSAGES

_CONTEXT_RE = re.compile(r'^msgctxt "#([0-9]+)"$', re.M)


def _quoted(value):
    return json.dumps(str(value), ensure_ascii=False)


def runtime_catalog():
    combined = {}
    for source_name, catalog in (("messages", MESSAGES), ("interactive_messages", INTERACTIVE_MESSAGES)):
        for key, value in catalog.items():
            if not isinstance(value, tuple) or len(value) != 2:
                raise ValueError(f"{source_name}.{key} must define (numeric_id, fallback)")
            string_id, fallback = value
            string_id = int(string_id)
            if string_id < 30000 or not str(fallback):
                raise ValueError(f"{source_name}.{key} has invalid localisation metadata")
            existing = combined.get(string_id)
            if existing and existing[1] != str(fallback):
                raise ValueError(
                    f"Localisation ID {string_id} is assigned to incompatible fallbacks: "
                    f"{existing[0]} and {source_name}.{key}"
                )
            combined[string_id] = (f"{source_name}.{key}", str(fallback))
    return combined


def render_strings_po(source_text):
    text = str(source_text or "").replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"
    existing_ids = [int(value) for value in _CONTEXT_RE.findall(text)]
    duplicates = sorted({value for value in existing_ids if existing_ids.count(value) > 1})
    if duplicates:
        raise ValueError(f"Duplicate language string IDs: {duplicates}")
    existing = set(existing_ids)
    additions = []
    for string_id, (key, fallback) in sorted(runtime_catalog().items()):
        if string_id in existing:
            continue
        additions.extend([
            "",
            f"#. generated from {key}",
            f'msgctxt "#{string_id}"',
            f"msgid {_quoted(fallback)}",
            f"msgstr {_quoted(fallback)}",
        ])
    if additions:
        text = text.rstrip() + "\n" + "\n".join(additions) + "\n"
    return text


def po_value(line):
    try:
        return ast.literal_eval(line)
    except (SyntaxError, ValueError) as exc:
        raise ValueError("Invalid PO quoted value") from exc
