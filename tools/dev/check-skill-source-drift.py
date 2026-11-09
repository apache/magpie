#!/usr/bin/env python3
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
"""
Check the curated skill sources against what their repositories ship today.

A source that versions its skills independently is curated as one descriptor
per skill, each pinned to that skill's ``<skill>-<version>`` tag. Descriptors
that share a repository are checked together, against one catalogue named
after any one of them.

An organization's ``organizations/<org>/skill-sources.md`` pins a source to a
tag and may also carry a *catalogue*: a table, between
``<!-- BEGIN SKILL-SOURCE CATALOGUE: <id> -->`` and the matching ``END``
marker, of every skill the source ships and how each one installs. Both go
stale silently: a source adds a skill, turns a single-file skill into a
directory, tags a skill for the first time, or tags a newer version of the
pinned one, and nothing in this repository notices. This script notices.

For every descriptor whose ``url`` is a GitHub repository it reads, through
the GitHub REST API:

- the skills under ``layout.skills_root`` on the default branch: a ``<name>.md``
  file (``single-file``), a ``<name>/SKILL.md`` directory (``untagged``, or
  ``pinned`` when ``provides`` names it), and anything under ``draft/``
  (``draft``);
- the repository's tags, to resolve the pin and find newer ones;
- the plugin catalog of each agent marketplace the source may publish to
  (``MARKETPLACES``: Claude Code, Codex, GitHub Copilot), for the catalogue's
  last column — the marketplaces a skill installs from, comma-separated, or
  ``—`` for none.

It reports, as Markdown on stdout:

- a skill the source ships that the catalogue does not list, or the reverse;
- a catalogue status that no longer matches the source's layout;
- a skill named in ``provides`` that is not a directory at the pinned tag;
- a pinned tag that no longer resolves to the recorded ``commit`` (a moved
  tag: treat it as suspicious, never re-pin blindly);
- a newer ``<skill>-<version>`` tag for a pinned skill, or a first tag for an
  unpinned one;
- a marketplaces column that disagrees with the source's catalogs.

Exit status: 0 when everything matches, 1 when there is drift to act on,
2 when the check itself could not run (a network or API error, a catalogue
naming an unknown source). Read-only: it never edits a file.

Usage:

    check-skill-source-drift.py              # report on every org's sources
    check-skill-source-drift.py --root DIR   # repository root (default: this repo)

Set ``GITHUB_TOKEN`` (or ``GH_TOKEN``) to raise the API rate limit.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
API = "https://api.github.com"

STATUSES = ("pinned", "untagged", "single-file", "draft")
# Agent marketplace -> the catalog file it reads at the source's root. The same
# paths apache/magpie publishes its own plugins under (docs/setup/marketplace.md).
MARKETPLACES = {
    "claude-code": ".claude-plugin/marketplace.json",
    "codex": ".agents/plugins/marketplace.json",
    "copilot": "marketplace.json",
}
DRAFT_DIR = "draft"

_CATALOGUE_RE = re.compile(
    r"<!--\s*BEGIN SKILL-SOURCE CATALOGUE:\s*(?P<id>[\w.-]+)\s*-->(?P<body>.*?)"
    r"<!--\s*END SKILL-SOURCE CATALOGUE:\s*(?P=id)\s*-->",
    re.DOTALL,
)
_FENCE_RE = re.compile(r"^```ya?ml\s*$(?P<body>.*?)^```\s*$", re.DOTALL | re.MULTILINE)
_GITHUB_URL_RE = re.compile(r"^https://github\.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+?)(?:\.git)?/?$")
_VERSIONED_REF_RE = re.compile(r"^(?P<name>.+?)-v?(?P<version>\d+(?:\.\d+)*)$")


class CheckError(Exception):
    """The check could not run; distinct from drift, which is a result."""


# --------------------------------------------------------------------------
# Parsing the org files
# --------------------------------------------------------------------------


@dataclass
class Descriptor:
    id: str
    url: str = ""
    ref: str = ""
    commit: str = ""
    method: str = ""
    skills_root: str = "skills"
    provides: list[str] = field(default_factory=list)


@dataclass
class CatalogueRow:
    skill: str
    status: str
    marketplaces: frozenset[str]


def parse_descriptors(text: str) -> list[Descriptor]:
    """Read the descriptors in the ```yaml fences — stdlib only, the same
    flat shape the skill validator parses. Commented lines and placeholder
    ids (``<source-id>``) declare nothing."""
    out: list[Descriptor] = []
    for fence in _FENCE_RE.finditer(text):
        cur: Descriptor | None = None
        for raw in fence.group("body").splitlines():
            line = raw.rstrip()
            if not line.strip() or line.lstrip().startswith("#"):
                continue
            m = re.match(r"^\s*(?:-\s+)?id:\s*(\S+)\s*$", line)
            if m:
                source_id = m.group(1).strip("'\"")
                cur = None if "<" in source_id else Descriptor(id=source_id)
                if cur is not None:
                    out.append(cur)
                continue
            if cur is None:
                continue
            m = re.match(r"^\s*-\s+skill:\s*(\S+)\s*$", line)
            if m:
                cur.provides.append(m.group(1).strip("'\""))
                continue
            m = re.match(r"^\s*([A-Za-z_][\w-]*):\s*(.*?)\s*$", line)
            if m:
                key, val = m.group(1), m.group(2).split(" #")[0].strip().strip("'\"")
                if key in ("url", "ref", "commit", "method", "skills_root") and val:
                    setattr(cur, key, val)
    return out


def _cell(text: str) -> str:
    return text.strip().strip("`").strip()


