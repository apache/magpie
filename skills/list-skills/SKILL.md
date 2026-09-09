---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-list-skills
family: utilities
mode: Meta
description: |
  Print a human-readable index of every skill installed for this
  repository, grouped by the family each one declares, with the
  name to invoke it by and the first sentence of its
  `description`. Discovery is installation-aware: it covers a
  pinned snapshot install, the framework checkout, and
  marketplace plugin installs, so the index matches what the
  agent can actually run. Generated on every run from live
  `SKILL.md` frontmatter, so it never goes stale when skills are
  added, removed, or rewritten.
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

Print a human-readable index of the skills installed for this
repository. The index is generated on every run from live
`SKILL.md` frontmatter — there is no cached copy to keep in sync.
The skill exists for humans (newcomers reading the repo,
maintainers checking what is available); agents route invocations
via the same frontmatter the script reads, so this skill is
purely informational.

What counts as "installed" depends on how Magpie was put in
place, so the script covers all three shapes and labels which one
each entry came from:

| Install | Where the skills live | Invocation shown |
|---|---|---|
| Pinned snapshot | `.agents/skills/` plus the per-agent relays beside it | `/magpie-<skill>` |
| Framework checkout | the repo's own `skills/` | `/magpie-<skill>` |
| Marketplace plugin | the plugin cache this script runs from, and its sibling plugins | `/<plugin>:<skill>` |

---

## Prerequisites

- Python 3.11+ on `PATH`. Nothing else — the script is
  stdlib-only, as `skills/pyproject.toml` requires of every
  helper script in this tree, and declares that contract in
  [PEP 723](https://peps.python.org/pep-0723/) inline metadata.
  `uv run --script` and a bare `python3` therefore behave
  identically.

---

## Step 1 — Run the listing script

Run the bundled script and present its output to the user
verbatim:

```bash
python3 <framework>/skills/list-skills/scripts/list_skills.py
```

Under a marketplace install there is no `<framework>` directory —
the skill is inside the plugin cache. Use the base directory
reported for this skill instead:

```bash
python3 <this-skill-dir>/scripts/list_skills.py
```

For a layout that puts each description on its own indented line
(easier to read when descriptions are long), pass `--verbose`;
to inspect a repository other than the enclosing one, pass
`--root`:

```bash
python3 <framework>/skills/list-skills/scripts/list_skills.py --verbose
python3 <framework>/skills/list-skills/scripts/list_skills.py --root /path/to/repo
```

The script:

- resolves the repository from `git rev-parse --show-toplevel`
  (or `--root`), **not** from its own location — under a
  per-family plugin install its own location is one family, not
  the whole install;
- walks the agent-target directories that install writes into
  (`.agents/skills/` and its relays — the registry in
  [`../setup/agents.md`](../setup/agents.md) is the source of
  truth), the framework's own `skills/` when the repo is the
  framework checkout, and the sibling plugins in the marketplace
  cache when it is running from one;
- de-duplicates by the name you would type, so relay directories
  collapse to one entry while a skill available from *two*
  install methods keeps both — they are two different things to
  type;
- groups by each skill's declared `family:` frontmatter key, per
  Golden rule 8. Family is **never** inferred from the name
  prefix: `repo-health` and `contributor-growth` span several
  prefixes, and `write-skill` is family `utilities`, not family
  `write`. A skill that declares no family lands in `other`;
- prints each entry with the first sentence of its description,
  then a summary of which install each entry came from.

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
  files. It only reads `SKILL.md` files under the install
  directories listed above.
- **No paraphrasing.** Always present the script output verbatim.
  Paraphrasing reintroduces the staleness this skill exists to
  prevent.

---

## References

- [`scripts/list_skills.py`](scripts/list_skills.py) — the
  listing script Step 1 invokes.
- [`AGENTS.md`](../../AGENTS.md#reusable-skills) — the
  framework's "Reusable skills" section, which explains the
  skills layout and frontmatter convention.
- [`../setup/agents.md`](../setup/agents.md) — the agent-target
  registry the discovery list mirrors.
- [`../../docs/setup/marketplaces.md`](../../docs/setup/marketplaces.md)
  — why the invocation name differs between install methods.
- [`write-skill`](../write-skill/SKILL.md) — sibling skill for
  authoring a new skill. Use it when the listing reveals a gap
  that warrants a new entry.
