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
"""Collect the apache-magpie adoption state of a repo as JSON.

Read-only. Enumerates the on-disk adoption artefacts —
the two lock files, the framework-skill symlinks across every
agent target, the snapshot, the overrides directory, the
post-checkout hook, and the .gitignore coverage — and emits a
single JSON document the ``setup-status`` skill renders into a
dashboard.

The script never fetches over the network and never writes: the
upstream-tip drift check and any remediation belong to
``/magpie-setup verify`` / ``/magpie-setup upgrade``.

Usage::

    python3 collect_status.py [--repo <path>] [--pretty]

``--repo`` defaults to the git top-level of the current directory,
falling back to the current directory when git is unavailable.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

# The agent-target registry is owned by skills/setup/agents.md
# ("## The registry") — the single source of truth. At runtime the
# collector PARSES that table (see load_agent_targets), so adding a
# vendor row there automatically flows into this dashboard with no
# edit here. The list below is only a FALLBACK used when agents.md
# cannot be located or parsed (e.g. a partial snapshot). Keep it a
# faithful mirror so the fallback degrades gracefully. The first
# entry is the canonical home every other target relays into;
# `reads` names the agents that read each directory (per-user
# global paths like ~/.codex/skills/ are out of scope — adoption is
# project-scope only).
_FALLBACK_TARGETS = [
    (
        "universal",
        ".agents/skills",
        "canonical",
        "Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode, "
        "Cline, Zed, Warp, Amp, and the rest of the shared-path cluster",
    ),
    ("claude-code", ".claude/skills", "relay", "Claude Code"),
    ("github", ".github/skills", "relay", "GitHub's skill loader"),
    ("windsurf", ".windsurf/skills", "relay", "Windsurf"),
    ("goose", ".goose/skills", "relay", "Goose"),
]


def _strip_md(cell: str) -> str:
    """Drop backticks and bold markers from a table cell."""
    return cell.replace("`", "").replace("**", "").strip()


def load_agent_targets() -> tuple[list[tuple[str, str, str, str]], str]:
    """Parse the registry table from the sibling setup skill's
    agents.md, the single source of truth. Returns (targets,
    source) where source is "agents.md" on success or "fallback".

    Located relative to this script (`../../setup/agents.md`),
    which holds in both the framework-source and snapshot layouts
    since the skill dir structure is identical in each.
    """
    agents_md = (Path(__file__).resolve().parent / ".." / ".." / "setup" / "agents.md")
    try:
        text = agents_md.read_text(encoding="utf-8")
    except OSError:
        return _FALLBACK_TARGETS, "fallback"

    targets: list[tuple[str, str, str, str]] = []
    in_table = False
    for raw in text.splitlines():
        line = raw.strip()
        if not line.startswith("|"):
            in_table = False
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) < 4:
            continue
        header = _strip_md(cells[0]).lower()
        if header in ("target id", ""):
            in_table = header == "target id" or in_table
            continue
        if set(_strip_md(cells[0])) <= {"-", ":"}:  # the |---| divider
            continue
        if not in_table:
            continue
        target_id = _strip_md(cells[0])
        skills_dir = _strip_md(cells[1]).rstrip("/")
        kind = "canonical" if "canonical" in cells[2].lower() else "relay"
        reads = _strip_md(cells[3])
        if target_id and skills_dir:
            targets.append((target_id, skills_dir, kind, reads))

    if not targets:
        return _FALLBACK_TARGETS, "fallback"
    return targets, "agents.md"

# Opt-in families the lock can record. Membership is read from each
# skill's ``family:`` frontmatter key (see skills/setup/SKILL.md
# Golden rule 8), NOT the name prefix — families like ``repo-health``
# and ``contributor-growth`` span several prefixes. ``setup`` and
# ``utilities`` are always-on; anything with no readable family lands
# in "other".
OPT_IN_FAMILIES = [
    "security",
    "pr-management",
    "issue",
    "release-management",
    "repo-health",
    "pairing",
    "mentoring",
    "contributor-growth",
]
ALWAYS_ON_FAMILIES = ["setup", "utilities"]


def repo_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).resolve()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        return Path(out.stdout.strip()).resolve()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return Path.cwd().resolve()


def parse_lock(path: Path) -> dict | None:
    """Parse a ``key: value`` lock file, dropping comments/blanks."""
    if not path.is_file():
        return None
    data: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        data[key.strip()] = value.strip()
    return data


def read_family(skill_dir: Path) -> str:
    """Read the ``family:`` frontmatter key from a skill's SKILL.md.

    Returns the declared family, or ``"other"`` when the SKILL.md is
    absent / unreadable or declares no family. Membership is never
    inferred from the name prefix (Golden rule 8)."""
    skill_md = skill_dir / "SKILL.md"
    try:
        text = skill_md.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return "other"
    if not text.startswith("---"):
        return "other"
    end = text.find("\n---", 3)
    frontmatter = text[3:end] if end != -1 else text
    for raw in frontmatter.splitlines():
        line = raw.strip()
        if line.startswith("family:"):
            return line.partition(":")[2].strip() or "other"
    return "other"


def link_info(entry: Path, root: Path) -> dict:
    """Describe one ``magpie-*`` directory entry."""
    name = entry.name
    skill = name[len("magpie-") :]
    info: dict = {"name": name, "skill": skill}
    if not entry.is_symlink():
        info.update(is_symlink=False, resolves=False, raw_target=None)
        # A non-symlink magpie-* (e.g. the committed magpie-setup
        # copy in an adopter repo) still resolves if it holds a
        # SKILL.md.
        info["resolves"] = (entry / "SKILL.md").is_file()
        info["kind"] = "copy" if info["resolves"] else "broken"
        info["family"] = read_family(entry)
        return info
    raw = os.readlink(entry)
    info["raw_target"] = raw
    info["is_symlink"] = True
    resolved = (entry.parent / raw).resolve() if not os.path.isabs(raw) else Path(raw)
    info["resolves"] = (resolved / "SKILL.md").is_file()
    # Family comes from the target skill's frontmatter (Golden rule 8),
    # not the symlink name. A relay points at the canonical entry, which
    # itself points at the skill dir — resolve() collapses both hops.
    info["family"] = read_family(resolved)
    # Relay links point back at the canonical .agents/skills home;
    # canonical links point at the snapshot or the in-repo source.
    if ".agents/skills/magpie-" in raw:
        info["kind"] = "relay"
    elif ".apache-magpie/" in raw:
        info["kind"] = "canonical-snapshot"
    else:
        info["kind"] = "canonical-source"
    return info


def collect_targets(root: Path, registry: list[tuple]) -> list[dict]:
    targets = []
    for target_id, rel, expected_kind, reads in registry:
        d = root / rel
        rec: dict = {
            "id": target_id,
            "dir": rel,
            "expected_kind": expected_kind,
            "reads": reads,
            "present": d.is_dir(),
            "entries": [],
        }
        if d.is_dir():
            entries = sorted(
                p for p in d.iterdir() if p.name.startswith("magpie-")
            )
            rec["entries"] = [link_info(p, root) for p in entries]
        rec["magpie_count"] = len(rec["entries"])
        rec["live_count"] = sum(1 for e in rec["entries"] if e["resolves"])
        rec["dangling"] = [e["name"] for e in rec["entries"] if not e["resolves"]]
        targets.append(rec)
    return targets


def families_installed(canonical_entries: list[dict]) -> dict:
    """Group the canonical (universal) entries by family."""
    fam: dict[str, list[str]] = {}
    for e in canonical_entries:
        if not e["resolves"]:
            continue
        fam.setdefault(e["family"], []).append(e["skill"])
    for v in fam.values():
        v.sort()
    summary = {
        "opt_in": {f: sorted(fam.get(f, [])) for f in OPT_IN_FAMILIES},
        "always_on": {f: sorted(fam.get(f, [])) for f in ALWAYS_ON_FAMILIES},
        "other": sorted(fam.get("other", [])),
    }
    summary["opt_in_present"] = [f for f in OPT_IN_FAMILIES if fam.get(f)]
    summary["opt_in_absent"] = [f for f in OPT_IN_FAMILIES if not fam.get(f)]
    return summary


def compute_drift(committed: dict | None, local: dict | None) -> dict:
    if committed is None:
        return {"checked": False, "reason": "not adopted (no committed lock)"}
    if committed.get("method") == "local":
        return {"checked": False, "reason": "method:local — no remote snapshot to drift against"}
    if local is None:
        return {"checked": False, "reason": "local lock absent — snapshot not fetched on this machine"}
    pairs = [
        ("method", committed.get("method"), local.get("source_method")),
        ("url", committed.get("url"), local.get("source_url")),
        ("ref", committed.get("ref"), local.get("source_ref")),
    ]
    mismatches = [
        {"field": f, "committed": c, "local": l}
        for f, c, l in pairs
        if c is not None and l is not None and c != l
    ]
    return {
        "checked": True,
        "in_sync": not mismatches,
        "mismatches": mismatches,
        "note": "upstream-tip check for git-branch needs network — run /magpie-setup verify",
    }


def gitignore_coverage(root: Path, targets: list[dict]) -> dict:
    gi = root / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.is_file() else ""
    lines = {ln.strip() for ln in text.splitlines()}
    cov = {
        "present": gi.is_file(),
        "snapshot_ignored": "/.apache-magpie/" in lines,
        "local_lock_ignored": "/.apache-magpie.local.lock" in lines,
        "settings_local_ignored": "/.claude/settings.local.json" in lines,
        "targets": {},
    }
    for t in targets:
        if not t["present"]:
            continue
        glob = f"/{t['dir']}/magpie-*"
        keep_setup = f"!/{t['dir']}/magpie-setup"
        keep_all = f"!/{t['dir']}/magpie-*"
        cov["targets"][t["id"]] = {
            # normal-adopter pattern: ignore the relayed/snapshot
            # symlinks, un-ignore only the committed bootstrap.
            "glob_ignored": glob in lines,
            "setup_unignored": keep_setup in lines,
            # self-adoption pattern: every magpie-* symlink is
            # committed, so the whole glob is un-ignored.
            "all_unignored": keep_all in lines,
        }
    return cov


def hook_status(root: Path) -> dict:
    hook = root / ".git" / "hooks" / "post-checkout"
    if not hook.is_file():
        return {"present": False}
    content = hook.read_text(encoding="utf-8", errors="replace")
    return {
        "present": True,
        "executable": os.access(hook, os.X_OK),
        "has_verify_recipe": "magpie-setup verify" in content,
    }


def verdict(d: dict) -> str:
    """A one-line health verdict, computed deterministically."""
    if not d["adopted"]:
        return "❌ not adopted"
    bad = warn = False
    for t in d["agent_targets"]:
        if t["present"] and t["dangling"]:
            bad = True
        if t["present"] and t["magpie_count"] == 0:
            warn = True
    dr = d["drift"]
    if dr.get("checked") and not dr.get("in_sync"):
        fields = {m["field"] for m in dr.get("mismatches", [])}
        if fields & {"method", "url"}:
            bad = True
        elif fields:
            warn = True
    if bad:
        return "❌ action needed"
    if warn:
        return "⚠️ needs attention"
    return "✅ healthy"


def render_markdown(d: dict) -> str:
    """Render the deterministic dashboard as GitHub-flavoured
    Markdown: a pipe table for the agent-target matrix (narrow
    columns only) plus a `serves` bullet legend for the wide
    agents-served text. Keeping that one wide field out of the table
    is what stops the table from wrapping and breaking."""
    repo = os.path.basename(d["repo"].rstrip("/")) or d["repo"]
    cl = d["committed_lock"] or {}
    pin = cl.get("ref") or cl.get("source") or cl.get("url") or "—"
    mode = d["mode"] or "—"
    if d["self_adopted"]:
        mode += " (self-adopted)"

    out: list[str] = []
    out.append(f"## apache-magpie adoption — {repo}")
    out.append("")
    out.append(f"**mode:** {mode} · **pinned:** {pin} · **verdict:** {verdict(d)}")
    out.append("")

    # Agent targets — a Markdown pipe table (narrow columns); the
    # wide agents-served text goes in the bullet legend below.
    out.append("### Agent targets")
    out.append("")
    out.append("| Target | Dir | Kind | Skills | Status |")
    out.append("|---|---|---|---|---|")
    for t in d["agent_targets"]:
        if not t["present"]:
            status, skills = "⚪ absent", "—"
        elif t["magpie_count"] == 0:
            status, skills = "⚠️ unwired", "0"
        elif t["dangling"]:
            status, skills = f"❌ {len(t['dangling'])} broken", str(t["magpie_count"])
        else:
            status, skills = "✅ wired", str(t["magpie_count"])
        kind = (sorted({e["kind"] for e in t["entries"]}) or [t["expected_kind"]])[0]
        out.append(f"| {t['id']} | `{t['dir']}` | {kind} | {skills} | {status} |")
    out.append("")
    out.append("**serves** (which agents read each target dir):")
    out.append("")
    for t in d["agent_targets"]:
        out.append(f"- `{t['id']}` — {t['reads']}")
    if d["registry_source"] != "agents.md":
        out.append("- ⚠️ registry from built-in fallback (agents.md unreadable) — may be stale")
    out.append("")

    # Skill families — a Markdown table.
    fam = d["families"]
    out.append("### Skill families")
    out.append("")
    out.append("| Family | Type | Installed |")
    out.append("|---|---|---|")
    for f in OPT_IN_FAMILIES:
        n = len(fam["opt_in"][f])
        out.append(f"| {f} | opt-in | {'✅ ' + str(n) if n else '— none'} |")
    out.append(f"| setup | always-on | {len(fam['always_on']['setup'])} |")
    out.append(f"| utilities | always-on | {len(fam['always_on']['utilities'])} |")
    out.append(f"| other | — | {len(fam['other'])} |")
    out.append("")

    # Drift & integrity.
    dr = d["drift"]
    if dr.get("in_sync"):
        drift_line = "✅ in sync"
    elif not dr.get("checked"):
        drift_line = f"n/a ({dr.get('reason', '')})"
    else:
        drift_line = "⚠️ drift → `/magpie-setup upgrade`"
    if d["self_adopted"]:
        snap = "in-repo source (local)"
    elif d["snapshot"]["present"]:
        snap = "present"
    else:
        snap = "❌ missing"
    out.append("### Drift & integrity")
    out.append("")
    out.append(f"- **drift:** {drift_line} · **snapshot:** {snap}")
    out.append(
        f"- **overrides:** {'present' if d['overrides']['present'] else '—'} · "
        f"**hook:** {'installed' if d['post_checkout_hook']['present'] else '—'}"
    )
    out.append("- → deep check (integrity, permissions, worktrees): `/magpie-setup verify`")
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default=None, help="repo root (default: git top-level)")
    parser.add_argument(
        "--format",
        choices=["json", "md"],
        default="md",
        help="md (default, the deterministic dashboard) or json (machine-readable)",
    )
    parser.add_argument("--pretty", action="store_true", help="indent the JSON output")
    args = parser.parse_args(argv)

    root = repo_root(args.repo)
    committed = parse_lock(root / ".apache-magpie.lock")
    local = parse_lock(root / ".apache-magpie.local.lock")

    registry, registry_source = load_agent_targets()
    targets = collect_targets(root, registry)
    canonical = next(
        (t for t in targets if t["expected_kind"] == "canonical"),
        targets[0] if targets else {"entries": []},
    )

    snapshot = root / ".apache-magpie"
    method = committed.get("method") if committed else None

    result = {
        "repo": str(root),
        "adopted": committed is not None,
        "mode": method,
        "self_adopted": method == "local",
        "committed_lock": committed,
        "local_lock": local,
        "snapshot": {
            "present": snapshot.exists(),
            "is_symlink": snapshot.is_symlink(),
        },
        "drift": compute_drift(committed, local),
        "registry_source": registry_source,
        "agent_targets": targets,
        "active_target_ids": [t["id"] for t in targets if t["present"]],
        "families": families_installed(canonical["entries"]),
        "overrides": {
            "present": (root / ".apache-magpie-overrides").is_dir(),
            "has_readme": (root / ".apache-magpie-overrides" / "README.md").is_file(),
        },
        "post_checkout_hook": hook_status(root),
        "gitignore": gitignore_coverage(root, targets),
    }

    if args.format == "md":
        sys.stdout.write(render_markdown(result))
    else:
        json.dump(result, sys.stdout, indent=2 if args.pretty else None, sort_keys=False)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
