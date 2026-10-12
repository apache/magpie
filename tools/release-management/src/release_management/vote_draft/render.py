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
"""Render what release-vote-draft hands the RM, from `release-config load --skill vote-draft`.

The functions are pure: they take the loaded configuration and the facts the
agent read from the planning issue, and return the step's JSON contract plus
`text`. Nothing here sends mail, posts a comment or touches the network; the
reworded `--expedited` reason stays the agent's judgement, and a reason that
still names a CVE or a security fix comes back as a warning.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from release_management.shell import dq, w

DEFAULT_SUBJECT = "[VOTE] Release <Product Name> <version> from <version>-rcN"
VERIFY_HEADING = "How to verify this candidate"
POLICY_URL = "https://www.apache.org/legal/release-policy.html#release-approval"
EMBARGOED = re.compile(r"CVE-\d{4}-\d+|security|vulnerability|vulnerabilities|exploit", re.IGNORECASE)
FRAMEWORK_REPRO = "https://github.com/apache/magpie/blob/main/docs/release-management/reproducibility.md"
NO_PROJECT_PAGE = " (the project's own verification page is not configured yet)"
VERDICTS = ("PASS", "PASS-WITH-WARNINGS", "FAIL", "none")

AGENTIC_PATH = """\
Agentic path (any agent with the Magpie release skills, read-only):
  /{skill} {tag}
  It checks the signature against KEYS, the checksum, licence headers
  (RAT), LICENSE/NOTICE, prohibited binaries, dangling links, version
  strings, rebuilds the source artefact from the tag to confirm it is
  byte-identical to what is staged and that its SWHID is the recorded
  one, and rebuilds and compares every convenience artefact."""

CI_SIGNED = """\
[This candidate was signed by CI under the project's automated
release signing. Policy requires a committer's byte-identical rebuild
on their own hardware before promotion: run the verification with
--trusted-hardware --post-to {planning_issue} and say so in your
vote.]"""

OBLIGATION = f"""\
A binding +1 means you downloaded the artefact, verified it, and built
and tested it on your own hardware; the tools above are an aid, not a
substitute ({POLICY_URL})."""

ATR_COMMAND = """\
# ATR sends the [VOTE] to {vote_list} and tabulates replies.
# --no-auto-publish is REQUIRED for the hybrid: ATR must NOT publish
# (SVN owns promotion). Confirm current flags with `atr vote start --help`.
atr vote start -m {vote_list} \\
  --duration {hours} \\
  --subject {subject} \\
  --no-auto-publish \\
  {revision}{project} {version}
# Optional: --revision <rev> targets a specific uploaded revision
#   (defaults to the latest). Verb/flag names may shift between ATR
#   releases — a required `revision` positional was dropped in favour of
#   this optional flag, so do not hard-depend on `atr revisions`.
# If `atr check concerns {project} {version}` lists concern-group keys,
#   acknowledge them: --concerns-noted <comma,separated,keys>."""


class RenderError(ValueError):
    """The inputs ask for something the skill must refuse to draft."""


@dataclass
class Record:
    """The reproducibility record release-rc-cut posted; only the fields it holds are rendered."""

    repository: str | None = None
    commit: str | None = None
    swhid: str | None = None
    epoch: str | None = None
    sha512: str | None = None

    def lines(self) -> list[str]:
        rows = [
            ("repository:       ", self.repository),
            ("source commit:    ", self.commit),
            ("SWHID (content):  ", self.swhid),
            ("SOURCE_DATE_EPOCH:", self.epoch),
            ("sha512:           ", self.sha512),
        ]
        present = [f"  {label} {value}" for label, value in rows if value]
        return ["Reproducibility record (from the planning issue):", *present] if present else []


_PASTE = "_(paste from"


def _tick(value: str) -> str | None:
    value = value.strip()
    if not value or value.startswith(_PASTE):
        return None
    return value.strip("`").strip() or None


