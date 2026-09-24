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
Run reviewers in parallel, each in its own process group with a timeout.

A reviewer that is missing, not logged in, slow, or incoherent never stops the
others; each gets a result with a status and a reason. On timeout the whole
process group is killed: reviewer CLIs spawn helpers that inherit stdout, and
killing only the direct child would leave `communicate()` waiting on them.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import signal
import subprocess
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field

from ._util import first_line
from .backends import BACKENDS, BackendOutputError, RunContext
from .findings import Finding, MalformedOutput, parse_findings

STATUSES = ("ok", "unavailable", "error", "timeout", "skipped")
RAW_LIMIT = 2000
_AUTH_HINTS = re.compile(
    r"not logged in|log ?in\b|authentication|authenticate|unauthori[sz]ed|\b401\b|credential", re.I
)


@dataclass
class ReviewerResult:
    reviewer: str
    status: str
    findings: list[Finding] = field(default_factory=list)
    reason: str = ""
    seconds: float = 0.0
    raw: str = ""


def _communicate(
    argv: list[str], stdin: str | None, timeout_s: float, cwd: os.PathLike[str] | str, env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    proc = subprocess.Popen(
        argv,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=cwd,
        env=dict(env),
        start_new_session=True,
    )
    try:
        out, err = proc.communicate(stdin, timeout=timeout_s)
    except subprocess.TimeoutExpired:
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def run_one(name: str, ctx: RunContext, timeout_s: float, env: Mapping[str, str]) -> ReviewerResult:
    backend = BACKENDS[name]
    inv = backend.build(ctx)
    path = shutil.which(inv.argv[0], path=env.get("PATH", ""))
    if path is None:
        return ReviewerResult(name, "unavailable", reason="not on PATH")
    start = time.monotonic()
    try:
        proc = _communicate([path, *inv.argv[1:]], inv.stdin, timeout_s, ctx.repo_dir, env)
    except subprocess.TimeoutExpired:
        return ReviewerResult(
            name, "timeout", reason=f"no answer within {timeout_s:g}s", seconds=time.monotonic() - start
        )
    except OSError as exc:
        return ReviewerResult(name, "unavailable", reason=f"cannot execute: {exc}")
    seconds = time.monotonic() - start
    if proc.returncode != 0:
        detail = first_line(proc.stderr) or first_line(proc.stdout) or "(no output)"
        status = "unavailable" if _AUTH_HINTS.search(proc.stderr + proc.stdout) else "error"
        return ReviewerResult(
            name,
            status,
            reason=f"exit {proc.returncode}: {detail}",
            seconds=seconds,
            raw=(proc.stderr or proc.stdout)[:RAW_LIMIT],
        )
    text = proc.stdout
    try:
        text = backend.extract(proc.stdout, ctx)
        findings = parse_findings(text, name)
    except (BackendOutputError, MalformedOutput) as exc:
        return ReviewerResult(
            name, "error", reason=f"malformed output: {exc}", seconds=seconds, raw=text[:RAW_LIMIT]
        )
    return ReviewerResult(name, "ok", findings=findings, seconds=seconds)


def run_all(
    names: Sequence[str], contexts: Mapping[str, RunContext], timeout_s: float, env: Mapping[str, str]
) -> list[ReviewerResult]:
    if not names:
        return []
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        futures = {n: pool.submit(run_one, n, contexts[n], timeout_s, env) for n in names}
        return [futures[n].result() for n in names]
