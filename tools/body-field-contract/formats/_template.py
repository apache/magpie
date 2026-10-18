# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""A body-field format adapter: the contract's operations for one non-default layout.

Copy this file, rename it after the layout (``key_value.py``), and change only
the section marked FORMAT. Everything below it implements the format adapter
interface of tools/body-field-contract/contract.md ("Format adapters"): the
same operations as the default parser, the same refusals and the same
``needs_decision`` kinds, for this layout's own boundary rule. It uses the
Python standard library only, and must stay that way: the local-files tracker
loads it from the project's override directory, after checking its hash.

The conformance suite runs every adapter against the generic properties every
layout shares and against the adapter's own fixtures
(``<name>.cases.jsonl`` beside it); both must pass before the adapter is
enabled.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

# ------------------------------------------------------------------ FORMAT
# What a field boundary is in this layout. The default here is a
# `Name: value` line at column 0, the name a capitalised run of letters,
# digits, spaces, `/`, `-` or `_`: the value starts after the colon and runs
# to the next boundary.

FORMAT = "key-value"
DESCRIPTION = "fields are `Name: value` lines at column 0; a value runs to the next such line"

_BOUNDARY = re.compile(r"(?P<name>[A-Z][A-Za-z0-9 /_-]{0,60}):(?:[ \t]|$)")


def boundary_name(line: str) -> str | None:
    """The field ``line`` starts, or None: the layout's one boundary rule."""
    match = _BOUNDARY.match(_content(line))
    return " ".join(match.group("name").split()) if match else None


def boundary_line(name: str) -> str:
    """The line that starts field ``name`` in this layout (for appends and the conformance properties)."""
    return f"{name}:"


#: A body in this layout and its fields, for the conformance properties (synthetic values only).
SAMPLE_BODY = "Summary: A synthetic summary.\nAffected versions: 1.0 to 1.2\nSeverity: Low\n"
SAMPLE_FIELDS = {"Summary": "A synthetic summary.", "Affected versions": "1.0 to 1.2", "Severity": "Low"}

# ------------------------------------------------------------------ interface (unchanged per layout)


class FieldNotFoundError(LookupError):
    """The field is absent."""


class DuplicateFieldError(FieldNotFoundError):
    """The field appears more than once."""


class AmbiguousFieldError(FieldNotFoundError):
    """Readers could disagree on the field, or a rewrite would change another one."""


_LINE = re.compile(r"[^\r\n]*(?:\r\n|\r|\n)|[^\r\n]+\Z")
_ANY_EOL = re.compile(r"\r\n|\r|\n")


def split_lines(body: str) -> list[str]:
    """``body`` split at ``\\n``, ``\\r\\n`` and ``\\r`` only, endings kept (BF-LINE-1, BF-LINE-2)."""
    return _LINE.findall(body)


def _content(line: str) -> str:
    return line.rstrip("\r\n")


@dataclass(frozen=True)
class Section:
    name: str
    first_line: str  # the boundary line, value text included
    body_lines: list[str]


def parse(body: str) -> tuple[list[str], list[Section]]:
    """The preamble and one section per boundary, in order; byte-exact when joined."""
    preamble: list[str] = []
    sections: list[Section] = []
    for line in split_lines(body):
        name = boundary_name(line)
        if name is not None:
            sections.append(Section(name, line, []))
        else:
            (sections[-1].body_lines if sections else preamble).append(line)
    return preamble, sections


def _locate(sections: list[Section], name: str) -> int:
    copies = [i for i, s in enumerate(sections) if s.name == name]
    if not copies:
        raise FieldNotFoundError(f"field not found: {name!r}")
    if len(copies) > 1:
        raise DuplicateFieldError(f"field {name!r} appears {len(copies)} times; refusing to guess")
    return copies[0]


def _value_of(section: Section) -> str:
    first = _content(section.first_line)
    inline = first.split(":", 1)[1].strip(" \t")
    rest = "".join(section.body_lines).strip("\r\n")
    return "\n".join(part for part in (inline, rest) if part)