def parse_catalogues(text: str) -> dict[str, list[CatalogueRow]]:
    """Read every catalogue table: first column the skill, the *Install
    through Magpie* status the first cell that is a known status, the last
    column the marketplaces the skill installs from."""
    out: dict[str, list[CatalogueRow]] = {}
    for m in _CATALOGUE_RE.finditer(text):
        rows: list[CatalogueRow] = []
        for line in m.group("body").splitlines():
            line = line.strip()
            if not line.startswith("|") or set(line) <= set("|-: "):
                continue
            cells = [_cell(c) for c in line.strip("|").split("|")]
            if cells[0].lower() == "skill":
                continue
            status = next((c for c in cells[1:] if c in STATUSES), "")
            if not status:
                raise CheckError(f"catalogue {m.group('id')}: row for {cells[0]!r} has no status")
            names = frozenset(n.strip().strip("`") for n in cells[-1].split(",")) - {"", "—", "-"}
            unknown = names - set(MARKETPLACES)
            if unknown:
                raise CheckError(
                    f"catalogue {m.group('id')}: {cells[0]!r} names unknown marketplace(s) {sorted(unknown)}"
                )
            rows.append(CatalogueRow(cells[0], status, names))
        out[m.group("id")] = rows
    return out


# --------------------------------------------------------------------------
# Reading the source repository
# --------------------------------------------------------------------------

Fetch = Callable[[str], object]
"""GET an API path (``/repos/...``); return parsed JSON, or None on 404."""


def github_fetch(path: str) -> object:
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    req = urllib.request.Request(API + path, headers={"Accept": "application/vnd.github+json"})
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return None
        raise CheckError(f"GET {path}: HTTP {exc.code}") from exc
    except urllib.error.URLError as exc:
        raise CheckError(f"GET {path}: {exc.reason}") from exc


@dataclass
class Upstream:
    layout: dict[str, str]
    """skill name -> ``single-file`` / ``directory`` / ``draft`` at the default branch."""
    tags: dict[str, str]
    """tag name -> the commit it resolves to (resolved lazily; '' until then)."""
    marketplaces: dict[str, set[str]]
    """marketplace -> the plugin names its catalog lists."""


def _listing(fetch: Fetch, base: str, path: str, ref: str | None = None) -> list[dict[str, str]]:
    query = f"?ref={urllib.parse.quote(ref)}" if ref else ""
    got = fetch(f"{base}/contents/{urllib.parse.quote(path)}{query}")
    return got if isinstance(got, list) else []


def read_layout(fetch: Fetch, base: str, skills_root: str) -> dict[str, str]:
    layout: dict[str, str] = {}
    for entry in _listing(fetch, base, skills_root):
        name, kind = entry["name"], entry["type"]
        if kind == "file" and name.endswith(".md") and name.lower() != "readme.md":
            layout[name[:-3]] = "single-file"
        elif kind == "dir" and name == DRAFT_DIR:
            for sub in _listing(fetch, base, f"{skills_root}/{name}"):
                if sub["type"] == "file" and sub["name"].endswith(".md"):
                    layout[sub["name"][:-3]] = "draft"
                elif sub["type"] == "dir":
                    layout[sub["name"]] = "draft"
        elif kind == "dir":
            files = {e["name"] for e in _listing(fetch, base, f"{skills_root}/{name}")}
            if "SKILL.md" in files:
                layout[name] = "directory"
    return layout


