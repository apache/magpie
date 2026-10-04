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
"""Version and RC formats: one rule for the source release, a scheme per convenience artefact.

The source release candidate every release-* skill takes (`<version>` plus
`rcN`, tagged `<version>-rcN`) has one format everywhere: a dotted version of
two or more numeric parts with no `.postN`, and `rcN` with N >= 1.

Convenience (non-source) artefacts may carry their own version (the optional
`version` field of each `release-build.md § Convenience artefacts` entry,
default the release version; `<version>` in it is rendered), e.g. a wheel
re-released as `2.10.5.post1` against source release `2.10.5`. That version
follows its ecosystem's rules, named by the entry's optional `version_scheme`. `SCHEMES` is the registry of schemes the tool
validates; any other name is accepted and reported as unvalidated, so the RM
decides. Add a scheme by adding a `Scheme` to `SCHEMES`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

RC = re.compile(r"^rc[1-9]\d*$")
SOURCE_VERSION = re.compile(r"^\d+(?:\.\d+)+$")
SOURCE_RC_ID = re.compile(r"^(?P<version>\d+(?:\.\d+)+)-(?P<rc>rc[1-9]\d*)$")

SOURCE_VERSION_SHAPE = "a dotted version of two or more numeric parts, no `.postN` (e.g. 2.11.0)"
RC_SHAPE = "rc<N> with N >= 1 (e.g. rc1)"
SOURCE_RC_ID_SHAPE = "<version>-rc<N>: a dotted version of two or more numeric parts, no `.postN`, then `-rc` and N >= 1 (e.g. 2.11.0-rc1)"


@dataclass(frozen=True)
class Scheme:
    """A convenience-artefact versioning scheme the tool can validate."""

    name: str
    version: re.Pattern[str]
    rc: re.Pattern[str]
    version_shape: str
    rc_shape: str


SCHEMES: dict[str, Scheme] = {
    "python": Scheme(
        name="python",
        version=re.compile(r"^\d+(?:\.\d+)+(?:\.post\d+)?$"),
        rc=RC,
        version_shape="a dotted version with an optional `.postN` (e.g. 2.11.0 or 2.11.0.post1)",
        rc_shape=RC_SHAPE,
    ),
}


def artefact_version(entry: dict[str, Any], release_version: str | None) -> str | None:
    """The artefact's own `version` (with `<version>` rendered), else the release version."""
    raw = entry.get("version")
    if raw in (None, ""):
        return release_version
    text = str(raw).strip()
    if "<version>" in text:
        return text.replace("<version>", release_version) if release_version is not None else None
    return text


def check_convenience(entry: dict[str, Any], release_version: str | None, rc: str | None) -> dict[str, Any]:
    """Validate one convenience artefact's version against its `version_scheme`.

    The version checked is the artefact's own (`artefact_version`). Returns
    `{name, version, version_scheme, status, problems}` with `status` one of
    `valid`, `invalid` or `unvalidated` (no scheme, or a scheme not in `SCHEMES`).
    """
    version = artefact_version(entry, release_version)
    raw_scheme = entry.get("version_scheme")
    scheme_name = str(raw_scheme).strip() if raw_scheme not in (None, "") else None
    out: dict[str, Any] = {"name": entry.get("name"), "version": version, "version_scheme": scheme_name, "status": "unvalidated", "problems": []}
    scheme = SCHEMES.get(scheme_name.lower()) if scheme_name else None
    if scheme is None or version is None:
        return out
    if not scheme.version.match(version):
        out["problems"].append(f"version {version!r} is not {scheme.version_shape}")
    if rc is not None and not scheme.rc.match(rc):
        out["problems"].append(f"RC {rc!r} is not {scheme.rc_shape}")
    out["status"] = "invalid" if out["problems"] else "valid"
    return out
