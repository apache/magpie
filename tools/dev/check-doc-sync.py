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

"""Check the documentation claims that must track the tree, and silently rot.

Eight checks, all mechanical, each one written after the drift it catches was
found by hand:

1. **Spec-index completeness.** Every ``tools/spec-loop/specs/<name>.md`` is
   listed in both ``overview.md`` and ``README.md``. Ten specs were absent from
   both — including per-family specs and one added four PRs earlier — because
   nothing checked, and an index that lists two-thirds of its subject reads
   exactly like one that lists all of it.

2. **Per-family skill counts in README.md.** The family table's "N skills" cell
   against the live ``family:`` frontmatter. Two cells were wrong: one went
   stale when three skills landed, the other had been drifting for months.

3. **Per-mode skill counts in docs/modes.md.** The *Modes at a glance* table's
   Skill-count column against the live ``mode:`` frontmatter. The validator's
   ``modes-doc`` rule checks section *membership* but reads only the mode and
   status columns, so the counts were unguarded.

4. **Total-skill claims in prose.** A small allowlist of files whose "N skills"
   phrasing means the whole catalogue.

5. **Per-family *plugin* skill counts.** The marketplace tables in
   ``docs/setup/marketplaces.md`` and ``docs/quick-start.md`` list a bare count
   per ``magpie-<family>`` plugin, plus a total for the all-in-one ``magpie``
   row. Check 2 does not reach them — those cells are bare integers in a table
   column, not the "N skills" phrasing check 4 matches — so both tables sat two
   families out of date (``security`` 12, ``utilities`` 4, total 70) while
   README.md, which *is* guarded, carried the right numbers. These counts drive
   an install decision, so a stale one costs the reader context they were
   choosing against.

6. **Per-family skill counts in the family READMEs.** Each
   ``docs/<family>/README.md`` opens with an "Install & first runs" section
   claiming "one plugin, N skills". Ten more numbers a human would have to
   remember; the family is read from the install command in the same file, so
   ``issue`` under ``docs/issue-management/`` resolves correctly.

7. **The portable single-token form declares its install.** A doc showing
   ``/magpie-<skill>`` is teaching a command that exists only on a snapshot or
   self-adoption install; since the marketplace install is now the default, the
   page has to say so. ``/magpie-setup`` is exempt — it names the install
   *mechanism* — and a filesystem path (``.agents/skills/magpie-<skill>/``,
   several of which are ``test -f`` assertions in the spec files) is not an
   invocation.

8. **Every script in ``tools/dev/`` is named in its README.** These scripts are
   the framework's own gates, and an undocumented one is invisible to the next
   contributor who has to decide whether it applies to their change. Naming it
   is the minimum; the README says what each guards.

Why counting is worth a hook at all: every one of these is a number a human has
to remember to update while thinking about something else, and none of them
breaks anything when wrong. They just quietly mislead the next reader.

Run from the repo root:

    python3 tools/dev/check-doc-sync.py
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

SKILLS_DIR = Path("skills")
SPECS_DIR = Path("tools/spec-loop/specs")
SPEC_INDEXES = (SPECS_DIR / "overview.md", SPECS_DIR / "README.md")
# The index files themselves are not specs.
SPEC_INDEX_NAMES = {p.name for p in SPEC_INDEXES}

# Files whose bare "N skills" phrasing means the whole catalogue. Deliberately
# an allowlist rather than a repo-wide sweep: plenty of docs legitimately count
# a subset ("Nine skills cover the staged path"), and a greedy scan would flag
# those as drift forever.
TOTAL_COUNT_FILES = (Path("docs/setup/marketplaces.md"), Path("docs/quick-start.md"))

# Files carrying a per-family marketplace-plugin table: a `magpie-<family>` row
# with a bare skill count, and an all-in-one `magpie` row counting the lot.
FAMILY_PLUGIN_FILES = (Path("docs/setup/marketplaces.md"), Path("docs/quick-start.md"))

# Family README "Install & first runs" sections: the family is named by the
# `/plugin install magpie-<family>@...` line, the count by the prose above it.
FAMILY_README_GLOB = "docs/*/README.md"

# Markdown that documents how to invoke a skill. The stutter guard reads these;
# eval fixtures are expected *outputs*, not documentation, so they are excluded.
DOC_GLOBS = ("*.md", "docs/**/*.md", "skills/**/*.md", "tools/**/*.md", "projects/**/*.md")
DOC_EXCLUDE_PARTS = ("skill-evals",)
# A doc that *explains* the stutter has to show one. Marking the line is
# deliberate and greppable; excluding whole files would silence real drift in
# the same page that documents the rule.
STUTTER_ALLOW = "<!-- allow-stutter -->"

# A doc showing the portable single-token form (`/magpie-issue-triage`) is
# teaching a command that only exists on a snapshot / self-adoption install. It
# must say so. `/magpie-setup` itself is exempt everywhere: it names the
# *mechanism* (the skill that installs, upgrades and verifies a snapshot), and
# that mechanism only exists on that install anyway.
# Either wording counts as the page telling the reader which install it means:
# the snapshot guides state it one way, the marketplace-form pages the other.
PORTABLE_FORM_NOTES = (
    "Skill names differ on this install",
    "Skill names here are the marketplace form",
)
# Pages that are wholly about the snapshot install and carry the note, or whose
# subject *is* the portable naming convention.
PORTABLE_FORM_ALLOWED = {
    Path("docs/setup/marketplaces.md"),  # documents both forms side by side
    Path("docs/quick-start.md"),  # its snapshot section carries an inline note
    Path("CONTRIBUTING.md"),  # self-adoption section carries an inline note
    Path("tools/skill-and-tool-validator/README.md"),  # documents the name: convention
    Path("tools/dev/README.md"),  # documents these checks
}

# Dev scripts must each be named in tools/dev/README.md. Suffixes rather than a
# mode check: a script is a script whether or not its executable bit survived a
# checkout.
DEV_DIR = Path("tools/dev")
DEV_SCRIPT_SUFFIXES = (".py", ".sh")

# `| [**security**](docs/security/README.md) | opt-in | … | 15 skills, [`docs/…`] |`
_README_FAMILY_ROW = re.compile(
    r"^\|\s*\[?\*\*(?P<family>[a-z-]+)\*\*\]?[^|]*\|.*?\|\s*(?P<count>\d+) skills?[,)]",
)
# `| **Triage** | *(Agentic Triage)* … | stable (…) | 35 |`
_MODES_GLANCE_ROW = re.compile(r"^\|\s*\*\*(?P<mode>[A-Za-z ]+?)\*\*\s*\|.*\|\s*(?P<count>\d+)\s*\|\s*$")
_BARE_TOTAL = re.compile(r"\b(?P<count>\d+) skills\b")
# `| `magpie-security` | 15 | ~4.8k |` — the per-family plugin row.
_PLUGIN_FAMILY_ROW = re.compile(r"^\|\s*`magpie-(?P<family>[a-z-]+)`\s*\|\s*(?P<count>\d+)\s*\|")
# `| **`magpie`** (all) | **74** | **~21.7k** |` — the all-in-one row.
_PLUGIN_ALL_ROW = re.compile(r"^\|\s*\*?\*?`magpie`\*?\*?\s*\(all\)\s*\|\s*\*?\*?(?P<count>\d+)\*?\*?\s*\|")
# `Install just this family — one plugin, 15 skills.`
_README_INSTALL_COUNT = re.compile(r"one plugin, (?P<count>\d+) skills")
# ``/plugin install magpie-security@apache-magpie``
_README_INSTALL_PLUGIN = re.compile(r"/plugin install magpie-(?P<family>[a-z-]+)@")


def _frontmatter(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    return m.group(1) if m else ""


def _key_counts(key: str) -> dict[str, int]:
    """Count live skills by a single-valued frontmatter key (``family``/``mode``)."""
    counts: dict[str, int] = {}
    for skill_md in sorted(SKILLS_DIR.glob("*/SKILL.md")):
        m = re.search(rf"^{key}:\s*(\S+)\s*$", _frontmatter(skill_md), re.M)
        if m:
            counts[m.group(1)] = counts.get(m.group(1), 0) + 1
    return counts


def check_spec_index(errors: list[str]) -> None:
    if not SPECS_DIR.is_dir():
        return
    index_text = {p: p.read_text(encoding="utf-8") for p in SPEC_INDEXES if p.is_file()}
    for spec in sorted(SPECS_DIR.glob("*.md")):
        if spec.name in SPEC_INDEX_NAMES:
            continue
        for index, text in index_text.items():
            if f"({spec.name})" not in text:
                errors.append(
                    f"{index}: spec '{spec.name}' is not listed — every spec belongs in both indexes"
                )


def check_readme_family_counts(errors: list[str]) -> None:
    readme = Path("README.md")
    if not readme.is_file():
        return
    live = _key_counts("family")
    for lineno, line in enumerate(readme.read_text(encoding="utf-8").splitlines(), 1):
        m = _README_FAMILY_ROW.match(line)
        if not m:
            continue
        family, declared = m.group("family"), int(m.group("count"))
        actual = live.get(family)
        if actual is None:
            continue  # a table row that is not a skill family
        if declared != actual:
            errors.append(
                f"README.md:{lineno}: family '{family}' says {declared} skills; "
                f"live family: frontmatter has {actual}"
            )


def check_modes_glance_counts(errors: list[str]) -> None:
    modes = Path("docs/modes.md")
    if not modes.is_file():
        return
    text = modes.read_text(encoding="utf-8")
    if "## Modes at a glance" not in text:
        return
    glance = text.split("## Modes at a glance", 1)[1].split("\n## ", 1)[0]
    live = _key_counts("mode")
    offset = text[: text.index("## Modes at a glance")].count("\n") + 1
    for lineno, line in enumerate(glance.splitlines(), offset):
        m = _MODES_GLANCE_ROW.match(line)
        if not m:
            continue
        mode, declared = m.group("mode").strip(), int(m.group("count"))
        actual = live.get(mode)
        if actual is None:
            # A mode with no skills (e.g. one deliberately switched off) must
            # declare 0 rather than be skipped.
            if declared != 0:
                errors.append(
                    f"docs/modes.md:{lineno}: mode '{mode}' says {declared} skills; "
                    f"no skill declares that mode"
                )
            continue
        if declared != actual:
            errors.append(
                f"docs/modes.md:{lineno}: mode '{mode}' says {declared} skills; "
                f"live mode: frontmatter has {actual}"
            )


def check_total_counts(errors: list[str], total: int) -> None:
    for path in TOTAL_COUNT_FILES:
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in _BARE_TOTAL.finditer(line):
                declared = int(m.group("count"))
                if declared != total:
                    errors.append(f"{path}:{lineno}: says {declared} skills; the catalogue has {total}")


def check_family_plugin_counts(errors: list[str], total: int) -> None:
    """Per-family marketplace-plugin tables against the live family frontmatter.

    Distinct from :func:`check_readme_family_counts`: that one reads README's
    family table, keyed on ``**family**`` with an "N skills" cell. These tables
    are keyed on the *plugin* name (``magpie-<family>``) and carry a bare
    integer, so neither of the existing patterns matches them.
    """
    live = _key_counts("family")
    for path in FAMILY_PLUGIN_FILES:
        if not path.is_file():
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            m = _PLUGIN_FAMILY_ROW.match(line)
            if m:
                family, declared = m.group("family"), int(m.group("count"))
                actual = live.get(family)
                if actual is None:
                    errors.append(
                        f"{path}:{lineno}: plugin 'magpie-{family}' names no live family; "
                        f"known families: {', '.join(sorted(live))}"
                    )
                elif declared != actual:
                    errors.append(
                        f"{path}:{lineno}: plugin 'magpie-{family}' says {declared} skills; "
                        f"live family: frontmatter has {actual}"
                    )
                continue
            m = _PLUGIN_ALL_ROW.match(line)
            if m and int(m.group("count")) != total:
                errors.append(
                    f"{path}:{lineno}: the all-in-one 'magpie' row says {m.group('count')} "
                    f"skills; the catalogue has {total}"
                )


def check_family_readme_counts(errors: list[str]) -> None:
    """The "N skills" claim in each family README's install section.

    The family is taken from the ``/plugin install magpie-<family>@`` line in
    the same file rather than from the directory name, because one family's
    docs do not sit in a directory named after it (``issue`` lives under
    ``docs/issue-management/``).
    """
    live = _key_counts("family")
    for path in sorted(Path(".").glob(FAMILY_README_GLOB)):
        text = path.read_text(encoding="utf-8")
        plugin = _README_INSTALL_PLUGIN.search(text)
        count = _README_INSTALL_COUNT.search(text)
        if not plugin or not count:
            continue  # not a family README with an install section
        family, declared = plugin.group("family"), int(count.group("count"))
        actual = live.get(family)
        lineno = text[: count.start()].count("\n") + 1
        if actual is None:
            errors.append(
                f"{path}:{lineno}: install section names plugin 'magpie-{family}', which is no live family"
            )
        elif declared != actual:
            errors.append(
                f"{path}:{lineno}: says {declared} skills for family '{family}'; "
                f"live family: frontmatter has {actual}"
            )


def check_no_plugin_name_stutter(errors: list[str]) -> None:
    """No doc may invoke a family skill by a name that repeats its family.

    ``/magpie-security:security-issue-triage`` says "security" twice. The family
    plugins advertise a de-stuttered alias (``/magpie-security:issue-triage``,
    see ``plugin_alias`` in ``check-family-plugins.py``), so a stuttering form in
    the docs is a command nobody can run.
    """
    families = set(_key_counts("family"))
    seen: set[Path] = set()
    for pattern in DOC_GLOBS:
        for path in sorted(Path(".").glob(pattern)):
            if path in seen or any(part in DOC_EXCLUDE_PARTS for part in path.parts):
                continue
            seen.add(path)
            for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
                if STUTTER_ALLOW in line:
                    continue
                for family in families:
                    for repeated in {family, family.split("-")[0]}:
                        bad = f"/magpie-{family}:{repeated}-"
                        if bad in line:
                            errors.append(
                                f"{path}:{lineno}: '{bad}…' repeats the family name; "
                                f"the plugin advertises the alias without it"
                            )


def check_portable_form_is_flagged(errors: list[str]) -> None:
    """A doc using the single-token skill form must say which install it is for.

    The marketplace install is the default, so `/magpie-issue-triage` in a page
    that never mentions the snapshot reads as a command the reader can run, and
    it is not. Either the page carries the note, or it is on the allowlist.

    `/magpie-setup` (with or without a verb) is deliberately not matched: it is
    the name of the install mechanism, not a skill a marketplace user invokes.
    """
    skills = {p.parent.name for p in SKILLS_DIR.glob("*/SKILL.md")} - {"setup"}
    seen: set[Path] = set()
    for pattern in DOC_GLOBS:
        for path in sorted(Path(".").glob(pattern)):
            if path in seen or any(part in DOC_EXCLUDE_PARTS for part in path.parts):
                continue
            seen.add(path)
            if path in PORTABLE_FORM_ALLOWED:
                continue
            text = path.read_text(encoding="utf-8")
            if any(note in text for note in PORTABLE_FORM_NOTES):
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for skill in skills:
                    # Only an invocation, never a filesystem path: the lookbehind
                    # rejects `.agents/skills/magpie-<skill>/` (several of which
                    # are `test -f` assertions in the spec files) and the
                    # lookahead rejects anything that continues into a path.
                    if re.search(rf"(?<![A-Za-z0-9_.-])/magpie-{re.escape(skill)}(?![A-Za-z0-9_/-])", line):
                        errors.append(
                            f"{path}:{lineno}: '/magpie-{skill}' is the snapshot-install form; "
                            f"use '/<plugin>:<alias>' or state which install this page means"
                        )


def check_token_figures(errors: list[str]) -> None:
    """Published always-on token figures against the live frontmatter.

    Delegates to ``estimate-skill-tokens.py`` so the measurement lives in one
    place; loaded through importlib because its filename is hyphenated.
    """
    script = DEV_DIR / "estimate-skill-tokens.py"
    if not script.is_file():
        return
    spec = importlib.util.spec_from_file_location("estimate_skill_tokens", script)
    if not spec or not spec.loader:
        return
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.check(errors)


def check_dev_scripts_documented(errors: list[str]) -> None:
    readme = DEV_DIR / "README.md"
    if not DEV_DIR.is_dir() or not readme.is_file():
        return
    text = readme.read_text(encoding="utf-8")
    for script in sorted(DEV_DIR.iterdir()):
        if not script.is_file() or script.suffix not in DEV_SCRIPT_SUFFIXES:
            continue
        if script.name not in text:
            errors.append(
                f"{readme}: '{script.name}' is not named — every script in "
                f"{DEV_DIR}/ must be documented there"
            )


def main() -> int:
    if not SKILLS_DIR.is_dir():
        print("check-doc-sync: run from the repository root", file=sys.stderr)
        return 2
    total = len(list(SKILLS_DIR.glob("*/SKILL.md")))
    errors: list[str] = []
    check_spec_index(errors)
    check_readme_family_counts(errors)
    check_modes_glance_counts(errors)
    check_total_counts(errors, total)
    check_family_plugin_counts(errors, total)
    check_family_readme_counts(errors)
    check_no_plugin_name_stutter(errors)
    check_portable_form_is_flagged(errors)
    check_token_figures(errors)
    check_dev_scripts_documented(errors)

    if errors:
        print("check-doc-sync: documentation is out of step with the tree.\n", file=sys.stderr)
        for err in errors:
            print(f"  {err}", file=sys.stderr)
        print(
            f"\n{len(errors)} problem(s). These are counts and index entries a human has to "
            "remember to update; nothing breaks when they are wrong, which is why they drift.",
            file=sys.stderr,
        )
        return 1
    print(f"check-doc-sync: OK ({total} skills; spec indexes, declared counts, and dev-script docs agree).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
