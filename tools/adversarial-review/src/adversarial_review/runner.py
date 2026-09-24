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
others; each gets a result with a status and a reason.

Output goes to temporary files, not pipes. Reviewer CLIs spawn helpers that
inherit stdout; with pipes, reading to EOF waits for the last helper, so a
finished answer could be lost to the timeout, and a helper that called
`setsid` could outlive any bound. With files, the wait ends when the reviewer
itself exits. The whole process group is then killed, whatever happened, so
no helper is left running and billing.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

from ._util import first_line
from .backends import BACKENDS, BackendOutputError, RunContext
from .findings import Finding, MalformedOutput, normalize_path, parse_findings

STATUSES = ("ok", "unavailable", "error", "timeout", "skipped")
RAW_LIMIT = 2000
# Matched against stderr only: a reviewer's stdout is a review, and a review of
# login code talks about logins.
_AUTH_ERRORS = re.compile(
    r"not logged in|please (?:log ?in|sign ?in|authenticate)|(?:login|authentication) required"
    r"|unauthori[sz]ed|invalid api key|set an auth method|re-?authenticate",
    re.I,
)

_live_groups: set[int] = set()
_live_lock = threading.Lock()


@dataclass
class ReviewerResult:
    reviewer: str
    status: str
    findings: list[Finding] = field(default_factory=list)
    reason: str = ""
    seconds: float = 0.0
    raw: str = ""


def _kill_group(pgid: int) -> None:
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(pgid, signal.SIGKILL)


def terminate_all() -> None:
    """Kill every reviewer process group still running (for signal handlers)."""
    with _live_lock:
        groups = list(_live_groups)
    for pgid in groups:
        _kill_group(pgid)


def _execute(
    argv: list[str], stdin: str | None, timeout_s: float, cwd: os.PathLike[str] | str, env: Mapping[str, str]
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="adversarial-review-io-") as tmp:
        io_dir = Path(tmp)
        (io_dir / "stdin").write_text(stdin or "", encoding="utf-8")
        with (
            open(io_dir / "stdin", encoding="utf-8") as fin,
            open(io_dir / "stdout", "w", encoding="utf-8") as fout,
            open(io_dir / "stderr", "w", encoding="utf-8") as ferr,
        ):
            proc = subprocess.Popen(
                argv, stdin=fin, stdout=fout, stderr=ferr, cwd=cwd, env=dict(env), start_new_session=True
            )
            with _live_lock:
                _live_groups.add(proc.pid)
            try:
                proc.wait(timeout=timeout_s)
            finally:
                _kill_group(proc.pid)
                with _live_lock:
                    _live_groups.discard(proc.pid)
                with contextlib.suppress(subprocess.TimeoutExpired):
                    proc.wait(timeout=5)
        out = (io_dir / "stdout").read_text(encoding="utf-8", errors="replace")
        err = (io_dir / "stderr").read_text(encoding="utf-8", errors="replace")
    return subprocess.CompletedProcess(argv, proc.returncode, out, err)


def run_one(name: str, ctx: RunContext, timeout_s: float, env: Mapping[str, str]) -> ReviewerResult:
    backend = BACKENDS[name]
    inv = backend.build(ctx)
    path = shutil.which(inv.argv[0], path=env.get("PATH", ""))
    if path is None:
        return ReviewerResult(name, "unavailable", reason="not on PATH")
    start = time.monotonic()
    try:
        proc = _execute([path, *inv.argv[1:]], inv.stdin, timeout_s, ctx.repo_dir, env)
    except subprocess.TimeoutExpired:
        return ReviewerResult(
            name, "timeout", reason=f"no answer within {timeout_s:g}s", seconds=time.monotonic() - start
        )
    except OSError as exc:
        return ReviewerResult(name, "unavailable", reason=f"cannot execute: {exc}")
    seconds = time.monotonic() - start
    if proc.returncode != 0:
        detail = first_line(proc.stderr) or first_line(proc.stdout) or "(no output)"
        status = "unavailable" if _AUTH_ERRORS.search(proc.stderr) else "error"
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
        findings, problems = parse_findings(text, name)
    except (BackendOutputError, MalformedOutput) as exc:
        return ReviewerResult(
            name, "error", reason=f"malformed output: {exc}", seconds=seconds, raw=text[:RAW_LIMIT]
        )
    findings = [normalize_path(f, ctx.repo_dir) for f in findings]
    if problems:
        reason = f"skipped {len(problems)} malformed finding(s): " + "; ".join(problems[:3])
        return ReviewerResult(name, "ok", findings, reason=reason, seconds=seconds, raw=text[:RAW_LIMIT])
    return ReviewerResult(name, "ok", findings=findings, seconds=seconds)


def run_all(
    names: Sequence[str], contexts: Mapping[str, RunContext], timeout_s: float, env: Mapping[str, str]
) -> list[ReviewerResult]:
    if not names:
        return []
    with ThreadPoolExecutor(max_workers=len(names)) as pool:
        futures = {n: pool.submit(run_one, n, contexts[n], timeout_s, env) for n in names}
        return [futures[n].result() for n in names]
