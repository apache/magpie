#
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
"""
Which reviewer CLIs are installed, and which harness is running this tool.

A probe is `<cli> --version`, which makes no model call. So `detect` cannot know
whether a CLI is logged in; `run` reports that when the CLI fails for auth.
"""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass

from ._util import first_line
from .backends import BACKENDS


@dataclass(frozen=True)
class Detection:
    name: str
    path: str | None
    version: str | None
    available: bool
    is_self: bool
    reason: str


def running_harness(env: Mapping[str, str]) -> str | None:
    for backend in BACKENDS.values():
        for var, want in backend.self_markers:
            value = env.get(var)
            if value and (want is None or value == want):
                return backend.name
    return None


def resolve_self(override: str | None, env: Mapping[str, str]) -> str | None:
    if override is None:
        return running_harness(env)
    if override == "none":
        return None
    if override in BACKENDS:
        return override
    raise ValueError(f"unknown harness {override!r}; expected one of {', '.join(BACKENDS)} or 'none'")


def detect(env: Mapping[str, str], self_name: str | None, probe_timeout: float = 15.0) -> list[Detection]:
    rows: list[Detection] = []
    for name in BACKENDS:
        is_self = name == self_name
        path = shutil.which(name, path=env.get("PATH", ""))
        if path is None:
            rows.append(Detection(name, None, None, False, is_self, "not on PATH"))
            continue
        try:
            proc = subprocess.run(
                [path, "--version"], capture_output=True, text=True, timeout=probe_timeout, env=dict(env)
            )
        except subprocess.TimeoutExpired:
            rows.append(Detection(name, path, None, False, is_self, "`--version` timed out"))
            continue
        except OSError as exc:
            rows.append(Detection(name, path, None, False, is_self, f"cannot execute: {exc}"))
            continue
        if proc.returncode != 0:
            detail = first_line(proc.stderr) or first_line(proc.stdout) or "(no output)"
            reason = f"`--version` failed (exit {proc.returncode}): {detail}"
            rows.append(Detection(name, path, None, False, is_self, reason))
            continue
        rows.append(Detection(name, path, first_line(proc.stdout), True, is_self, ""))
    return rows
