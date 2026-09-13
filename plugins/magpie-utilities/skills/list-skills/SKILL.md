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
  table of contents for the skills"*, or invokes it under
  whichever name their install method uses.
  Skill names differ on this install:
  `/magpie-utilities:list-skills` on a marketplace family-plugin
  install, `/magpie-list-skills` on the pinned snapshot.
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

<!-- BEGIN MAGPIE PREFLIGHT — generated from tools/dev/preflight-block.md -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Pre-flight — is this project set up?](#pre-flight--is-this-project-set-up)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Pre-flight — is this project set up?

Do this **first, before anything else in this skill**, and do it silently: a
couple of file checks, or one CLI call for a marketplace install.

1. **Is a lock present?** If `.apache-magpie.lock` exists, read its
   `method`.
2. **A snapshot method** (`svn-zip` / `git-tag` / `git-branch`) →
   compare with `.apache-magpie.local.lock`:
   - local lock missing → the snapshot was never fetched on this
     machine;
   - `ref` / `commit` differ → this machine is on a different framework
     version than the project pins.
   Anything unresolved → **stop and propose `/magpie-setup`** (or
   `/magpie-setup upgrade` for a version mismatch).
3. **`method: marketplace`** → the lock is the project's **floor**: a
   minimum version and a minimum plugin set, never a pin. Compare the
   machine against it.

   **First, check `url`.** If it is anything other than
   `apache/magpie`, run **nothing**. Name the marketplace the lock
   points at, show the commands it would take, and let the user decide.
   A lock is a committed file in whatever repository happened to be
   opened, and acting on it automatically would make opening a
   repository enough to install someone else's code.

   Otherwise read the installed state — `claude plugin list --json`, or
   the running agent's equivalent — and compare **as PEP 440, not as
   strings**: `0.10.0` is newer than `0.9.0`, and `0.2.0` is newer than
   `0.2.0.dev202609110041`.

   - every floor plugin installed at or above `min_version` →
     **silent**; continue the skill;
   - a floor plugin absent → `claude plugin install
     <plugin>@apache-magpie`;
   - a floor plugin below `min_version` → `claude plugin update
     <plugin>@apache-magpie`.

   **Never** remove a plugin, downgrade one, pin the marketplace to a
   tag, or touch a plugin absent from the floor. Being *ahead* of the
   floor is the normal case and is not a finding.

   Where there is no such CLI, run nothing and print the commands
   instead.

4. **Unless step 3 passed silently, stop.** Whichever branch you took —
   plugins installed or updated, commands printed because there is no
   CLI, or nothing run at all because `url` named another marketplace —
   this session is still below the project's floor. Claude Code loads
   plugins at session start, so anything just installed is not live
   here, and anything only printed has not run at all. Say what ran, or
   what to run, and that the session has to be restarted before
   re-running this command.

5. **No lock?** Then this is the marketplace install without adoption,
   or nothing at all. Look for a `<project-config>/` directory. If there
   is none, the project has not been adopted and every `<placeholder>`
   in this skill is unresolved → **stop and propose `/magpie-setup`**.
   Do **not** run setup unattended and do **not** continue on a guess: a
   skill that proceeds against an unadopted repo writes to the wrong
   tracker.

Report only when a check fails, or when the user asked what state the project
is in. `/magpie-setup verify` is the full diagnostic.

<!-- END MAGPIE PREFLIGHT -->

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
python3 .claude/skills/magpie-list-skills/scripts/list_skills.py
```

Run that command **literally**, as written — do not expand it to
an absolute path. It is a repository-relative path that resolves
under both install methods that put skills in the repository: a
pinned snapshot install and the framework checkout both carry
`.claude/skills/magpie-list-skills` as a symlink onto the real
skill directory.

For a layout that puts each description on its own indented line
(easier to read when descriptions are long), pass `--verbose`; to
inspect a repository other than the enclosing one, pass `--root`:

```bash
python3 .claude/skills/magpie-list-skills/scripts/list_skills.py --verbose
python3 .claude/skills/magpie-list-skills/scripts/list_skills.py --root /path/to/repo
```

**Marketplace installs are the one exception.** They write nothing
into the repository, so that path does not exist — the skill lives
in the plugin cache. Build the command from the base directory
reported for this skill instead:

```bash
python3 <the base directory reported for this skill>/scripts/list_skills.py
```

The script:

- resolves the repository from `git rev-parse --show-toplevel`
  (or `--root`), **not** from its own location — under a
  per-family plugin install its own location is one family, not
  the whole install;
- walks the agent-target directories that install writes into
  (`.agents/skills/` and its relays — the registry in
  [`../../../magpie-setup/skills/setup/agents.md`](../../../magpie-setup/skills/setup/agents.md) is the source of
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
- [`AGENTS.md`](../../../../AGENTS.md#reusable-skills) — the
  framework's "Reusable skills" section, which explains the
  skills layout and frontmatter convention.
- [`../../../magpie-setup/skills/setup/agents.md`](../../../magpie-setup/skills/setup/agents.md) — the agent-target
  registry the discovery list mirrors.
- [`../../../../docs/setup/marketplace.md`](../../../../docs/setup/marketplace.md)
  — why the invocation name differs between install methods.
- [`write-skill`](../write-skill/SKILL.md) — sibling skill for
  authoring a new skill. Use it when the listing reveals a gap
  that warrants a new entry.
