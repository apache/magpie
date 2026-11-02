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
"""Render what release-archive-sweep hands the release manager, from `release-config load --skill archive-sweep`.

The functions are pure: they take the loaded configuration and what the
retention rule decided, and return the step's JSON contract. Nothing here
runs `svn`, `gh`, `aws` or `atr`, lists the distribution area or archives
anything: the release manager runs every command (Golden rule 1).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from release_management.archive_sweep.retention import version_key
from release_management.promote.render import RenderError as PromoteRenderError
from release_management.promote.render import s3_location
from release_management.shell import dq, w

BACKENDS = ("svnpubsub", "atr", "github-releases", "s3", "self-hosted")
ASF_BACKENDS = ("svnpubsub", "atr")
ASF_ARCHIVE_DEFAULT = "https://archive.apache.org/dist/{project}/"
DEFAULT_RULE = "latest_of_each_supported_line"
STRICT_TRAIN = re.compile(r"(?<![\w.])(\d+(?:\.\d+)*\.x)(?![\w.])")
BRANCH = re.compile(r"`([^`]+)`")
RC_MARKER = re.compile(r"-?<rc ?N>|-?<rcN>|-?rc<N>")
GITHUB_DELETION_WARNING = (
    "GitHub releases have no archive equivalent: `gh release delete` removes the release page "
    "permanently (and the tag only if `--cleanup-tag` is added). Confirm with the RM that deleting "
    "each version is intentional."
)
ATR_NOTE = (
    "Archive in ATR, not in a shell: ATR updates the release catalog and removes the files from "
    "dist/release itself, so do not also run `svn mv` or `svn rm`. If the project enables "
    "*Auto archive prior release*, check ATR's record first: the previous release may already be archived."
)


class RenderError(ValueError):
    """The command set cannot be rendered as configured; the skill surfaces this and stops."""


@dataclass
class Sweep:
    """The resolved configuration every archive-sweep output is rendered from."""

    config: dict[str, Any]
    derived: dict[str, Any]
    upstream: str = "<upstream>"
    project: str = "<project>"
    warnings: list[str] = field(default_factory=list)

    @classmethod
    def from_load(
        cls, loaded: dict[str, Any], *, upstream: str | None = None, project: str | None = None
    ) -> Sweep:
        config = loaded.get("config") or {}
        dist_name = config.get("project_dist_name")
        return cls(
            config=config,
            derived=loaded.get("derived") or {},
            upstream=upstream or "<upstream>",
            project=str(dist_name or project or "<project>"),
        )

    @property
    def backend(self) -> str:
        return str(self.config.get("release_dist_backend") or "")

    @property
    def template(self) -> str:
        template = self.config.get("release_dist_url_template")
        if not template:
            raise RenderError("release_dist_url_template is unset")
        return str(template).replace("<bucket>", "release").replace("<project>", self.project)

    def _release_template(self) -> str:
        """The template with the RC segment removed; it must name `<version>`."""
        template = RC_MARKER.sub("", self.template)
        if "<version>" not in template:
            raise RenderError(f"release_dist_url_template {self.template!r} has no <version> segment")
        return template

    def release_url(self, version: str) -> str:
        """The released version's location: the template, `release` bucket, no RC segment."""
        return self._release_template().replace("<version>", version).rstrip("/")

    def release_dir(self) -> str:
        """The directory holding every released version: the template cut before the `<version>` segment.

        The whole path segment holding `<version>` goes, literal text around it included:
        `…/foo/v<version>/` lists `…/foo/`, whose entries are named `v<version>`.
        """
        head = self._release_template().split("<version>", 1)[0]
        return head[: head.rfind("/") + 1]

    @property
    def entry_affix(self) -> tuple[str, str]:
        """The literal text around `<version>` in its path segment: `v<version>` → (`v`, ``).

        A listing entry is that prefix, the version and that suffix; `retention`
        strips them before reading versions, and URLs and tags add them back.
        """
        template = self._release_template()
        head, tail = template.split("<version>", 1)
        prefix = head[head.rfind("/") + 1 :]
        suffix = tail.split("/", 1)[0]
        return prefix, suffix

    def entry(self, version: str) -> str:
        """The listing entry (directory name, release tag) a version is published under."""
        prefix, suffix = self.entry_affix
        return f"{prefix}{version}{suffix}"

    @property
    def archive_base(self) -> str:
        url = self.config.get("archive_url_template")
        if url:
            return str(url).replace("<project>", self.project)
        if self.backend in ASF_BACKENDS and self.config.get("project_dist_name"):
            return ASF_ARCHIVE_DEFAULT.format(project=self.project)
        raise RenderError(
            f"archive destination for {self.backend} is not configured (archive_url_template missing)"
        )

    def archive_url(self, version: str) -> str:
        base = self.archive_base
        if "<version>" in base:
            return base.replace("<version>", version).rstrip("/")
        # The archive mirrors the release directory: the entry keeps its name.
        return base.rstrip("/") + "/" + self.entry(version)


