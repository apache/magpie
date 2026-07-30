#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Validate the marketplace plugins against the skills' `family:` frontmatter —
the source of truth.

Checks that every plugin is properly defined:

- every ecosystem manifest that declares the framework version
  (`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`,
  `gemini-extension.json`, `apm.yml`) mirrors `pyproject.toml`'s
  `project.version` verbatim — including a `.devN` suffix;
- the all-in-one `magpie` manifest (`.claude-plugin/plugin.json`) names itself
  correctly, declares `skills: ./skills`, and wires the `hooks/check-upgrade.sh`
  SessionStart hook (which must exist);
- every `.claude-plugin/marketplace.json` entry resolves to a matching,
  uniquely-named `plugin.json` and carries the root manifest's version;
- for every family declared in a skill's `family:` frontmatter there is a
  `plugins/magpie-<family>/` plugin whose manifest is well-formed, inherits the
  root manifest's shared metadata (version, author, homepage, repository,
  license), and whose `skills/` directory contains exactly that family's skills
  as single-hop symlinks into the shared `skills/<skill>` tree.

Drift — a new skill, a changed family, a stale symlink, a malformed or
mis-named manifest, a dangling marketplace entry, a family manifest left behind
at the previous release's version — fails the check.

Run with `--fix` to propagate the version from `pyproject.toml` and regenerate
the family plugins + symlinks + marketplace entries from the frontmatter. A
release bump therefore has one edit point: `pyproject.toml`, then `--fix`.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
import tomllib
from pathlib import Path

SKILLS = Path("skills")
PLUGINS = Path("plugins")
MARKETPLACE = Path(".claude-plugin/marketplace.json")
ROOT_MANIFEST = Path(".claude-plugin/plugin.json")  # the all-in-one `magpie` plugin
HOOK_SCRIPT = Path("hooks/check-upgrade.sh")  # referenced by the all-in-one plugin hook
SYMLINK_TARGET = "../../../skills/{skill}"  # relative to plugins/magpie-<f>/skills/

# `pyproject.toml` is the single authority for the framework version — it is what
# the post-release `chore: bump version` commit edits. Every ecosystem manifest
# mirrors that string verbatim (including a `.devN` suffix), so `release-prepare`
# can bump them all with one literal search/replace. Dev versions are never
# published to a marketplace, so a PEP 440 suffix never reaches a consumer.
PYPROJECT = Path("pyproject.toml")
ECOSYSTEM_MANIFESTS = (
    ROOT_MANIFEST,
    Path(".codex-plugin/plugin.json"),
    Path("gemini-extension.json"),
    Path("apm.yml"),
)
APM_VERSION_RE = re.compile(r"^(version:[ \t]*)(\S+)[ \t]*$", re.M)
# Substituted rather than re-serialised: these manifests are hand-authored, and a
# json.dumps() round-trip would reformat them (escaping em-dashes, expanding
# inline objects) far beyond the one string being bumped.
JSON_VERSION_RE = re.compile(r'("version"[ \t]*:[ \t]*")[^"]*(")')

# Metadata the per-family plugins and the marketplace entries inherit verbatim
# from the all-in-one manifest, so a release bump has exactly one edit point.
# `version` + `author` are what `claude plugin validate --strict` warns about
# when absent; the rest carry attribution into a marketplace listing.
INHERITED = ("version", "author", "homepage", "repository", "license")

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


def load_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8")), None
    except (OSError, ValueError) as exc:
        return None, f"{path}: cannot read/parse ({exc})"


def validate_manifest(
    path: Path, expected_name: str, inherited: dict | None = None
) -> list[str]:
    """A plugin.json must exist, be valid JSON, name itself correctly, and
    declare its skills + a description. Per-family manifests additionally carry
    the root manifest's shared metadata (`inherited`) verbatim."""
    if not path.is_file():
        return [f"{path}: missing plugin manifest"]
    data, err = load_json(path)
    if err:
        return [err]
    errors: list[str] = []
    if data.get("name") != expected_name:
        errors.append(f"{path}: name is {data.get('name')!r}, expected {expected_name!r}")
    if data.get("skills") != "./skills":
        errors.append(f"{path}: 'skills' is {data.get('skills')!r}, expected './skills'")
    if not str(data.get("description", "")).strip():
        errors.append(f"{path}: missing/empty 'description'")
    for key, want in (inherited or {}).items():
        if data.get(key) != want:
            errors.append(
                f"{path}: {key!r} is {data.get(key)!r}, expected {want!r} "
                f"(inherited from {ROOT_MANIFEST})"
            )
    return errors


