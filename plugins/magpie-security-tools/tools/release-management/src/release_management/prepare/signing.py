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
"""release-prepare Step A (🪶 ASF-specific): the eligibility gate, the workflow file and the config diff.

Read from `release-config load --skill prepare automated-signing`. The Infra
ticket and the Security Team mail stay drafts the agent writes and the
release manager files and sends; nothing here holds or names key material.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_WORKFLOW = ".github/workflows/release-candidate.yml"
WORKFLOW_TITLE = "ci: add the reproducible release-candidate workflow (ATR staging, no signing step)"
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PREFIX = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
FORMAT = re.compile(r"^[a-z0-9][a-z0-9.]*$")
KEY_MATERIAL = re.compile(
    r"BEGIN PGP|PRIVATE KEY|gpg\s+--(?:batch\s+)?(?:--)?(?:sign|detach-sign|import)", re.IGNORECASE
)
#: Any signing tool or key-import action in the release manager's `build_command`.
SIGNING_IN_BUILD = re.compile(
    r"\bgpg2?\b|\bsignify\b|\bcosign\s+sign|\bminisign\b|ghaction-import-gpg|import-gpg", re.IGNORECASE
)
NOT_REPRODUCIBLE = "no release-verify-rc report with Step 9 PASS and every artefact `identical`: cut and verify one RC with the checks on first"
ENABLED_AFTER = (
    "Infra has provisioned the key",
    "its public block is in KEYS (`release-keys-sync`)",
    "the Security Team has approved the workflow",
    "the workflow PR is merged",
)


class RenderError(ValueError):
    """The workflow cannot be rendered from these values; the skill surfaces this and stops."""


def eligibility(load: dict[str, Any], *, verify_rc_identical: bool = False) -> dict[str, Any]:
    """A1: every condition of the gate, fail-closed; `--verify-rc-identical` is the planning-issue fact."""
    derived = load.get("derived") or {}
    build = load.get("build") or {}
    config = load.get("config") or {}
    organization = load.get("organization") or "independent"
    missing: list[str] = []
    if not derived.get("automated_signing_offered"):
        missing.append(
            f"automated release signing is not offered: release_process.automated_signing is not set "
            f"for this project's organization ({organization})"
        )
    if not build.get("found"):
        missing.append("release-build.md not found in <project-config>")
    if build.get("source_archive_method") != "git-archive":
        missing.append(
            f"release-build.md source_archive_method is {build.get('source_archive_method')!r}; it must be `git-archive`"
        )
    if build.get("reproducibility_source") != "on":
        missing.append(
            f"release-build.md reproducibility_source is {build.get('reproducibility_source')!r}; it must be `on`"
        )
    convenience = build.get("convenience_artefacts") or []
    for entry in convenience:
        if entry.get("reproducibility") != "byte-identical":
            missing.append(
                f"convenience artefact {entry.get('name')!r} has reproducibility {entry.get('reproducibility')!r}; it must be `byte-identical`"
            )
    has_binaries = any(a.get("kind") == "convenience" for a in build.get("expected_artefacts") or [])
    if not convenience and has_binaries and build.get("reproducibility_binaries") != "byte-identical":
        missing.append(
            f"release-build.md reproducibility_binaries is {build.get('reproducibility_binaries')!r} "
            "with convenience binaries in expected_artefacts; it must be `byte-identical`"
        )
    if not verify_rc_identical:
        missing.append(NOT_REPRODUCIBLE)
    if "atr" not in (config.get("release_vote_backend"), config.get("release_dist_backend")):
        missing.append(
            "neither release_vote_backend nor release_dist_backend is `atr`: the workflow stages to ATR"
        )
    eligible = not missing
    return {
        "organization": organization,
        "eligible": eligible,
        "missing_conditions": missing,
        "workflow_path": config.get("ci_release_workflow") or DEFAULT_WORKFLOW,
        "read": [] if eligible else ["automated-signing-ineligible.md"],
    }


def _artefact_prefix(prefix: Any, project: str) -> str:
    text = str(prefix or f"apache-{project}")
    return re.sub(r"-?<version>$", "", text) or f"apache-{project}"


def workflow(load: dict[str, Any], template: str, *, project: str) -> dict[str, Any]:
    """A4: the template with the project's slug, artefact prefix, source format and build command."""
    build = load.get("build") or {}
    config = load.get("config") or {}
    if not SLUG.match(project):
        raise RenderError(f"--project {project!r} is not an ASF project slug")
    prefix = _artefact_prefix(build.get("source_archive_prefix"), project)
    fmt = str(build.get("source_archive_format") or "tar.gz")
    if not PREFIX.match(prefix):
        raise RenderError(f"source_archive_prefix {prefix!r} cannot be written into the workflow")
    if not FORMAT.match(fmt):
        raise RenderError(f"source_archive_format {fmt!r} cannot be written into the workflow")
    text = template
    text = text.replace("ARTEFACT_PREFIX: apache-<project>        ", f"ARTEFACT_PREFIX: {prefix:<24}", 1)
    text = text.replace("SOURCE_FORMAT: tar.gz                    ", f"SOURCE_FORMAT: {fmt:<26}", 1)
    text = text.replace("PROJECT: <project>                       ", f"PROJECT: {project:<32}", 1)
    text = text.replace("<project>", project)
    warnings: list[str] = []
    command = build.get("build_command")
    if command and SIGNING_IN_BUILD.search(str(command)):
        raise RenderError(
            "build_command invokes a signing tool or imports a key; Step A never adds a signing step"
        )
    if command:
        indented = "\n".join(
            ("          " + line) if line.strip() else "" for line in str(command).splitlines()
        )
        text = text.replace("          <BUILD_COMMAND>", indented, 1)
        text = text.replace("<BUILD_COMMAND>", "the build command above")
    else:
        warnings.append(
            "no build_command (source-only): delete the 'Build convenience binaries' step and the binary rebuild note"
        )
    unpinned = [line.strip() for line in text.splitlines() if "@<COMMIT_SHA>" in line]
    if unpinned:
        warnings.append(f"{len(unpinned)} action(s) still need pinning to a commit SHA")
    if KEY_MATERIAL.search(text):
        raise RenderError(
            "the rendered workflow contains key material or a signing step; Step A never adds one"
        )
    path = config.get("ci_release_workflow") or DEFAULT_WORKFLOW
    return {
        "workflow_pr": {"path": path, "title": WORKFLOW_TITLE, "proposed": True},
        "content": text,
        "unpinned_actions": unpinned,
        "warnings": warnings,
    }


def config_diff(load: dict[str, Any], *, infra_ticket: str | None = None) -> dict[str, Any]:
    """A5: the `release-management-config.md § Signing` lines, and what has to happen before `enabled`."""
    config = load.get("config") or {}
    path = config.get("ci_release_workflow") or DEFAULT_WORKFLOW
    diff = ["automated_release_signing: requested", f"ci_release_workflow: {path}"]
    diff.append(
        f"ci_signing_infra_ticket: {infra_ticket}"
        if infra_ticket
        else "ci_signing_infra_ticket: (once the ticket exists)"
    )
    return {"config_diff": diff, "enabled_only_after": list(ENABLED_AFTER)}
