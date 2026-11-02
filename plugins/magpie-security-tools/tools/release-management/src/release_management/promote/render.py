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
# The digests rc-cut stages one `.<digest>` file for (rc_cut.render.ALLOWED_DIGESTS).
ALLOWED_DIGESTS = frozenset({"sha512", "sha256"})
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
    upstream: str | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    """Step 0: the tool's blockers plus the checks it cannot see, folded into one verdict.

    Every fact defaults to the blocking side: no `--vote-passed` means the label
    was not seen, and there is no override for it (Golden rule 3). `target` is
    the target-listing result, `empty` or `populated`; anything else (the check
    was skipped or errored) is a blocker, never an empty target (Golden rule 4).
    `scope` records which release the verdict is for, so the render can refuse
    a verdict reached for another project, backend or staging / target URL.
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
        "scope": {
            "project": project or "<project>",
            "upstream": upstream or "<upstream>",
            "dist_backend": values.get("dist_backend"),
            "staging_url": values.get("staging_url"),
            "target_url": values.get("target_url"),
        },
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
    build: dict[str, Any] = field(default_factory=dict)

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
            build=loaded.get("build") or {},
        )

    @property
    def sidecars(self) -> tuple[str, ...]:
        """The signature and per-digest checksum files rc-cut staged next to each artefact.

        `.asc`, then one `.<digest>` per `digest_set` entry (default `sha512`),
        normalised as rc-cut normalises it; only sha512 and sha256 are accepted.
        """
        raw = self.build.get("digest_set") or self.meta.get("digest_set") or ["sha512"]
        digests = [str(d).strip().lower() for d in raw]
        unknown = sorted(set(digests) - ALLOWED_DIGESTS)
        if unknown:
            raise RenderError(
                f"digest_set lists unsupported digest(s) {', '.join(repr(d) for d in unknown)}: "
                "only sha512 and sha256 are staged, so the held artefacts' checksum files cannot be named"
            )
        return (".asc", *(f".{d}" for d in dict.fromkeys(digests)))

    @property
    def sidecar_text(self) -> str:
        """`.asc and .sha512`, `.asc, .sha512 and .sha256`, … for the comments and HOLD notes."""
        *head, last = self.sidecars
        return f"{', '.join(head)} and {last}"

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


# A held name spliced into an svn URL, an `aws s3 --exclude` pattern or a release-asset
# name must be one plain file name: no path separator, wildcard or whitespace.
_PLAIN_FILE_NAME = re.compile(r"[A-Za-z0-9_.+:@%=,~-]+")


def _own_name(entry: dict[str, Any], version: str) -> str:
    """A declared artefact's name rendered with its own version, as `release-config load` renders it."""
    raw = entry.get("version")
    own = version if raw in (None, "") else str(raw).strip().replace("<version>", version)
    return str(entry.get("name")).replace("<version>", own)


def _held_channel(p: Promote, entry: dict[str, Any]) -> str:
    """Where a held artefact would have published; unknown → `dist-release` (staged with the source)."""
    if entry.get("publish_channel"):
        return str(entry["publish_channel"])
    name = str(entry.get("name"))
    for declared in p.meta.get("convenience_artefacts") or []:
        if isinstance(declared, dict) and _own_name(declared, p.version) == name:
            return str(declared.get("publish_channel") or "dist-release")
    return "dist-release"


def staged_held(p: Promote) -> list[str]:
    """The held artefacts staged alongside the source, which the promotion itself must leave out."""
    held = [e for e in (p.meta.get("convenience") or {}).get("held") or [] if isinstance(e, dict)]
    names = [str(e.get("name")) for e in held if _held_channel(p, e) == "dist-release"]
    for name in names:
        if not _PLAIN_FILE_NAME.fullmatch(name) or name in (".", ".."):
            raise RenderError(
                f"held convenience artefact {name!r} is staged with the source but is not a plain file name, "
                "so the promotion cannot leave it out safely: remove it from the staging location by hand, "
                "re-run `release-verify-rc`, then re-run this skill"
            )
    return names


