# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Read and write the metadata block at the top of an issue file.

Two styles are understood, because those are the two a hand-kept tracker
tends to grow:

* ``front-matter`` — a ``---`` fenced block of ``key: value`` lines (the YAML
  subset people actually write: scalars, ``[a, b]`` inline lists, ``- item``
  block lists).
* ``bold-fields`` — ``**Key:** value`` lines at the top of the file, before
  the first heading.

Key order and unknown keys survive a round trip, so rewriting one value never
reshuffles a file a human maintains.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

Value = str | list[str] | None

_BOLD_RE = re.compile(r"^\*\*(?P<key>[^*:]+?):?\*\*:?\s*(?P<value>.*)$")
_KEY_RE = re.compile(r"^(?P<key>[A-Za-z][\w .-]*?)\s*:\s*(?P<value>.*)$")


@dataclass
class Metadata:
    """Ordered metadata with the style it was read in."""

    style: str = "front-matter"
    values: dict[str, Value] = field(default_factory=dict)
    list_style: str = "inline"

    def find_key(self, candidates: list[str]) -> str | None:
        """Return the stored key matching any candidate, case-insensitively."""
        lowered = {k.lower(): k for k in self.values}
        for cand in candidates:
            if cand.lower() in lowered:
                return lowered[cand.lower()]
        return None


def _unquote(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        inner = raw[1:-1]
        return inner.replace('\\"', '"') if raw[0] == '"' else inner.replace("''", "'")
    return raw


def _split_inline_list(raw: str) -> list[str]:
    inner = raw.strip()[1:-1]
    items: list[str] = []
    buf = ""
    quote = ""
    for ch in inner:
        if quote:
            buf += ch
            if ch == quote:
                quote = ""
        elif ch in "\"'":
            quote = ch
            buf += ch
        elif ch == ",":
            items.append(buf)
            buf = ""
        else:
            buf += ch
    if buf.strip():
        items.append(buf)
    return [_unquote(i) for i in items if i.strip()]


def _parse_scalar_or_list(raw: str) -> Value:
    raw = raw.strip()
    if raw.startswith("[") and raw.endswith("]"):
        return _split_inline_list(raw)
    if raw in ("", "~", "null"):
        return None
    return _unquote(raw)


def split(text: str) -> tuple[Metadata, str]:
    """Split ``text`` into its metadata and the remaining markdown body."""
    lines = text.splitlines(keepends=True)
    if lines and lines[0].strip() == "---":
        meta = Metadata(style="front-matter")
        current_list: str | None = None
        for idx in range(1, len(lines)):
            line = lines[idx].rstrip("\n").rstrip("\r")
            if line.strip() == "---":
                body = "".join(lines[idx + 1 :])
                return meta, body.lstrip("\n")
            if current_list and re.match(r"^\s*-\s+", line):
                item = re.sub(r"^\s*-\s+", "", line)
                existing = meta.values.get(current_list)
                if not isinstance(existing, list):
                    existing = []
                    meta.values[current_list] = existing
                existing.append(_unquote(item))
                meta.list_style = "block"
                continue
            m = _KEY_RE.match(line)
            if not m:
                continue
            key, value = m.group("key").strip(), m.group("value")
            if value.strip() == "":
                meta.values[key] = None
                current_list = key
            else:
                meta.values[key] = _parse_scalar_or_list(value)
                current_list = None
        # Unterminated front matter: treat the whole file as body.
        return Metadata(style="front-matter"), text

    meta = Metadata(style="bold-fields")
    title_line = ""
    consumed = 0
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if line == "":
            continue
        if line.startswith("# ") and not title_line and not meta.values:
            title_line = raw_line if raw_line.endswith("\n") else raw_line + "\n"
            consumed = idx + 1
            continue
        m = _BOLD_RE.match(line)
        if not m:
            break
        meta.values[m.group("key").strip()] = _parse_bold_value(
            m.group("key").strip(), m.group("value").strip()
        )
        consumed = idx + 1
    if not meta.values:
        return Metadata(style="none"), text
    rest = "".join(lines[consumed:]).lstrip("\n")
    return meta, (title_line + "\n" + rest) if title_line else rest


_LIST_KEYS = {"labels", "tags", "assignees", "assignee", "owners", "components"}


def _parse_bold_value(key: str, value: str) -> Value:
    if value in ("", "-", "n/a", "N/A", "_No response_"):
        return [] if key.lower() in _LIST_KEYS else None
    if key.lower() in _LIST_KEYS:
        return [v.strip().strip("`") for v in value.split(",") if v.strip()]
    return value


def _quote(value: str) -> str:
    if value == "" or re.search(r"[:#\[\]{},&*!|>'\"%@`]", value) or value != value.strip():
        return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return value


def render(meta: Metadata, body: str) -> str:
    """Render metadata back above ``body`` in the style it was read in."""
    if meta.style == "none" or not meta.values:
        return body
    if meta.style == "bold-fields":
        out = []
        for key, value in meta.values.items():
            text = ", ".join(value) if isinstance(value, list) else value or ""
            out.append(f"**{key}:** {text}".rstrip())
        # Keep a leading H1 above the bold block.
        if body.startswith("# "):
            first, _, rest = body.partition("\n")
            return first + "\n\n" + "\n".join(out) + "\n\n" + rest.lstrip("\n")
        return "\n".join(out) + "\n\n" + body
    out = ["---"]
    for key, value in meta.values.items():
        if isinstance(value, list):
            if meta.list_style == "block":
                out.append(f"{key}:")
                out.extend(f"  - {_quote(v)}" for v in value)
                if not value:
                    out[-1] = f"{key}: []"
            else:
                out.append(f"{key}: [" + ", ".join(_quote(v) for v in value) + "]")
        elif value is None:
            out.append(f"{key}:")
        else:
            out.append(f"{key}: {_quote(value)}")
    out.append("---")
    return "\n".join(out) + "\n\n" + body
