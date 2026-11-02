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
"""Step 4 (Apache RAT) and Step 7's `REVIEW` resolution, from what the agent saved."""

from __future__ import annotations

import re
from typing import Any

from release_management.verify_rc.common import VerifyError, VerifyRc, q

_RAT_LINE = re.compile(r"^\s*!\?{5}\s+(\S.*?)\s*$")
_RAT_HEADER = re.compile(r"unapproved licen[cs]es?\s*:?\s*$", re.IGNORECASE)


def unapproved_files(report: str) -> list[str]:
    """Paths RAT lists as having an unapproved or missing licence header.

    Two report shapes are read: the `!????? <path>` lines of the detailed
    listing, and the indented paths under a `Files with unapproved licenses:`
    (older RAT: `Unapproved licenses:`) header, up to the next blank line
    after the first path.
    """
    found: list[str] = []
    lines = report.splitlines()
    for line in lines:
        match = _RAT_LINE.match(line)
        if match:
            found.append(match.group(1))
    for index, line in enumerate(lines):
        if not _RAT_HEADER.search(line.strip()):
            continue
        started = False
        for follow in lines[index + 1 :]:
            text = follow.strip()
            if not text:
                if started:
                    break
                continue
            if text.startswith(("*", "=", "-")) or not follow[:1].isspace():
                break
            started = True
            found.append(text)
    return list(dict.fromkeys(found))


def rat_recipe(v: VerifyRc, unpacked_dir: str | None = None) -> str:
    """The paste-ready RAT run against the unpacked source artefact."""
    source = v.source_artefact
    tree = unpacked_dir or v.unpacked_dir
    unpack = f"unzip {q(source)}" if source.endswith(".zip") else f"tar -xf {q(source)}"
    excludes = v.meta.get("rat_excludes_path") or "<rat-excludes-file>"
    config = v.meta.get("rat_config_path")
    return "\n".join(
        [
            "# Unpack the source artefact first",
            unpack,
            "",
            f"# Run RAT (Maven example; adapt per project build system{'; config: ' + str(config) if config else ''})",
            f"cd {q(tree)} && mvn apache-rat:check -pl .",
            "",
            "# Or standalone jar",
            f"java -jar apache-rat-<ver>.jar -d {q(tree)} -x {q(str(excludes))}",
        ]
    )


def rat(
    v: VerifyRc, *, report: str | None, exit_code: int | None, unpacked_dir: str | None = None
) -> dict[str, Any]:
    """Step 4: RAT exit code and report → PASS / FAIL; RAT config absent → SKIP with a WARN."""
    config, excludes = v.meta.get("rat_config_path"), v.meta.get("rat_excludes_path")
    out: dict[str, Any] = {
        "step": "rat-license-headers",
        "status": None,
        "classification": None,
        "rat_config_path": config,
        "rat_excludes_path": excludes,
        "unapproved_files": [],
        "paste_recipe": rat_recipe(v, unpacked_dir),
    }
    if not config and not excludes:
        return out | {
            "status": "WARN",
            "classification": "SKIP",
            "warning": "release-build.md § Apache RAT configuration is absent: add it; do not proceed to the vote without it",
        }
    files = unapproved_files(report or "")
    # A report naming unapproved files is a FAIL on its own; nothing PASSes without RAT's exit code.
    if exit_code is None and not files:
        return out | {
            "pending": ["run the paste_recipe and pass --exit-code (and --report with RAT's output)"]
        }
    failed = bool(files) or (exit_code is not None and exit_code != 0)
    classification = "FAIL" if failed else "PASS"
    return out | {"status": classification, "classification": classification, "unapproved_files": files}


def _validator_result(raw: str) -> tuple[int, str | None]:
    code, sep, detail = raw.partition(":")
    try:
        return int(code.strip()), (detail.strip() or None) if sep else None
    except ValueError as exc:
        raise VerifyError(f"--validator-result wants CODE[:DETAIL], got {raw!r}") from exc


def source_tree(symlinks: dict[str, Any], results: list[str]) -> dict[str, Any]:
    """Step 7: resolve `release-verify symlinks`' `REVIEW` from the validators' exit codes.

    A tool-computed `FAIL` / `PASS` / `SKIP` is final. Under `REVIEW`, every
    validator that exited non-zero is one `validator_failures` entry and
    makes the step `FAIL`; all zero is `PASS`. `results` are in the order of
    the tool's `validators_to_run`.
    """
    if symlinks.get("step") != "source-tree-integrity":
        raise VerifyError("--symlinks is not the JSON `release-verify symlinks` printed")
    validators = [str(c) for c in symlinks.get("validators_to_run") or []]
    out: dict[str, Any] = {
        "step": "source-tree-integrity",
        "status": symlinks.get("status"),
        "dangling_symlinks": list(symlinks.get("dangling_symlinks") or []),
        "outside_symlinks": list(symlinks.get("outside_symlinks") or []),
        "validator_failures": list(symlinks.get("validator_failures") or []),
        "paste_recipe": symlinks.get("paste_recipe", ""),
    }
    if out["status"] != "REVIEW":
        return out
    if len(results) > len(validators):
        raise VerifyError(f"{len(results)} --validator-result values for {len(validators)} validators")
    failures = []
    for command, raw in zip(validators, results, strict=False):
        code, detail = _validator_result(raw)
        if code != 0:
            failures.append({"validator": command, "detail": detail or f"exited {code}"})
    if len(results) < len(validators) and not failures:
        return out | {"pending": validators[len(results) :]}
    return out | {"status": "FAIL" if failures else "PASS", "validator_failures": failures}
