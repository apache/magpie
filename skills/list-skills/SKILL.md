---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-list-skills
family: utilities
mode: Meta
description: |
  Print a human-readable index of every skill in this repository,
  grouped by family prefix (`pr-management`, `security`, `setup`,
  …) with each skill's name and the first sentence of its
  `description`. The listing is generated on every run from the
  live `.claude/skills/*/SKILL.md` files, so it never goes stale
  when skills are added, removed, or rewritten.
when_to_use: |
  Invoke when a human asks *"what skills are available"*, *"list
  the skills"*, *"show me the skills in this repo"*, *"give me a
  table of contents for the skills"*, or types `/magpie-list-skills`.
  This is a help-style overview for humans onboarding to the
  repository — agents route via the live frontmatter
  `description` field directly and do not need this index to
  choose a skill.
capability: capability:stats
license: Apache-2.0
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → adopting project's `.apache-magpie/` directory
     <tracker>        → value of `tracker_repo:` in <project-config>/project.md
     <upstream>       → value of `upstream_repo:` in <project-config>/project.md
     <framework>      → `.apache-magpie/apache-magpie` in adopters; `.` in
                        the framework standalone -->

# list-skills

Print a human-readable index of the skills in this repository.
The index is generated on every run from the live
`.claude/skills/*/SKILL.md` files — there is no cached copy to
keep in sync. The skill exists for humans (newcomers reading the
repo, maintainers checking what is available); agents route
invocations via the same frontmatter the script reads, so this
skill is purely informational.

---

## Prerequisites

- Python 3.9+ on `PATH` with `PyYAML` importable. The framework's
  Python toolchain already meets this; no extra setup.

---

## Step 1 — Run the listing script

Run the bundled script and present its output to the user
verbatim:

```bash
python3 .claude/skills/magpie-list-skills/scripts/list_skills.py
```

For a layout that puts each description on its own indented line
(easier to read when descriptions are long), pass `--verbose`:

```bash
python3 .claude/skills/magpie-list-skills/scripts/list_skills.py --verbose
```

The script:

- walks `.claude/skills/*/SKILL.md` relative to its own location;
- parses each skill's YAML frontmatter for `name` + `description`;
- groups skills by family prefix (the first hyphen-separated
  token, with `pr-management` recognised as a two-token family —
  see [`KNOWN_TWO_TOKEN_FAMILIES`](scripts/list_skills.py));
- prints each skill with the first sentence of its description.

When a new multi-token family appears (e.g. a hypothetical
`docs-build-*`), add the prefix to `KNOWN_TWO_TOKEN_FAMILIES` in
[`scripts/list_skills.py`](scripts/list_skills.py); otherwise the
new skills land under the single-token head.

---

## Step 2 — Hand the output to the user

Quote the script output back to the user as-is. Do not
paraphrase, summarise, or re-order — the value of this skill is
that the listing is the canonical, deterministic view of what
exists. If the user asks for more detail on a specific skill,
read that skill's `SKILL.md` and answer from it.

---

## Hard rules

- **Read-only.** This skill never edits, creates, or deletes
  files. It only reads `SKILL.md` files under `.claude/skills/`.
- **No paraphrasing.** Always present the script output verbatim.
  Paraphrasing reintroduces the staleness this skill exists to
  prevent.

---

## References

- [`scripts/list_skills.py`](scripts/list_skills.py) — the
  listing script Step 1 invokes.
- [`AGENTS.md`](../../AGENTS.md#reusable-skills) — the
  framework's "Reusable skills" section, which explains the
  `.claude/skills/` layout and frontmatter convention.
- [`write-skill`](../write-skill/SKILL.md) — sibling skill for
  authoring a new skill. Use it when the listing reveals a gap
  that warrants a new entry.
