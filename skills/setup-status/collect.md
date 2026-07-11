<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# collect — the adoption-state JSON the dashboard reads

[`scripts/collect_status.py`](scripts/collect_status.py) walks the
repo's on-disk adoption artefacts and emits one JSON document.
It is **read-only** and **offline**: it parses files and reads
symlinks; it never fetches over the network and never writes. The
upstream-tip drift check and any remediation belong to
[`/magpie-setup verify`](../setup/verify.md) and
[`/magpie-setup upgrade`](../setup/upgrade.md).

The skill renders the dashboard via `--format md`
([Step 1](SKILL.md#step-1--render-the-dashboard)); this `--format
json` form is the same data for tooling that wants the raw fields:

```bash
python3 <framework>/skills/setup-status/scripts/collect_status.py --format json --pretty
```

## Top-level fields

| Field | Meaning |
|---|---|
| `repo` | Absolute path of the inspected repo root. |
| `adopted` | `true` when `<committed-lock>` (`.apache-magpie.lock`) exists. `false` → not adopted; [Step 0](SKILL.md#step-0--pre-flight-check) already stopped. |
| `mode` | Install method from the committed lock: `local`, `git-branch`, `git-tag`, `svn-zip`, or `null`. |
| `self_adopted` | `true` when `mode == local` — the framework checkout linking its own `skills/` source. |
| `committed_lock` | Parsed `<committed-lock>` (the project pin), or `null`. |
| `local_lock` | Parsed `<local-lock>` (per-machine fetch), or `null`. Always `null` under `method:local`. |
| `snapshot` | `{present, is_symlink}` for `.apache-magpie/`. |
| `drift` | The committed-vs-local comparison (see below). |
| `registry_source` | `agents.md` when the agent-target list was parsed live from [`../setup/agents.md`](../setup/agents.md) (the normal case), or `fallback` when that file could not be read and the script's built-in mirror was used. |
| `agent_targets` | One record per registry target (see below). |
| `active_target_ids` | The subset of registry ids whose directory is present on disk. |
| `families` | The installed-skill roster grouped by family (see below). |
| `overrides` | `{present, has_readme}` for `.apache-magpie-overrides/`. |
| `post_checkout_hook` | `{present, executable, has_verify_recipe}`. |
| `gitignore` | Coverage flags (see below). |

## `agent_targets[]`

The registry is **parsed live** from
[`../setup/agents.md`](../setup/agents.md) on every run — its
`## The registry` table is the single source of truth. Adding a
vendor row there flows into this dashboard automatically; no edit
to the collector is needed. (The script keeps a built-in mirror
only as a `fallback` when agents.md cannot be read — see
`registry_source` above.) Today the table yields `universal`
(`.agents/skills/`, the canonical home) plus the `claude-code`,
`github`, `windsurf`, and `goose` relay targets. Each record
carries:

| Field | Meaning |
|---|---|
| `id`, `dir` | Registry id and project skills directory. |
| `reads` | The agents that read this directory, verbatim from the [`../setup/agents.md`](../setup/agents.md) registry. For `universal` this is the whole shared-path cluster (Codex, Cursor, Gemini CLI, Copilot, OpenCode, Cline, Zed, Warp, Amp, …), so one wired directory serves many agents. |
| `expected_kind` | `canonical` for `universal`, `relay` for the rest. |
| `present` | Directory exists on disk. |
| `entries[]` | One per `magpie-*` entry: `name`, `skill`, `family`, `is_symlink`, `raw_target`, `resolves`, `kind`. |
| `magpie_count`, `live_count`, `dangling[]` | Roll-ups over `entries`. |

`entries[].kind` is one of: `canonical-source` (links into the
in-repo `skills/<n>/` — self-adoption), `canonical-snapshot`
(links into `.apache-magpie/skills/<n>/` — a normal adopter),
`relay` (links back at `../../.agents/skills/magpie-<n>`), `copy`
(a real directory holding `SKILL.md` — the committed
`magpie-setup` bootstrap), or `broken` (a non-symlink with no
`SKILL.md`).

## `families`

Each installed canonical skill is bucketed by the `family:`
frontmatter key read from its `SKILL.md` (never by name prefix —
`repo-health` and `contributor-growth` span several prefixes, per
[Golden rule 8](../setup/SKILL.md#golden-rules)):

- `opt_in` — the user-selectable families: `security`,
  `pr-management`, `issue`, `release-management`, `repo-health`,
  `pairing`, `mentoring`, `contributor-growth`. `opt_in_present` /
  `opt_in_absent` list which are wired.
- `always_on` — `setup` (every `family: setup` skill plus the
  committed `setup` bootstrap) and `utilities` (`list-skills`,
  `write-skill`, `optimize-skill`, `skill-reconciler`): wired
  unconditionally per
  [Golden rule 8](../setup/SKILL.md#golden-rules).
- `other` — any installed skill whose `SKILL.md` declares no
  readable family. Reported by name so the dashboard never
  silently drops it (empty for a healthy framework snapshot).

The bucketing reads what is actually on disk. The authoritative
opt-in pick for a normal adopter is recorded in the lock files;
when present, prefer the lock's family list over the on-disk read
for the *intended* set, and use the on-disk read for the
*installed* set so the dashboard can flag a gap between them.

## `drift`

| `checked` | Then |
|---|---|
| `false`, reason `method:local …` | Self-adoption has no remote snapshot to drift against. |
| `false`, reason `local lock absent …` | The snapshot was never fetched on this machine. Propose [`/magpie-setup upgrade`](../setup/upgrade.md). |
| `true` | `in_sync` plus any `mismatches[]` over `method` / `url` / `ref`. The `git-branch` upstream-tip comparison needs network and is **not** done here — `note` names `/magpie-setup verify` as the skill that does it. |

## `gitignore`

Top-level flags (`snapshot_ignored`, `local_lock_ignored`,
`settings_local_ignored`) plus a per-target map. Each target
carries `glob_ignored` + `setup_unignored` (the **normal-adopter**
pattern: ignore the symlinks, keep the bootstrap tracked) and
`all_unignored` (the **self-adoption** pattern: every `magpie-*`
symlink is committed, so the whole glob is un-ignored).

Interpretation is mode-aware — see
[`render.md`](render.md#mode-aware-interpretation). Deep
`.gitignore` validation is owned by
[`/magpie-setup verify`](../setup/verify.md); this skill only
surfaces the headline.