def _s3(url: str) -> str:
    """`url` as an `s3://bucket/key` URL, read the way release-promote reads it.

    A path-style host (`s3.<region>.amazonaws.com`) carries the bucket in the
    path; a virtual-hosted one (`<bucket>.s3.<region>.amazonaws.com`, even a
    bucket named `s3-…`) carries it in the host and keeps the whole path as key.
    """
    try:
        bucket, key = s3_location(url)
    except PromoteRenderError as exc:
        raise RenderError(str(exc)) from exc
    return f"s3://{bucket}/{key}"


def _fence(lines: list[str]) -> str:
    return "```text\n" + "\n".join(lines) + "\n```"


# --------------------------------------------------------------------------- Step 0


def verdict(preflight: dict[str, Any]) -> dict[str, Any]:
    """Step 0: `release-config preflight`'s blockers as written, folded into the step's JSON."""
    values = preflight.get("values") or {}
    blockers = [str(b) for b in preflight.get("blockers") or []]
    return {
        "verdict": "blocked" if blockers else "proceed",
        "blockers": blockers,
        "non_asf": bool(values.get("non_asf")),
        "dist_backend": values.get("dist_backend"),
    }


# --------------------------------------------------------------------------- Step 1


def listing(sweep: Sweep) -> dict[str, Any]:
    """Step 1.1: the read that lists what is on the distribution surface."""
    backend = sweep.backend
    command: str | None = None
    note: str | None = None
    if backend == "svnpubsub":
        command = f"svn list {w(sweep.release_dir())}"
    elif backend == "atr":
        note = (
            "No shell listing: read the project's release list in ATR, which is also the record of what "
            f"is already archived. The distribution area is still {sweep.release_dir()} (ATR's Finish commits there)."
        )
    elif backend == "github-releases":
        command = f"gh release list --repo {w(sweep.upstream)} --exclude-drafts"
        note = "Each published (non-draft) release tag is a candidate."
    elif backend == "s3":
        command = f"aws s3 ls {w(_s3(sweep.release_dir()))}"
    elif backend == "self-hosted":
        note = "Run the adopter-supplied listing command from release-management-config.md."
    else:
        raise RenderError(f"unknown release_dist_backend {backend!r}")
    return {
        "backend": backend,
        "command": command,
        "note": note,
        "read": f"backends/{backend}.md",
    }


def trains(sweep: Sweep, *, keep: int | None = None) -> dict[str, Any]:
    """Step 1.2: `trains.json` from release-trains.md's release lines.

    A line naming exactly one strict `N.x` / `N.M.x` train becomes
    `{"label", "pattern"}`; any other line is a loose train the agent places
    (its versions come back `unmapped`). `keep` comes from `--keep` or the
    default rule; a free-text rule is the agent's to translate.
    """
    rule = str(sweep.config.get("archive_retention_rule") or DEFAULT_RULE)
    out: list[dict[str, Any]] = []
    loose: list[str] = []
    seen: set[str] = set()
    for line in sweep.derived.get("release_lines") or []:
        found = sorted(set(STRICT_TRAIN.findall(str(line))))
        if len(found) == 1:
            entry: dict[str, Any] = {"label": found[0], "pattern": found[0]}
        else:
            branch = BRANCH.search(str(line))
            label = branch.group(1) if branch else str(line)
            entry = {"label": label, "pattern": str(line)}
            loose.append(label)
        if entry["label"] in seen:
            continue
        seen.add(entry["label"])
        if keep is not None and keep != 1:
            entry["keep"] = keep
        out.append(entry)
    keep_decided = keep is not None or rule == DEFAULT_RULE
    notes = []
    if not keep_decided:
        notes.append(
            f"archive_retention_rule {rule!r} is not {DEFAULT_RULE!r}: decide how many versions each train "
            "keeps (`keep`) and re-run with --keep N, or set it per train; the latest of every train always stays"
        )
    if loose:
        notes.append(
            "loose train(s) "
            + ", ".join(repr(label) for label in loose)
            + ': list each one\'s versions under "versions" after the first retention run'
        )
    prefix, suffix = _affix_or_none(sweep)
    if prefix or suffix:
        notes.append(
            f"listing entries are named {prefix}<version>{suffix} (release_dist_url_template): "
            "`retention` reads the version between them"
        )
    return {
        "trains": out,
        "loose": loose,
        "retention_rule": rule,
        "keep_decided": keep_decided,
        "entry_prefix": prefix,
        "entry_suffix": suffix,
        "notes": notes,
    }


