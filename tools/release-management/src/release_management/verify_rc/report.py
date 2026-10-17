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
"""Step 10: the attestation decision and the report / `--post-to` comment skeleton.

The overall verdict is `release-verify verdict`'s — this module reads its JSON
and never recomputes the roll-up. It decides one thing on its own: whether
the planning-issue comment carries the trusted-hardware attestation
`release-promote` Step 0 looks for. It never posts anything.
"""

from __future__ import annotations

from typing import Any

from release_management.verify_rc.common import VOTER_OBLIGATION_REMINDER, VerifyError, VerifyRc

ATTESTATION_TITLE = "Reproducibility validated on trusted hardware"
INFRA_SIGNING = "https://infra.apache.org/release-signing.html#automated-release-signing"


def _hit_names(v: VerifyRc, hits: list[str]) -> list[str]:
    """Artefact names behind Step 9's `known_divergences_hit` (`"<name>: <pattern>"`).

    Matched against the declared names rather than split at a colon: a
    container image's name carries its own `:<tag>`, and the pattern can carry
    `: ` too, so no single split point recovers the name.
    """
    names = sorted((e["name"] for e in v.convenience()), key=len, reverse=True)
    out = []
    for hit in hits:
        name = next((n for n in names if hit == n or hit.startswith(f"{n}: ")), None)
        out.append(name if name is not None else hit.split(": ", 1)[0])
    return out


def attestation(
    v: VerifyRc, repro: dict[str, Any] | None, *, trusted_hardware: bool
) -> tuple[bool, str | None]:
    """(eligible, why not). Only under automated signing, Step 9 `PASS` with every
    artefact `identical`, and `--trusted-hardware` passed by the person running it."""
    if not v.ci_automated:
        return False, None
    if repro is None or repro.get("status") != "PASS":
        status = None if repro is None else repro.get("status")
        return False, f"Step 9 is {status or 'missing'}, not PASS"
    source = repro.get("source") or {}
    if source.get("verdict") != "identical":
        return False, f"the source artefact is {source.get('verdict') or 'not compared'}, not identical"
    binaries = repro.get("binaries") or {}
    others = [
        *(binaries.get("differs") or []),
        *_hit_names(v, binaries.get("known_divergences_hit") or []),
    ]
    if others:
        return False, f"not every artefact is identical ({', '.join(others)})"
    # Fail closed: every declared convenience artefact must be positively
    # `identical`. One that was skipped, left pending or never rebuilt
    # carries no evidence, so it blocks the attestation too.
    identical = set(binaries.get("identical") or [])
    unproven = [e["name"] for e in v.convenience() if e["name"] not in identical]
    if unproven:
        return False, f"not every artefact was shown identical ({', '.join(unproven)})"
    if not trusted_hardware:
        return False, "--trusted-hardware was not passed; the skill cannot assert where it runs"
    return True, None


def attestation_block(v: VerifyRc, *, commit: str, epoch: Any, committer: str) -> str:
    return "\n".join(
        [
            f"> **{ATTESTATION_TITLE}** — `{v.rc_tag}` at",
            f"> commit `{commit}`, `SOURCE_DATE_EPOCH {epoch}`; every staged artefact",
            f"> rebuilt on `@{committer}`'s own hardware and confirmed bit-by-bit",
            "> identical (`repro-archive compare --require-identical`). Per",
            f"> [Infra § Automated release signing]({INFRA_SIGNING}).",
        ]
    )


def _pairs(values: list[str], flag: str) -> list[tuple[str, str]]:
    out = []
    for raw in values:
        step, sep, text = raw.partition("=")
        if not sep:
            raise VerifyError(f"{flag} wants STEP=TEXT, got {raw!r}")
        out.append((step.strip(), text.strip()))
    return out


