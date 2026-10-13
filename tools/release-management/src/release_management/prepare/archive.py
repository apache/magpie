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
"""release-prepare Step 2e: the source-archive contents review.

`mode` decides whether the full review, the drift check or nothing runs, and
renders the read-only listings to save from the local clone (into
`$TMPDIR`). `review` classifies every top-level entry from those listings
into the buckets of `docs/release-management/reproducibility.md`, proposes
the exclude-bucket entries in their `.gitattributes` form, and checks each
against the shipped files that reference it and the committed symlinks.
The release manager confirms every entry one by one; a *project's call* or
an unclassified entry is theirs to decide, and nothing here can propose
excluding a never-excludable path.
"""

from __future__ import annotations

import fnmatch
import posixpath
import re
from typing import Any

from release_management.shell import dq, w

NEVER = "ship, never excludable"
VOTER = "ship, input to voter checks"
SHIP = "ship"
CALL = "project's call"
VCS = "exclude: VCS metadata"
CI = "exclude: CI / bot config"
EDITOR = "exclude: editor / IDE"
LINT = "exclude: lint config not needed to build"
AGENT = "agent-view dirs"
SCRATCH = "exclude: release-tooling scratch"
RELAY = "exclude: agent-view relay"
INSIDE = "split: look inside"
UNCLASSIFIED = "unclassified"

EXCLUDE_BUCKETS = (VCS, CI, EDITOR, LINT, SCRATCH, RELAY)

NEVER_NAMES = re.compile(r"^(LICENSE|NOTICE|DISCLAIMER|DISCLAIMER-WIP)([.-].*)?$|^licenses$", re.IGNORECASE)
BUILD_DESCRIPTORS = {
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "package.json",
    "Cargo.toml",
    "Makefile",
    "CMakeLists.txt",
    "go.mod",
    "build.xml",
    "BUILD",
    "BUILD.bazel",
    "WORKSPACE",
    "MODULE.bazel",
    "meson.build",
    "configure.ac",
    "Gemfile",
    "requirements.txt",
}
LOCK_FILES = {
    "uv.lock", "poetry.lock", "Pipfile.lock", "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "Cargo.lock",
    "go.sum", "Gemfile.lock", "composer.lock",
}  # fmt: skip
TABLE = {
    ".asf.yaml": CALL,
    ".github": INSIDE,
    ".gitignore": CALL,
    ".gitattributes": VCS,
    ".gitmodules": VCS,
    ".mailmap": VCS,
    ".gitlab-ci.yml": CI,
    ".travis.yml": CI,
    ".circleci": CI,
    ".pre-commit-config.yaml": CI,
    ".github/workflows": CI,
    ".github/dependabot.yml": CI,
    ".idea": EDITOR,
    ".vscode": EDITOR,
    ".devcontainer": EDITOR,
    ".lychee.toml": LINT,
    ".markdownlint.json": LINT,
    ".typos.toml": LINT,
    ".zizmor.yml": LINT,
    ".yamllint": LINT,
    ".codespellrc": LINT,
    ".claude": AGENT,
    ".agents": AGENT,
    ".kiro": AGENT,
    ".cursor": AGENT,
    ".apache-magpie.session-state.json": SCRATCH,
    ".apache-magpie.local.lock": SCRATCH,
}
LOOK_INSIDE = {".github", ".claude", ".agents", ".kiro", ".cursor"}
DOAP = re.compile(r"^doap_.*\.rdf$")

LISTINGS_FULL = """\
git archive --format=tar HEAD | tar -tf - | sort > "$TMPDIR/would-ship.txt"
git ls-files > "$TMPDIR/tracked.txt"
git ls-files -s | awk -F'\\t' '$1 ~ /^120000 / {print $2}' | while IFS= read -r p; do printf '%s -> %s\\n' "$p" "$(readlink "$p")"; done > "$TMPDIR/symlinks.txt\""""


# --------------------------------------------------------------------------- when it runs


