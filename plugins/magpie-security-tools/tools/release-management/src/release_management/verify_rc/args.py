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
"""Turn `release-build.md` / `release-management-config.md` into the `release-verify` invocations.

One `--expect` per required expected artefact and one `--expect-optional` per
optional one (in the listed order), one `--digest` per digest `release-verify`
checks, the Binary-exclude list as `--prohibit` / `--accept`, the
source-tree validators as `--validator`, and the version manifests as
`--manifest`. The agent runs the printed commands; this module runs nothing.
"""

from __future__ import annotations

from typing import Any

from release_management.verify_rc.common import VerifyRc, dq, q

RELEASE_VERIFY = "uv run --project <framework>/tools/release-verify release-verify"
#: The digests `release-verify --digest` accepts; md5 is detected on its own (a WARN), never passed.
CHECKED_DIGESTS = ("sha512", "sha256")


def _digests(v: VerifyRc) -> tuple[list[str], list[str]]:
    wanted = ["sha512", *v.digests]
    checked = [d for d in dict.fromkeys(wanted) if d in CHECKED_DIGESTS]
    ignored = [d for d in dict.fromkeys(v.digests) if d not in CHECKED_DIGESTS]
    return checked, ignored


def _join(head: str, parts: list[str]) -> str:
    """`head` and its options, wrapped one option group per line for paste."""
    lines = [head]
    current = ""
    for part in parts:
        if current and len(current) + len(part) > 90:
            lines.append(current)
            current = ""
        current = f"{current} {part}".strip()
    if current:
        lines.append(current)
    return " \\\n  ".join(lines)


def invocations(
    v: VerifyRc,
    *,
    staging_copy: str = "<staging-copy>",
    keys_file: str = "<keys-file>",
    unpacked_dir: str | None = None,
    previous_dir: str | None = None,
) -> dict[str, Any]:
    """Every `release-verify` command of Steps 1-3 and 5-8, plus `all`, resolved from the config."""
    tree = unpacked_dir or v.unpacked_dir
    expect: list[str] = []
    for entry in v.artefacts:
        flag = "--expect" if entry.get("required", True) else "--expect-optional"
        expect.append(f"{flag} {dq(str(entry['name']))}")
    if not expect:
        expect = ["--expect " + dq("<artefact-pattern>")]
    checked, ignored = _digests(v)
    digest = [f"--digest {d}" for d in checked]
    keys = [f"--keys {q(keys_file)}"]
    keys_url = v.meta.get("keys_file_url")
    if keys_url:
        keys.append(f"--keys-url {dq(str(keys_url))}")
    prohibit = [f"--prohibit {dq(g)}" for g in v.meta.get("binary_prohibit") or []]
    accept = [f"--accept {dq(g)}" for g in v.meta.get("binary_accept") or []]
    validators = [f"--validator {dq(c)}" for c in v.meta.get("source_tree_validators") or []]
    manifests = [f"--manifest {q(str(m))}" for m in v.meta.get("version_manifest_files") or []]
    previous = [f"--previous {q(previous_dir)}"] if previous_dir else []
    staged, unpacked = q(staging_copy), q(tree)
    commands = {
        "inventory": _join(f"{RELEASE_VERIFY} inventory", [f"--dir {staged}", *expect, *digest]),
        "signatures": _join(f"{RELEASE_VERIFY} signatures", [f"--dir {staged}", *expect, *keys]),
        "checksums": _join(f"{RELEASE_VERIFY} checksums", [f"--dir {staged}", *expect, *digest]),
        "notice-license": _join(f"{RELEASE_VERIFY} notice-license", [f"--tree {unpacked}", *previous]),
        "binaries": _join(f"{RELEASE_VERIFY} binaries", [f"--tree {unpacked}", *prohibit, *accept]),
        "symlinks": _join(f"{RELEASE_VERIFY} symlinks", [f"--tree {unpacked}", *validators]),
        "version": _join(
            f"{RELEASE_VERIFY} version", [f"--tree {unpacked}", f"--rc-tag {v.rc_tag}", *manifests]
        ),
        "all": _join(
            f"{RELEASE_VERIFY} all",
            [
                f"--dir {staged}",
                f"--tree {unpacked}",
                *expect,
                *digest,
                *keys,
                *previous,
                *prohibit,
                *accept,
                *validators,
                f"--rc-tag {v.rc_tag}",
                *manifests,
            ],
        ),
    }
    warnings = []
    if not v.artefacts:
        warnings.append("release-build.md § Expected artefact list names no artefact: fill it before Step 1")
    if not manifests:
        warnings.append("version_manifest_files is empty: Step 8 has nothing to check")
    if ignored:
        warnings.append(
            f"digest_set lists {', '.join(ignored)}: not passed to release-verify "
            "(only sha512 and sha256 are checked; a staged .md5 is reported on its own)"
        )
    return {
        "rc_tag": v.rc_tag,
        "unpacked_dir": tree,
        "required": [e["name"] for e in v.artefacts if e.get("required", True)],
        "optional": [e["name"] for e in v.artefacts if not e.get("required", True)],
        "digests": checked,
        "commands": commands,
        "warnings": warnings,
    }
