#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Validate the per-family marketplace plugins against the skills' `family:`
frontmatter — the source of truth.

For every family that skills declare in their `family:` frontmatter there must
be a `plugins/magpie-<family>/` plugin whose `skills/` directory contains
exactly that family's skills as single-hop symlinks into the shared
`skills/<skill>` tree, and `.claude-plugin/marketplace.json` must list it (plus
the all-in-one `magpie`). Drift — a new skill, a changed family, a stale
symlink — fails the check.

Run with `--fix` to regenerate the family plugins + symlinks + marketplace
entries from the frontmatter.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

SKILLS = Path("skills")
PLUGINS = Path("plugins")
MARKETPLACE = Path(".claude-plugin/marketplace.json")
SYMLINK_TARGET = "../../../skills/{skill}"  # relative to plugins/magpie-<f>/skills/

# Per-family descriptions used when (re)generating manifests. Keep in sync with
# the family README; `check` does not enforce these (only structure/symlinks).
DESC = {
    "security": "security-issue handling lifecycle — import through CVE publication, triage, sync, dedup, invalidate. Maintainer-only.",
    "release-management": "ASF release lifecycle: plan, RC cut/sign, vote, tally, promote, announce, archive, audit.",
    "setup": "framework install/maintenance: install (adopt), upgrade, verify, override, status, secure-agent setup, shared-config sync.",
    "pr-management": "PR-queue management: triage, stats, deep code review, quick-merge, stale-sweep, reviewer routing, pre-first-PR checks.",
    "issue": "issue lifecycle: triage, reproduction, fix drafting, reassess, stale-sweep, dedup, backlog stats.",
    "repo-health": "read-only repo-health audits: runner labels, workflow security, dependency/license/NOTICE, flaky tests, audit-finding fixes.",
    "contributor-growth": "path-to-committer: activity sweeps, nominations, sentiment, readiness, committer/post-vote onboarding.",
    "utilities": "framework meta-skills: write-skill, optimize-skill, skill-reconciler, list-skills.",
    "mentoring": "newcomer mentoring: welcome, newcomer-issue explanations, good-first-issue authoring + sweep.",
    "pairing": "pair a change with a structured self-review or a multi-agent adversarial review.",
}


def families_from_frontmatter() -> dict[str, set[str]]:
    fam: dict[str, set[str]] = {}
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        m = re.search(r"^family:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)
        if m:
            fam.setdefault(m.group(1), set()).add(path.parent.name)
    return fam


def check(fam: dict[str, set[str]]) -> list[str]:
    errors: list[str] = []

    try:
        market = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
        listed = {p["name"] for p in market.get("plugins", [])}
    except (OSError, ValueError) as exc:
        return [f"{MARKETPLACE}: cannot read/parse ({exc})"]

    if "magpie" not in listed:
        errors.append(f"{MARKETPLACE}: missing the all-in-one 'magpie' plugin entry")

    for family, skills in sorted(fam.items()):
        name = f"magpie-{family}"
        pdir = PLUGINS / name
        if not (pdir / ".claude-plugin" / "plugin.json").is_file():
            errors.append(f"{name}: missing {pdir}/.claude-plugin/plugin.json")
            continue
        if name not in listed:
            errors.append(f"{MARKETPLACE}: missing entry for '{name}'")

        sdir = pdir / "skills"
        have: dict[str, Path] = {}
        for entry in sorted(sdir.iterdir()) if sdir.is_dir() else []:
            if entry.is_symlink():
                have[entry.name] = entry.readlink()
            else:
                errors.append(f"{name}: {entry} is not a symlink")

        for skill in sorted(skills - set(have)):
            errors.append(f"{name}: missing symlink for '{skill}' (family={family})")
        for skill in sorted(set(have) - skills):
            errors.append(f"{name}: stale symlink '{skill}' — its skill is not family={family}")
        for skill in sorted(skills & set(have)):
            want = Path(SYMLINK_TARGET.format(skill=skill))
            if have[skill] != want:
                errors.append(f"{name}: {sdir / skill} -> {have[skill]} (expected {want})")

    for pdir in sorted(PLUGINS.glob("magpie-*")):
        family = pdir.name[len("magpie-"):]
        if family not in fam:
            errors.append(f"orphan plugin '{pdir.name}': no skill declares family '{family}'")

    return errors


def fix(fam: dict[str, set[str]]) -> None:
    for pdir in PLUGINS.glob("magpie-*"):
        shutil.rmtree(pdir)
    for family, skills in sorted(fam.items()):
        name = f"magpie-{family}"
        pdir = PLUGINS / name
        sdir = pdir / "skills"
        (pdir / ".claude-plugin").mkdir(parents=True)
        sdir.mkdir(parents=True)
        for skill in sorted(skills):
            (sdir / skill).symlink_to(SYMLINK_TARGET.format(skill=skill))
        manifest = {
            "name": name,
            "description": f"Apache Magpie — {DESC.get(family, family + ' family skills')}",
            "skills": "./skills",
        }
        (pdir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    market = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    keep = [p for p in market["plugins"] if p["name"] == "magpie"]
    for family, skills in sorted(fam.items()):
        keep.append({
            "name": f"magpie-{family}",
            "source": f"./plugins/magpie-{family}",
            "version": "0.2.0",
            "description": f"Apache Magpie {family} family ({len(skills)} skills).",
        })
    market["plugins"] = keep
    MARKETPLACE.write_text(json.dumps(market, indent=2) + "\n", encoding="utf-8")
    print("Regenerated per-family plugins + marketplace entries from frontmatter.")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fix", action="store_true", help="regenerate plugins from frontmatter")
    ap.add_argument("files", nargs="*", help="(ignored; present for pre-commit)")
    args = ap.parse_args()

    fam = families_from_frontmatter()
    if args.fix:
        fix(fam)
        return 0

    errors = check(fam)
    if errors:
        print("Family plugins are out of sync with skills' `family:` frontmatter:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("\nRun `python3 tools/dev/check-family-plugins.py --fix` to regenerate.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