def mode(
    load: dict[str, Any], *, review_archive: bool = False, previous_tag: str | None = None
) -> dict[str, Any]:
    """Full review, drift check, or skipped — from `release-config load`'s `build`."""
    build = load.get("build") or {}
    method = build.get("source_archive_method") or "git-archive"
    reviewed = build.get("export_ignore_reviewed")
    if method == "custom":
        return {
            "mode": "skipped",
            "archive_review": "skipped",
            "reason": "source_archive_method is custom: the build owns the archive contents",
            "commands": "",
        }
    if review_archive or not reviewed:
        why = (
            "--review-archive was passed"
            if review_archive
            else "export_ignore_reviewed is unset in release-build.md"
        )
        return {"mode": "full", "reason": why, "export_ignore_reviewed": reviewed, "commands": LISTINGS_FULL}
    if not previous_tag:
        return {
            "mode": "full",
            "reason": f"export_ignore_reviewed is {reviewed} but no previous tag to diff against",
            "export_ignore_reviewed": reviewed,
            "commands": LISTINGS_FULL,
        }
    drift = "\n".join(
        [
            f'git diff --name-only {w(previous_tag)} HEAD > "$TMPDIR/changed.txt"',
            'git ls-files > "$TMPDIR/tracked.txt"',
        ]
    )
    return {
        "mode": "drift",
        "reason": f"export_ignore_reviewed is {reviewed}",
        "export_ignore_reviewed": reviewed,
        "previous_tag": previous_tag,
        "commands": drift,
    }


# --------------------------------------------------------------------------- listings


def lines(text: str | None) -> list[str]:
    return [ln.rstrip("\r") for ln in (text or "").splitlines() if ln.strip()]


def export_ignore_patterns(text: str | None) -> list[str]:
    """The patterns `.gitattributes` marks `export-ignore` (not `-export-ignore`)."""
    out = []
    for raw in lines(text):
        line = raw.strip()
        if line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) >= 2 and "export-ignore" in parts[1:]:
            out.append(parts[0])
    return out


def ignored(path: str, patterns: list[str]) -> bool:
    """Whether `path` (or a parent directory) matches an `export-ignore` pattern."""
    pieces = path.strip("/").split("/")
    prefixes = ["/".join(pieces[: i + 1]) for i in range(len(pieces))]
    for pattern in patterns:
        pat = pattern.rstrip("/")
        if pat.startswith("/") or "/" in pat:
            anchored = pat.lstrip("/")
            if any(fnmatch.fnmatchcase(p, anchored) for p in prefixes):
                return True
        elif any(fnmatch.fnmatchcase(part, pat) for part in pieces):
            return True
    return False


