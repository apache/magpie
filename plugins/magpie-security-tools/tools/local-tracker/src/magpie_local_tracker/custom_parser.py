# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""A project's own body-field parser, for a report layout that is not ``###`` sections.

`setup config` generates one from tools/body-field-contract/formats/_template.py
when `detect` reports ``field_layout: custom``, runs the conformance suite on
it, and hands the maintainer ``trust-parser`` to run in their own terminal,
which records ``body_parser: {path, sha256}`` in the committed descriptor and
the same hash in the maintainer's own record.

The parser is code from the tracker's repository, which vetted operations run
outside the sandbox, so it is loaded only when every check holds:

1. the descriptor names it;
2. its path is a ``.py`` file directly in
   ``.apache-magpie-overrides/tools/local-tracker/parsers/`` at the top of the
   working copy: no absolute path, no ``..``, no symlink anywhere on the way;
3. its SHA-256 matches the descriptor's **and** the one the user confirmed on
   this machine, recorded in ``~/.config/apache-magpie/local-tracker-parsers.json``
   under the working copy's real path.

The record is kept where only the user writes. Nothing in a working copy can
stand in for it (a committed ``.svn/`` or any other file is the repository's
own content), and the secure setup never lets a sandboxed command write under
``~/.config/apache-magpie``. ``trust-parser`` asks for the confirmation itself,
on the controlling terminal, so an agent's shell, which has none, cannot record
one.

Any mismatch refuses (exit 2) and says to review the change and re-confirm
through `setup config`. A tracker whose descriptor says ``field_layout:
custom`` never falls back to the default parser.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path, PurePosixPath
from types import ModuleType

from .vcs import WorkingCopy

PARSER_DIR = PurePosixPath(".apache-magpie-overrides/tools/local-tracker/parsers")
#: The user's confirmed hashes: {working-copy real path: {parser path: sha256}}.
TRUST_FILE = Path("~/.config/apache-magpie/local-tracker-parsers.json")
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


class ParserUnverifiable(ParserRefused):
    """The user's record cannot be read here: the secure setup denies the sandbox reads under it."""


def _refuse(why: str) -> ParserRefused:
    return ParserRefused(
        f"{why}. The tracker's custom body parser is not loaded, and the tracker is not read with the "
        "default parser either: review the parser file's diff, then re-confirm it with `setup config` "
        "(which hands you the `magpie-local-tracker trust-parser` command to run in your own terminal)."
    )


def trust_file() -> Path:
    """The user's record of confirmed parsers, outside every working copy."""
    return TRUST_FILE.expanduser()


def _key(wc: WorkingCopy) -> str:
    return os.path.realpath(wc.top)


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


def _records() -> dict[str, object]:
    path = trust_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except PermissionError as exc:
        # The record shares ~/.config/apache-magpie with credentials, so the
        # secure setup's sandbox may not read it: nothing to re-confirm, the
        # command has to run where the record is readable.
        raise ParserUnverifiable(
            f"{path} cannot be read here ({exc.strerror}), so the tracker's custom body parser "
            "cannot be verified: inside the secure setup's sandbox that is by design. Run the command "
            "through vetted operations (vetted-op-read, vetted-op-tracker), which run outside the "
            "sandbox; the tracker is not read with the default parser meanwhile."
        ) from exc
    except (OSError, ValueError) as exc:
        raise _refuse(f"{path} cannot be read ({exc})") from exc
    return data if isinstance(data, dict) else {}


def trusted(wc: WorkingCopy) -> dict[str, str]:
    """The hashes the user confirmed for this working copy, by parser path."""
    entry = _records().get(_key(wc))
    return {str(k): str(v) for k, v in entry.items()} if isinstance(entry, dict) else {}


def trust(wc: WorkingCopy, relative: str, expected: str, confirm: Callable[[str], bool]) -> tuple[Path, str]:
    """Record ``relative``'s hash once it is ``expected``, the reviewed hash, and ``confirm`` says yes.

    ``confirm`` gets the question to put to the user. Returns the trust file and the hash.
    """
    path = resolve(wc, relative)
    actual = sha256_of(path.read_bytes())
    if actual != expected:
        raise _refuse(f"{relative} has SHA-256 {actual}, not the reviewed {expected}")
    if not confirm(f"Trust {path} (SHA-256 {actual}) as this tracker's body parser?"):
        raise _refuse(f"{relative} was not confirmed")
    records = _records()
    entry = records.get(_key(wc))
    entry = dict(entry) if isinstance(entry, dict) else {}
    entry[str(PurePosixPath(relative))] = actual
    records[_key(wc)] = entry
    target = trust_file()
    target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    target.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target, actual


def load(wc: WorkingCopy, spec: Mapping[str, object]) -> ModuleType:
    """The verified parser module the descriptor's ``body_parser`` names."""
    if not isinstance(spec, Mapping) or not spec.get("path"):
        raise _refuse("the descriptor says field_layout is custom but names no body_parser")
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