def read_tags(fetch: Fetch, base: str) -> dict[str, str]:
    refs = fetch(f"{base}/git/matching-refs/tags/") or []
    assert isinstance(refs, list)
    return {r["ref"].removeprefix("refs/tags/"): "" for r in refs}


def resolve_tag(fetch: Fetch, base: str, tag: str) -> str:
    """The commit a tag points at, peeling an annotated tag."""
    ref = fetch(f"{base}/git/ref/tags/{urllib.parse.quote(tag)}")
    if not isinstance(ref, dict):
        return ""
    obj = ref["object"]
    while obj["type"] == "tag":
        tag_obj = fetch(f"{base}/git/tags/{obj['sha']}")
        assert isinstance(tag_obj, dict)
        obj = tag_obj["object"]
    return str(obj["sha"])


def read_marketplaces(fetch: Fetch, base: str) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for market, path in MARKETPLACES.items():
        got = fetch(f"{base}/contents/{path}")
        if not isinstance(got, dict) or "content" not in got:
            out[market] = set()
            continue
        data = json.loads(base64.b64decode(got["content"]))
        out[market] = {p["name"] for p in data.get("plugins", [])}
    return out


# --------------------------------------------------------------------------
# Comparing
# --------------------------------------------------------------------------


def _version(text: str) -> tuple[int, ...]:
    return tuple(int(p) for p in text.split("."))


def tags_for(skill: str, tags: dict[str, str]) -> list[tuple[tuple[int, ...], str]]:
    """``<skill>-<version>`` tags for one skill, oldest first."""
    found = []
    for tag in tags:
        m = _VERSIONED_REF_RE.match(tag)
        if m and m.group("name") == skill:
            found.append((_version(m.group("version")), tag))
    return sorted(found)


def check_pin(desc: Descriptor, upstream: Upstream, pin_commit: str, pinned_dirs: set[str]) -> list[str]:
    """Findings for one descriptor's pin: the tag, its layout, newer tags."""
    findings: list[str] = []
    if desc.method == "git-tag" and desc.commit and pin_commit and pin_commit != desc.commit:
        findings.append(
            f"**Pinned tag moved.** `{desc.id}`: `{desc.ref}` now resolves to `{pin_commit[:12]}`, "
            f"not the recorded `{desc.commit[:12]}`. Find out why before re-pinning."
        )
    elif desc.method == "git-tag" and not pin_commit:
        findings.append(f"**Pinned tag missing.** `{desc.id}`: `{desc.ref}` no longer exists in the source.")
    for skill in desc.provides:
        if skill not in pinned_dirs:
            findings.append(
                f"`{skill}` is in `{desc.id}`'s `provides` but is not a "
                f"`{desc.skills_root}/{skill}/SKILL.md` directory at `{desc.ref}`, "
                f"so `/magpie-setup:setup skill-sources` cannot wire it."
            )
    pin_name = _VERSIONED_REF_RE.match(desc.ref)
    if pin_name:
        skill_tags = tags_for(pin_name.group("name"), upstream.tags)
        if skill_tags and skill_tags[-1][0] > _version(pin_name.group("version")):
            findings.append(f"**Newer tag** `{skill_tags[-1][1]}` for `{desc.id}` (pinned to `{desc.ref}`).")
    return findings


