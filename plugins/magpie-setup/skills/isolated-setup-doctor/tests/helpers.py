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
"""Shared test helpers for isolated-setup-doctor probe tests."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


def find_bash() -> str | None:
    """Finds a functional bash executable, preferring Git Bash over WSL on Windows."""
    if os.name == "nt":
        for candidate in [
            Path("C:/Program Files/Git/bin/bash.exe"),
            Path("C:/Program Files/Git/usr/bin/bash.exe"),
            Path("C:/Program Files (x86)/Git/bin/bash.exe"),
        ]:
            if candidate.is_file():
                return str(candidate)
        w = shutil.which("bash")
        if w and "system32" not in w.lower():
            return w
        return None
    return shutil.which("bash") or "bash"


def to_posix(path: Path | str) -> str:
    """Converts a Path or path string to POSIX format, converting Windows drive letters."""
    s = Path(path).as_posix()
    if os.name == "nt" and len(s) >= 2 and s[1] == ":":
        return f"/{s[0].lower()}{s[2:]}"
    return s


def run_probe_script(
    probe_path: Path,
    env_vars: dict[str, str],
    bin_dir: Path | None = None,
    cwd: Path | None = None,
) -> str:
    """Runs a probe script with proper PATH, POSIX paths, and UTF-8 encoding."""
    bash = find_bash()
    if not bash:
        raise RuntimeError("bash not found")

    # A minimal base, not the host environment: the host's CONTAINER_HOST /
    # DOCKER_HOST, or a gateway running on this machine, must not decide a test.
    keep = ["PATH", "HOME", "LANG", "LC_ALL", "TMPDIR"]
    if os.name == "nt":
        keep += ["SYSTEMROOT", "COMSPEC", "PATHEXT", "TEMP", "TMP", "USERPROFILE"]
    env = {name: os.environ[name] for name in keep if name in os.environ}
    env.update(env_vars)

    if bin_dir is not None:
        env["PATH"] = f"{bin_dir}{os.pathsep}{env.get('PATH', '')}"

    if os.name == "nt":
        probe_posix = to_posix(probe_path)
        if bin_dir is not None:
            bin_posix = to_posix(bin_dir)
            cmd = f'export PATH="{bin_posix}:$PATH"; bash "{probe_posix}"'
        else:
            cmd = f'bash "{probe_posix}"'
        args = [bash, "-c", cmd]
    else:
        args = [bash, str(probe_path)]

    res = subprocess.run(
        args,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        cwd=cwd,
    )
    return res.stdout