def parse_rc_comment(text: str) -> Record:
    """The reproducibility record from the planning-issue comment `release-rc-cut` Step 4 rendered.

    Fields still showing rc-cut's `_(paste from …)_` placeholder are absent, never invented.
    """
    found: dict[str, str | None] = {}
    patterns = {
        "commit": r"^- Commit:\s*(.+?)\s+—\s+repository\s+(\S+)\s*$",
        "epoch": r"^- `SOURCE_DATE_EPOCH`:\s*(.+)$",
        "sha512": r"^- sha512:\s*(.+)$",
        "swhid_rev": r"^- swhid_rev:\s*(.+)$",
        "swhid_dir": r"^- swhid_dir:\s*(.+)$",
        "artefacts": r"^- \*\*Artefacts:\*\*\s*(.+)$",
    }
    for line in text.splitlines():
        for key, pattern in patterns.items():
            match = re.match(pattern, line.strip())
            if not match:
                continue
            found[key] = match.group(1) if key == "artefacts" else _tick(match.group(1))
            if key == "commit":
                found["repository"] = match.group(2)
    swhid = found.get("swhid_dir")
    rev = (found.get("swhid_rev") or "").split(";")[0]
    if swhid and ";origin=" not in swhid and found.get("repository"):
        swhid = f"{swhid};origin={found['repository']}" + (f";anchor={rev}" if rev else "")
    sha512 = found.get("sha512")
    artefacts = re.findall(r"`([^`]+)`", found.get("artefacts") or "")
    if sha512 and artefacts:
        sha512 = f"{sha512} ({artefacts[0]})"
    return Record(
        repository=found.get("repository") if found.get("commit") else None,
        commit=found.get("commit"),
        swhid=swhid,
        epoch=found.get("epoch"),
        sha512=sha512,
    )


@dataclass
class VoteDraft:
    """The resolved inputs the `[VOTE]` draft and the planning-issue comment are rendered from."""

    version: str
    rc: str
    product_name: str
    meta: dict[str, Any]
    config: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_load(cls, loaded: dict[str, Any], *, product_name: str) -> VoteDraft:
        meta = loaded.get("metadata") or {}
        version, rc = meta.get("version"), meta.get("rc_number")
        if not version or not rc:
            raise RenderError(
                "release-config load output has no version / rc_number: run it with --skill vote-draft <version>-rcN"
            )
        if not product_name:
            raise RenderError("--product-name is required (the project's display name, from project.md)")
        return cls(str(version), str(rc), product_name, meta, loaded.get("config") or {})

    @property
    def tag(self) -> str:
        return f"{self.version}-{self.rc}"

    @property
    def window_hours(self) -> int:
        raw = self.meta.get("vote_window_hours") or self.config.get("vote_window_hours") or 72
        try:
            return int(str(raw).strip())
        except ValueError as exc:
            raise RenderError(f"vote_window_hours={raw!r} is not an integer") from exc

    @property
    def vote_list(self) -> str:
        value = self.meta.get("vote_list") or self.config.get("vote_dev_list")
        if not value:
            raise RenderError("vote_dev_list is unset in release-management-config.md")
        return str(value)

    @property
    def vote_backend(self) -> str:
        return str(self.meta.get("vote_backend") or "manual")

    @property
    def dist_backend(self) -> str | None:
        value = self.config.get("release_dist_backend")
        return str(value) if value else None

    def render(self, text: str) -> str:
        return (
            text.replace("<version>-<rcN>", self.tag)
            .replace("<version>-rcN", self.tag)
            .replace("<Product Name>", self.product_name)
            .replace("<version>", self.version)
            .replace("<rcN>", self.rc)
        )

    @property
    def subject(self) -> str:
        return self.render(str(self.meta.get("subject_template") or DEFAULT_SUBJECT))

    def convenience(self) -> list[dict[str, Any]]:
        out = []
        for entry in self.meta.get("convenience_artefacts") or []:
            if isinstance(entry, dict) and entry.get("name"):
                own = str(entry.get("version") or self.version)
                out.append(entry | {"name": self.render(str(entry["name"]).replace("<version>", own))})
        return out


