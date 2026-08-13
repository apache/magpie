#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Validate the marketplace plugins against the skills' `family:` frontmatter —
the source of truth.

Checks that every plugin is properly defined:

- every ecosystem manifest that declares the framework version
  (`.claude-plugin/plugin.json`, the Agent Plugins 1.0 `plugin.json`,
  `.codex-plugin/plugin.json`, `gemini-extension.json`, `apm.yml`) mirrors
  `pyproject.toml`'s `project.version` verbatim — including a `.devN` suffix;
- the all-in-one `magpie` manifest (`.claude-plugin/plugin.json`) names itself
  correctly, declares `skills: ./skills`, and wires the `hooks/check-upgrade.sh`
  SessionStart hook (which must exist);
- the root `plugin.json` conforms to Agent Plugins 1.0 — the pinned `$schema`,
  the name pattern, the closed ten-field set (so a Claude-only component path
  never leaks in), and the same shared metadata as the Claude manifest;
- every `.claude-plugin/marketplace.json` entry resolves to a matching,
  uniquely-named `plugin.json` and carries the root manifest's version;
- the Codex and Copilot catalogs (`.agents/plugins/marketplace.json`,
  `marketplace.json`) list the all-in-one plugin and *only* that — the family
  plugins are Claude Code-only, so advertising them there would offer those
  clients something they cannot install;
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

# The vendor-neutral Agent Plugins 1.0 manifest for the same all-in-one plugin.
# It lives at the repo root (the spec permits no alternative location) and is
# read by VS Code / Copilot, which auto-detect the format from the root manifest
# and treat the `$schema` value as the AP1 marker. Its schema is *closed*: only
# the ten fields below are permitted, so component paths (`skills`, `hooks`)
# must NOT appear — AP1 fixes skills at `skills/` and defines no hook component.
AP1_MANIFEST = Path("plugin.json")
AP1_SCHEMA = "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json"
AP1_FIELDS = frozenset(
    {
        "$schema",
        "name",
        "version",
        "description",
        "author",
        "homepage",
        "repository",
        "license",
        "keywords",
        "extensions",
    }
)
AP1_AUTHOR_FIELDS = frozenset({"name", "email", "url"})

# The non-Claude catalogs. These list the all-in-one plugin *only*: the family
# plugins reach their skills through symlinks that deliberately resolve outside
# the family's own root, which Agent Plugins 1.0 forbids (a symlink's final
# target must stay within the plugin root). Materialising them into real
# directories would mean vendored copies of every skill — PRINCIPLES §13. So
# per-family is a Claude Code feature, and this check keeps the other catalogs
# from drifting into advertising something their clients cannot install.
CLIENT_CATALOGS = (
    Path(".agents/plugins/marketplace.json"),  # Codex CLI repo marketplace
    Path("marketplace.json"),  # GitHub Copilot / VS Code
)
# `name`: 1–64 chars, lowercase alphanumeric plus `-`/`.`, no `--`/`..`,
# alphanumeric at both ends.
AP1_NAME_RE = re.compile(r"^(?!.*(?:--|\.\.))[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?$")