def parse_symlinks(text: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in lines(text):
        link, sep, target = line.partition(" -> ")
        if sep:
            out[link.strip().removeprefix("./")] = target.strip()
    return out


def parse_refs(text: str | None) -> dict[str, list[str]]:
    """`candidate<TAB>referrer` lines, as the rendered `git grep` loop prints them."""
    out: dict[str, list[str]] = {}
    for line in lines(text):
        candidate, sep, referrer = line.partition("\t")
        if sep:
            out.setdefault(candidate.strip(), []).append(referrer.strip())
    return out


def _resolve(link: str, target: str) -> str:
    return posixpath.normpath(posixpath.join(posixpath.dirname(link), target))


def _is_dir(path: str, tracked: list[str]) -> bool:
    prefix = path.rstrip("/") + "/"
    return any(t.startswith(prefix) for t in tracked)


def entry_form(path: str, tracked: list[str]) -> str:
    """Root-anchored `/name` for a root file, `dir/` for a directory, the path itself for a nested file."""
    if _is_dir(path, tracked):
        return path.rstrip("/") + "/"
    return f"/{path}" if "/" not in path else path


# --------------------------------------------------------------------------- classification


def bucket(path: str, *, voter_inputs: set[str], manifests: set[str]) -> str:
    name = path.rstrip("/")
    if name in voter_inputs:
        return VOTER
    top = name.split("/")[0]
    if "/" not in name and NEVER_NAMES.match(name):
        return NEVER
    if name in TABLE:
        return TABLE[name]
    if "/" in name:
        return SHIP if top in LOOK_INSIDE else bucket(top, voter_inputs=voter_inputs, manifests=manifests)
    if name in BUILD_DESCRIPTORS or name in LOCK_FILES or name in manifests:
        return SHIP
    if DOAP.match(name):
        return CALL
    if name.startswith("."):
        return UNCLASSIFIED
    return SHIP


def never_excludable(path: str, b: str, *, manifests: set[str]) -> str | None:
    name = path.rstrip("/")
    if b == NEVER:
        return "LICENSE / NOTICE / DISCLAIMER always ship"
    if b == VOTER:
        return "an input to the checks voters run (RAT excludes, in-tree validators)"
    if "/" not in name and (name in BUILD_DESCRIPTORS or name in LOCK_FILES or name in manifests):
        return "a build descriptor or lock file"
    return None


def _top_entries(tracked: list[str]) -> list[str]:
    seen: list[str] = []
    for path in tracked:
        top = path.split("/")[0]
        if top not in seen:
            seen.append(top)
    return sorted(seen)


def _children(top: str, tracked: list[str]) -> list[str]:
    seen: list[str] = []
    for path in tracked:
        parts = path.split("/")
        if parts[0] == top and len(parts) > 1:
            child = f"{top}/{parts[1]}"
            if child not in seen:
                seen.append(child)
    return sorted(seen)


def _chains(links: dict[str, str]) -> list[dict[str, str]]:
    """Every symlink whose resolved target is, or passes through, another committed symlink."""
    out = []
    for link, target in sorted(links.items()):
        resolved = _resolve(link, target)
        parts = resolved.split("/")
        for i in range(len(parts)):
            prefix = "/".join(parts[: i + 1])
            if prefix in links and prefix != link:
                out.append({"link": link, "target": target, "via": prefix})
                break
    return out


def _relay_dirs(chains: list[dict[str, str]]) -> list[str]:
    return sorted({posixpath.dirname(c["link"]) for c in chains if "/" in c["link"]})


def classify(
    tracked: list[str],
    *,
    links: dict[str, str] | None = None,
    voter_inputs: set[str] | None = None,
    manifests: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Every top-level entry with its bucket; `.github/` and the agent-view dirs one level down."""
    links = links or {}
    voters = {v.strip("/") for v in voter_inputs or set()}
    mans = {m.strip("/") for m in manifests or set()}
    relays = set(_relay_dirs(_chains(links)))
    out = []
    for top in _top_entries(tracked):
        b = bucket(top, voter_inputs=voters, manifests=mans)
        entry: dict[str, Any] = {"path": top, "bucket": b, "directory": _is_dir(top, tracked)}
        if top in LOOK_INSIDE:
            kids = []
            for child in _children(top, tracked):
                if child in relays:
                    cb = RELAY
                elif child in TABLE:
                    cb = TABLE[child]
                elif b == AGENT:
                    cb = AGENT
                else:
                    cb = SHIP
                kids.append({"path": child, "bucket": cb, "directory": _is_dir(child, tracked)})
            entry["inside"] = kids
        out.append(entry)
    return out


def _candidates(entries: list[dict[str, Any]], links: dict[str, str]) -> list[dict[str, Any]]:
    """The exclude-bucket entries, at the finest level classified; an agent-view dir whole unless it holds a canonical view."""
    chained = {c["link"] for c in _chains(links)}
    single_hop_tops = {link.split("/")[0] for link in links if link not in chained}
    out = []
    for entry in entries:
        inside = entry.get("inside")
        if entry["bucket"] == AGENT and entry["path"] not in single_hop_tops:
            out.append({"path": entry["path"], "bucket": AGENT})
            continue
        if inside is not None:
            out += [
                {"path": k["path"], "bucket": k["bucket"]} for k in inside if k["bucket"] in EXCLUDE_BUCKETS
            ]
            continue
        if entry["bucket"] in EXCLUDE_BUCKETS:
            out.append({"path": entry["path"], "bucket": entry["bucket"]})
    return out


def refs_command(candidates: list[str]) -> str:
    """One `git grep -l -F` per candidate, each hit prefixed with the candidate and a tab."""
    if not candidates:
        return ""
    words = " ".join(dq(c.rstrip("/").lstrip("/")) for c in candidates)
    return (
        f"for p in {words}; do "
        'git grep -l -F -- "$p" | awk -v p="$p" \'{print p "\\t" $0}\'; '
        'done > "$TMPDIR/refs.txt"'
    )


def before_after(framework: str = "<framework>") -> str:
    fw = w(framework)
    return "\n".join(
        [
            '# "before": the attributes committed at HEAD',
            f"uv run --project {fw}/tools/reproducible-archive repro-archive build \\",
            '  --ref HEAD --prefix p --format tar.gz -o "$TMPDIR/before.tar.gz"',
            '# "after": the proposed .gitattributes as edited in the working tree',
            f"uv run --project {fw}/tools/reproducible-archive repro-archive build \\",
            '  --ref HEAD --prefix p --format tar.gz --worktree-attributes -o "$TMPDIR/after.tar.gz"',
            f"uv run --project {fw}/tools/reproducible-archive repro-archive compare \\",
            '  "$TMPDIR/before.tar.gz" "$TMPDIR/after.tar.gz"   # \'removed\' = exactly what the review strips',
        ]
    )


def review(
    tracked: list[str],
    *,
    gitattributes: str | None = None,
    links: dict[str, str] | None = None,
    refs: dict[str, list[str]] | None = None,
    changed: list[str] | None = None,
    exclude: list[str] | None = None,
    keep: list[str] | None = None,
    reasons: dict[str, str] | None = None,
    voter_inputs: set[str] | None = None,
    manifests: set[str] | None = None,
    previous_tag: str | None = None,
    framework: str = "<framework>",
) -> dict[str, Any]:
    """The bucket table, the proposed entries and their checks; `changed` makes it the drift check."""
    links = links or {}
    voters = {v.strip("/") for v in voter_inputs or set()}
    mans = {m.strip("/") for m in manifests or set()}
    existing = export_ignore_patterns(gitattributes)
    entries = classify(tracked, links=links, voter_inputs=voters, manifests=mans)
    for entry in entries:
        entry["already_excluded"] = ignored(entry["path"], existing)
        for kid in entry.get("inside") or []:
            kid["already_excluded"] = ignored(kid["path"], existing)

    candidates = [c for c in _candidates(entries, links) if not ignored(c["path"], existing)]
    # the review writes the file, so it is VCS metadata to exclude even before it exists
    if (
        changed is None
        and not ignored(".gitattributes", existing)
        and not any(c["path"] == ".gitattributes" for c in candidates)
    ):
        candidates.insert(0, {"path": ".gitattributes", "bucket": VCS})
    touched: set[str] | None = None
    if changed is not None:
        touched = set()
        for path in changed:
            parts = path.split("/")
            touched.add(parts[0])
            if len(parts) > 1:
                touched.add(f"{parts[0]}/{parts[1]}")
        candidates = [c for c in candidates if c["path"] in touched]
    kept = {k.strip("/") for k in keep or []}
    chosen = [c for c in candidates if c["path"] not in kept]
    by_path = {c["path"]: c["bucket"] for c in chosen}
    rm_added: set[str] = set()
    for extra in exclude or []:
        path = extra.strip().strip("/")
        if path and path not in by_path:
            by_path[path] = bucket(path, voter_inputs=voters, manifests=mans)
            rm_added.add(path)

    excluded_now = [*existing, *(entry_form(p, tracked) for p in by_path)]
    refs_map = refs or {}
    proposed, refused = [], []
    for path, b in by_path.items():
        why_not = never_excludable(path, b, manifests=mans)
        form = entry_form(path, tracked)
        referrers = sorted(
            {r for r in refs_map.get(path, []) if r != ".gitattributes" and not ignored(r, excluded_now)}
        )
        item: dict[str, Any] = {"path": path, "entry": form, "bucket": b}
        if path in rm_added:
            item["rm_choice"] = True
        if why_not:
            refused.append(item | {"reason": why_not})
            continue
        if referrers:
            refused.append(item | {"reason": "referenced by shipped files", "referrers": referrers})
            continue
        item["comment"] = (reasons or {}).get(path) or b.removeprefix("exclude: ")
        proposed.append(item)

    ship_links = {k: v for k, v in links.items() if not ignored(k, excluded_now)}
    chains = [c for c in _chains(links) if c["link"] in ship_links]
    stripped = [
        {"link": link, "target": target}
        for link, target in sorted(ship_links.items())
        if ignored(_resolve(link, target), excluded_now)
    ]
    block = "\n".join(f"# {p['comment']}\n{p['entry']} export-ignore" for p in proposed)
    needs_rm = [
        e["path"]
        for e in entries
        if e["bucket"] in (CALL, UNCLASSIFIED)
        and not e["already_excluded"]
        and (touched is None or e["path"] in touched)
        and e["path"] not in by_path
        and e["path"] not in kept
    ]
    out: dict[str, Any] = {
        "mode": "drift" if changed is not None else "full",
        "entries": entries,
        "existing_export_ignore": existing,
        "needs_rm": needs_rm,
        "proposed": proposed,
        "refused": refused,
        "symlink_chains": chains,
        "stripped_symlink_targets": stripped,
        "gitattributes_block": block,
        "refs_command": "" if refs is not None else refs_command([p["path"] for p in proposed]),
        "before_after_commands": before_after(framework) if proposed else "",
    }
    if changed is not None and not proposed and not refused and not needs_rm:
        out["archive_review"] = "skipped"
        out["note"] = f"no new top-level paths since `{previous_tag or '<previous-tag>'}`"
    return out
