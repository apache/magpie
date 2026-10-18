# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""A project's own body-field parser, for a report layout that is not ``###`` sections.

`setup config` generates one from tools/body-field-contract/formats/_template.py
when `detect` reports ``field_layout: custom``, runs the conformance suite on
it, and, on the maintainer's explicit confirmation, records it with
``trust-parser``: ``body_parser: {path, sha256}`` in the committed descriptor
and the same hash in the working copy's personal layer.

The parser is code from the tracker's repository, which vetted operations run
outside the sandbox, so it is loaded only when every check holds:

1. the descriptor names it;
2. its path is a ``.py`` file directly in
   ``.apache-magpie-overrides/tools/local-tracker/parsers/`` at the top of the
   working copy: no absolute path, no ``..``, no symlink anywhere on the way;
3. its SHA-256 matches the descriptor's **and** the one recorded in the
   personal layer, which is never committed: ``<git-common-dir>/apache-magpie/``
   on Git, ``<working-copy>/.svn/apache-magpie/`` on Subversion.

Any mismatch refuses (exit 2) and says to review the change and re-confirm
through `setup config`. A tracker whose descriptor says ``field_layout:
custom`` never falls back to the default parser.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from types import ModuleType

from .vcs import VcsError, WorkingCopy

PARSER_DIR = PurePosixPath(".apache-magpie-overrides/tools/local-tracker/parsers")
TRUST_FILE = "local-tracker-parsers.json"
#: What a format adapter provides (tools/body-field-contract/contract.md, "Format adapters").
INTERFACE = (
    "FORMAT",
    "list_fields",
    "extract_field",
    "replace_field",
    "append_field",
    "normalise",
    "boundary_name",
    "FieldNotFoundError",
    "DuplicateFieldError",
    "AmbiguousFieldError",
)


class ParserRefused(Exception):
    """The custom parser cannot be trusted; the message says why and what to do."""


def _refuse(why: str) -> ParserRefused:
    return ParserRefused(
        f"{why}. The tracker's custom body parser is not loaded, and the tracker is not read with the "
        "default parser either: review the parser file's diff, then re-confirm it with `setup config` "
        "(which records the reviewed hash with `magpie-local-tracker trust-parser`)."
    )


def personal_layer(wc: WorkingCopy) -> Path:
    """Where this working copy's never-committed trust record lives."""
    try:
        return wc.admin_dir() / "apache-magpie"
    except VcsError as exc:
        raise _refuse(
            "a custom body parser needs a Git or Subversion working copy, whose admin area holds the trust record"
        ) from exc


def resolve(wc: WorkingCopy, relative: str) -> Path:
    """The parser's absolute path, refusing anything outside the parser directory or behind a symlink."""
    rel = PurePosixPath(relative)
    if (
        not relative
        or "\\" in relative
        or rel.is_absolute()
        or ".." in rel.parts
        or rel.parent != PARSER_DIR
        or rel.suffix != ".py"
    ):
        raise _refuse(
            f"the descriptor's body_parser path {relative!r} is not a .py file directly in {PARSER_DIR}/"
        )
    current = wc.top
    for part in rel.parts:
        current = current / part
        if current.is_symlink():
            raise _refuse(f"{current} is a symlink")
    if not current.is_file():
        raise _refuse(f"{current} does not exist")
    return current


def sha256_of(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def trusted(wc: WorkingCopy) -> dict[str, str]:
    """The confirmed hashes recorded on this machine, by parser path."""
    path = personal_layer(wc) / TRUST_FILE
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as exc:
        raise _refuse(f"{path} cannot be read ({exc})") from exc
    return {str(k): str(v) for k, v in data.items()} if isinstance(data, dict) else {}


def trust(wc: WorkingCopy, relative: str, expected: str) -> tuple[Path, str]:
    """Record ``relative``'s hash in the personal layer; refuses unless it is ``expected``, the reviewed hash.

    Returns the trust file and the hash.
    """
    actual = sha256_of(resolve(wc, relative).read_bytes())
    if actual != expected:
        raise _refuse(f"{relative} has SHA-256 {actual}, not the reviewed {expected}")
    layer = personal_layer(wc)
    layer.mkdir(parents=True, exist_ok=True)
    records = trusted(wc)
    records[str(PurePosixPath(relative))] = actual
    (layer / TRUST_FILE).write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return layer / TRUST_FILE, actual


def load(wc: WorkingCopy, spec: Mapping[str, object]) -> ModuleType:
    """The verified parser module the descriptor's ``body_parser`` names."""
    if not isinstance(spec, Mapping) or not spec.get("path"):
        raise _refuse("the descriptor says field_layout is custom but names no body_parser")
    personal_layer(wc)  # a working copy first: without one there is nowhere to confirm a parser
    relative = str(spec.get("path") or "")
    recorded = str(spec.get("sha256") or "")
    path = resolve(wc, relative)
    data = path.read_bytes()
    actual = sha256_of(data)
    if actual != recorded:
        raise _refuse(f"{relative} has SHA-256 {actual}, but the descriptor records {recorded or 'none'}")
    confirmed = trusted(wc).get(str(PurePosixPath(relative)))
    if confirmed != actual:
        raise _refuse(
            f"{relative} (SHA-256 {actual}) has not been confirmed on this machine"
            + (f"; the confirmed version was {confirmed}" if confirmed else "")
        )
    name = f"_magpie_local_tracker_parser_{actual[:16]}"
    module_spec = importlib.util.spec_from_loader(name, loader=None)
    assert module_spec is not None
    module = importlib.util.module_from_spec(module_spec)
    module.__file__ = str(path)
    sys.modules[name] = module  # dataclasses resolve annotations through sys.modules
    # Executed from the bytes just hashed, never re-read from disk.
    exec(compile(data, str(path), "exec"), module.__dict__)
    missing = [attr for attr in INTERFACE if not hasattr(module, attr)]
    if missing:
        raise _refuse(f"{relative} does not provide {', '.join(missing)}")
    return module