def embargo_warnings(reason: str | None) -> list[str]:
    """A reason that would leak the security framing onto the public `[VOTE]` thread (Golden rule 4)."""
    hits = sorted({m.group(0) for m in EMBARGOED.finditer(reason or "")})
    if not hits:
        return []
    return [
        f"the --expedited reason names {', '.join(repr(h) for h in hits)}: the [VOTE] thread and the planning issue "
        "are public, so reword it neutrally (e.g. 'Time-sensitive fix release'), keep any approval the RM cited, "
        "tell the RM what was left out, and render again"
    ]


def _notice(prefix: str, reason: str, tail: str) -> str:
    return f"[{prefix}: {reason.strip().rstrip('.')}{tail}]"


def verify_section(
    draft: VoteDraft, record: Record, *, atr_candidate_url: str | None, planning_issue: str | None
) -> str:
    """The *How to verify* section every `[VOTE]` carries, whichever backend sends it."""
    skill = draft.meta.get("verification_skill") or "magpie-release-management:verify-rc"
    record_lines = record.lines()
    first = f"{VERIFY_HEADING} before voting\n" + "-" * 42 + "\n"
    if record_lines:
        first += "\n".join(record_lines) + "\n\n"
    sections = [
        first + AGENTIC_PATH.format(skill=skill, tag=draft.tag),
        "Manual path (the same checks, longhand):\n"
        f"  {draft.meta.get('verification_doc_url') or FRAMEWORK_REPRO + NO_PROJECT_PAGE}\n"
        f"  Reproducibility background: {draft.meta.get('reproducibility_doc_url') or FRAMEWORK_REPRO}",
    ]
    if draft.vote_backend == "atr":
        sections.append(f"ATR check results for this candidate:\n  {atr_candidate_url}")
    if draft.meta.get("signing_mode") == "ci-automated":
        sections.append(CI_SIGNED.format(planning_issue=planning_issue or "<planning-issue-url>"))
    sections.append(OBLIGATION)
    return "\n\n".join(sections)


def _missing(
    draft: VoteDraft,
    *,
    staging_url: str | None,
    tag_url: str | None,
    changelog_url: str | None,
    svn_revision: str | None,
    atr_candidate_url: str | None,
) -> list[str]:
    missing = [
        name
        for name, value in (
            ("staging_url", staging_url),
            ("tag_url", tag_url),
            ("changelog_url", changelog_url),
            ("keys_url", draft.meta.get("keys_url")),
        )
        if not value
    ]
    if draft.dist_backend == "svnpubsub" and not svn_revision:
        missing.append("svn_revision (required when release_dist_backend = svnpubsub)")
    if draft.vote_backend == "atr" and not atr_candidate_url:
        missing.append("atr_candidate_url (required when vote_backend = atr)")
    return missing


