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
"""The loaded release configuration: raw values, defaults, derived values."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from release_config import mdconfig as md

RMC = "release-management-config.md"
BUILD = "release-build.md"
TRAINS = "release-trains.md"
PMC_ROSTER = "pmc-roster.md"
PROJECT = "project.md"

# Defaults the templates and skills state for optional keys. Required keys
# (checked per skill) never get a default.
CONFIG_DEFAULTS: dict[str, Any] = {
    "git_upstream_remote": "origin",
    "release_vote_backend": "manual",
    "keyserver": "keys.openpgp.org",
    "automated_release_signing": "off",
    "vote_verification_skill": "magpie-release-management:verify-rc",
    "release_approver_roster_path": "<project-config>/pmc-roster.md",
}
DIST_BACKENDS = ("svnpubsub", "atr", "github-releases", "s3", "self-hosted")
# The ASF distribution backends; both mirror dist/release to archive.apache.org.
ASF_DIST_BACKENDS = ("svnpubsub", "atr")
ASF_ARCHIVE_DEFAULT = "https://archive.apache.org/dist/<project>/"
ORG_MANIFEST = "organization.md"

_DIGEST = re.compile(r"^(sha\d+|sha3-\d+|sha-\d+|md5|sha1|blake2\w*)$", re.IGNORECASE)


@dataclass
class BuildConfig:
    found: bool
    table: dict[str, Any] = field(default_factory=dict)
    sections: dict[str, bool] = field(default_factory=dict)
    build_command: str | None = None
    build_command_declared: bool = False
    expected_artefacts: list[dict[str, str]] = field(default_factory=list)
    digest_set: list[str] = field(default_factory=list)
    convenience_artefacts: list[dict[str, Any]] = field(default_factory=list)
    template_example_skipped: bool = False

    def value(self, key: str, default: Any = None) -> Any:
        value = self.table.get(key)
        return default if value in (None, "", []) else value

    @property
    def source_archive_method(self) -> str:
        return str(self.value("source_archive_method", "git-archive"))

    @property
    def reproducibility_source(self) -> str:
        default = "on" if self.source_archive_method == "git-archive" else "off"
        return str(self.value("reproducibility_source", default))

    @property
    def reproducibility_binaries(self) -> str:
        return str(self.value("reproducibility_binaries", "off"))

    def as_dict(self) -> dict[str, Any]:
        return {
            "found": self.found,
            "sections": self.sections,
            "build_command": self.build_command,
            "expected_artefacts": self.expected_artefacts,
            "digest_set": self.digest_set,
            "source_archive_method": self.source_archive_method,
            "source_archive_format": str(self.value("source_archive_format", "tar.gz")),
            "source_archive_prefix": self.value("source_archive_prefix"),
            "export_ignore_reviewed": self.value("export_ignore_reviewed"),
            "reproducibility_source": self.reproducibility_source,
            "reproducibility_binaries": self.reproducibility_binaries,
            "convenience_artefacts": self.convenience_artefacts,
        }


def _expected_artefacts(block: str | None) -> list[dict[str, str]]:
    """Filenames in backticks (no spaces, has a dot), kind from the words after each."""
    if not block:
        return []
    spans = [(m.start(), m.end(), m.group(1).strip()) for m in re.finditer(r"`([^`]+)`", block)]
    spans = [s for s in spans if " " not in s[2] and "." in s[2] and not s[2].startswith(("http", "-"))]
    out: list[dict[str, str]] = []
    for index, (_, end, name) in enumerate(spans):
        tail = block[end : spans[index + 1][0] if index + 1 < len(spans) else len(block)]
        convenience = re.search(r"\bconvenience\b", tail, re.IGNORECASE) and not re.search(r"\bno convenience\b", tail, re.IGNORECASE)
        out.append({"name": name, "kind": "convenience" if convenience else "source"})
    return out


def load_build(text: str | None) -> BuildConfig:
    if text is None:
        return BuildConfig(found=False)
    build = BuildConfig(found=True, table=md.table_values(text))
    names = {
        "source_archive": "Source archive",
        "build_invocation": "Build invocation",
        "convenience_artefacts": "Convenience artefacts",
        "expected_artefacts": "Expected artefact",
        "digest_set": "Digest set",
        "reproducibility_checks": "Reproducibility checks",
        "binary_exclude": "Binary-exclude",
        "rat_configuration": "RAT configuration",
    }
    sections = {key: md.section_lines(text, title) for key, title in names.items()}
    build.sections = {key: lines is not None for key, lines in sections.items()}

    # build_command: a table key, else the section's first unquoted fence.
    if "build_command" in build.table:
        build.build_command_declared = True
        build.build_command = build.table["build_command"] or None
    elif sections["build_invocation"] is not None:
        build.build_command_declared = True
        build.build_command = md.first_fence(sections["build_invocation"])

    if build.table.get("expected_artefacts"):
        build.expected_artefacts = [{"name": n, "kind": "source" if i == 0 else "convenience"} for i, n in enumerate(build.table["expected_artefacts"])]
    else:
        build.expected_artefacts = _expected_artefacts(md.first_text_block(sections["expected_artefacts"]))

    if build.table.get("digest_set"):
        build.digest_set = [d.lower() for d in build.table["digest_set"]]
    else:
        tokens = md.backtick_tokens(md.first_text_block(sections["digest_set"]))
        build.digest_set = [t.lower() for t in tokens if _DIGEST.match(t)]

    fence = md.first_fence(sections["convenience_artefacts"], "yaml")
    entries = md.parse_yaml_list(fence, "convenience_artefacts") if fence else None
    for entry in entries or []:
        if "<project>" in str(entry.get("name", "")):
            build.template_example_skipped = True
            continue
        if "reproducibility" not in entry or entry["reproducibility"] in (None, ""):
            entry["reproducibility"] = build.reproducibility_binaries
        build.convenience_artefacts.append(entry)
    return build


def parse_time(value: str) -> datetime:
    """`2026-06-11 09:45 UTC`, `2026-06-11T09:45:00Z`, `…+00:00` → aware UTC datetime."""
    text = value.strip().replace(" UTC", "").replace("UTC", "").strip()
    text = text.replace("Z", "+00:00")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}(:\d{2})?", text):
        text = text.replace(" ", "T")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def plus_one_hour(value: str) -> str:
    return iso(parse_time(value) + timedelta(hours=1))


def render_dist_url(template: str, version: str, rc: str | None, bucket: str) -> str:
    """Render `release_dist_url_template` for staging (`rc` set) or the final release (`rc` None).

    `<bucket>` → `dev` / `release`. A template that spells the RC itself
    (`<version>-<rcN>`) gets the RC substituted there, or the `-<rcN>` segment
    stripped for the release URL; otherwise `<version>` becomes `<version>-rcN`
    for staging and plain `<version>` for the release.
    """
    url = template.replace("<bucket>", bucket)
    rc_marker = re.search(r"-?<rc ?N>|-?<rcN>|-?rc<N>", url)
    if rc_marker:
        marker = rc_marker.group(0)
        replacement = ("-" + rc if marker.startswith("-") else rc) if rc else ""
        return url.replace(marker, replacement).replace("<version>", version)
    return url.replace("<version>", f"{version}-{rc}" if rc else version)


@dataclass
class Loaded:
    resolver: md.Resolver
    sources: dict[str, str | None]
    raw: dict[str, Any]
    build: BuildConfig
    organization: str
    trains_text: str | None
    user_text: str | None
    automated_signing_offered: bool = False
    automated_signing_source: str = "framework default"

    def present(self, key: str) -> bool:
        value = self.raw.get(key)
        return value not in (None, "", [])

    def get(self, key: str) -> Any:
        if self.present(key):
            return self.raw[key]
        return CONFIG_DEFAULTS.get(key)

    @property
    def is_asf(self) -> bool:
        """`project.md` → `organization: ASF` — the one ASF-identity rule."""
        return self.organization.upper() == "ASF"

    @property
    def non_asf(self) -> bool:
        return not self.is_asf

    @property
    def approver_roster_path(self) -> str:
        """`release_approver_roster_path`, default `<project-config>/pmc-roster.md`."""
        return str(self.get("release_approver_roster_path"))

    @property
    def signing_mode(self) -> str:
        enabled = str(self.get("automated_release_signing")) == "enabled"
        return "ci-automated" if self.automated_signing_offered and enabled else "rm-key"

    def release_lines(self) -> list[str]:
        block = md.first_text_block(md.section_lines(self.trains_text, "Release branches currently in flight"))
        if block is None and self.trains_text is not None and md.section_lines(self.trains_text, "Release branches") is None:
            block = md.first_text_block(self.trains_text.splitlines())
        if not block:
            return []
        lines = [part.strip() for part in re.split(r"(?:^|\s)[-*]\s+(?=\S)", block) if part.strip()]
        return lines

    def config_with_defaults(self) -> dict[str, Any]:
        merged = dict(CONFIG_DEFAULTS)
        merged.update({k: v for k, v in self.raw.items() if v not in (None, "", [])})
        return merged


def _framework_roots(project_root: Path) -> list[Path]:
    """Where the framework's `organizations/` may live: this checkout, the adopter's snapshot, the repo itself."""
    candidates = [Path(__file__).resolve().parents[4], project_root / ".apache-magpie", project_root]
    return [root for root in candidates if (root / "organizations").is_dir()]


def org_manifest_chain(resolver: md.Resolver, organization: str) -> list[tuple[Path, str]]:
    """The organization manifests in resolution order, each with a display label: in-tree, then adopter-local."""
    chain: list[tuple[Path, str]] = []
    rel = f"organizations/{organization}/{ORG_MANIFEST}"
    for root in _framework_roots(resolver.project_root)[:1]:
        path = root / rel
        if path.is_file():
            chain.append((path, f"<framework>/{rel}"))
    local = resolver.find(rel)
    if local is not None:
        chain.append((local, resolver.display(local) or str(local)))
    return chain


def automated_signing(project_text: str | None, resolver: md.Resolver, organization: str) -> tuple[bool, str]:
    """`release_process.automated_signing`: project.md → organization manifest → framework default (not offered)."""
    declared = md.nested_key_declared(project_text, "release_process", "automated_signing")
    if declared is not None:
        return declared, "project.md"
    for path, label in org_manifest_chain(resolver, organization):
        declared = md.nested_key_declared(md.read_text(path), "release_process", "automated_signing")
        if declared is not None:
            return declared, label
    return False, "framework default"


def load(project_root: Path, config_dir: Path | None, user_config: str | None) -> Loaded:
    resolver = md.Resolver(project_root, config_dir)
    paths = {name: resolver.find(name) for name in (RMC, BUILD, TRAINS, PMC_ROSTER, PROJECT)}
    user_path = md.user_config_path(user_config, resolver)
    texts = {name: md.read_text(path) for name, path in paths.items()}
    sources = {name: resolver.display(path) for name, path in paths.items()}
    sources["user.md"] = str(user_path) if user_path else None
    organization = md.organization(texts[PROJECT])
    offered, offered_source = automated_signing(texts[PROJECT], resolver, organization)
    return Loaded(
        resolver=resolver,
        sources=sources,
        raw=md.table_values(texts[RMC]) if texts[RMC] is not None else {},
        build=load_build(texts[BUILD]),
        organization=organization,
        trains_text=texts[TRAINS],
        user_text=md.read_text(user_path),
        automated_signing_offered=offered,
        automated_signing_source=offered_source,
    )
