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
- **shared overrides** (`.apache-magpie-overrides/`): — · **personal overrides** (`.apache-magpie-local/`): —
- **hook:** —
- → deep check (integrity, permissions, worktrees): `setup verify`
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

### The adoption floor (`method: marketplace`)

When `.apache-magpie.lock` carries `method: marketplace`, the
collector reads the floor straight out of the committed lock — it is
on disk, so this stays offline — and the renderer prints it right
after the headline:

```markdown
### Adoption floor (`min_version` 0.3.0)

**marketplace `url`:** `apache/magpie`

| Floor |
|---|
| magpie-setup |
| magpie-utilities |
| magpie-agent-guard |

`status` does not know what is installed on this machine — that needs `claude plugin list`, which this offline check never runs. Run `/magpie-setup verify` for the floor-vs-installed comparison.
```

The `url` line is not decoration: it is the marketplace every
contributor's pre-flight would install from, and the pre-flight only
acts without asking when it is `apache/magpie`
([`locks.md`](../setup/locks.md#url-is-a-security-boundary)). This is
the one read-only "what did this repo adopt" surface, so it shows the
field that decides that.

**There is no "Installed" column.** What versions are actually
installed needs `claude plugin list`, and `status` must not be
dragged online to answer that — the collector never emits it, so the
renderer never has it to show. That comparison is `/magpie-setup
verify`'s job, stated plainly rather than faked with a column this
skill cannot fill honestly.

`mode: marketplace` also changes two of the existing lines you would
otherwise expect from a normal adopter: **pinned** reads `floor
≥<min_version>` (a floor is never a pin — see
[`../setup/locks.md`](../setup/locks.md)), and **snapshot** in "Drift
& integrity" reads `n/a (installed via the plugin manager)` rather
than `❌ missing` — there is no snapshot to fetch under this method,
so its absence is not a fault. See
[Mode-aware interpretation](#mode-aware-interpretation).

## Mode-aware interpretation

The same field means opposite things across adoption modes. Apply
this before assigning health:

| Signal | `method:local` (self-adoption) | `method:marketplace` | normal adopter (git/svn) |
|---|---|---|---|
| `snapshot.present == false` | ✅ expected — links go to in-repo `skills/` | ✅ expected — installed via the plugin manager, nothing is fetched into the repo | ❌ snapshot missing → `setup upgrade` |
| `local_lock == null` | ✅ expected — no per-machine fetch | ✅ expected — the plugin manager tracks its own installed state; there is nothing to lock | ⚠️ snapshot not fetched here → `setup upgrade` |
| `gitignore.targets[].all_unignored` | ✅ expected — symlinks are committed | not applicable — no framework symlinks exist under this method | not the pattern used; ignore |
| `gitignore.targets[].glob_ignored` + `setup_unignored` | not used | not applicable — no framework symlinks exist under this method | ✅ expected — symlinks gitignored, bootstrap tracked |
| `drift.checked == false` | ✅ nothing to drift against | ✅ nothing to drift against — see `committed_lock.plugins` / `min_version` instead, via [`/magpie-setup verify`](../setup/verify.md#adoption-floor) | depends on `reason` (see [`collect.md`](collect.md#drift)) |
| `local_overrides.present == false` | ✅ optional personal surface — not required | ✅ same — `.apache-magpie-local/` is always optional | ✅ same — `.apache-magpie-local/` is always optional |
| `gitignore.local_overrides_ignored == false` | advisory: add `/.apache-magpie-local/` to `.gitignore` | same advisory | same advisory |

Never report a self-adopted framework checkout, or a `method:marketplace`
adopter, as unhealthy merely for lacking a snapshot, a local lock, or
committed symlinks — those absences are correct in both cases. A
marketplace adopter has **no repo-side install footprint at all** by
design; the only thing this dashboard can honestly check for one is the
committed floor (above). Whether the floor is actually met is
`/magpie-setup verify`'s job, not this one's.
