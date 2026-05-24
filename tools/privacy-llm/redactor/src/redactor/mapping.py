# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
"""Local PII mapping store + identifier generation.

The mapping file at ``~/.config/apache-steward/pii-mapping.json``
records ``identifier → {type, value}`` so :mod:`redactor.reveal`
can reverse the substitution made by :mod:`redactor.redact`.
Identifiers are deterministic (first 24 bits of
``sha256(value.lower().strip())`` hex-encoded, prefixed by a
type code) so the mapping file is convenience storage, not the
source of truth for the identifier itself.

The contract is documented in ``tools/privacy-llm/pii.md``.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import pathlib
import tempfile
from collections.abc import Mapping

MAPPING_VERSION = 1

DEFAULT_MAPPING_DIR = pathlib.Path.home() / ".config" / "apache-steward"
DEFAULT_MAPPING_PATH = DEFAULT_MAPPING_DIR / "pii-mapping.json"
ENV_MAPPING_PATH = "PII_MAPPING_PATH"

# Type code → friendly type name in the stored entries. The codes
# are the prefix the identifier carries; the friendly names are
# what `pii-list` prints.
TYPE_CODES: dict[str, str] = {
    "N": "name",
    "E": "email",
    "P": "phone",
    "IP": "ip",
    "H": "handle",
    "A": "address",
}
# Reverse map: friendly type → code.
TYPE_NAMES: dict[str, str] = {v: k for k, v in TYPE_CODES.items()}

# Default identifier hex length (24 bits = 6 hex chars). On
# collision we extend in 8-bit increments.
DEFAULT_HEX_LEN = 6
COLLISION_EXTEND_BY = 2  # 2 hex chars = 8 bits


@dataclasses.dataclass(frozen=True)
class Entry:
    """One mapping row: identifier → real PII value, with type."""

    identifier: str
    type: str  # friendly type name (e.g. "name", "email")
    value: str


def locate_mapping_path(explicit: str | None = None) -> pathlib.Path:
    """Resolve the mapping path: ``--mapping-path`` → env → default."""
    if explicit:
        return pathlib.Path(explicit).expanduser()
    if env_path := os.environ.get(ENV_MAPPING_PATH):
        return pathlib.Path(env_path).expanduser()
    return DEFAULT_MAPPING_PATH


def load_mapping(path: pathlib.Path) -> dict[str, Entry]:
    """Load the mapping file. Returns ``{}`` if the file is missing.

    Raises ``ValueError`` if the file exists but is malformed or
    is at an unsupported version — the caller surfaces this to the
    user rather than silently overwriting.
    """
    if not path.exists():
        return {}
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a JSON object at the top level")
    version = raw.get("version")
    if version != MAPPING_VERSION:
        raise ValueError(
            f"{path}: mapping version {version!r}; this tool understands version {MAPPING_VERSION}. "
            f"Upgrade the redactor or migrate the mapping file."
        )
    entries_raw = raw.get("entries", {})
    if not isinstance(entries_raw, dict):
        raise ValueError(f"{path}: 'entries' must be an object")
    out: dict[str, Entry] = {}
    for ident, body in entries_raw.items():
        if not isinstance(body, dict):
            raise ValueError(f"{path}: entry {ident!r} must be an object")
        try:
            out[ident] = Entry(
                identifier=ident,
                type=str(body["type"]),
                value=str(body["value"]),
            )
        except KeyError as e:
            raise ValueError(f"{path}: entry {ident!r} missing field {e.args[0]!r}") from e
    return out


def save_mapping_atomic(path: pathlib.Path, mapping: Mapping[str, Entry]) -> None:
    """Write the mapping file atomically with mode 0o600.

    Uses ``tempfile.NamedTemporaryFile`` + ``os.replace`` so a
    crash mid-write cannot leave a half-written file in place.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": MAPPING_VERSION,
        "entries": {
            ident: {"type": entry.type, "value": entry.value} for ident, entry in sorted(mapping.items())
        },
    }
    serialised = json.dumps(payload, indent=2, sort_keys=False) + "\n"
    # delete=False so we control the rename; mode 0o600 set after
    # write to handle the cross-platform case (NamedTemporaryFile
    # creates the file with default umask).
    with tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        dir=path.parent,
        prefix=path.name,
        suffix=".tmp",
        delete=False,
    ) as tmp:
        tmp.write(serialised)
        tmp_path = pathlib.Path(tmp.name)
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, path)


def normalise_value(value: str) -> str:
    """Canonical form for hashing — lowercase + trim outer whitespace.

    Two values that differ only in case or trailing whitespace
    map to the same identifier. We deliberately do **not** strip
    internal whitespace (so ``Jane  Smith`` and ``Jane Smith``
    are distinct) — internal whitespace can be intentional in
    rare names and we do not want to coerce it.
    """
    return value.strip().lower()


def hash_value(value: str) -> str:
    """Hex-encoded SHA-256 of the value's normalised form."""
    return hashlib.sha256(normalise_value(value).encode("utf-8")).hexdigest()


def generate_identifier(
    type_code: str,
    value: str,
    existing: Mapping[str, Entry],
) -> tuple[str, bool]:
    """Compute the identifier for ``(type_code, value)``.

    Returns ``(identifier, is_collision_extended)``. The default
    is ``<TYPE_CODE>-<6 hex chars>``. If a different value already
    occupies that identifier, the hex length is extended by
    :data:`COLLISION_EXTEND_BY` (default 2) until the identifier
    is unique against ``existing``.

    Idempotency: if ``value`` is already mapped under the same
    type, the existing identifier is returned unchanged regardless
    of length.
    """
    if type_code not in TYPE_CODES:
        raise ValueError(f"unknown type code {type_code!r}; valid codes: {sorted(TYPE_CODES)}")

    friendly = TYPE_CODES[type_code]
    canonical = normalise_value(value)

    # Idempotency check — if this value is already mapped under
    # this type, return the existing identifier so we never grow
    # a second entry for the same value.
    for ident, entry in existing.items():
        if entry.type == friendly and normalise_value(entry.value) == canonical:
            return ident, False

    full_hex = hash_value(value)
    hex_len = DEFAULT_HEX_LEN
    extended = False
    while hex_len <= len(full_hex):
        candidate = f"{type_code}-{full_hex[:hex_len]}"
        if candidate not in existing:
            return candidate, extended
        # Identifier is taken — by a different value (idempotency
        # already returned above). Extend the hex length.
        hex_len += COLLISION_EXTEND_BY
        extended = True
    raise RuntimeError(
        f"unable to find a unique identifier for value (type={type_code!r}) "
        f"after extending to full {len(full_hex)}-char hash; the mapping file is "
        f"saturated. This is effectively impossible — investigate the mapping file."
    )


def upsert(
    mapping: dict[str, Entry],
    type_code: str,
    value: str,
) -> Entry:
    """Insert or fetch the mapping entry for ``(type_code, value)``.

    Mutates ``mapping`` in place when a new entry is created.
    Returns the resulting :class:`Entry` either way.
    """
    identifier, _ = generate_identifier(type_code, value, mapping)
    if identifier not in mapping:
        mapping[identifier] = Entry(
            identifier=identifier,
            type=TYPE_CODES[type_code],
            value=value,
        )
    return mapping[identifier]
