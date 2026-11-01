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
"""Step 6b: gate, recipe and classification of the `maven-artifact-verify` report."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from release_management.verify_rc.common import VerifyError, VerifyRc, dq

MAVEN_VERIFY = "uv run --project <framework>/tools/maven-artifact-verify"
PODLING_MARKERS = ("DISCLAIMER", "DISCLAIMER-WIP")
_POM_CHECKS = ("check1", "check2")
_TOOL_STATUSES = ("PASS", "WARN", "FAIL", "SKIP")
#: The `pending` entry when nothing says what Step 1 staged.
NAMES_PENDING = (
    "pass --inventory <inventory.json> (Step 1's saved `release-verify inventory` JSON) "
    "or --staged-dir <local staging copy>: without a listing the JVM gate cannot be decided"
)


def is_jvm(names: list[str]) -> bool:
    """Whether the Step 1 listing holds at least one `.jar` or `.pom`."""
    return any(n.endswith((".jar", ".pom")) for n in names)


def staged_names(inventory: Any, staged_dir: str | None) -> list[str] | None:
    """Every staged filename: Step 1's `found` and `unexpected`, plus a local listing when given.

    `None` when neither was supplied, so the caller reports it pending rather
    than a confident `SKIP`; an inventory that is not Step 1's JSON, or a
    `staged_dir` that is not a directory, is a `VerifyError`.
    """
    if inventory is None and not staged_dir:
        return None
    names: list[str] = []
    if inventory is not None:
        if not isinstance(inventory, dict) or inventory.get("step") != "inventory":
            raise VerifyError("--inventory is not the JSON `release-verify inventory` printed")
        names += [str(n) for n in inventory.get("found") or []]
        names += [str(n) for n in inventory.get("unexpected") or []]
    if staged_dir:
        if not Path(staged_dir).is_dir():
            raise VerifyError(f"--staged-dir {staged_dir!r} is not a directory")
        names += sorted(p.name for p in Path(staged_dir).iterdir() if p.is_file())
    return list(dict.fromkeys(names))


def podling(tree: str | None) -> bool:
    """The podling signal: a `DISCLAIMER` or `DISCLAIMER-WIP` at the unpacked source root."""
    return bool(tree) and any((Path(str(tree)) / m).is_file() for m in PODLING_MARKERS)


def digest_set(v: VerifyRc) -> list[str]:
    """`jvm_digest_set` when set, otherwise the § Digest set (default `sha512`)."""
    return [str(d).lower() for d in v.meta.get("jvm_digest_set") or []] or v.digests or ["sha512"]


def recipe(v: VerifyRc, staged_dir: str, *, is_podling: bool, companions: list[str]) -> str:
    flags = f"--digests {','.join(digest_set(v))}" + (" --podling" if is_podling else "")
    lines = [
        f"{MAVEN_VERIFY} \\",
        f"  maven-artifact-verify {dq(staged_dir)} {flags}",
        "# without uv:",
        "# python3 <framework>/tools/maven-artifact-verify/src/maven_artifact_verify/__init__.py ...",
    ]
    if companions:
        lines += ["", "# Companion signatures (same KEYS flow as Step 2):"]
        lines += [f"gpg --verify {dq(c + '.asc')} {dq(c)}" for c in companions]
    return "\n".join(lines)


def _signed_companions(report: dict[str, Any], staged_dir: str) -> list[str]:
    """Companions whose `.asc` is staged: a companion with no `.asc` is already a finding."""
    out: list[str] = []
    local = Path(staged_dir)
    for jar in report.get("jars") or []:
        for comp in jar.get("companions") or []:
            name = str(comp.get("companion") or "")
            if not name or name == jar.get("jar") or comp.get("classification") == "ABSENT":
                continue
            if local.is_dir():
                if (local / f"{name}.asc").is_file():
                    out.append(name)
                continue
            detail = str(comp.get("detail") or "")
            if comp.get("classification") == "PASS" or (
                ".asc" not in detail and "missing companion" not in detail
            ):
                out.append(name)
    return out


def _pom_findings(report: dict[str, Any]) -> list[str]:
    out: list[str] = []
    for pom in report.get("poms") or []:
        label = pom.get("pom")
        for check in _POM_CHECKS:
            results = pom.get(check) or {}
            for key, status in results.items():
                if key.endswith("_detail") or status in (None, "PASS", "SKIP"):
                    continue
                detail = results.get(f"{key}_detail") or ""
                if status == "FAIL":
                    out.append(f"{label}: {detail}" if detail else f"{label}: {check} {key} FAIL")
                else:
                    out.append(f"{label}: {check} {key} {status}" + (f" — {detail}" if detail else ""))
    return out


def _companion_findings(report: dict[str, Any], location: str) -> tuple[list[str], bool]:
    """Non-passing companion checks, and whether an `ABSENT` jar fails under `staged`."""
    out: list[str] = []
    absent_fails = False
    absent: list[str] = []
    for jar in report.get("jars") or []:
        for comp in jar.get("companions") or []:
            classification = comp.get("classification")
            if classification in (None, "PASS"):
                continue
            name = comp.get("companion") or jar.get("jar")
            if classification == "ABSENT":
                absent.append(str(name))
                if location == "staged":
                    absent_fails = True
                    out.append(
                        f"{name} is declared by a staged POM but not staged locally (ABSENT); "
                        "jvm_companion_location: staged — the RC was expected to stage it, a FAIL"
                    )
                else:
                    out.append(
                        f"{name} is declared by a staged POM but not staged locally (ABSENT); "
                        f"jvm_companion_location: {location} — an observation, not a failure"
                    )
                continue
            detail = comp.get("detail") or classification
            out.append(f"{name}: {detail}")
    for finding in report.get("findings") or []:
        text = str(finding)
        if any(text.startswith(f"{name} ") for name in absent):
            continue
        out.append(text)
    return out, absent_fails


def _observations(report: dict[str, Any]) -> list[str]:
    obs = report.get("observations") or {}
    out: list[str] = []
    for item in obs.get("timestamp_signal") or []:
        counts = ""
        if item.get("entries") is not None and item.get("distinct_timestamps") is not None:
            counts = f" ({item['distinct_timestamps']} distinct across {item['entries']} entries)"
        out.append(f"{item.get('jar')}: {item.get('signal')}{counts} - {item.get('detail')}")
    for item in obs.get("namespace_signal") or []:
        if item.get("signal") == "unreadable":
            out.append(f"{item.get('jar')}: unreadable - {item.get('detail')}")
            continue
        under = item.get("under_org_apache")
        where = (
            "is under org.apache.*"
            if under
            else "is NOT under org.apache.* (informational even for ASF projects - "
            "published coordinates cannot be renamed retroactively)"
        )
        out.append(f"{item.get('jar')}: groupId {item.get('group_id')} {where}; {item.get('detail')}")
    for item in obs.get("companion_content") or []:
        out.append(f"{item.get('jar')}: {item.get('signal')} - {item.get('detail')}")
    return out


def jvm(
    v: VerifyRc,
    *,
    names: list[str] | None,
    tree: str | None,
    staged_dir: str | None,
    report_text: str | None,
) -> dict[str, Any]:
    """Step 6b's gate, recipe and — given the tool report — its JSON contract."""
    base: dict[str, Any] = {
        "step": "jvm-artefacts",
        "status": None,
        "tool_report": None,
        "pom_findings": [],
        "companion_findings": [],
        "observations": [],
        "paste_recipe": "",
    }
    if str(v.meta.get("jvm_artefact_checks") or "on") == "off":
        return base | {
            "status": "SKIP",
            "skip_reason": "release-build.md § JVM artefact checks declares jvm_artefact_checks: off",
            "paste_recipe": "# Step 6b skipped: jvm_artefact_checks: off",
        }
    if names is None:
        return base | {"pending": [NAMES_PENDING]}
    if not is_jvm(names):
        return base | {
            "status": "SKIP",
            "skip_reason": "the Step 1 listing holds no .jar and no .pom",
            "paste_recipe": "# Step 6b skipped: no .jar or .pom staged",
        }
    staged = staged_dir or "<staged-dir>"
    report = json.loads(report_text) if report_text is not None else None
    if report is not None and (not isinstance(report, dict) or report.get("status") not in _TOOL_STATUSES):
        raise VerifyError(
            "--report is not maven-artifact-verify's JSON report (no PASS / WARN / FAIL / SKIP status)"
        )
    # The podling signal is read from the unpacked tree; without one, the report's own flag stands.
    is_podling = podling(tree) if tree else bool(report and report.get("podling"))
    if report is None or report_text is None:
        pending = ["run the paste_recipe and pass --report with maven-artifact-verify's JSON"]
        if not tree:
            pending.insert(
                0, "pass --tree <unpacked-dir> so --podling is decided from DISCLAIMER / DISCLAIMER-WIP"
            )
        return base | {
            "paste_recipe": recipe(v, staged, is_podling=is_podling, companions=[]),
            "podling": is_podling,
            "pending": pending,
        }
    location = str(v.meta.get("jvm_companion_location") or "nexus-staging")
    companions, absent_fails = _companion_findings(report, location)
    status = report.get("status")
    if absent_fails and status != "SKIP":
        status = "FAIL"
    return base | {
        "status": status,
        "tool_report": report_text.strip(),
        "pom_findings": _pom_findings(report),
        "companion_findings": companions,
        "observations": _observations(report),
        "paste_recipe": recipe(
            v, staged, is_podling=is_podling, companions=_signed_companions(report, staged)
        ),
    }
