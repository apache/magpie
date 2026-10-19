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
    # Set when the front matter uses YAML this parser does not model (block
    # scalars, nested mappings, comments, …); rewriting it would lose data.
    unsupported: str = ""

    def find_key(self, candidates: list[str]) -> str | None:
        """Return the stored key matching any candidate, case-insensitively."""
        lowered = {k.lower(): k for k in self.values}
        for cand in candidates:
            if cand.lower() in lowered:
                return lowered[cand.lower()]
        return None


def _unescape_double(inner: str) -> str:
    """Undo exactly what `_quote` does: `\\\\` -> `\\`, `\\"` -> `"`; any other
    backslash is literal."""
    out: list[str] = []
    i = 0
    while i < len(inner):
        ch = inner[i]
        if ch == "\\" and i + 1 < len(inner) and inner[i + 1] in '\\"':
            out.append(inner[i + 1])
            i += 2
            continue
        out.append(ch)
        i += 1
    return "".join(out)


def _unquote(raw: str) -> str:
    raw = raw.strip()
    if len(raw) >= 2 and raw[0] == raw[-1] and raw[0] in "\"'":
        inner = raw[1:-1]
        return _unescape_double(inner) if raw[0] == '"' else inner.replace("''", "'")
    return raw


def _has_inline_comment(raw: str) -> bool:
    """A YAML ``# comment`` after a value.

    A quote only opens a quoted scalar when it *starts* the value (``Bob's
    report`` is a plain scalar); inside double quotes a backslash escapes the
    next character, inside single quotes ``''`` is a literal quote. After the
    scalar, a ``#`` preceded by whitespace starts a comment.
    """
    text = raw.strip()
    if text[:1] == "[":
        # A flow sequence: quotes open quoted items at item boundaries only.
        i, quote, at_item = 1, "", True
        while i < len(text):
            ch = text[i]
            if quote == '"':
                if ch == "\\":
                    i += 2
                    continue
                if ch == '"':
                    quote = ""
            elif quote == "'":
                if ch == "'":
                    if text[i + 1 : i + 2] == "'":
                        i += 2
                        continue
                    quote = ""
            elif at_item and ch in "\"'":
                quote, at_item = ch, False
            elif ch == ",":
                at_item = True
            elif ch == "]":
                break
            elif not ch.isspace():
                at_item = False
            i += 1
        rest = text[i + 1 :]
        return re.search(r"\s#", rest) is not None or rest.lstrip().startswith("#")
    if text[:1] == '"':
        i = 1
        while i < len(text):
            if text[i] == "\\":
                i += 2
                continue
            if text[i] == '"':
                break
            i += 1
        rest = text[i + 1 :]
    elif text[:1] == "'":
        i = 1
        while i < len(text):
            if text[i] == "'":
                if text[i + 1 : i + 2] == "'":
                    i += 2
                    continue
                break
            i += 1
        rest = text[i + 1 :]
    else:
        rest = " " + text
    return re.search(r"\s#", rest) is not None or rest.lstrip().startswith("#")


def _split_inline_list(raw: str) -> list[str]:
    """Items of a flow sequence, by the scalar rules `_has_inline_comment` uses:
    a quote opens a quoted item only at an item boundary (``[Bob's report,
    triaged]`` is two plain items), ``\\`` escapes inside double quotes, and
    ``''`` is a literal quote inside single quotes."""
    inner = raw.strip()[1:-1]
    items: list[str] = []
    buf = ""
    quote = ""
    at_item = True
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote == '"':
            buf += ch
            if ch == "\\" and i + 1 < len(inner):
                buf += inner[i + 1]
                i += 2
                continue
            if ch == '"':
                quote = ""
        elif quote == "'":
            buf += ch
            if ch == "'":
                if inner[i + 1 : i + 2] == "'":
                    buf += "'"
                    i += 2
                    continue
                quote = ""
        elif ch == ",":
            items.append(buf)
            buf, at_item = "", True
        elif at_item and ch in "\"'":
            quote, at_item = ch, False
            buf += ch
        else:
            if not ch.isspace():
                at_item = False
            buf += ch
        i += 1
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
                if _has_inline_comment(item):
                    meta.unsupported = meta.unsupported or "comments"
                existing = meta.values.get(current_list)
                if not isinstance(existing, list):
                    existing = []
                    meta.values[current_list] = existing
                existing.append(_unquote(item))
                meta.list_style = "block"
                continue
            if line.strip() == "":
                continue
            if line.lstrip().startswith("#"):
                meta.unsupported = meta.unsupported or "comments"
                continue
            m = _KEY_RE.match(line)
            if not m or line[:1].isspace():
                meta.unsupported = meta.unsupported or "nested or multi-line values"
                current_list = None
                continue
            key, value = m.group("key").strip(), m.group("value")
            if _has_inline_comment(value):
                meta.unsupported = meta.unsupported or "comments"
            if value.strip()[:1] in ("|", ">", "{", "&", "*", "!"):
                meta.unsupported = (
                    meta.unsupported or f"the YAML construct {value.strip()[:1]!r} (key {key!r})"
                )
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