def _binary_lines(v: VerifyRc, repro: dict[str, Any] | None) -> list[str]:
    """One line per convenience artefact in the words release-promote reads back."""
    if not repro:
        return []
    binaries = repro.get("binaries") or {}
    identical = set(binaries.get("identical") or [])
    differs = set(binaries.get("differs") or [])
    warned = set(_hit_names(v, binaries.get("known_divergences_hit") or []))
    lines = []
    for entry in v.convenience():
        name = entry["name"]
        state = (
            "identical"
            if name in identical
            else "differs"
            if name in differs
            else "warn"
            if name in warned
            else "not checked"
        )
        lines.append(f"- `{name}`: {state}")
    return lines


def report(
    v: VerifyRc,
    verdict: dict[str, Any],
    *,
    repro: dict[str, Any] | None,
    rebuilt_sha512: str | None,
    staging_url: str | None,
    utc: str,
    post_to: str | None,
    trusted_hardware: bool,
    committer: str | None,
    findings: list[str],
    fail_details: list[str],
    warn_details: list[str],
) -> dict[str, Any]:
    """Step 10's JSON contract, with the report text and (with `--post-to`) the comment to propose."""
    if verdict.get("step") != "verdict" and "verdict" in verdict:
        verdict = verdict["verdict"]
    overall = verdict.get("overall")
    if overall is None:
        raise VerifyError(
            f"the verdict is unresolved (steps still REVIEW: {verdict.get('unresolved')}); resolve them first"
        )
    found = dict(_pairs(findings, "--finding"))
    skip = set(verdict.get("skip_steps") or [])
    summary = [
        {
            "step": s["step"],
            "status": s["status"],
            "finding": found.get(s["step"], "skipped" if s["step"] in skip else ""),
        }
        for s in verdict.get("step_summary") or []
    ]
    eligible, why_not = attestation(v, repro, trusted_hardware=trusted_hardware)
    source = (repro or {}).get("source") or {}
    commit = source.get("recorded_commit") or "<commit>"
    epoch = source.get("source_date_epoch") or "<SOURCE_DATE_EPOCH>"
    lines = [
        f"## release-verify-rc — `{v.rc_tag}`",
        "",
        f"- Staging URL: {staging_url or v.meta.get('staging_url') or '<staging-url>'}",
        f"- Verified (UTC): {utc}",
        "",
        VOTER_OBLIGATION_REMINDER,
        "",
        "| Step | Status | Finding |",
        "|---|---|---|",
        *[f"| {s['step']} | {s['status']} | {s['finding']} |" for s in summary],
    ]
    if fail_details:
        lines += ["", "**FAIL detail**", "", *[f"- {d}" for d in fail_details]]
    if warn_details:
        lines += ["", "**WARN detail**", "", *[f"- {d}" for d in warn_details]]
    lines += ["", f"**Overall verdict:** {overall}"]
    if repro is not None:
        lines += [
            "",
            "**Reproducibility record**",
            "",
            f"- Step 9: {repro.get('status')} (source {source.get('verdict') or 'not compared'})",
            f"- Commit `{commit}`, `SOURCE_DATE_EPOCH {epoch}`",
            f"- sha512 of the rebuilt source artefact: `{rebuilt_sha512 or '<not recorded>'}`",
            *_binary_lines(v, repro),
        ]
    text = "\n".join(lines)
    comment = None
    if post_to:
        parts = [text]
        if eligible:
            parts += [
                "",
                attestation_block(v, commit=commit, epoch=epoch, committer=committer or "<committer>"),
            ]
        elif why_not:
            parts += ["", f"No trusted-hardware attestation: {why_not}."]
        comment = "\n".join(parts)
    return {
        "step": "report",
        "rc_tag": v.rc_tag,
        "verification_utc": utc,
        "overall": overall,
        "voter_obligation_reminder": True,
        "step_summary": summary,
        "fail_details": fail_details,
        "warn_details": warn_details,
        "reproducibility_attestation": bool(post_to) and eligible,
        "post_to_comment": comment,
        "text": text,
        "attestation_withheld_because": why_not,
    }
