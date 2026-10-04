#!/usr/bin/env python3
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
"""Compute the next development version for each configured version file.

Usage::

    next_dev_version.py --version 2.11.0 --config <release-management-config.md> [<file> ...]

``--config`` is the resolved ``release-management-config.md``; the script
reads its ``version_manifest_files`` key (table row or ``key: a, b`` line).
With no ``<file>`` arguments it reports on exactly those files; any
``<file>`` passed that is not one of them is reported as not configured.
``--version-files a,b`` names the list directly instead of ``--config``.

The default convention bumps the minor version and resets the patch:

- Python packaging (``pyproject.toml``, ``setup.cfg``, ``setup.py``, and a
  ``*.py`` file only when it is a configured version file) ->
  ``X.(Y+1).0.dev0``;
- Maven ``pom.xml`` -> ``X.(Y+1).0-SNAPSHOT``;
- ``Cargo.toml``, any other format, and any file that is not a configured
  version file -> no value; ``needs_rm_confirmation`` is true and the
  Release Manager supplies or confirms the string.

A project with another convention (a patch bump, say) has the RM supply the
next version in the conversation. Exit 0 on success, 2 on bad input.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

VERSION_RE = re.compile(r"^(\d+)\.(\d+)(?:\.(\d+))?(?:[.-]?post\d+)?$")
KEY = "version_manifest_files"
PYTHON_NAMES = ("pyproject.toml", "setup.cfg", "setup.py")


def _norm(path: str) -> str:
    return str(PurePosixPath(path.strip().strip("`").removeprefix("./")))


def _split_values(raw: str) -> list[str]:
    ticked = re.findall(r"`([^`]+)`", raw)
    values = ticked if ticked else [v for v in re.split(r"[,\s]+", raw) if v]
    return [_norm(v) for v in values if v.strip()]


def configured_files(config_text: str) -> list[str]:
    """``version_manifest_files`` from a release-management-config.md."""
    for line in config_text.splitlines():
        if KEY not in line:
            continue
        stripped = line.strip()
        if stripped.startswith("|"):
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) >= 2 and cells[0].strip("`") == KEY:
                return _split_values(cells[1])
        else:
            m = re.match(rf"^[-*\s]*`?{KEY}`?\s*:\s*(.+)$", stripped)
            if m:
                return _split_values(m.group(1).strip("[]"))
    raise ValueError(f"{KEY} not found in the config file")


def manifest_format(path: str, configured: bool) -> str:
    name = PurePosixPath(path).name
    if not configured:
        return "unknown"
    if name in PYTHON_NAMES or name.endswith(".py"):
        return "python"
    if name == "pom.xml":
        return "maven"
    if name == "Cargo.toml":
        return "cargo"
    return "unknown"


def next_versions(version: str, configured: list[str], files: list[str] | None = None) -> dict[str, Any]:
    match = VERSION_RE.match(version.strip())
    if not match:
        raise ValueError(f"--version {version!r} is not an X.Y[.Z] release version")
    if not configured:
        raise ValueError(f"{KEY} is empty")
    base = f"{match.group(1)}.{int(match.group(2)) + 1}.0"
    wanted = {_norm(c) for c in configured}
    out_files = []
    for path in files or configured:
        is_configured = _norm(path) in wanted
        fmt = manifest_format(path, is_configured)
        proposed = {"python": f"{base}.dev0", "maven": f"{base}-SNAPSHOT"}.get(fmt)
        out_files.append(
            {
                "file": path,
                "configured": is_configured,
                "format": fmt,
                "next_dev_version": proposed,
                "needs_rm_confirmation": proposed is None,
            }
        )
    return {
        "current_version": version.strip(),
        "files": out_files,
        "not_configured": [f["file"] for f in out_files if not f["configured"]],
        "needs_rm_confirmation": any(f["needs_rm_confirmation"] for f in out_files),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--version", required=True, help="the version just released")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--config", help=f"resolved release-management-config.md carrying {KEY}")
    source.add_argument("--version-files", help=f"comma-separated {KEY}, instead of --config")
    parser.add_argument("files", nargs="*", help=f"files to report on; defaults to {KEY}")
    args = parser.parse_args(argv)
    try:
        if args.config:
            configured = configured_files(Path(args.config).read_text(encoding="utf-8"))
        else:
            configured = _split_values(args.version_files)
        out = next_versions(args.version, configured, args.files)
    except (OSError, ValueError) as exc:
        print(json.dumps({"error": str(exc)}))
        return 2
    print(json.dumps(out, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
