#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
"""Generate each family's *Before the first run* config table from frontmatter.

A Magpie skill reads project-specific values from `<project-config>/` — the
adopter's copy of `projects/_template/`. Which files, and whether a skill can
work without one, was recorded in exactly two places and neither was reliable:

- **Prose, inconsistently.** Only 8 of the 74 skills carry a configuration
  section at all, under three different headings, and optionality is marked
  by whatever phrasing the author reached for ("(Optional)", "if absent",
  "falls back", or nothing).
- **A hand-maintained table** in nine of the ten family READMEs, which had
  drifted exactly as far as an unguarded table does: `security` listed none of
  the thirteen files its skills read, `repo-health` none of its three,
  `release-management` one of five, `pr-management` six of eleven.

So the required set is now **declared** in frontmatter, once, per skill:

    requires_config:
      - project.md
      - pr-management-config.md

Required means: absent, the skill would act on a guess. That is judgement and
cannot be derived — but it is the *only* thing that needs declaring. The
optional set is everything a skill references minus what it declares, which
this script derives, so the larger half never needs maintaining. A skill with
no `requires_config:` requires nothing: everything it reads is a refinement of
a default it can reach on its own.

Checks:

- every declared file is actually referenced somewhere in that skill, so the
  declaration cannot quietly become fiction;
- every file any skill reads has a template in `projects/_template/`, so a
  skill cannot ask an adopter for config the framework is unable to scaffold;
- each family README's generated block matches what the frontmatter says.

`--fix` rewrites the blocks. The descriptions come from the adopter scaffold's
own index (`projects/_template/README.md`), falling back to each template's
title, so no third copy of "what this file is for" is introduced here.

Run from the repo root:

    python3 tools/dev/check-skill-config.py
    python3 tools/dev/check-skill-config.py --fix
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

PLUGINS = Path("plugins")
TEMPLATE_DIR = Path("projects/_template")
TEMPLATE_INDEX = TEMPLATE_DIR / "README.md"

BEGIN = "<!-- BEGIN generated: skill-config (tools/dev/check-skill-config.py --fix) -->"
END = "<!-- END generated: skill-config -->"

# One family's docs directory is not named after the family.
DOCS_DIR_OVERRIDES = {"issue": "issue-management"}

_CONFIG_REF = re.compile(r"<project-config>/([a-z0-9-]+\.md)")
# `requires_config:` followed by an indented `- name.md` list. The frontmatter
# is parsed here rather than with a YAML library for the same reason the skill
# validator does it by hand: the format is deliberately simple and the checks
# stay stdlib-only, so they run anywhere without an install.
_REQUIRES = re.compile(r"^requires_config:[ \t]*\n((?:[ \t]+-[ \t]*\S+[ \t]*\n)+)", re.M)
_INDEX_ROW = re.compile(r"^\| \[`([a-z0-9.-]+\.md)`\]\([^)]*\) \| (.+?) \|[ \t]*$", re.M)
# The first H1. Most templates title themselves `TODO: `<Project Name>` — X`;
# a few just say X. Strip the scaffolding prefix when it is there.
_TEMPLATE_TITLE = re.compile(r"^# (?:TODO:\s*`<Project Name>`\s*[—-]\s*)?(.+?)[ \t]*$", re.M)


def frontmatter_block(text: str) -> str:
    """The frontmatter, or an empty string. Only the head of the file."""
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 3)
    return text[4:end] if end != -1 else ""


def declared(skill_md: Path) -> list[str]:
    """The skill's declared required config, in the order it will render."""
    m = _REQUIRES.search(frontmatter_block(skill_md.read_text(encoding="utf-8")))
    if not m:
        return []
    return sorted({line.strip().lstrip("-").strip() for line in m.group(1).splitlines() if line.strip()})


def referenced(skill_dir: Path) -> set[str]:
    """Every `<project-config>/…` file the skill mentions, across all its pages."""
    found: set[str] = set()
    for md in skill_dir.rglob("*.md"):
        found |= set(_CONFIG_REF.findall(md.read_text(encoding="utf-8")))
    return found


def descriptions() -> dict[str, str]:
    """What each config file carries, from the adopter scaffold's own index.

    The index is prose a human wrote and is the better description where it
    exists; a template's title is the deterministic fallback, so a newly added
    template is never nameless in the generated table.
    """
    out: dict[str, str] = {}
    for path in sorted(TEMPLATE_DIR.glob("*.md")):
        if path.name == "README.md":
            continue
        if m := _TEMPLATE_TITLE.search(path.read_text(encoding="utf-8")):
            out[path.name] = m.group(1).strip().rstrip(".")
    if TEMPLATE_INDEX.is_file():
        for name, purpose in _INDEX_ROW.findall(TEMPLATE_INDEX.read_text(encoding="utf-8")):
            purpose = re.sub(r"\*\*(.+?)\*\*", r"\1", purpose)
            # The index names which skills read a file; the generated table has
            # a column for that, derived. Drop the hand-written sentence rather
            # than print two answers to the same question, one of them stale.
            purpose = re.sub(r"\s*(?:Used|Read) by [^.]*\.\s*$", "", purpose)
            # The table already has a Required/Optional heading over it.
            purpose = re.sub(r"^Optional\.\s*", "", purpose)
            out[name] = purpose.strip()
    return out


