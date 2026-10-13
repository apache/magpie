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
"""Render every block release-rc-cut emits, from `release-config load --skill rc-cut`.

The functions are pure: they take the loaded configuration (the JSON
`release-config load` prints) and the facts the agent supplies, and return
the step's JSON contract plus `text`, the block shown to the release manager.
Nothing here runs a command, reads a key or touches the network.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from release_management.shell import dq, w

PROHIBITED_DIGESTS = frozenset({"md5", "sha1"})
DIGEST_TOOLS = {"sha512": "sha512sum", "sha256": "sha256sum"}
STOP_ON = ["differs", "DIFFERS"]
REPRO = "uv run --project <framework>/tools/reproducible-archive repro-archive"
EPOCH_FROM_TOOL = f'export SOURCE_DATE_EPOCH="$({REPRO} epoch --ref {{tag}})"'


class RenderError(ValueError):
    """The configuration asks for something the skill must refuse to emit."""


@dataclass
class RcCut:
    """The resolved inputs every rc-cut block is rendered from."""

    version: str
    rc: str
    meta: dict[str, Any]
    config: dict[str, Any] = field(default_factory=dict)
    build: dict[str, Any] = field(default_factory=dict)
    upstream: str = "<upstream>"
    project: str = "<project>"

    @classmethod
    def from_load(
        cls, loaded: dict[str, Any], *, upstream: str | None = None, project: str | None = None
    ) -> RcCut:
        meta = loaded.get("metadata") or {}
        version, rc = meta.get("version"), meta.get("rc_number")
        if not version or not rc:
            raise RenderError(
                "release-config load output has no version / rc_number: run it with --skill rc-cut <version> <rcN>"
            )
        return cls(
            version=str(version),
            rc=str(rc),
            meta=meta,
            config=loaded.get("config") or {},
            build=loaded.get("build") or {},
            upstream=upstream or "<upstream>",
            project=project or "<project>",
        )

    @property
    def tag(self) -> str:
        return f"{self.version}-{self.rc}"

    @property
    def rc_label(self) -> str:
        """`rc1` → `RC1`, as the tag message and release title spell it."""
        return "RC" + self.rc[2:] if self.rc.lower().startswith("rc") else self.rc

    @property
    def artefacts(self) -> list[str]:
        return [str(a) for a in self.meta.get("expected_artefacts") or []]

    @property
    def source_artefact(self) -> str:
        """The canonical source artefact: the first `expected_artefacts` entry the build marks `source`."""
        kinds = [a.get("kind") for a in self.build.get("expected_artefacts") or [] if isinstance(a, dict)]
        for name, kind in zip(self.artefacts, kinds, strict=False):
            if kind == "source":
                return name
        return self.artefacts[0] if self.artefacts else "<source-artefact-filename>"

    @property
    def digests(self) -> list[str]:
        digests = [str(d).lower() for d in self.meta.get("digest_set") or ["sha512"]]
        bad = sorted(set(digests) & PROHIBITED_DIGESTS)
        if bad:
            raise RenderError(
                f"digest_set lists prohibited digest(s) {', '.join(bad)}: MD5 and SHA-1 are never emitted (Golden rule 3)"
            )
        return digests

    @property
    def ci_automated(self) -> bool:
        return self.meta.get("signing_mode") == "ci-automated"

    @property
    def remote(self) -> str:
        return str(self.meta.get("git_upstream_remote") or "origin")

    def render(self, text: Any) -> str:
        """Substitute the release placeholders a config value may carry."""
        return (
            str(text)
            .replace("<version>-<rcN>", self.tag)
            .replace("<version>", self.version)
            .replace("<rcN>", self.rc)
            .replace("<project>", self.project)
            .replace("<upstream>", self.upstream)
        )

    def convenience(self) -> list[dict[str, Any]]:
        out = []
        for entry in self.meta.get("convenience_artefacts") or []:
            if not isinstance(entry, dict):
                continue
            own = str(entry.get("version") or self.version)
            name = str(entry.get("name", "")).replace("<version>", own)
            out.append(entry | {"name": self.render(name)})
        return out


def tag_exists(refs: str, tag: str) -> bool:
    """Whether `refs/tags/<tag>` is among the refs the `tags` read printed.

    The read lists every tag starting with the prefix, so `rc1` also lists
    `rc10`: only an exact line counts.
    """
    return any(line.strip() == f"refs/tags/{tag}" for line in refs.splitlines())


def _source_block(cut: RcCut) -> list[str]:
    method = cut.meta.get("source_archive_method") or "git-archive"
    build_command = cut.meta.get("build_command")
    lines = [
        f"# gitignore the RC artefacts first ({', '.join(f'{a}*' for a in cut.artefacts) or '<artefact>*'})",
        "# so a stray `git add` never commits an RC build.",
        f"# Run at the release tag {cut.tag}",
    ]
    if method == "custom":
        if not build_command:
            raise RenderError("source_archive_method is custom but build_command is unset")
        return [
            *lines,
            f'export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct {dq(cut.tag)})"',
            str(build_command),
        ]
    lines += [
        f"{REPRO} build \\",
        f"  --ref {dq(cut.tag)} --format {w(cut.meta.get('source_archive_format') or 'tar.gz')} \\",
        f"  --prefix {dq(cut.meta.get('source_archive_prefix') or '')} \\",
        f"  --origin {dq('https://github.com/' + cut.upstream)} \\",
        f"  -o {dq(cut.source_artefact)}",
        "# → prints: commit <sha>, SOURCE_DATE_EPOCH <epoch>, sha512 <digest>,",
        "#           swhid_rev swh:1:rev:<sha>;origin=…, swhid_dir swh:1:dir:<tree>;origin=…;anchor=…,",
        "#           swhid_dir_note <identical to | differs from> the repository tree",
    ]
    if build_command:
        lines += [
            "",
            "# Convenience binaries (build_command):",
            EPOCH_FROM_TOOL.format(tag=dq(cut.tag)),
            str(build_command),
        ]
    return lines


def _convenience_blocks(cut: RcCut) -> list[str]:
    entries = cut.convenience()
    if not entries:
        return ["# no convenience artefacts declared"]
    lines: list[str] = []
    for entry in entries:
        lines += [
            f"# Convenience artefact: {entry['name']} ({entry.get('kind') or 'artefact'}) — built from the tagged source",
            EPOCH_FROM_TOOL.format(tag=dq(cut.tag)),
            cut.render(entry.get("build_command") or "<build_command>"),
            "",
        ]
    return lines[:-1]


def step2(cut: RcCut) -> dict[str, Any]:
    """Step 2: tag, build, sign and checksum commands."""
    tag_cmds = "\n".join(
        [
            f"git tag -s {w(cut.tag)} \\",
            f"  -m {dq(f'Release {cut.version} {cut.rc_label}')} \\",
            "  HEAD",
            f"git push {w(cut.remote)} {w(cut.tag)}",
        ]
    )
    build = "\n".join([*_source_block(cut), "", *_convenience_blocks(cut)])
    warnings = []
    fmt = str(cut.meta.get("source_archive_format") or "tar.gz")
    if (
        cut.meta.get("source_archive_method") or "git-archive"
    ) == "git-archive" and not cut.source_artefact.endswith(fmt):
        warnings.append(
            f"source artefact {cut.source_artefact} does not end in .{fmt} (source_archive_format)"
        )
    if cut.ci_automated:
        sign: list[str] = []
        sums: list[str] = []
    else:
        sign = [f"gpg --detach-sign --armor {w(a)}" for a in cut.artefacts]
        sums = [
            f"{DIGEST_TOOLS.get(d, d + 'sum')} {w(a)} > {w(f'{a}.{d}')}"
            for a in cut.artefacts
            for d in cut.digests
        ]
    sections = [
        "## Section 1 — Tag",
        tag_cmds,
        "## Section 2 — Build",
        build,
    ]
    if not cut.ci_automated:
        sections += [
            "## Section 3 — Sign (each produces <artefact>.asc; your key agent prompts for the passphrase)",
            "\n".join(sign),
            "## Section 4 — Checksums",
            "\n".join(sums),
        ]
    return {
        "section_1_tag_commands": tag_cmds,
        "section_2_build_command": build,
        "section_3_sign_commands": sign,
        "section_4_checksum_commands": sums,
        "prohibited_digests_omitted": True,
        "proposed": True,
        "next_step": "2c" if cut.ci_automated else "3",
        "warnings": warnings,
        "text": "\n\n".join(sections),
    }


def step2b(cut: RcCut, *, skip: bool = False, epoch: str = "<SOURCE_DATE_EPOCH>") -> dict[str, Any]:
    """Step 2b: the optional reproducibility self-check (mandatory under ci-automated)."""
    source_on = cut.meta.get("reproducibility_source") == "on"
    binaries = str(cut.meta.get("reproducibility_binaries") or "off")
    mandatory = cut.ci_automated
    skipped = (not source_on and binaries == "off") or (skip and not mandatory)
    result: dict[str, Any] = {
        "source_check_enabled": source_on and not skipped,
        "binary_check_mode": "off" if skipped else binaries,
        "mandatory": mandatory,
        "skipped": skipped,
        "source_check_commands": [],
        "binary_check_commands": [],
        "stop_on": STOP_ON,
        "proposed": True,
    }
    if skipped:
        result["text"] = "Reproducibility self-check skipped."
        return result
    src = cut.source_artefact
    fmt = cut.meta.get("source_archive_format") or "tar.gz"
    prefix = cut.meta.get("source_archive_prefix") or ""
    if source_on:
        rebuild = (
            ["mkdir -p rebuild", f"( cd rebuild && {cut.meta.get('build_command') or '<build_command>'} )"]
            if cut.meta.get("source_archive_method") == "custom"
            else [
                "mkdir -p rebuild",
                f"{REPRO} build --ref {dq(cut.tag)} --format {w(fmt)} --prefix {dq(prefix)} -o {dq('rebuild/' + src)}",
            ]
        )
        result["source_check_commands"] = [
            f"{REPRO} check {dq(src)} --epoch {dq(epoch)}",
            *rebuild,
            f"{REPRO} compare --require-identical {dq(src)} {dq('rebuild/' + src)}",
        ]
    binary_cmds: list[str] = []
    for entry in cut.convenience():
        mode = str(entry.get("reproducibility") or binaries)
        name = entry["name"]
        if mode == "off":
            binary_cmds.append(f"# SKIP: {name} (reproducibility off)")
            continue
        binary_cmds += [
            f"export SOURCE_DATE_EPOCH={dq(epoch)}",
            f"( cd rebuild && {cut.render(entry.get('build_command') or '<build_command>')} )",
        ]
        if mode == "documented-divergence":
            binary_cmds.append(
                cut.render(
                    entry.get("verification_command") or f"diffoscope {w(name)} {w('rebuild/' + name)}"
                )
            )
        else:
            binary_cmds.append(
                f"cmp {dq(name)} {dq('rebuild/' + name)} && echo {dq('identical: ' + name)} || echo {dq('DIFFERS: ' + name)}"
            )
    result["binary_check_commands"] = binary_cmds
    blocks = []
    if result["source_check_commands"]:
        blocks.append(
            "# Source: lint, rebuild from the tag, require byte-identical output\n"
            + "\n".join(result["source_check_commands"])
        )
    if binary_cmds:
        blocks.append("# Convenience artefacts\n" + "\n".join(binary_cmds))
    result["text"] = (
        "\n\n".join(blocks)
        + "\n\n# Any differs / DIFFERS stops the cut: fix the build before signing anything."
    )
    return result


def step2c(cut: RcCut, *, organization: str = "ASF") -> dict[str, Any]:
    """Step 2c: the CI-signed flow (only for signing_mode ci-automated)."""
    if not cut.ci_automated:
        raise RenderError("Step 2c applies only when signing_mode is ci-automated")
    workflow = str(cut.config.get("ci_release_workflow") or "<ci_release_workflow>")
    trigger = [
        f"git push {w(cut.remote)} {w(cut.tag)}",
        f"gh run list --repo {w(cut.upstream)} --workflow {w(workflow)} --branch {w(cut.tag)}",
        f"gh run watch --repo {w(cut.upstream)} <run-id>",
        f"atr check status {w(cut.project)} {w(cut.version)} --verbose",
    ]
    text = "\n".join(
        [
            f"# 1. Push the signed tag — this triggers {workflow}",
            trigger[0],
            "# 2. Watch the run; it builds reproducibly, self-compares, checksums and uploads to ATR. It publishes nothing.",
            trigger[1],
            trigger[2],
            "# 3. Confirm the staged candidate and its checks in ATR",
            trigger[3],
            "# 4. Record the run URL and the SOURCE_DATE_EPOCH from the run log for Step 4",
        ]
    )
    handoff = (
        f"Before this RC can be promoted, a committer must run `release-verify-rc {cut.tag}` on their own hardware; "
        "its Step 9 rebuilds every artefact and requires `identical`. "
        "`release-promote` refuses to promote without that attestation on the planning issue."
    )
    return {
        "signing_mode": "ci-automated",
        "organization": organization,
        "ci_release_workflow": workflow,
        "trigger_commands": trigger,
        "local_sign_commands_omitted": True,
        "trusted_hardware_validation_required": True,
        "proposed": True,
        "handoff": handoff,
        "text": text + "\n\n" + handoff,
    }


def _assert_dev_only(url: str) -> None:
    if re.search(r"/dist/release(/|$)", url):
        raise RenderError(
            f"refusing to stage to {url}: dist/release/ is on the promotion-path denylist (Golden rule 5)"
        )


def step3(cut: RcCut, *, asf_id: str = "<asf-id>", local_dir: str = "<local-artefact-dir>") -> dict[str, Any]:
    """Step 3: backend-shaped staging commands, plus ATR upload and registry staging."""
    if cut.ci_automated:
        raise RenderError(
            "Step 3 is skipped under signing_mode ci-automated: CI stages, Step 2c recorded the run"
        )
    backend = str(cut.meta.get("backend") or "")
    url = str(cut.meta.get("staging_url") or "")
    staging: list[str]
    if backend == "svnpubsub":
        if not url:
            raise RenderError("staging_url is unset: release_dist_url_template did not render")
        _assert_dev_only(url)
        staging = [
            f"svn import {w(local_dir)}/ \\\n  {w(url.rstrip('/') + '/')} \\\n  --username {w(asf_id)} \\\n"
            f"  -m {dq(f'Release {cut.project} {cut.version} {cut.rc}')}"
        ]
    elif backend == "github-releases":
        files = " ".join(
            w(n) for a in cut.artefacts for n in (a, f"{a}.asc", *(f"{a}.{d}" for d in cut.digests))
        )
        staging = [
            f"gh release create {w(cut.tag)} \\\n  --repo {w(cut.upstream)} \\\n  --title {dq(f'Release {cut.version} {cut.rc_label}')} \\\n  --prerelease \\\n  --draft",
            f"gh release upload {w(cut.tag)} --repo {w(cut.upstream)} \\\n  {files}",
        ]
    elif backend == "s3":
        if not url:
            raise RenderError("staging_url is unset: release_dist_url_template did not render")
        staging = [f"aws s3 cp --recursive {w(local_dir)}/ \\\n  {w(url.rstrip('/') + '/')}"]
    elif backend == "self-hosted":
        template = cut.config.get("release_publish_command_template")
        if not template:
            raise RenderError(
                "release_dist_backend is self-hosted but release_publish_command_template is unset"
            )
        staging = [cut.render(template)]
    else:
        raise RenderError(f"unknown release_dist_backend {backend!r}")
    atr: list[str] = []
    vote_backend = str(cut.meta.get("vote_backend") or "manual")
    if vote_backend == "atr":
        for a in cut.artefacts:
            atr += [
                f"atr upload {w(cut.project)} {w(cut.version)} {w(name)} {w(name)}"
                for name in (a, f"{a}.asc", *(f"{a}.{d}" for d in cut.digests))
            ]
        atr += [
            f"atr check status   {w(cut.project)} {w(cut.version)} --verbose   # confirm checks pass",
            f"atr check concerns {w(cut.project)} {w(cut.version)}             # list any concern-group keys to ack at vote time",
        ]
    registry = []
    travelling = []
    for entry in cut.convenience():
        if entry.get("staging") == "registry-staging":
            registry.append(cut.render(entry.get("stage_command") or "<stage_command>"))
        else:
            travelling.append(entry["name"])
    blocks = [f"# Stage to {backend}\n" + "\n".join(staging)]
    if atr:
        blocks.append(
            "# Upload the SAME signed + checksummed artefacts to ATR (Compose) so it runs its checks and can drive the [VOTE].\n"
            "# Verb/flag names may shift between ATR releases; confirm with `atr <cmd> --help`. ATR Finish/publish is not part of staging.\n"
            + "\n".join(atr)
        )
    if registry:
        blocks.append(
            "# Convenience artefacts staged to their registry (never the final publish_channel)\n"
            + "\n".join(registry)
        )
    if travelling:
        blocks.append(
            f"# {', '.join(travelling)} travel with the source in the blocks above; nothing extra to stage."
        )
    return {
        "backend": backend,
        "vote_backend": vote_backend,
        "staging_commands": staging,
        "atr_upload_commands": atr,
        "registry_staging_commands": registry,
        "staging_url": url,
        "dist_dev_only": backend == "svnpubsub",
        "proposed": True,
        "text": "\n\n".join(blocks),
    }


RECORD_KEYS = ("commit", "SOURCE_DATE_EPOCH", "sha512", "swhid_rev", "swhid_dir", "swhid_dir_note", "origin")


def parse_record(printed: str) -> dict[str, str]:
    """The `key value` lines `repro-archive build` printed (the RM pastes them back)."""
    record: dict[str, str] = {}
    for line in printed.splitlines():
        key, _, value = line.strip().partition(" ")
        if key in RECORD_KEYS and value:
            record[key] = value.strip()
    return record


def step4(
    cut: RcCut,
    *,
    record: dict[str, str] | None = None,
    self_check: str = "skipped",
    run_url: str | None = None,
    allow_unreviewed_archive: str | None = None,
    convenience_outcomes: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Step 4: the planning-issue comment that records the RC for downstream skills."""
    record = record or {}
    outcomes = convenience_outcomes or {}

    def rec(key: str) -> str:
        return f"`{record[key]}`" if record.get(key) else "_(paste from `repro-archive build`)_"

    lines = [
        f"### Release candidate `{cut.tag}`",
        "",
        f"- **Tag:** https://github.com/{cut.upstream}/releases/tag/{cut.tag}",
        f"- **Staging:** {cut.meta.get('staging_url') or '_(not rendered)_'}",
        "- **Artefacts:** " + ", ".join(f"`{a}`" for a in cut.artefacts),
        "",
        "#### Reproducibility record",
        "",
        f"- Commit: {rec('commit')} — repository https://github.com/{cut.upstream}",
        f"- `SOURCE_DATE_EPOCH`: {rec('SOURCE_DATE_EPOCH')}",
        f"- sha512: {rec('sha512')}",
        f"- swhid_rev: {rec('swhid_rev')}",
        f"- swhid_dir: {rec('swhid_dir')}",
        f"- Content vs repository tree: {record.get('swhid_dir_note') or '_(paste from `repro-archive build`)_'}",
        f"- Archive: `{cut.meta.get('source_archive_format') or 'tar.gz'}`, prefix `{cut.meta.get('source_archive_prefix') or ''}`",
        f"- Self-check (Step 2b): {self_check}",
    ]
    if cut.ci_automated:
        lines.append(f"- CI run: {run_url or '_(paste the workflow run URL)_'}")
    entries = cut.convenience()
    if entries:
        lines += ["", "#### Convenience artefacts", ""]
        for entry in entries:
            lines.append(
                f"- `{entry['name']}` ({entry.get('kind') or 'artefact'}) — staged {entry.get('staging') or 'dist-dev'}, "
                f"reproducibility `{entry.get('reproducibility') or cut.meta.get('reproducibility_binaries') or 'off'}` "
                f"({outcomes.get(entry['name'], self_check)}), "
                f"{'in' if entry.get('vote_included') else 'not in'} the vote, built from {rec('swhid_dir')}"
            )
    if allow_unreviewed_archive is not None:
        lines += [
            "",
            "> **The source archive contents were not reviewed** (`--allow-unreviewed-archive`)"
            + (f": {allow_unreviewed_archive}" if allow_unreviewed_archive else "."),
        ]
    lines += ["", "Proposed next label: `rc-staging`"]
    missing = [k for k in ("commit", "SOURCE_DATE_EPOCH", "sha512", "swhid_dir") if not record.get(k)]
    return {
        "proposed_comment_summary": f"Records RC {cut.tag}: tag, staging URL, {len(cut.artefacts)} artefact(s) and the reproducibility record.",
        "includes_rc_tag": True,
        "includes_staging_url": bool(cut.meta.get("staging_url")),
        "includes_artefact_list": bool(cut.artefacts),
        "proposed_label": "rc-staging",
        "proposed": True,
        "record_missing": missing,
        "comment": "\n".join(lines) + "\n",
    }