def compare_catalogue(rows: list[CatalogueRow], upstream: Upstream, provided: set[str]) -> list[str]:
    """Findings for the catalogue against the source's default branch."""
    findings: list[str] = []
    listed = {r.skill: r for r in rows}
    for skill in sorted(set(upstream.layout) | set(listed)):
        row, kind = listed.get(skill), upstream.layout.get(skill)
        if row is None:
            findings.append(f"**New skill** `{skill}` ({kind}) is not in the catalogue.")
            continue
        if kind is None:
            findings.append(f"`{skill}` is in the catalogue but the source no longer ships it.")
            continue
        if skill in provided:
            expected = "pinned"
        elif kind == "directory":
            expected = "untagged"
        else:
            expected = kind
        if row.status != expected:
            findings.append(f"`{skill}` is catalogued `{row.status}`, but the source makes it `{expected}`.")
        actual = {market for market, names in upstream.marketplaces.items() if skill in names}
        if actual != row.marketplaces:
            shown = ", ".join(sorted(actual)) or "none"
            findings.append(
                f"`{skill}` installs from these marketplaces: {shown}; the catalogue says "
                f"{', '.join(sorted(row.marketplaces)) or 'none'}."
            )
        skill_tags = tags_for(skill, upstream.tags)
        if skill_tags and skill not in provided and kind != "draft":
            findings.append(
                f"**Tagged** `{skill}` is now tagged (`{skill_tags[-1][1]}`) and could be pinned."
            )
    return findings


def check_repo(fetch: Fetch, descs: list[Descriptor], rows: list[CatalogueRow] | None) -> list[str]:
    """Check every descriptor that points at one repository, and its catalogue.

    A source that versions its skills independently is curated as one
    descriptor per skill, each pinned to that skill's own tag; they share the
    repository, so they share one catalogue."""
    m = _GITHUB_URL_RE.match(descs[0].url)
    if not m:
        return [f"Skipped: `{descs[0].url}` is not a GitHub repository; check it by hand."]
    base = f"/repos/{m.group('owner')}/{m.group('repo')}"
    upstream = Upstream(
        layout=read_layout(fetch, base, descs[0].skills_root),
        tags=read_tags(fetch, base),
        marketplaces=read_marketplaces(fetch, base),
    )
    findings: list[str] = []
    provided: set[str] = set()
    for desc in descs:
        pin_commit = resolve_tag(fetch, base, desc.ref) if desc.method == "git-tag" else ""
        pinned_dirs = set()
        for skill in desc.provides:
            files = {e["name"] for e in _listing(fetch, base, f"{desc.skills_root}/{skill}", desc.ref)}
            if "SKILL.md" in files:
                pinned_dirs.add(skill)
        provided.update(desc.provides)
        findings += check_pin(desc, upstream, pin_commit, pinned_dirs)
    if rows is None:
        findings.append(
            f"No catalogue for `{descs[0].url}`: add one so new skills in the source get noticed."
        )
    else:
        findings += compare_catalogue(rows, upstream, provided)
    return findings


def run(root: Path, fetch: Fetch) -> tuple[int, str]:
    sections: list[str] = []
    drift = False
    for path in sorted((root / "organizations").glob("*/skill-sources.md")):
        if path.parent.name.startswith("_"):
            continue
        rel = path.relative_to(root)
        text = path.read_text(encoding="utf-8")
        descriptors = {d.id: d for d in parse_descriptors(text)}
        catalogues = parse_catalogues(text)
        unknown = set(catalogues) - set(descriptors)
        if unknown:
            raise CheckError(f"{rel}: catalogue for unknown source(s) {sorted(unknown)}")
        by_repo: dict[str, list[Descriptor]] = {}
        for desc in descriptors.values():
            by_repo.setdefault(desc.url.rstrip("/").removesuffix(".git"), []).append(desc)
        for descs in by_repo.values():
            ids = {d.id for d in descs}
            named = [cid for cid in catalogues if cid in ids]
            if len(named) > 1:
                raise CheckError(f"{rel}: more than one catalogue for {descs[0].url}: {named}")
            rows = catalogues[named[0]] if named else None
            findings = check_repo(fetch, descs, rows)
            title = f"### `{descs[0].url}` ({rel})"
            if findings:
                drift = drift or any(not f.startswith("Skipped:") for f in findings)
                sections.append(title + "\n\n" + "\n".join(f"- {f}" for f in findings))
            else:
                sections.append(title + "\n\nIn sync.")
    report = "## Skill-source drift\n\n" + ("\n\n".join(sections) if sections else "No curated sources.")
    return (1 if drift else 0), report + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    args = parser.parse_args(argv)
    try:
        status, report = run(args.root, github_fetch)
    except CheckError as exc:
        print(f"check-skill-source-drift: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(report)
    return status


if __name__ == "__main__":
    sys.exit(main())