# `pyproject.toml` is the single authority for the framework version — it is what
# the post-release `chore: bump version` commit edits. Every ecosystem manifest
# mirrors that string verbatim (including a `.devN` suffix), so `release-prepare`
# can bump them all with one literal search/replace. Dev versions are never
# published to a marketplace, so a PEP 440 suffix never reaches a consumer.
PYPROJECT = Path("pyproject.toml")
ECOSYSTEM_MANIFESTS = (
    ROOT_MANIFEST,
    AP1_MANIFEST,
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


def validate_ap1_manifest(inherited: dict | None = None) -> list[str]:
    """The root `plugin.json` conforms to Agent Plugins 1.0.

    Enforced here rather than by a JSON-Schema dependency: the schema is small,
    closed, and the failure we actually care about is someone copying a
    Claude-only field (`skills`, `hooks`, `mcpServers`) into it, which AP1
    clients reject as a fatal manifest error rather than ignore.
    """
    if not AP1_MANIFEST.is_file():
        return [f"{AP1_MANIFEST}: missing (Agent Plugins 1.0 manifest)"]
    data, err = load_json(AP1_MANIFEST)
    if err:
        return [err]
    errors: list[str] = []

    if data.get("$schema") != AP1_SCHEMA:
        errors.append(
            f"{AP1_MANIFEST}: '$schema' is {data.get('$schema')!r}, expected {AP1_SCHEMA!r} "
            f"(without it, VS Code/Copilot fall back to the legacy format)"
        )
    name = data.get("name")
    if name != "magpie":
        errors.append(f"{AP1_MANIFEST}: name is {name!r}, expected 'magpie'")
    elif not AP1_NAME_RE.match(name):
        errors.append(f"{AP1_MANIFEST}: name {name!r} violates the AP1 name pattern")

    extra = sorted(set(data) - AP1_FIELDS)
    if extra:
        errors.append(
            f"{AP1_MANIFEST}: {', '.join(repr(k) for k in extra)} not permitted — "
            f"the AP1 manifest schema is closed to {len(AP1_FIELDS)} fields "
            f"(client-specific data belongs in 'extensions' or the client's own manifest)"
        )

    author = data.get("author")
    if author is not None:
        if not isinstance(author, dict):
            errors.append(f"{AP1_MANIFEST}: 'author' must be an object")
        else:
            bad = sorted(set(author) - AP1_AUTHOR_FIELDS)
            if bad:
                errors.append(
                    f"{AP1_MANIFEST}: author has {', '.join(repr(k) for k in bad)}; "
                    f"AP1 permits only {', '.join(sorted(AP1_AUTHOR_FIELDS))}"
                )

    # AP1 fixes the skills location; there is no manifest field to point
    # elsewhere, so the real `skills/` tree is what any AP1 client will load.
    if not SKILLS.is_dir():
        errors.append(f"{SKILLS}: missing — AP1 clients discover skills only here")

    for key, want in (inherited or {}).items():
        if data.get(key) != want:
            errors.append(
                f"{AP1_MANIFEST}: {key!r} is {data.get(key)!r}, expected {want!r} "
                f"(inherited from {ROOT_MANIFEST})"
            )
    return errors


def check_client_catalogs() -> list[str]:
    """The Codex and Copilot catalogs list the all-in-one plugin and only that."""
    errors: list[str] = []
    for path in CLIENT_CATALOGS:
        if not path.is_file():
            errors.append(f"{path}: missing (client plugin catalog)")
            continue
        data, err = load_json(path)
        if err:
            errors.append(err)
            continue
        entries = data.get("plugins")
        if not isinstance(entries, list):
            errors.append(f"{path}: 'plugins' is missing or not a list")
            continue
        names = [e.get("name") for e in entries if isinstance(e, dict)]
        if "magpie" not in names:
            errors.append(f"{path}: missing the all-in-one 'magpie' plugin entry")
        if families := sorted(n for n in names if n and n.startswith("magpie-")):
            errors.append(
                f"{path}: lists per-family plugin(s) {', '.join(families)} — the family "
                f"plugins are Claude Code-only (their skill symlinks resolve outside the "
                f"family plugin root, which Agent Plugins 1.0 forbids)"
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
    errors += validate_ap1_manifest(shared)
    errors += check_client_catalogs()
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


def unowned_entries(pdir: Path) -> list[str]:
    """Anything in a family plugin dir that `--fix` did not generate.

    A blanket `rmtree` is safe only for as long as these directories hold
    nothing but a generated manifest and symlinks. The moment a family grows a
    `commands/`, an `agents/`, or a README, a blanket delete would silently
    discard it. So enumerate what regeneration owns and report anything else,
    so the operator gets an error naming the file instead of a quiet loss.
    """
    if not pdir.is_dir():
        return []
    mdir, sdir = pdir / ".claude-plugin", pdir / "skills"
    unexpected = sorted(p for p in pdir.iterdir() if p not in {mdir, sdir})
    if mdir.is_dir():
        unexpected += sorted(p for p in mdir.iterdir() if p.name != "plugin.json")
    if sdir.is_dir():
        unexpected += sorted(p for p in sdir.iterdir() if not p.is_symlink())
    if not unexpected:
        return []
    return [
        f"{pdir}: refusing to regenerate — not generated by --fix: "
        f"{', '.join(str(p) for p in unexpected)} "
        f"(move it out, or teach --fix to generate it)"
    ]


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

    # Check every family dir *before* deleting any of them, so a stray file in
    # the last one does not leave the first nine already destroyed.
    stale = sorted(PLUGINS.glob("magpie-*"))
    if rm_errs := [e for pdir in stale for e in unowned_entries(pdir)]:
        for e in rm_errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    for pdir in stale:
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

    market, market_err = load_json(MARKETPLACE)
    if market_err:
        print(f"  - {market_err}", file=sys.stderr)
        return 1
    # The all-in-one entry is carried over, not regenerated, so it is the one
    # thing here that `--fix` cannot reconstruct. Bail out rather than write a
    # marketplace containing only the families: `check` would catch that on the
    # next run, but the destructive rewrite would already have happened.
    entries = market.get("plugins")
    if not isinstance(entries, list):
        print(f"  - {MARKETPLACE}: 'plugins' is missing or not a list", file=sys.stderr)
        return 1
    keep = [p | {"version": shared["version"]} for p in entries if p.get("name") == "magpie"]
    if not keep:
        print(
            f"  - {MARKETPLACE}: no all-in-one 'magpie' entry to carry over "
            f"(--fix regenerates only the family entries; restore it before rerunning)",
            file=sys.stderr,
        )
        return 1
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
