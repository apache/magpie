<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# render — the adoption dashboard

**The dashboard is rendered deterministically by the collector
itself — do not hand-rebuild it.** Run:

```bash
python3 <framework>/skills/setup-status/scripts/collect_status.py --format md
```

and present that output **verbatim** as the dashboard. The
`--format md` renderer owns the headline, the full agent-target
matrix (including the **Reads / agents-served** column and the
`universal` cluster note), the family roster, and the drift /
integrity summary. Rendering it in-script is deliberate: an
LLM-formatted table reliably drops columns (the Reads column in
particular), so the matrix must not depend on a formatting pass.

After printing the verbatim dashboard, the agent may **add**:

1. A one-line mode-aware interpretation where it helps (see
   [Mode-aware interpretation](#mode-aware-interpretation)) —
   without contradicting or re-tabulating the script output.
2. The reconfigure offer from [`adjust.md`](adjust.md).

The JSON form (`--format json`, see [`collect.md`](collect.md))
remains available for tooling that wants the raw fields.

## Layout reference (what `--format md` emits)

The sections below document the layout the renderer produces, so a
reviewer can reason about it. They are **not** a separate
hand-rendering recipe.

It is **GitHub-flavoured Markdown**: a pipe table for the target
matrix (narrow columns only) plus a `serves` bullet legend for the
wide agents-served text (kept out of the table so no column wraps
and breaks). A self-adopted framework checkout renders like:

```markdown
## apache-magpie adoption — magpie

**mode:** local (self-adopted) · **pinned:** skills/ · **verdict:** ✅ healthy

### Agent targets

| Target | Dir | Kind | Skills | Status |
|---|---|---|---|---|
| universal | `.agents/skills` | canonical-source | 40 | ✅ wired |
| claude-code | `.claude/skills` | relay | 40 | ✅ wired |
| github | `.github/skills` | relay | 40 | ✅ wired |
| windsurf | `.windsurf/skills` | relay | — | ⚪ absent |
| goose | `.goose/skills` | relay | — | ⚪ absent |

**serves** (which agents read each target dir):

- `universal` — Codex, Cursor, Gemini CLI, GitHub Copilot, OpenCode, Cline, Zed, Warp, …
- `claude-code` — Claude Code
- `github` — GitHub's skill loader
- `windsurf` — Windsurf
- `goose` — Goose

### Skill families

security ✅ 12 · pr-management ✅ 8 · issue ✅ 8 · release-management ✅ 10 · repo-health ✅ 6 · pairing ✅ 2 · mentoring ✅ 4 · contributor-growth ✅ 6 · always-on setup(9) utilities(4) · other 0

### Drift & integrity

- **drift:** n/a (method:local …) · **snapshot:** in-repo source (local)
- **overrides:** — · **hook:** —
- → deep check (integrity, permissions, worktrees): `/magpie-setup verify`
```

Notes on the format:

- **Status column**: `✅ wired` (all live), `❌ N broken` (dangling
  symlinks), `⚠️ unwired` (dir present, zero `magpie-*`), `⚪
  absent` (dir not present). Kept narrow so the table never wraps.
- **`serves` legend** carries the agents that read each directory —
  the one wide field, deliberately a bullet list outside the table.
  `universal` is one directory but a whole cluster, so its bullet
  names them and the operator sees the framework supports far more
  than the five target ids.
- **Verdict** (worst wins, computed by `verdict()` in the
  collector): `❌` not adopted / `method`|`url` drift / dangling
  links; `⚠️` `ref` drift / a present-but-unwired target; `✅`
  otherwise.
- The target list is **parsed live** from
  [`../setup/agents.md`](../setup/agents.md), so it stays current
  as the framework adds vendors. If `registry_source` is
  `fallback`, agents.md was unreadable and the built-in mirror was
  used (the renderer prints a stale-list warning). Per-user global
  paths (`~/.codex/skills/`, …) are out of scope — project-scope
  adoption only.

## Mode-aware interpretation

The same field means opposite things across adoption modes. Apply
this before assigning health:

| Signal | `method:local` (self-adoption) | normal adopter (git/svn) |
|---|---|---|
| `snapshot.present == false` | ✅ expected — links go to in-repo `skills/` | ❌ snapshot missing → `/magpie-setup upgrade` |
| `local_lock == null` | ✅ expected — no per-machine fetch | ⚠️ snapshot not fetched here → `/magpie-setup upgrade` |
| `gitignore.targets[].all_unignored` | ✅ expected — symlinks are committed | not the pattern used; ignore |
| `gitignore.targets[].glob_ignored` + `setup_unignored` | not used | ✅ expected — symlinks gitignored, bootstrap tracked |
| `drift.checked == false` | ✅ nothing to drift against | depends on `reason` (see [`collect.md`](collect.md#drift)) |

Never report a self-adopted framework checkout as unhealthy merely
for lacking a snapshot, a local lock, or ignored symlinks — those
absences are correct there.