def step2(
    draft: VoteDraft,
    *,
    tag_url: str | None,
    changelog_url: str | None,
    staging_url: str | None = None,
    svn_revision: str | None = None,
    record: Record | None = None,
    canned_body: str | None = None,
    expedited: str | None = None,
    skip_verify: str | None = None,
    atr_candidate_url: str | None = None,
    atr_revision: str | None = None,
    planning_issue: str | None = None,
    project: str | None = None,
    rm_name: str = "<RM name>",
) -> dict[str, Any]:
    """Step 2: the `[VOTE]` subject and body, and the `atr vote start` command under `vote_backend = atr`."""
    record = record or Record()
    staging_url = staging_url or draft.meta.get("staging_url")
    missing = _missing(
        draft,
        staging_url=staging_url,
        tag_url=tag_url,
        changelog_url=changelog_url,
        svn_revision=svn_revision,
        atr_candidate_url=atr_candidate_url,
    )
    if missing:
        raise RenderError(
            "metadata missing, never invented: " + ", ".join(missing) + " — read it from the planning issue"
        )
    hours = draft.window_hours
    if hours < 72 and not expedited:
        raise RenderError(
            f"vote_window_hours ({hours}) is below the ASF 72-hour floor and --expedited <reason> was not passed (Golden rule 3)"
        )
    subject = draft.subject
    verify = verify_section(draft, record, atr_candidate_url=atr_candidate_url, planning_issue=planning_issue)
    notices = []
    if expedited:
        notices.append(
            _notice(
                "EXPEDITED",
                expedited,
                ". ASF policy requires this deviation to be noted in the project's next board report.",
            )
        )
    if skip_verify:
        notices.append(
            _notice(
                "SKIP-VERIFY",
                "release-verify-rc was not run for this RC; the RM accepted this with the reason: "
                + skip_verify,
                ".",
            )
        )
    canned_missing_verify = False
    if canned_body:
        body = draft.render(canned_body)
        for key, value in {
            "<vote_list>": draft.vote_list,
            "<staging_url>": staging_url,
            "<svn_revision>": svn_revision,
            "<tag_url>": tag_url,
            "<changelog_url>": changelog_url,
            "<keys_url>": draft.meta.get("keys_url"),
            "<vote_window_hours>": str(hours),
            "<RM name>": rm_name,
        }.items():
            if value:
                body = body.replace(key, str(value))
        body = body.rstrip("\n")
        if VERIFY_HEADING.lower() not in body.lower():
            canned_missing_verify = True
            body += "\n\n" + verify
        if notices:
            body += "\n\n" + "\n\n".join(notices)
    else:
        staged = f"  {staging_url}" + (
            f"\n  (SVN revision: r{svn_revision})" if draft.dist_backend == "svnpubsub" else ""
        )
        blocks = [
            f"To: {draft.vote_list}\nSubject: {subject}",
            "Hi all,",
            f"I propose we release the following artifacts as {draft.product_name} {draft.version}.",
            f"The release artifacts, signatures, and checksums are available at:\n{staged}",
            f"The release tag to be voted upon:\n  {tag_url}",
            f"The changelog for this release:\n  {changelog_url}",
            f"Keys to verify artifact signatures:\n  {draft.meta.get('keys_url')}",
        ]
        entries = draft.convenience()
        if entries:
            rows = [
                f"  {e['name']}  —  staged at {e.get('staging') or 'dist-dev'}"
                + ("  — included in this vote" if e.get("vote_included") else "")
                for e in entries
            ]
            modes = ", ".join(dict.fromkeys(str(e.get("reproducibility") or "off") for e in entries))
            blocks.append(
                "Convenience artefacts (built from the source above; not the release itself):\n"
                + "\n".join(rows)
                + "\n  Each one is verified by rebuilding it from the tag and comparing\n"
                f"  ({modes}); a convenience artefact that does not\n"
                "  reproduce from the voted source will be withheld from publication."
            )
        blocks += [
            verify,
            "Please vote to release:\n"
            f"  [ ] +1  Release {draft.product_name} {draft.version}\n"
            "  [ ] +0\n"
            "  [ ] -1  Do not release (please comment with specific reasons)",
            f"This vote is open for at least {hours} hours.",
            *notices,
            f"Thanks,\n{rm_name}",
        ]
        body = "\n\n".join(blocks)
    atr = ""
    if draft.vote_backend == "atr":
        atr = ATR_COMMAND.format(
            vote_list=w(draft.vote_list),
            hours=w(hours),
            subject=dq(subject),
            revision=f"--revision {w(atr_revision)} \\\n  " if atr_revision else "",
            project=w(project or draft.config.get("project_dist_name") or "<project>"),
            version=w(draft.version),
        )
    warnings = embargo_warnings(expedited)
    if not draft.meta.get("verification_doc_url"):
        warnings.append(
            "vote_verification_doc_url is unset: the body links the framework's reproducibility.md and says the "
            "project page is missing; add the key (release-management-config.md § Vote)"
        )
    if canned_missing_verify:
        warnings.append(
            f"canned_body has no '{VERIFY_HEADING}' section: it was appended; the project's canned [VOTE] block should gain it"
        )
    text = f"Subject: {subject}\n\n{body}" + (f"\n\n{atr}" if atr else "")
    return {
        "subject": subject,
        "body": body,
        "vote_window_hours": hours,
        "vote_backend": draft.vote_backend,
        "atr_vote_command": atr,
        "expedited": bool(expedited),
        "skip_verify_logged": bool(skip_verify),
        "verify_section_appended": canned_missing_verify,
        "warnings": warnings,
        "text": text,
    }