def _with_sidecars(p: Promote, names: list[str]) -> list[str]:
    """Each held artefact followed by its signature and checksum files, which are withheld with it."""
    return [f"{name}{suffix}" for name in names for suffix in ("", *p.sidecars)]


def _svnpubsub(
    p: Promote,
    *,
    apache_id: str | None,
    result_vote_url: str | None,
    rc_commit_sha: str | None,
    withheld: list[str],
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
    total = 4 if withheld else 3
    n = total - 3
    move = f"# Step {n + 1} of {total} — move RC to release (release_dist_backend=svnpubsub)"
    first = [move]
    if withheld:
        base = staging if staging.endswith("/") else staging + "/"
        message = f"Withholding unreproduced convenience artefacts from {product} {p.version} ({p.rc})"
        # No comment line between `&&` and `svn mv`: a shell that does not take
        # interactive comments would end the chain there and run the move anyway.
        first = [
            f"# Step 1 of {total} — withhold the held convenience artefacts (see the HOLD notes below):",
            f"# remove each, with its {p.sidecar_text}, from the RC directory so the svn mv",
            "# does not promote it. If any is missing, svn rm fails and the && stops the move.",
            f"{move}, chained after Step 1",
            "svn rm \\",
            *[f"  {w(base + name)} \\" for name in _with_sidecars(p, withheld)],
            f"  --username {w(user)} \\",
            f"  -m {dq(message)} &&",
        ]
    return "\n".join(
        [
            *first,
            "svn mv \\",
            f"  {w(staging)} \\",
            f"  {w(target)} \\",
            f"  --username {w(user)} \\",
            f"  -m {dq(f'Promoting {product} {p.version} (from {p.rc}). [RESULT]: {vote}')}",
            "",
            f"# Step {n + 2} of {total} — verify the move landed (release_dist_backend=svnpubsub)",
            f"svn list {w(target)}",
            "",
            f"# Step {n + 3} of {total} — cut and push the FINAL release tag on the SAME commit the",
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


def _github_releases(
    p: Promote, *, draft_tag: str | None, draft_tag_confirmed: bool, withheld: list[str]
) -> str:
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
    first: list[str] = []
    if withheld:
        first = [
            "# Withhold the held convenience artefacts (see the HOLD notes below): delete each,",
            f"# with its {p.sidecar_text}, from the draft release before publishing it.",
            "# If one is missing, delete-asset fails and the && stops the publish.",
            *[
                f"gh release delete-asset {w(tag)} {w(name)} --repo {w(p.upstream)} --yes &&"
                for name in _with_sidecars(p, withheld)
            ],
        ]
    return "\n".join(
        [
            f"# Publish the draft GitHub Release for {p.version} as a full release (rc-cut drafted it as a prerelease)",
            *first,
            f"gh release edit {w(tag)} \\",
            f"  --repo {w(p.upstream)} \\",
            "  --draft=false \\",
            "  --prerelease=false \\",
            f"  --tag {w(p.version)}",
            "",
            "# Verify the release is published",
            f"gh release view {w(p.version)} --repo {w(p.upstream)}",
        ]
    )


def _s3(p: Promote, *, withheld: list[str]) -> str:
    staging_url = str(p.meta.get("staging_url") or "")
    target_url = str(p.meta.get("target_url") or "")
    if not staging_url or not target_url:
        raise RenderError("staging_url / target_url did not render: check release_dist_url_template")
    staging, target = s3_uri(staging_url), s3_uri(target_url)
    note = []
    if withheld:
        note = [
            "# The --exclude flags leave the held convenience artefacts (see the HOLD notes below),",
            f"# with their {p.sidecar_text}, in the RC prefix.",
        ]
    return "\n".join(
        [
            "# Promote RC to release prefix",
            *note,
            "aws s3 mv \\",
            f"  {w(staging)} \\",
            f"  {w(target)} \\",
            *[f"  --exclude {w(name)} \\" for name in _with_sidecars(p, withheld)],
            "  --recursive",
            "",
            "# Verify the move",
            f"aws s3 ls {w(target)}",
        ]
    )


def _self_hosted(p: Promote, *, withheld: list[str]) -> str:
    template = p.meta.get("promote_command_template")
    if not template:
        raise RenderError("release_dist_backend is self-hosted but release_publish_command_template is unset")
    if withheld:
        raise RenderError(
            f"held convenience artefacts are staged with the source ({', '.join(withheld)}), and "
            "release_publish_command_template cannot be told to leave them out: remove them from the staging "
            "location by hand, or fix the build and re-run `release-verify-rc`, then re-run this skill"
        )
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


WITHHELD_HOW = {
    "svnpubsub": "The svn rm above removes it, with its {sidecars}, from the RC directory before the svn mv.",
    "s3": "The --exclude flags above leave it, with its {sidecars}, out of the aws s3 mv.",
    "github-releases": "The delete-asset above removes it, with its {sidecars}, from the draft release before it is published.",
}
NOT_EMITTED = "No publish command for it is emitted."


def hold_note(name: str, tag: str, reason: str, how: str = NOT_EMITTED) -> str:
    return "\n".join(
        [
            f"HOLD: {name} — not published. release-verify-rc Step 9 did not",
            f"reproduce it from {tag} ({reason}). A binary that",
            "cannot be rebuilt from the voted source is not known to be what the vote",
            f"approved. {how}",
            "Fix the build or document the divergence in release-build.md,",
            f"re-run `release-verify-rc {tag}`, then re-run this skill.",
        ]
    )


def _convenience(p: Promote, withheld: list[str]) -> tuple[str, list[str], list[str]]:
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
        how = WITHHELD_HOW[p.backend].format(sidecars=p.sidecar_text) if name in withheld else NOT_EMITTED
        lines += ["", hold_note(name, p.tag, reason, how)]
        held_out.append(f"{name}: {reason}")
    return "\n".join(lines), publish_out, held_out


def handoff_from_verdict(p: Promote, step0: dict[str, Any], *, handoff: bool | None = None) -> bool:
    """The hand-off flag Step 2 renders with, read from the Step 0 verdict.

    Only `proceed` and `handoff-non-pmc` render; a `blocked` (or missing) verdict
    is refused, as is a verdict for another RC, project, upstream, backend or
    staging / target URL. `handoff`, when given, must agree.
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
    scope = step0.get("scope")
    if not isinstance(scope, dict):
        raise RenderError(
            "the Step 0 verdict does not record which release it is for (no `scope`): "
            f"rerun `promote verdict` for {p.tag} with --upstream and --project"
        )
    expected = {
        "project": p.project,
        "upstream": p.upstream,
        "dist_backend": p.backend,
        "staging_url": p.meta.get("staging_url"),
        "target_url": p.meta.get("target_url"),
    }
    for key, want in expected.items():
        if scope.get(key) != want:
            raise RenderError(
                f"the Step 0 verdict is for {key} {scope.get(key)!r}, but the load is for {want!r}: "
                f"rerun Step 0 for this release"
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
    """Step 2: the backend-shaped command set, the convenience artefacts and the mirror note.

    A held artefact staged alongside the source (`staged_held`) is left out of
    the promotion itself, before it runs; a backend that cannot leave it out refuses.
    """
    withheld = staged_held(p)
    if p.backend == "svnpubsub":
        block = _svnpubsub(
            p,
            apache_id=apache_id,
            result_vote_url=result_vote_url,
            rc_commit_sha=rc_commit_sha,
            withheld=withheld,
        )
    elif p.backend == "github-releases":
        block = _github_releases(
            p, draft_tag=draft_tag, draft_tag_confirmed=draft_tag_confirmed, withheld=withheld
        )
    elif p.backend == "s3":
        block = _s3(p, withheld=withheld)
    elif p.backend == "self-hosted":
        block = _self_hosted(p, withheld=withheld)
    elif p.backend == "atr":
        raise RenderError(
            "release-promote does not support release_dist_backend atr yet: "
            "promote the release with ATR's Finish step on the ATR platform"
        )
    else:
        raise RenderError(f"unknown release_dist_backend {p.backend!r}")
    handoff_note = _handoff(p, rm=rm, roster_path=roster_path) if handoff else None
    convenience, publish, held = _convenience(p, withheld)
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
