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
"""Assemble release-promote's Step 0 verdict and render its Step 2 command set.

The functions are pure: they take what `release-config preflight` / `load
--skill promote` printed and the facts the agent read (the planning-issue
labels, the target listing, the verify-rc attestation), and return the step's
JSON contract. Nothing here runs `svn`, `gh`, `aws` or `git`, and nothing
applies a label: the release manager runs every command (Golden rule 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

from release_management.shell import dq, w

PROPOSED_LABEL = "promoted"
DEFAULT_ROSTER = "<project-config>/pmc-roster.md"

MIRROR_NOTE = """\
Mirror propagation (svnpubsub) / CDN cache (other backends):
  Allow up to 24 hours for the promoted release to appear on all mirrors.
  ASF policy requires waiting at least 1 hour after the promote commit
  before updating the download page or sending the [ANNOUNCE] email.
  Earliest announce time: <promote_timestamp + 1h> UTC (once the promote commit is confirmed)."""

NOT_VOTE_PASSED = "planning issue does not carry vote-passed label"
TARGET_STATES = ("empty", "populated")
TARGET_UNCHECKED = (
    "target URL check result unknown: list {target} (svn list / gh release view / aws s3 ls) "
    "and pass --target empty or --target populated"
)
RENDERABLE_VERDICTS = ("proceed", "handoff-non-pmc")
TRUSTED_HARDWARE = (
    "automated release signing requires every artefact to be rebuilt bit-by-bit identical on trusted hardware "
    "before publication ([Infra § Automated release signing](https://infra.apache.org/release-signing.html#automated-release-signing)); "
    "run `release-verify-rc {tag} --trusted-hardware --post-to {planning_issue}` on your own machine first"
)


class RenderError(ValueError):
    """The command set cannot be rendered as configured; the skill surfaces this and stops."""


# --------------------------------------------------------------------------- Step 0


def _short_target(url: str) -> str:
    """`https://dist.apache.org/repos/dist/release/foo/1.0/` → `dist/release/foo/1.0/`."""
    index = url.find("dist/release/")
    return url[index:] if index >= 0 else url


def verdict(
    preflight: dict[str, Any],
    *,
    vote_passed: bool,
    target: str | None,
    attestation: bool = False,
    planning_issue_found: bool = True,
    planning_issue: str = "<planning-issue>",
) -> dict[str, Any]:
    """Step 0: the tool's blockers plus the checks it cannot see, folded into one verdict.

    Every fact defaults to the blocking side: no `--vote-passed` means the label
    was not seen, and there is no override for it (Golden rule 3). `target` is
    the target-listing result, `empty` or `populated`; anything else (the check
    was skipped or errored) is a blocker, never an empty target (Golden rule 4).
    """
    values = preflight.get("values") or {}
    version, rc = values.get("version"), values.get("rc")
    tag = f"{version}-{rc}" if version and rc else "<version>-rc<N>"
    blockers = [str(b) for b in preflight.get("blockers") or []]
    if not planning_issue_found:
        blockers.append(f"no planning issue found for {version or '<version>'}: pass --planning-issue <url>")
    elif not vote_passed:
        blockers.append(NOT_VOTE_PASSED)
    short = _short_target(str(values.get("target_url") or "<target_url>"))
    target_populated = target == "populated"
    if target_populated:
        blockers.append(f"target URL {short} already contains content")
    elif target != "empty":
        blockers.append(TARGET_UNCHECKED.format(target=short))
    if values.get("trusted_hardware_attestation_required") and not attestation:
        blockers.append(TRUSTED_HARDWARE.format(tag=tag, planning_issue=planning_issue))
    non_asf = bool(values.get("non_asf"))
    rm_is_pmc = True if non_asf else values.get("rm_is_pmc") is True
    if blockers:
        outcome = "blocked"
    elif not rm_is_pmc:
        outcome = "handoff-non-pmc"
    else:
        outcome = "proceed"
    read = []
    if target_populated:
        read.append("blockers/target-exists.md")
    if any(b.startswith("automated release signing requires") for b in blockers):
        read.append("blockers/trusted-hardware.md")
    if outcome == "handoff-non-pmc":
        read.append("outcomes/handoff-non-pmc.md")
    return {
        "verdict": outcome,
        "blockers": blockers,
        "rm_is_pmc": rm_is_pmc,
        "non_asf": non_asf,
        "version": version,
        "rc": rc,
        "dist_backend": values.get("dist_backend"),
        "read": read,
    }


# --------------------------------------------------------------------------- Step 2


def apache_name(product: str) -> str:
    """The `Apache <product-name>` the svn message and tag message spell, without doubling `Apache`."""
    return product if product.startswith("Apache ") or product.startswith("<") else f"Apache {product}"


@dataclass
class Promote:
    """The resolved inputs the Step 2 command set is rendered from."""

    version: str
    rc: str
    meta: dict[str, Any]
    upstream: str = "<upstream>"
    project: str = "<project>"
    product_name: str = "<product-name>"
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_load(
        cls,
        loaded: dict[str, Any],
        *,
        upstream: str | None = None,
        project: str | None = None,
        product_name: str | None = None,
    ) -> Promote:
        meta = loaded.get("metadata") or {}
        version, rc = meta.get("version"), meta.get("rc")
        if not version or not rc:
            raise RenderError(
                "release-config load output has no version / rc: run it with --skill promote <version>-rc<N>"
            )
        return cls(
            version=str(version),
            rc=str(rc),
            meta=meta,
            upstream=upstream or "<upstream>",
            project=project or "<project>",
            product_name=product_name or "<product-name>",
        )

    @property
    def tag(self) -> str:
        return f"{self.version}-{self.rc}"

    @property
    def backend(self) -> str:
        return str(self.meta.get("dist_backend") or "")

    def value(self, given: str | None, placeholder: str, what: str) -> str:
        """A fact the agent supplies; missing → the placeholder, and a warning naming it."""
        if given:
            return given
        self.warnings.append(f"{what} is unknown: the block carries {placeholder} for the RM to fill in")
        return placeholder

    def render(self, text: str) -> str:
        out = text
        for spelling in ("<version>-<rcN>", "<version>-rc<N>", "<version>-rcN"):
            out = out.replace(spelling, self.tag)
        return out.replace("<rcN>", self.rc).replace("rc<N>", self.rc).replace("<version>", self.version)


# Path-style endpoints carry the bucket in the path: `s3.amazonaws.com`,
# `s3.<region>.amazonaws.com` and the legacy `s3-<region>.amazonaws.com`.
_S3_PATH_STYLE_HOST = re.compile(r"s3(?:[.-][a-z0-9-]+)?\.amazonaws\.com")
# Virtual-hosted: the bucket is everything before the LAST `.s3.` / `.s3-`.
_S3_VIRTUAL_HOST = re.compile(r"(.+)\.s3[.-](?:[a-z0-9-]+\.)*amazonaws\.com")


def s3_location(url: str) -> tuple[str, str]:
    """`(bucket, key)` for an `s3://<bucket>/<key>` or an `https://…amazonaws.com/…` URL.

    The key keeps every path segment after the bucket, so a template prefix
    (`s3://bkt/releases/<version>/`) survives into the command.
    """
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    path = parsed.path.lstrip("/")
    bucket, key = "", ""
    if parsed.scheme == "s3":
        bucket, key = host, path
    elif parsed.scheme in ("http", "https") and host.endswith(".amazonaws.com"):
        virtual = _S3_VIRTUAL_HOST.fullmatch(host)
        if _S3_PATH_STYLE_HOST.fullmatch(host):
            bucket, _, key = path.partition("/")
        elif virtual:
            bucket, key = virtual.group(1), path
    if not bucket or "<" in bucket:
        raise RenderError(
            f"cannot read the S3 bucket name from release_dist_url_template {url!r}: "
            "expected s3://<bucket-name>/…, https://<bucket-name>.s3.<region>.amazonaws.com/… "
            "or https://s3.<region>.amazonaws.com/<bucket-name>/…"
        )
    return bucket, key


def s3_bucket(template: str) -> str:
    """The bucket name in `release_dist_url_template`."""
    return s3_location(template)[0]


def s3_uri(url: str) -> str:
    """The `s3://<bucket>/<key>/` prefix a rendered staging / target URL names."""
    bucket, key = s3_location(url)
    prefix = key if not key or key.endswith("/") else key + "/"
    return f"s3://{bucket}/{prefix}"


def _svnpubsub(
    p: Promote, *, apache_id: str | None, result_vote_url: str | None, rc_commit_sha: str | None
) -> str:
    staging = str(p.meta.get("staging_url") or "")
    target = str(p.meta.get("target_url") or "")
    if not staging or not target:
        raise RenderError("staging_url / target_url did not render: check release_dist_url_template")
    product = apache_name(p.product_name)
    user = p.value(apache_id, "<apache_id>", "the RM's apache_id")
    vote = p.value(result_vote_url, "<result_vote_url>", "the [RESULT] [VOTE] archive URL")
    sha = p.value(rc_commit_sha, "<rc-commit-sha>", f"the commit {p.tag} points to")
    fingerprint = p.value(
        p.meta.get("rm_gpg_fingerprint"), "<rm_gpg_fingerprint>", "release_manager.gpg_fingerprint (user.md)"
    )
    remote = str(p.meta.get("git_upstream_remote") or "origin")
    return "\n".join(
        [
            "# Step 1 of 3 — move RC to release (release_dist_backend=svnpubsub)",
            "svn mv \\",
            f"  {w(staging)} \\",
            f"  {w(target)} \\",
            f"  --username {w(user)} \\",
            f"  -m {dq(f'Promoting {product} {p.version} (from {p.rc}). [RESULT]: {vote}')}",
            "",
            "# Step 2 of 3 — verify the move landed (release_dist_backend=svnpubsub)",
            f"svn list {w(target)}",
            "",
            "# Step 3 of 3 — cut and push the FINAL release tag on the SAME commit the",
            "# approved RC was built from (no rebuild). Downstream links (changelog,",
            f"# [ANNOUNCE], site) must reference this final {p.version} tag, never {p.tag}.",
            "# git signs tags via gpg.format=ssh globally, so override to openpgp to use the",
            f"# RM's release key ({fingerprint} from the RM user.md; YubiKey inserted).",
            f"git -c gpg.format=openpgp tag -s -u {w(fingerprint)} \\",
            f"  {w(p.version)} {w(sha)} \\",
            f"  -m {dq(f'{product} {p.version}')}",
            f"git push {w(remote)} {w('refs/tags/' + p.version)}",
            f"git -c gpg.format=openpgp tag -v {w(p.version)}   # confirm the release key signed it",
        ]
    )


def _github_releases(p: Promote, *, draft_tag: str | None, draft_tag_confirmed: bool) -> str:
    if not draft_tag:
        raise RenderError(
            "release_dist_backend is github-releases but --draft-tag was not passed: read the tag the draft "
            f"release carries (`gh release list --repo {p.upstream}`) and rerun with --draft-tag <tag>"
        )
    tag = draft_tag
    if tag != p.tag and not draft_tag_confirmed:
        raise RenderError(
            f"the draft release is tagged {tag}, not {p.tag}: ask the RM to confirm the correct tag name, "
            "then rerun with --draft-tag <tag> --draft-tag-confirmed"
        )
    return "\n".join(
        [
            f"# Publish the draft GitHub Release for {p.version}",
            f"gh release edit {w(tag)} \\",
            f"  --repo {w(p.upstream)} \\",
            "  --draft=false \\",
            f"  --tag {w(p.version)}",
            "",
            "# Verify the release is published",
            f"gh release view {w(p.version)} --repo {w(p.upstream)}",
        ]
    )


def _s3(p: Promote) -> str:
    staging_url = str(p.meta.get("staging_url") or "")
    target_url = str(p.meta.get("target_url") or "")
    if not staging_url or not target_url:
        raise RenderError("staging_url / target_url did not render: check release_dist_url_template")
    staging, target = s3_uri(staging_url), s3_uri(target_url)
    return "\n".join(
        [
            "# Promote RC to release prefix",
            "aws s3 mv \\",
            f"  {w(staging)} \\",
            f"  {w(target)} \\",
            "  --recursive",
            "",
            "# Verify the move",
            f"aws s3 ls {w(target)}",
        ]
    )


def _self_hosted(p: Promote) -> str:
    template = p.meta.get("promote_command_template")
    if not template:
        raise RenderError("release_dist_backend is self-hosted but release_publish_command_template is unset")
    return p.render(str(template))


def _handoff(p: Promote, *, rm: str | None, roster_path: str | None) -> str:
    who = rm or "<RM's GitHub handle or apache_id>"
    roster = roster_path or DEFAULT_ROSTER
    if p.backend == "svnpubsub":
        lines = [
            "HAND-OFF: The distribution tree at dist/release/ (release_dist_backend=svnpubsub) is PMC-write-only.",
            f"{who} does not appear on the PMC roster in",
            f"{roster}. Ask a PMC member to run the svn mv command below (release_dist_backend=svnpubsub)",
            f"on your behalf, or request PMC access from VP of {p.project}.",
        ]
    else:
        lines = [
            f"HAND-OFF: {who} does not appear on the PMC roster in",
            f"{roster}. Ask a PMC member to run the command set below",
            f"on your behalf, or request PMC access from VP of {p.project}.",
        ]
    return "\n".join([*lines, "", "The command set a PMC member would run:"])


def hold_note(name: str, tag: str, reason: str) -> str:
    return "\n".join(
        [
            f"HOLD: {name} — not published. release-verify-rc Step 9 did not",
            f"reproduce it from {tag} ({reason}). A binary that",
            "cannot be rebuilt from the voted source is not known to be what the vote",
            "approved. Fix the build or document the divergence in release-build.md,",
            f"re-run `release-verify-rc {tag}`, then re-run this skill.",
        ]
    )


def _convenience(p: Promote) -> tuple[str, list[str], list[str]]:
    split = p.meta.get("convenience") or {}
    publish = [e for e in split.get("publish") or [] if isinstance(e, dict)]
    held = [e for e in split.get("held") or [] if isinstance(e, dict)]
    if not publish and not held:
        return "", [], []
    lines = ["# Convenience artefacts — after the source promotion and the final tag"]
    publish_out: list[str] = []
    for entry in publish:
        name = str(entry.get("name"))
        channel = str(entry.get("publish_channel") or "dist-release")
        command = entry.get("publish_command")
        if channel == "dist-release":
            lines.append(
                f"# {name}: promoted with the source above (publish_channel: dist-release); nothing to run"
            )
            publish_out.append(f"{name}: promoted with the source")
        elif command:
            lines += [f"# {name} → {channel}", p.render(str(command))]
            publish_out.append(f"{name}: {p.render(str(command))}")
        else:
            p.warnings.append(
                f"{name} publishes to {channel} but declares no publish_command: nothing emitted"
            )
            lines.append(
                f"# {name} → {channel}: no publish_command declared in release-build.md; nothing emitted"
            )
            publish_out.append(f"{name}: no publish_command declared")
    held_out: list[str] = []
    for entry in held:
        name, reason = str(entry.get("name")), str(entry.get("reason") or "not checked")
        lines += ["", hold_note(name, p.tag, reason)]
        held_out.append(f"{name}: {reason}")
    return "\n".join(lines), publish_out, held_out


def handoff_from_verdict(p: Promote, step0: dict[str, Any], *, handoff: bool | None = None) -> bool:
    """The hand-off flag Step 2 renders with, read from the Step 0 verdict.

    Only `proceed` and `handoff-non-pmc` render; a `blocked` (or missing) verdict
    is refused, as is a verdict for another RC. `handoff`, when given, must agree.
    """
    outcome = step0.get("verdict")
    if outcome not in RENDERABLE_VERDICTS:
        raise RenderError(
            f"the Step 0 verdict is {outcome!r}, not proceed or handoff-non-pmc: resolve its blockers "
            "and rerun `promote verdict` before rendering"
        )
    seen = (step0.get("version"), step0.get("rc"))
    if seen != (p.version, p.rc):
        raise RenderError(
            f"the Step 0 verdict is for {seen[0]}-{seen[1]}, but the load is for {p.tag}: rerun Step 0 for {p.tag}"
        )
    derived = outcome == "handoff-non-pmc"
    if handoff is not None and handoff != derived:
        raise RenderError(
            f"--handoff disagrees with the Step 0 verdict {outcome!r}: drop --handoff, the verdict decides"
        )
    return derived


def step2(
    p: Promote,
    *,
    handoff: bool = False,
    rm: str | None = None,
    roster_path: str | None = None,
    apache_id: str | None = None,
    result_vote_url: str | None = None,
    rc_commit_sha: str | None = None,
    draft_tag: str | None = None,
    draft_tag_confirmed: bool = False,
) -> dict[str, Any]:
    """Step 2: the backend-shaped command set, the convenience artefacts and the mirror note."""
    if p.backend == "svnpubsub":
        block = _svnpubsub(
            p, apache_id=apache_id, result_vote_url=result_vote_url, rc_commit_sha=rc_commit_sha
        )
    elif p.backend == "github-releases":
        block = _github_releases(p, draft_tag=draft_tag, draft_tag_confirmed=draft_tag_confirmed)
    elif p.backend == "s3":
        block = _s3(p)
    elif p.backend == "self-hosted":
        block = _self_hosted(p)
    elif p.backend == "atr":
        raise RenderError(
            "release-promote does not support release_dist_backend atr yet: "
            "promote the release with ATR's Finish step on the ATR platform"
        )
    else:
        raise RenderError(f"unknown release_dist_backend {p.backend!r}")
    handoff_note = _handoff(p, rm=rm, roster_path=roster_path) if handoff else None
    convenience, publish, held = _convenience(p)
    sections = [s for s in (handoff_note, block, convenience, MIRROR_NOTE) if s]
    return {
        "staging_url": p.meta.get("staging_url"),
        "target_url": p.meta.get("target_url"),
        "dist_backend": p.backend,
        "command_block": "\n\n".join(sections),
        "rm_is_pmc": not handoff,
        "handoff_note": handoff_note,
        "proposed_label": PROPOSED_LABEL,
        "mirror_note_present": True,
        "convenience_publish_commands": publish,
        "convenience_held": held,
        "warnings": p.warnings,
    }
