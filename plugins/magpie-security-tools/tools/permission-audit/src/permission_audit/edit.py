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
"""Atomic edit of `.claude/settings*.json` permission allow-list.

Concurrent writers (notably `setup-isolated-setup-install`, which
writes the same file's `sandbox.filesystem.*` arrays) must not
silently clobber each other. The edit path is:

1. POSIX `fcntl.flock` advisory exclusive lock on the target file.
2. Re-parse the file under the lock (so the in-memory copy reflects
   any change a competing writer landed between our audit pass and
   our edit pass).
3. Mutate `permissions.allow[]` in place.
4. Write to `<file>.tmp.<pid>` in the same directory.
5. `os.replace(tmp, target)` — atomic on the same filesystem.
6. Release the lock.

The lock is taken on the **target file** itself, which is the
convention `sandbox-add-project-root.sh` already follows. Two
edit processes serialize without either losing work; a reader
takes no lock and may briefly observe pre- or post-edit content
but never a partial JSON.

The function preserves every other key in the file verbatim
(indent, ordering, unknown fields) — only `permissions.allow[]`
is touched. Top-level keys are written in their original order.
"""

from __future__ import annotations

import fcntl
import json
import os
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class EditOutcome:
    added: list[str]
    removed: list[str]
    file_was_created: bool


def apply_changes(
    settings_path: Path,
    additions: Iterable[str],
    removals: Iterable[str],
    create_if_missing: bool = False,
) -> EditOutcome:
    """Apply additions and removals to a settings file's allow list.

    Args:
        settings_path: absolute path to `.claude/settings.json` or
            `.claude/settings.local.json`.
        additions: allow-list entries to add (skipped if already
            present; preserves declaration order otherwise).
        removals: allow-list entries to remove (no-op if absent).
        create_if_missing: when True, create the file with the
            minimum-viable JSON (`{"permissions": {"allow": []}}`)
            if it does not exist. Default False — most callers
            should never be in a state where the file does not
            already exist (the sandbox-allowlist helper would have
            created it).

    Returns:
        `EditOutcome` describing what changed.

    Raises:
        FileNotFoundError: if the file does not exist and
            `create_if_missing` is False.
        ValueError: if the file exists but is not valid JSON, or
            if `permissions.allow` is present but not a list.
    """
    additions_list = list(additions)
    removals_set = set(removals)
    file_was_created = False

    if not settings_path.exists():
        if not create_if_missing:
            raise FileNotFoundError(settings_path)
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text("{}\n", encoding="utf-8")
        file_was_created = True

    # Open in r+ mode so we can lock + re-read under the lock.
    with settings_path.open("r+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            fh.seek(0)
            raw = fh.read()
            try:
                data = json.loads(raw) if raw.strip() else {}
            except json.JSONDecodeError as e:
                raise ValueError(f"{settings_path}: invalid JSON: {e}") from e

            if not isinstance(data, dict):
                raise ValueError(f"{settings_path}: top-level value is not an object")

            perms = data.setdefault("permissions", {})
            if not isinstance(perms, dict):
                raise ValueError(f"{settings_path}: .permissions is not an object")
            allow = perms.setdefault("allow", [])
            if not isinstance(allow, list):
                raise ValueError(f"{settings_path}: .permissions.allow is not a list")

            existing = set(allow)
            removed: list[str] = []
            added: list[str] = []

            if removals_set:
                kept: list[str] = []
                for entry in allow:
                    if entry in removals_set:
                        removed.append(entry)
                    else:
                        kept.append(entry)
                allow[:] = kept
                existing -= removals_set

            for entry in additions_list:
                if entry not in existing:
                    allow.append(entry)
                    existing.add(entry)
                    added.append(entry)

            if not added and not removed:
                return EditOutcome(added=[], removed=[], file_was_created=file_was_created)

            tmp_path = settings_path.with_name(f"{settings_path.name}.tmp.{os.getpid()}")
            tmp_path.write_text(
                json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            os.replace(tmp_path, settings_path)

            return EditOutcome(added=added, removed=removed, file_was_created=file_was_created)
        finally:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
