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
"""What every verify-rc command reads from `release-config load --skill verify-rc <version>-rcN`."""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from typing import Any

from release_management.shell import dq as dq  # re-exported for the step modules

#: The voter-obligation reminder (Golden rule 4), verbatim in every report.
VOTER_OBLIGATION_REMINDER = (
    "> *This report is a mechanical pre-flight aid. A `PASS` result does\n"
    "> not discharge a voter's ASF obligation to download, build, and\n"
    "> test the candidate on their own hardware before posting a binding\n"
    "> `+1`.*"
)

ARCHIVE_SUFFIXES = (".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar", ".zip")
_SAFE = re.compile(r"[\w@%+=:,./-]+")


class VerifyError(ValueError):
    """The input cannot be classified: reported as `{"ok": false, "error": ...}` with exit code 2."""


def q(value: str) -> str:
    """Shell-quote a value unless it is plainly safe."""
    return value if _SAFE.fullmatch(value) else shlex.quote(value)


@dataclass
class VerifyRc:
    """The resolved verify-rc configuration."""

    version: str
    rc: str
    meta: dict[str, Any]
    config: dict[str, Any] = field(default_factory=dict)
    organization: str = "independent"

    @classmethod
    def from_load(cls, loaded: dict[str, Any]) -> VerifyRc:
        meta = loaded.get("metadata") or {}
        version, rc = meta.get("version"), meta.get("rc")
        if not version or not rc:
            raise VerifyError(
                "release-config load output has no version / rc: run it with --skill verify-rc <version>-rcN"
            )
        return cls(
            version=str(version),
            rc=str(rc),
            meta=meta,
            config=loaded.get("config") or {},
            organization=str(meta.get("organization") or loaded.get("organization") or "independent"),
        )

    @property
    def rc_tag(self) -> str:
        return f"{self.version}-{self.rc}"

    @property
    def is_asf(self) -> bool:
        return self.organization.upper() == "ASF"

    @property
    def ci_automated(self) -> bool:
        """`automated_release_signing: enabled` under an organization that offers it."""
        return self.meta.get("signing_mode") == "ci-automated"

    @property
    def artefacts(self) -> list[dict[str, Any]]:
        out = []
        for entry in self.meta.get("expected_artefacts") or []:
            if isinstance(entry, str):
                entry = {"name": entry, "kind": "source", "required": True}
            out.append(entry)
        return out

    @property
    def source_artefact(self) -> str:
        for entry in self.artefacts:
            if entry.get("kind") == "source":
                return str(entry["name"])
        return str(self.artefacts[0]["name"]) if self.artefacts else "<source-artefact>"

    @property
    def unpacked_dir(self) -> str:
        """The source artefact's filename without its archive extension (`-source-release` kept)."""
        name = self.source_artefact
        for suffix in ARCHIVE_SUFFIXES:
            if name.endswith(suffix):
                return name[: -len(suffix)]
        return name

    @property
    def digests(self) -> list[str]:
        return [str(d).lower() for d in self.meta.get("digest_set") or ["sha512"]]

    def convenience(self) -> list[dict[str, Any]]:
        """Each convenience artefact with its name rendered (its own `version`, default the release's)."""
        out = []
        for entry in self.meta.get("convenience_artefacts") or []:
            if not isinstance(entry, dict):
                continue
            own = str(entry.get("version") or self.version)
            name = str(entry.get("name", "")).replace("<version>-<rcN>", self.rc_tag)
            name = name.replace("<version>", own).replace("<rcN>", self.rc)
            mode = str(entry.get("reproducibility") or self.meta.get("reproducibility_binaries") or "off")
            out.append(entry | {"name": name, "reproducibility": mode})
        return out