def pyproject_version() -> tuple[str | None, list[str]]:
    """The framework version — the single authority every manifest mirrors."""
    try:
        version = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]
    except (OSError, ValueError, KeyError) as exc:
        return None, [f"{PYPROJECT}: cannot read project.version ({exc})"]
    return str(version), []


def manifest_version(path: Path) -> tuple[str | None, str | None]:
    """Read the version out of a manifest in whichever format it uses."""
    if path.suffix in (".yml", ".yaml"):
        try:
            m = APM_VERSION_RE.search(path.read_text(encoding="utf-8"))
        except OSError as exc:
            return None, f"{path}: cannot read ({exc})"
        return (m.group(2) if m else None), None
    data, err = load_json(path)
    if err:
        return None, err
    return data.get("version"), None


def write_manifest_version(path: Path, version: str) -> list[str]:
    """Rewrite a manifest's version in place, touching nothing else."""
    pattern = APM_VERSION_RE if path.suffix in (".yml", ".yaml") else JSON_VERSION_RE
    text = path.read_text(encoding="utf-8")
    new, n = pattern.subn(
        (rf"\g<1>{version}" if pattern is APM_VERSION_RE else rf"\g<1>{version}\g<2>"),
        text,
        count=1,
    )
    if n != 1:
        return [f"{path}: no 'version' declaration to rewrite"]
    path.write_text(new, encoding="utf-8")
    # The substitution is textual — confirm it produced the intended value.
    have, err = manifest_version(path)
    if err:
        return [err]
    if have != version:
        return [f"{path}: rewrite produced {have!r}, expected {version!r}"]
    return []


def check_ecosystem_versions(version: str) -> list[str]:
    """Every ecosystem manifest mirrors `pyproject.toml`'s version verbatim."""
    errors: list[str] = []
    for path in ECOSYSTEM_MANIFESTS:
        if not path.is_file():
            errors.append(f"{path}: missing (declares the framework version)")
            continue
        have, err = manifest_version(path)
        if err:
            errors.append(err)
        elif have != version:
            errors.append(
                f"{path}: version is {have!r}, expected {version!r} (from {PYPROJECT})"
            )
    return errors


def root_metadata() -> tuple[dict, list[str]]:
    """The subset of the all-in-one manifest that the family plugins inherit."""
    data, err = load_json(ROOT_MANIFEST)
    if err:
        return {}, [err]
    missing = [k for k in INHERITED if not data.get(k)]
    if missing:
        return {}, [f"{ROOT_MANIFEST}: missing {', '.join(repr(k) for k in missing)}"]
    return {k: data[k] for k in INHERITED}, []


def families_from_frontmatter() -> dict[str, set[str]]:
    fam: dict[str, set[str]] = {}
    for path in sorted(SKILLS.glob("*/SKILL.md")):
        m = re.search(r"^family:\s*(\S+)", path.read_text(encoding="utf-8"), re.M)
        if m:
            fam.setdefault(m.group(1), set()).add(path.parent.name)
    return fam


