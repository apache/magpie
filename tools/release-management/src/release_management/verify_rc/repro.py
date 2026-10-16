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
"""Step 9: whether it runs, its recipe, and the status roll-up from `repro-archive` JSON.

Inputs are what the voter's own run printed: `repro-archive check --json`
(a list of `{name, status, detail}`), `repro-archive compare --json` (the
`Comparison`), the commit the tag resolved to, and one result per
convenience artefact. Nothing here rebuilds, compares or runs anything.
"""

from __future__ import annotations

import re
from typing import Any

from release_management.verify_rc.common import VerifyError, VerifyRc, dq

REPRO = "uv run --project <framework>/tools/reproducible-archive repro-archive"
MODES = ("off", "documented-divergence", "byte-identical")  # weakest → strictest
_SWHID_DIR = re.compile(r"swh:1:dir:[0-9a-f]{40}")


def swhid_core(value: str | None) -> str | None:
    """The bare `swh:1:dir:<hash>`: qualifiers (`;origin=…;anchor=…`) are ignored."""
    if not value:
        return None
    match = _SWHID_DIR.search(value)
    return match.group(0) if match else value.split(";", 1)[0].strip()


def plan(v: VerifyRc, *, skip_repro: bool) -> dict[str, Any]:
    """Whether Step 9 runs: `mandatory` under automated signing, where `--skip-repro` is ignored."""
    mandatory = v.ci_automated
    source_on = str(v.meta.get("reproducibility_source") or "off") == "on"
    entries = v.convenience()
    binaries_on = str(v.meta.get("reproducibility_binaries") or "off") != "off" or any(
        e["reproducibility"] != "off" for e in entries
    )
    enabled = source_on or binaries_on or mandatory
    skipped = not enabled or (skip_repro and not mandatory)
    reason = None
    if not enabled:
        reason = "reproducibility_source is off and no convenience artefact is checked"
    elif skipped:
        reason = "--skip-repro was passed"
    return {
        "mandatory": mandatory,
        "skipped": skipped,
        "skip_reason": reason,
        "skip_repro_ignored": bool(skip_repro and mandatory),
        # Automated signing requires the source check, whatever reproducibility_source says.
        "source_enabled": not skipped and (source_on or mandatory),
        "binaries_enabled": not skipped and binaries_on,
    }


def recipe(v: VerifyRc, *, clone: str, remote: str, staged_dir: str, mandatory: bool) -> str:
    source = v.source_artefact
    tag = v.rc_tag
    fmt = v.meta.get("source_archive_format") or "tar.gz"
    prefix = v.meta.get("source_archive_prefix") or ""
    lines = [
        "# 1. The tag resolves to the commit recorded on the planning issue",
        f"git -C {clone} fetch --tags {remote}",
        f'git -C {clone} rev-parse "{tag}^{{commit}}"          # expect: <recorded commit>',
        f'git -C {clone} tag -v "{tag}"                       # signed tag verifies against KEYS',
        "",
        "# 2. The staged archive satisfies every reproducible-builds.org rule, and its content is the recorded tree",
        f"{REPRO} check --json \\",
        f'  {dq(source)} --epoch "<recorded SOURCE_DATE_EPOCH>" \\',
        '  --swhid "<recorded swh:1:dir:…>"',
        "",
    ]
    if v.meta.get("source_archive_method") == "custom":
        lines += [
            "# 3. Re-run the adopter's build_command at the tag under the recorded epoch, then compare",
            f'git -C {clone} checkout "{tag}"',
            'export SOURCE_DATE_EPOCH="<recorded SOURCE_DATE_EPOCH>"',
            f"( cd {clone} && {v.meta.get('build_command') or '<build_command>'} )",
            "# <build-output>: the directory build_command writes the source artefact to, inside the clone",
            "mkdir -p rebuilt",
            f'cp "{clone}/<build-output>/{source}" "rebuilt/{source}"',
        ]
    else:
        lines += [
            "# 3. Rebuild from the tag with the recorded epoch, prefix and format, then compare",
            f"{REPRO} build \\",
            f'  --repo {clone} --ref "{tag}" --format {fmt} \\',
            f'  --prefix "{prefix}" --epoch "<recorded SOURCE_DATE_EPOCH>" \\',
            f"  -o rebuilt/{source}",
        ]
    lines.append(
        f"{REPRO} compare --json {dq(source)} rebuilt/{source}"
        + (" --require-identical" if mandatory else "")
    )
    entries = [e for e in v.convenience() if e["reproducibility"] != "off"]
    if entries:
        lines += [
            "",
            "# Convenience artefacts: rebuild each from the tag and compare",
            'export SOURCE_DATE_EPOCH="<recorded SOURCE_DATE_EPOCH>"',
            f'git -C {clone} checkout "{tag}"',
        ]
        for e in entries:
            name = e["name"]
            lines += [f"( cd {clone} && {e.get('build_command') or '<build_command>'} )"]
            if e.get("staging") == "registry-staging":
                lines.append(
                    f"# {name}: pull the staged image by digest and compare it with the local rebuild; say which digest was pulled"
                )
            elif e["reproducibility"] == "documented-divergence":
                lines.append(
                    f'{e.get("verification_command") or "<verification_command>"} "{staged_dir}/{name}" "{clone}/<build-output>/{name}"'
                )
            else:
                lines.append(
                    f'cmp "{staged_dir}/{name}" "{clone}/<build-output>/{name}" \\\n'
                    f'  && echo "identical: {name}" || echo "DIFFERS: {name}"'
                )
    return "\n".join(lines)