def parse_time(value: str) -> datetime:
    """`2026-06-11T15:00:00Z`, `2026-06-11 15:00 UTC` or any ISO-8601 time with an offset."""
    text = value.strip()
    if text.upper().endswith(" UTC"):
        text = text[:-4].strip() + "+00:00"
    text = text.replace("Z", "+00:00").replace("z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise RenderError(f"--sent-at {value!r} is not an ISO-8601 time") from exc
    if parsed.tzinfo is None:
        raise RenderError(f"--sent-at {value!r} carries no timezone; give it in UTC")
    return parsed.astimezone(UTC)


def _utc(moment: datetime) -> str:
    return moment.strftime("%Y-%m-%d %H:%M UTC")


def step3(
    draft: VoteDraft, *, sent_at: str, subject: str | None = None, expedited: str | None = None
) -> dict[str, Any]:
    """Step 3: the proposed planning-issue comment, with the window-close time computed."""
    sent = parse_time(sent_at)
    hours = draft.window_hours
    closes = sent + timedelta(hours=hours)
    subject = subject or draft.subject
    if expedited:
        lines = [
            f"**Vote open (expedited):** `{subject}`",
            f"sent to `{draft.vote_list}` on {_utc(sent)}.",
            f"Vote window closes: {_utc(closes)} (minimum, {hours}-hour expedited window).",
            "",
            f"**Expedited:** {expedited.strip().rstrip('.')}.",
            "Reminder: note this deviation in the project's next board report per ASF policy.",
        ]
    else:
        lines = [
            f"**Vote open:** `{subject}`",
            f"sent to `{draft.vote_list}` on {_utc(sent)}.",
            f"Vote window closes: {_utc(closes)} (minimum).",
        ]
    lines += ["", "Next step: `release-vote-tally` after the window closes."]
    comment = "\n".join(lines)
    return {
        "comment_body": comment,
        "proposed": True,
        "window_closes_utc": closes.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "warnings": embargo_warnings(expedited),
        "text": comment,
    }


def verdict(
    preflight: dict[str, Any],
    *,
    planning_issue: str | None,
    verify_rc_verdict: str,
    verify_rc_for: str | None,
) -> dict[str, Any]:
    """Step 0: the tool's blockers plus the planning-issue and verify-rc gates (Golden rule 5)."""
    values = preflight.get("values") or {}
    blockers = [str(b) for b in preflight.get("blockers") or []]
    warnings = [str(w) for w in preflight.get("warnings") or []]
    skip = bool(values.get("skip_verify_override"))
    version, rc = values.get("version"), values.get("rc_number")
    tag = f"{version}-{rc}" if version and rc else None
    if not planning_issue:
        blockers.append(
            "no planning issue found: pass --planning-issue <url>, or open one on <upstream> labelled release-planning "
            "with the version in its title"
        )
    if verify_rc_verdict not in VERDICTS:
        raise RenderError(f"--verify-rc-verdict must be one of {', '.join(VERDICTS)}")
    if not skip and tag:
        same_rc = verify_rc_for == tag
        if verify_rc_verdict == "none" or not verify_rc_for:
            blockers.append(
                f"release-verify-rc has not reported PASS for {tag}: no verify-rc comment on the planning issue. "
                "Run release-verify-rc, or pass --skip-verify-check with a reason."
            )
        elif not same_rc:
            other = verify_rc_for.rsplit("-", 1)[-1]
            blockers.append(
                f"release-verify-rc has not reported PASS for {tag}; the latest verify result is for {other}, not {rc}. "
                f"Run release-verify-rc for {rc}, or pass --skip-verify-check with a reason."
            )
        elif verify_rc_verdict == "FAIL":
            blockers.append(
                f"release-verify-rc reported FAIL for {tag}: fix the RC, or pass --skip-verify-check with a reason."
            )
        elif verify_rc_verdict == "PASS-WITH-WARNINGS":
            warnings.append(
                f"release-verify-rc reported PASS-WITH-WARNINGS for {tag}: surface the warnings to the RM before drafting."
            )
    return {
        "verdict": "blocked" if blockers else "proceed",
        "blockers": blockers,
        "skip_verify_override": skip,
        "expedited": bool(values.get("expedited")),
        "warnings": warnings,
    }