def check(fam: dict[str, set[str]]) -> list[str]:
    errors: list[str] = []

    market, err = load_json(MARKETPLACE)
    if err:
        return [err]
    entries = market.get("plugins", [])
    listed = {p.get("name") for p in entries}

    shared, meta_errs = root_metadata()
    errors += meta_errs

    # 0) Every ecosystem manifest mirrors pyproject.toml's version.
    version, verr = pyproject_version()
    errors += verr
    if version is not None:
        errors += check_ecosystem_versions(version)

    # 1) The all-in-one `magpie` plugin: well-formed manifest, listed, and its
    #    SessionStart hook script is present + referenced.
    errors += validate_manifest(ROOT_MANIFEST, "magpie")
    if "magpie" not in listed:
        errors.append(f"{MARKETPLACE}: missing the all-in-one 'magpie' plugin entry")
    if not HOOK_SCRIPT.is_file():
        errors.append(f"{HOOK_SCRIPT}: missing (referenced by the all-in-one plugin's SessionStart hook)")
    root_data, root_err = load_json(ROOT_MANIFEST)
    if root_data is not None and "check-upgrade.sh" not in json.dumps(root_data.get("hooks", {})):
        errors.append(f"{ROOT_MANIFEST}: SessionStart hook does not reference hooks/check-upgrade.sh")

    # 2) Every marketplace entry resolves to a matching, uniquely-named manifest.
    seen: set[str] = set()
    for ent in entries:
        name = ent.get("name")
        source = ent.get("source")
        if not name or not source:
            errors.append(f"{MARKETPLACE}: entry missing 'name'/'source': {ent}")
            continue
        if name in seen:
            errors.append(f"{MARKETPLACE}: duplicate plugin entry '{name}'")
        seen.add(name)
        manifest = ROOT_MANIFEST if source == "." else Path(source) / ".claude-plugin" / "plugin.json"
        if not manifest.is_file():
            errors.append(f"{MARKETPLACE}: '{name}' source '{source}' has no {manifest}")
            continue
        data, jerr = load_json(manifest)
        if jerr is None and data.get("name") != name:
            errors.append(f"{MARKETPLACE}: '{name}' resolves to plugin.json named {data.get('name')!r}")
        if shared and ent.get("version") != shared["version"]:
            errors.append(
                f"{MARKETPLACE}: '{name}' version is {ent.get('version')!r}, "
                f"expected {shared['version']!r} (from {ROOT_MANIFEST})"
            )

    # 3) Per-family plugins: manifest well-formed + symlinks match the frontmatter.
    for family, skills in sorted(fam.items()):
        name = f"magpie-{family}"
        pdir = PLUGINS / name
        manifest_errs = validate_manifest(
            pdir / ".claude-plugin" / "plugin.json", name, inherited=shared or None
        )
        errors += manifest_errs
        if manifest_errs:
            continue
        if name not in listed:
            errors.append(f"{MARKETPLACE}: missing entry for '{name}'")

        sdir = pdir / "skills"
        have: dict[str, Path] = {}
        for link in sorted(sdir.iterdir()) if sdir.is_dir() else []:
            if link.is_symlink():
                have[link.name] = link.readlink()
            else:
                errors.append(f"{name}: {link} is not a symlink")

        for skill in sorted(skills - set(have)):
            errors.append(f"{name}: missing symlink for '{skill}' (family={family})")
        for skill in sorted(set(have) - skills):
            errors.append(f"{name}: stale symlink '{skill}' — its skill is not family={family}")
        for skill in sorted(skills & set(have)):
            want = Path(SYMLINK_TARGET.format(skill=skill))
            if have[skill] != want:
                errors.append(f"{name}: {sdir / skill} -> {have[skill]} (expected {want})")

    # 4) No orphan plugin dirs (a magpie-<x> with no skills declaring family x).
    for pdir in sorted(PLUGINS.glob("magpie-*")):
        family = pdir.name[len("magpie-"):]
        if family not in fam:
            errors.append(f"orphan plugin '{pdir.name}': no skill declares family '{family}'")

    return errors


def fix(fam: dict[str, set[str]]) -> int:
    # Propagate the authoritative version outward before reading the root
    # manifest's metadata, so a bump in pyproject.toml alone is enough.
    version, verr = pyproject_version()
    if verr or version is None:
        for e in verr or [f"{PYPROJECT}: no project.version"]:
            print(f"  - {e}", file=sys.stderr)
        return 1
    for path in ECOSYSTEM_MANIFESTS:
        if not path.is_file():
            print(f"  - {path}: missing (declares the framework version)", file=sys.stderr)
            return 1
        have, err = manifest_version(path)
        if err:
            print(f"  - {err}", file=sys.stderr)
            return 1
        if have != version:
            if write_errs := write_manifest_version(path, version):
                for e in write_errs:
                    print(f"  - {e}", file=sys.stderr)
                return 1
            print(f"{path}: version {have} -> {version}")

    shared, meta_errs = root_metadata()
    if meta_errs:
        for e in meta_errs:
            print(f"  - {e}", file=sys.stderr)
        print(
            f"\nCannot regenerate: the family plugins inherit "
            f"{', '.join(INHERITED)} from {ROOT_MANIFEST}.",
            file=sys.stderr,
        )
        return 1

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
            **shared,
            "skills": "./skills",
        }
        (pdir / ".claude-plugin" / "plugin.json").write_text(
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )

    market = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    keep = [p | {"version": shared["version"]} for p in market["plugins"] if p["name"] == "magpie"]
    for family, skills in sorted(fam.items()):
        keep.append({
            "name": f"magpie-{family}",
            "source": f"./plugins/magpie-{family}",
            "version": shared["version"],
            "description": f"Apache Magpie {family} family ({len(skills)} skills).",
        })
    market["plugins"] = keep
    MARKETPLACE.write_text(json.dumps(market, indent=2) + "\n", encoding="utf-8")
    print("Regenerated per-family plugins + marketplace entries from frontmatter.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fix", action="store_true", help="regenerate plugins from frontmatter")
    ap.add_argument("files", nargs="*", help="(ignored; present for pre-commit)")
    args = ap.parse_args()

    fam = families_from_frontmatter()
    if args.fix:
        return fix(fam)

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
