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

"""Read `.apache-magpie.lock` — the one shape, not general YAML.

The lock is written by `setup`, never by hand, and its grammar is fixed by
[`locks.md`]: `key: value` scalars at column 0, a `plugins:` sequence of
`- name`, and a `reconciled:` mapping whose `skills:` child maps a skill's
frontmatter `name:` to its `surface_hash`.  Comments and blank lines are
ignored.

A real YAML parser is the obvious alternative and is rejected for one
reason: this module is copied into an adopter's gitignored
`.apache-magpie-local/` and run with bare `python3`, where no third-party
package is available.  Vendoring a YAML implementation to read four keys
would be the larger sin.

The parser is deliberately strict about what it does not understand.  A
line it cannot place raises rather than being skipped, because a silently
half-read lock would produce a confident verdict about a floor the reader
never actually saw.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


class MalformedLock(ValueError):
    """The lock exists but does not parse. Never treated as 'no lock'."""


@dataclass
class Reconciled:
    version: str | None = None
    at: str | None = None
    skills: dict[str, str] = field(default_factory=dict)


@dataclass
class Lock:
    method: str | None = None
    url: str | None = None
    min_version: str | None = None
    ref: str | None = None
    commit: str | None = None
    plugins: list[str] = field(default_factory=list)
    reconciled: Reconciled | None = None


def _strip_comment(line: str) -> str:
    return line.split("#", 1)[0].rstrip()


def parse(text: str) -> Lock:
    """Parse the lock's text. Raises `MalformedLock` on anything unexpected."""
    lock = Lock()
    section: str | None = None
    for raw in text.splitlines():
        line = _strip_comment(raw)
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        body = line.strip()

        if indent == 0:
            section = None
            if body.endswith(":") and ":" not in body[:-1]:
                key = body[:-1]
                if key == "plugins":
                    section = "plugins"
                elif key == "reconciled":
                    section = "reconciled"
                    lock.reconciled = Reconciled()
                else:
                    raise MalformedLock(f"unknown block: {key!r}")
                continue
            if ":" not in body:
                raise MalformedLock(f"not a key: value line: {raw!r}")
            key, _, value = body.partition(":")
            key, value = key.strip(), value.strip()
            if key in {"method", "url", "min_version", "ref", "commit"}:
                setattr(lock, key, value)
            else:
                raise MalformedLock(f"unknown key: {key!r}")
            continue

        if section == "plugins":
            if not body.startswith("- "):
                raise MalformedLock(f"not a plugins entry: {raw!r}")
            lock.plugins.append(body[2:].strip())
            continue

        if section == "reconciled":
            assert lock.reconciled is not None
            if body == "skills:":
                section = "reconciled.skills"
                continue
            key, _, value = body.partition(":")
            key, value = key.strip(), value.strip()
            if key in {"version", "at"}:
                setattr(lock.reconciled, key, value)
                continue
            raise MalformedLock(f"unknown reconciled key: {key!r}")

        if section == "reconciled.skills":
            assert lock.reconciled is not None
            key, _, value = body.partition(":")
            if not value.strip():
                raise MalformedLock(f"skill entry without a hash: {raw!r}")
            lock.reconciled.skills[key.strip()] = value.strip()
            continue

        raise MalformedLock(f"indented line outside any block: {raw!r}")
    return lock


def load(path: Path) -> Lock | None:
    """Parse the lock at `path`, or `None` when there is no lock.

    Only a genuinely absent file is `None`.  An unreadable one raises, so a
    permission error is never mistaken for an unadopted project — the same
    distinction the pre-flight draws between *unknown* and *absent*.
    """
    if not path.exists():
        return None
    return parse(path.read_text(encoding="utf-8"))