def list_fields(body: str) -> list[str]:
    return [s.name for s in parse(body)[1]]


def extract_field(body: str, name: str) -> str:
    _, sections = parse(body)
    return _value_of(sections[_locate(sections, name)])


def _eol(body: str) -> str:
    first = _ANY_EOL.search(body)
    return first.group(0) if first else "\n"


def _render(name: str, value: str, eol: str) -> list[str]:
    lines = [_content(line) for line in split_lines(value.strip("\r\n"))] or [""]
    head = f"{boundary_line(name)} {lines[0]}".rstrip(" ")
    return [head + eol, *(line + eol for line in lines[1:])]


def _refuse_value(name: str, value: str) -> None:
    if any(boundary_name(line) is not None for line in split_lines(value)):
        raise AmbiguousFieldError(f"field {name!r}: the new value holds a line that would start a field")


def replace_field(body: str, name: str, value: str) -> str:
    """``body`` with ``name``'s value replaced; every other line byte-identical (BF-REP-*)."""
    _refuse_value(name, value)
    preamble, sections = parse(body)
    index = _locate(sections, name)
    eol = _eol(body)
    out = list(preamble)
    for i, section in enumerate(sections):
        if i == index:
            out.extend(_render(name, value, eol))
        else:
            out.append(section.first_line)
            out.extend(section.body_lines)
    new_body = "".join(out)
    _check_preserved(body, new_body, index)
    return new_body


def append_field(body: str, name: str, value: str) -> str:
    """``body`` with a new field ``name`` after the last one."""
    _refuse_value(name, value)
    if name in list_fields(body):
        raise DuplicateFieldError(f"field {name!r} already exists")
    eol = _eol(body)
    prefix = body if not body or body.endswith(("\n", "\r")) else body + eol
    new_body = prefix + "".join(_render(name, value, eol))
    if list_fields(new_body) != [*list_fields(body), name]:
        raise AmbiguousFieldError(f"field {name!r}: the append would change the body's other fields")
    return new_body


def _check_preserved(old: str, new: str, index: int) -> None:
    """Whole-body preservation: the same fields, every other section byte-identical (BF-REP-5)."""
    before, after = parse(old), parse(new)
    if before[0] != after[0] or [s.name for s in before[1]] != [s.name for s in after[1]]:
        raise AmbiguousFieldError("the rewrite would change another field; refusing it")
    for i, (b, a) in enumerate(zip(before[1], after[1], strict=True)):
        if i != index and (b.first_line, b.body_lines) != (a.first_line, a.body_lines):
            raise AmbiguousFieldError("the rewrite would change another field; refusing it")


@dataclass(frozen=True)
class NormaliseResult:
    text: str
    changes: list[dict[str, object]] = field(default_factory=list)
    needs_decision: list[dict[str, object]] = field(default_factory=list)


def normalise(
    body: str, known_fields: Iterable[str] | None = None, keep: Mapping[str, int] | None = None
) -> NormaliseResult:
    """Line endings to ``\\n`` (``line_endings``) and ``duplicate`` decisions; nothing else is rewritten."""
    changes: list[dict[str, object]] = []
    lines = split_lines(body)
    first_cr = next((n for n, line in enumerate(lines, 1) if line[len(_content(line)) :] not in ("", "\n")), None)
    text = "".join(_content(line) + ("\n" if line != _content(line) else "") for line in lines)
    if first_cr is not None:
        changes.append({"line": first_cr, "kind": "line_endings"})
    seen: dict[str, list[int]] = {}
    for number, line in enumerate(split_lines(text), 1):
        name = boundary_name(line)
        if name is not None:
            seen.setdefault(name, []).append(number)
    decisions: list[dict[str, object]] = [
        {"field": name, "kind": "duplicate", "lines": numbers} for name, numbers in seen.items() if len(numbers) > 1
    ]
    return NormaliseResult(text=text, changes=changes, needs_decision=decisions)