def _binary_results(values: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for raw in values:
        name, sep, result = raw.rpartition("=")
        if not sep or not name:
            raise VerifyError(f"--binary wants NAME=identical|differs|known:<pattern>, got {raw!r}")
        out[name.strip()] = result.strip()
    return out


def _known(entry: dict[str, Any], pattern: str) -> bool:
    """Whether `pattern` names one of the entry's `known_divergences`.

    Case-folded exact match against the whole entry or its key (the text before
    the first `:`); an empty pattern or key never matches, so an unlisted
    divergence cannot be downgraded from FAIL to WARN by a substring.
    """
    wanted = pattern.strip().casefold()
    if not wanted:
        return False
    for known in entry.get("known_divergences") or []:
        text = str(known).strip().casefold()
        key = text.split(":", 1)[0].strip()
        if wanted in {c for c in (text, key) if c}:
            return True
    return False


def binaries(v: VerifyRc, results: list[str], enabled: bool) -> dict[str, Any]:
    """Per artefact by its own mode: `byte-identical` any difference FAILs;
    `documented-divergence` a listed known divergence WARNs, anything else FAILs;
    `off` is a SKIP stated as published on trust."""
    entries = v.convenience()
    given = _binary_results(results)
    in_use = [e["reproducibility"] for e in entries if e["reproducibility"] != "off"]
    mode = max(in_use, key=MODES.index) if in_use else str(v.meta.get("reproducibility_binaries") or "off")
    out: dict[str, Any] = {"mode": mode, "identical": [], "differs": [], "known_divergences_hit": []}
    notes: list[str] = []
    pending: list[str] = []
    for e in entries:
        name = e["name"]
        if e["reproducibility"] == "off" or not enabled:
            notes.append(f"{name}: SKIP — reproducibility off; it is being published on trust")
            continue
        result = given.get(name)
        if result is None:
            pending.append(name)
        elif result.lower() == "identical":
            out["identical"].append(name)
        elif result.lower().startswith("known:") and e["reproducibility"] == "documented-divergence":
            pattern = result.split(":", 1)[1].strip()
            if _known(e, pattern):
                out["known_divergences_hit"].append(f"{name}: {pattern}")
            else:
                out["differs"].append(name)
                notes.append(f"{name}: divergence {pattern!r} is not among its known_divergences — FAIL")
        else:
            out["differs"].append(name)
    unknown = sorted(set(given) - {e["name"] for e in entries})
    if unknown:
        notes.append(
            f"--binary for an artefact § Convenience artefacts does not declare: {', '.join(unknown)}"
        )
    return {"binaries": out, "notes": notes, "pending": pending}


def _check_failures(check: list[dict[str, Any]] | None) -> tuple[list[str], str | None, bool | None]:
    """(rule failures other than swhid, swhid computed by check, swhid check passed)."""
    if not check:
        return [], None, None
    failures = [str(r.get("name")) for r in check if r.get("status") == "FAIL" and r.get("name") != "swhid"]
    swhid = next((r for r in check if r.get("name") == "swhid"), None)
    computed = swhid_core(str(swhid.get("detail") or "")) if swhid else None
    return failures, computed, (swhid.get("status") == "PASS") if swhid else None


def reproducibility(
    v: VerifyRc,
    *,
    skip_repro: bool,
    trusted_hardware: bool,
    recorded_commit: str | None,
    tag_commit: str | None,
    recorded_swhid: str | None,
    atr_swhid: str | None,
    epoch: int | None,
    check: list[dict[str, Any]] | None,
    compare: dict[str, Any] | None,
    binary_results: list[str],
    clone: str = "<upstream-clone>",
    remote: str = "<remote>",
    staged_dir: str = "<staged-dir>",
) -> dict[str, Any]:
    """Step 9's JSON contract."""
    p = plan(v, skip_repro=skip_repro)
    mandatory = p["mandatory"]
    fails: list[str] = []
    warns: list[str] = []
    pending: list[str] = []
    notes: list[str] = []
    if p["skip_repro_ignored"]:
        notes.append("--skip-repro ignored: automated_release_signing is enabled, so Step 9 is mandatory")
    rule_failures, check_swhid, check_swhid_passed = _check_failures(check)
    computed = check_swhid or swhid_core((compare or {}).get("swhid_a"))
    source: dict[str, Any] = {
        "enabled": p["source_enabled"],
        "verdict": None,
        "recorded_commit": recorded_commit,
        "source_date_epoch": epoch,
        "swhid_dir": computed,
        "swhid_matches": None,
        "rule_failures": rule_failures,
        "metadata_differences": [],
        "content_differences": [],
    }
    if p["source_enabled"]:
        if tag_commit and recorded_commit and tag_commit.strip().lower() != recorded_commit.strip().lower():
            source["verdict"] = "tag-moved"
            fails.append(
                f"tag moved: {v.rc_tag} resolves to {tag_commit}, the planning issue recorded {recorded_commit}"
            )
        elif compare is None:
            pending.append("--compare: what repro-archive compare --json printed")
        else:
            verdict = str(compare.get("verdict"))
            if verdict not in ("identical", "content-identical", "differs"):
                raise VerifyError(
                    f"--compare verdict {verdict!r} is not identical / content-identical / differs"
                )
            source["verdict"] = verdict
            source["metadata_differences"] = list(compare.get("metadata_differences") or [])
            source["content_differences"] = [
                f"{kind} {path}"
                for kind in ("added", "removed", "changed")
                for path in compare.get(kind) or []
            ]
            if verdict == "differs":
                fails.append("source differs: the artefact is not the tagged tree")
            elif verdict == "content-identical":
                (fails if mandatory else warns).append(
                    "source content-identical: archive metadata differs"
                    + (
                        " — automated signing requires bit-by-bit identity"
                        if mandatory
                        else " — the RM did not build with repro-archive build"
                    )
                )
        if recorded_commit is None:
            pending.append("--recorded-commit: the commit release-rc-cut recorded on the planning issue")
        elif tag_commit is None:
            pending.append('--tag-commit: what git rev-parse "<rc-tag>^{commit}" printed')
        # The check report and the recorded epoch are evidence in their own
        # right (the rules check runs against the epoch; the rebuild uses it):
        # an identical comparison alone never makes the step PASS.
        if epoch is None:
            pending.append("--epoch: the SOURCE_DATE_EPOCH release-rc-cut recorded on the planning issue")
        if not check:
            pending.append("--check: what repro-archive check --json printed")
        recorded = [s for s in (swhid_core(recorded_swhid), swhid_core(atr_swhid)) if s]
        if recorded and computed:
            source["swhid_matches"] = all(r == computed for r in recorded)
            if not source["swhid_matches"]:
                fails.append(f"content {computed} is not the recorded {', '.join(recorded)}")
        elif check_swhid_passed is not None:
            source["swhid_matches"] = check_swhid_passed
            if not check_swhid_passed:
                fails.append(f"content {computed} is not the SWHID repro-archive check was given")
        elif computed and not recorded:
            notes.append(
                f"the planning issue records no SWHID: the staged archive's content is {computed} — the RM can add it"
            )
        if rule_failures:
            (fails if mandatory else warns).append(
                f"repro-archive check rule failures: {', '.join(rule_failures)}"
            )
    bins = binaries(v, binary_results, p["binaries_enabled"])
    notes += bins["notes"]
    if p["binaries_enabled"]:
        pending += [f"--binary {name}=…" for name in bins["pending"]]
        if bins["binaries"]["differs"]:
            fails.append(
                f"convenience artefact(s) did not reproduce: {', '.join(bins['binaries']['differs'])}"
            )
        if bins["binaries"]["known_divergences_hit"]:
            warns.append("documented divergences: " + "; ".join(bins["binaries"]["known_divergences_hit"]))
    if p["skipped"]:
        status: str | None = "SKIP"
        notes.append(f"Step 9 skipped: {p['skip_reason']}")
    elif fails:
        status = "FAIL"
    elif pending:
        status = None
    elif warns:
        status = "WARN"
    else:
        status = "PASS"
    out: dict[str, Any] = {
        "step": "reproducibility",
        "status": status,
        "mandatory": mandatory,
        "source": source,
        "binaries": bins["binaries"],
        "trusted_hardware_asserted": trusted_hardware,
        "paste_recipe": ""
        if p["skipped"]
        else recipe(v, clone=clone, remote=remote, staged_dir=staged_dir, mandatory=mandatory),
        "findings": fails + warns,
        "notes": notes,
    }
    if status is None:
        out["pending"] = pending
    return out
