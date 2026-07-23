# SPDX-License-Identifier: GPL-3.0-or-later
import ast
import json
import re

from .interactive_messages import INTERACTIVE_MESSAGES
from .messages import MESSAGES

_CONTEXT_RE = re.compile(r'^msgctxt "#([0-9]+)"$', re.M)


def _quoted(value):
    return json.dumps(str(value), ensure_ascii=False)


def _po_value(block, keyword):
    lines = block.splitlines()
    for index, line in enumerate(lines):
        prefix = keyword + " "
        if not line.startswith(prefix):
            continue
        values = [line[len(prefix):].strip()]
        for continuation in lines[index + 1:]:
            continuation = continuation.strip()
            if not continuation.startswith('"'):
                break
            values.append(continuation)
        try:
            return "".join(ast.literal_eval(value) for value in values)
        except (SyntaxError, ValueError) as exc:
            raise ValueError(f"Invalid PO {keyword} value") from exc
    return None


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


def _source_catalog(text):
    output = {}
    for block in re.split(r"\n[ \t]*\n", text):
        contexts = _CONTEXT_RE.findall(block)
        if not contexts:
            continue
        if len(contexts) != 1:
            raise ValueError(f"One PO block contains multiple IDs: {contexts}")
        string_id = int(contexts[0])
        if string_id in output:
            raise ValueError(f"Duplicate language string ID: {string_id}")
        msgid = _po_value(block, "msgid")
        if msgid is None:
            raise ValueError(f"Language string {string_id} has no msgid")
        output[string_id] = msgid
    return output


def render_strings_po(source_text):
    text = str(source_text or "").replace("\r\n", "\n").replace("\r", "\n").rstrip() + "\n"
    existing = _source_catalog(text)
    additions = []
    for string_id, (key, fallback) in sorted(runtime_catalog().items()):
        if string_id in existing:
            if existing[string_id] != fallback:
                raise ValueError(
                    f"Localisation ID {string_id} source text conflicts with {key}: "
                    f"{existing[string_id]!r} != {fallback!r}"
                )
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