def _affix_or_none(sweep: Sweep) -> tuple[str, str]:
    try:
        return sweep.entry_affix
    except RenderError:  # no usable template: Step 2 refuses it on its own
        return "", ""


# --------------------------------------------------------------------------- Step 2


def step2(sweep: Sweep, retention: dict[str, Any], *, command_template: str | None = None) -> dict[str, Any]:
    """Step 2: the backend-shaped archive command set, oldest first."""
    if retention.get("retention_rule_error"):
        raise RenderError(
            "retention-rule-error: the rule would archive the latest release of a supported train; "
            "no archival command may be emitted"
        )
    if retention.get("mapping_complete") is not True:
        raise RenderError(
            "unmapped versions remain (or mapping_complete is absent): place them in a train and "
            "re-run the retention rule"
        )
    versions = [str(v) for v in retention.get("past_retention") or []]
    latest = retention.get("latest_of_each_line") or {}
    kept = {
        **{
            str(v): "the latest of its line"
            for v in (latest.values() if isinstance(latest, dict) else latest)
        },
        **{str(v): "an orphan" for v in retention.get("orphans") or []},
        **{str(v): "a pre-release" for v in retention.get("prereleases") or []},
    }
    clash = [f"{v} ({kept[v]})" for v in versions if v in kept]
    if clash:
        raise RenderError(
            "past_retention names version(s) that must never be archived: "
            + ", ".join(clash)
            + "; re-run the retention rule instead of editing its output"
        )
    backend = sweep.backend
    if versions and backend != "self-hosted":
        expected = sweep.entry_affix
        recorded = (str(retention.get("entry_prefix") or ""), str(retention.get("entry_suffix") or ""))
        if recorded != expected:
            raise RenderError(
                f"release_dist_url_template names each entry {expected[0]}<version>{expected[1]}, but the "
                f"retention output read entries as {recorded[0]}<version>{recorded[1]}: re-run `archive-sweep trains` "
                "and `archive-sweep retention` with that trains file"
            )
    extra: dict[str, Any] = {}
    lines: list[str] = []
    if not versions:
        lines = ["# Nothing is past retention: no archival command."]
    elif backend == "svnpubsub":
        for ver in versions:
            if lines:
                lines.append("")
            lines += [
                "svn mv \\",
                f"  {w(sweep.release_url(ver))} \\",
                f"  {w(sweep.archive_url(ver))} \\",
                f"  -m {dq(f'Archive {sweep.project} {ver} per retention policy')}",
            ]
    elif backend == "atr":
        lines = [f"# release_dist_backend=atr: archive each version in the ATR UI ({sweep.project}):"]
        lines += [f"#   {ver}" for ver in versions]
        lines.append("# No svn mv / svn rm: ATR removes the files from dist/release itself.")
        extra["atr_note"] = ATR_NOTE
    elif backend == "github-releases":
        lines = [
            f"gh release delete {w(sweep.entry(ver))} --repo {w(sweep.upstream)} --yes" for ver in versions
        ]
        extra["deletion_warning"] = GITHUB_DELETION_WARNING
        if sweep.upstream == "<upstream>":
            sweep.warnings.append("--upstream was not given: the commands carry <upstream>")
    elif backend == "s3":
        for ver in versions:
            if lines:
                lines.append("")
            lines += [
                "aws s3 mv \\",
                f"  {w(_s3(sweep.release_url(ver)) + '/')} \\",
                f"  {w(_s3(sweep.archive_url(ver)) + '/')} \\",
                "  --recursive",
            ]
    elif backend == "self-hosted":
        if not command_template:
            raise RenderError(
                "release_dist_backend is self-hosted: pass the adopter-supplied archival command template "
                "with --command-template (placeholders <ver>, <version>, <archive-url>)"
            )
        for ver in versions:
            lines.append(
                command_template.replace("<archive-url>", w(sweep.archive_url(ver)))
                .replace("<version>", w(ver))
                .replace("<ver>", w(ver))
            )
    else:
        raise RenderError(f"unknown release_dist_backend {backend!r}")
    read = [f"backends/{backend}.md"]
    if retention.get("orphans") or retention.get("prereleases"):
        read.append("outcomes/orphans.md")
    return {
        "archive_count": len(versions),
        "commands": _fence(lines),
        "backend": backend,
        "proposed": True,
        "versions": versions,
        "not_archived": sorted(
            {str(v) for v in [*(retention.get("orphans") or []), *(retention.get("prereleases") or [])]},
            key=version_key,
        ),
        "read": read,
        "warnings": sweep.warnings,
    } | extra