def families() -> dict[str, dict[str, tuple[list[str], set[str]]]]:
    """family -> skill alias -> (declared required, referenced)."""
    out: dict[str, dict[str, tuple[list[str], set[str]]]] = {}
    for pdir in sorted(PLUGINS.glob("magpie-*")):
        skills = pdir / "skills"
        if not skills.is_dir():
            continue
        fam = pdir.name.removeprefix("magpie-")
        for sdir in sorted(skills.iterdir()):
            if (sdir / "SKILL.md").is_file():
                out.setdefault(fam, {})[sdir.name] = (declared(sdir / "SKILL.md"), referenced(sdir))
    return out


def docs_readme(family: str) -> Path:
    return Path("docs") / DOCS_DIR_OVERRIDES.get(family, family) / "README.md"


def render(family: str, skills: dict[str, tuple[list[str], set[str]]], desc: dict[str, str]) -> str:
    """The generated block for one family README."""
    required: dict[str, list[str]] = {}
    optional: dict[str, list[str]] = {}
    for alias, (need, refs) in sorted(skills.items()):
        for name in sorted(refs):
            bucket = required if name in need else optional
            bucket.setdefault(name, []).append(alias)
    # A file some skill requires is required for the family, whatever the
    # others do with it: the reader is being told what to create, not what
    # each skill does on a per-file basis.
    for name in required:
        optional.pop(name, None)

    lines = [BEGIN, ""]
    if not required and not optional:
        lines += [
            "These skills read no project configuration. Nothing to set up beyond the",
            "install itself.",
            "",
            END,
        ]
        return "\n".join(lines)

    if required:
        lines += [
            "Every skill here resolves project-specific values from the adopter's",
            f"[`<project-config>/`](../../{TEMPLATE_DIR}/) directory.",
            "[`/magpie-setup adopt`](../setup/team-adoption.md) scaffolds all of them from",
            "templates; you fill in the `TODO` fields for the skills you use.",
            "",
        ]
    else:
        # Saying "configure these" over a table of things you need not configure
        # is how a family that asks nothing of an adopter reads as one that does.
        lines += [
            "**Nothing here has to be configured.** These skills read the file below",
            "when the project has one and fall back to a documented default when it",
            "does not.",
            "",
        ]

    def table(rows: dict[str, list[str]], header: str) -> list[str]:
        block = [header, "", "| File | What it carries | Read by |", "|---|---|---|"]
        for name in sorted(rows):
            users = ", ".join(f"`{a}`" for a in rows[name])
            block.append(
                f"| [`{name}`](../../{TEMPLATE_DIR}/{name}) "
                f"| {desc.get(name, '—')} | {users} |"
            )
        return block + [""]

    if required:
        lines += table(
            required,
            "**Required.** Without these a skill would act on a guess, so it stops and\nsays which file is missing.",
        )
    if optional:
        lines += table(
            optional,
            "**Optional.** Each has a documented fallback; absent, the skill still runs.",
        )

    lines.append(END)
    return "\n".join(lines)


def splice(body: str, block: str) -> str:
    """Replace the generated block, or insert it ahead of *Try these first*."""
    if BEGIN in body and END in body:
        start = body.index(BEGIN)
        end = body.index(END) + len(END)
        return body[:start] + block + body[end:]
    anchor = "### Try these first\n"
    if anchor not in body:
        raise ValueError("no '### Try these first' heading to insert before")
    section = "### Before the first run\n\n" + block + "\n\n"
    return body.replace(anchor, section + anchor, 1)


def check(fix: bool) -> list[str]:
    errors: list[str] = []
    desc = descriptions()
    templates = {p.name for p in TEMPLATE_DIR.glob("*.md")} - {"README.md"}
    fams = families()

    for family, skills in sorted(fams.items()):
        for alias, (need, refs) in sorted(skills.items()):
            for name in need:
                if name not in refs:
                    errors.append(
                        f"plugins/magpie-{family}/skills/{alias}/SKILL.md: declares "
                        f"requires_config {name!r}, which the skill never reads — "
                        f"remove it, or reference it where the skill uses it"
                    )
            for name in sorted(refs - templates):
                errors.append(
                    f"plugins/magpie-{family}/skills/{alias}: reads "
                    f"<project-config>/{name}, which has no {TEMPLATE_DIR}/{name} — "
                    f"a skill cannot ask for config the framework cannot scaffold"
                )

        readme = docs_readme(family)
        if not readme.is_file():
            errors.append(f"{readme}: missing")
            continue
        body = readme.read_text(encoding="utf-8")
        want = render(family, skills, desc)
        try:
            updated = splice(body, want)
        except ValueError as exc:
            errors.append(f"{readme}: {exc}")
            continue
        if updated == body:
            continue
        if fix:
            readme.write_text(updated, encoding="utf-8")
            print(f"{readme}: regenerated the config table")
        else:
            errors.append(
                f"{readme}: the config table is out of step with the skills' "
                f"requires_config frontmatter — run "
                f"`python3 tools/dev/check-skill-config.py --fix`"
            )
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fix", action="store_true", help="rewrite the generated blocks")
    parser.add_argument("files", nargs="*", help="(ignored; present for pre-commit)")
    args = parser.parse_args([] if argv is None else argv)

    if not PLUGINS.is_dir():
        print("check-skill-config: run from the repository root", file=sys.stderr)
        return 2

    errors = check(fix=args.fix)
    if errors:
        print("check-skill-config: skill configuration is out of step.\n", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    fams = families()
    declared_n = sum(1 for s in fams.values() for need, _ in s.values() if need)
    print(
        f"check-skill-config: OK ({declared_n} skills declare required config; "
        f"{len(fams)} family tables generated)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
