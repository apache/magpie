<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# adjust — reconfigure adoption from the dashboard

After [rendering](render.md), and unless `--no-adjust` was passed,
offer the user concrete, confirmable changes to the adoption
wiring. This skill **never edits symlinks, lock files, or
`.gitignore` itself**: every change is carried out by delegating
to [`/magpie-setup`](../setup/SKILL.md), the one skill that owns
adoption mutation. The status skill detects the delta, proposes
the exact command, and — on the user's explicit confirmation —
runs it.

## Step A — Detect the deltas

**Short-circuit first:** if `no_adjust` is set, the adjust flow is
skipped entirely — return `offer_adjustments: false` with empty
`deltas` and `delegated_commands`, and run no detection at all.
Only when `no_adjust` is unset do you evaluate the table below.

From the collected JSON, surface each of these that applies:

| Delta | Signal in the JSON |
|---|---|
| Registry target unwired | a registry dir is `present` but not in `active_target_ids`, or present with `magpie_count == 0` |
| Opt-in family not installed | `families.opt_in_absent` is non-empty |
| Opt-in family recorded but missing | the lock's family list includes a family absent from `families.opt_in_present` |
| Dangling symlinks | any target's `dangling[]` is non-empty |
| Drift | `drift.checked && !drift.in_sync`, or a `local lock absent` reason |
| Not adopted | `adopted == false` (already handled in [Step 0](SKILL.md#step-0--pre-flight-check)) |

Order the offers most → least impactful (drift and dangling links
before optional family additions). If no delta applies, say the
adoption is fully wired and stop — do not invent work.

### Map each delta to a `/magpie-setup` command

| Adjustment | Delegated command |
|---|---|
| Add an agent target | `/magpie-setup install agents:<full desired set>` |
| Enable an opt-in family | `/magpie-setup install skill-families:<full desired set>` |
| Repair dangling / missing symlinks | `/magpie-setup verify --auto-fix-symlinks` |
| Sync drift / fetch snapshot | `/magpie-setup upgrade` |
| Adopt from scratch | `/magpie-setup` |

**The `agents:` and `skill-families:` flags replace the set for
that run** (see [`../setup/SKILL.md` Inputs](../setup/SKILL.md#inputs)).
So to *add* a target or family, pass the **union of the existing
set and the new one**, computed from `active_target_ids` /
`families.opt_in_present`. `universal` is always retained by setup
even if omitted, because it is the canonical home every relay
points at.

Example — current targets are `universal, claude-code` and the
user wants GitHub too:

```bash
/magpie-setup install agents:universal,claude-code,github
```

Example — `security` and `pr-management` are installed and the
user wants the `issue` family as well:

```bash
/magpie-setup install skill-families:security,pr-management,issue
```

**Two hard rules when building these commands:**

- **Never use a `--target` / per-item flag.** Re-wiring an
  unwired target (one that is `present` with `magpie_count == 0`)
  uses the same `agents:<full set>` form — include the unwired
  target id in the set, do not pass it alone.
- **Collapse same-flag changes into one command.** Multiple
  absent families produce a *single* `skill-families:` command
  listing the full union, never one command per family. Likewise
  for multiple targets under `agents:`.

## Step B — Confirm, then delegate

1. Present the proposed change as a single line: *what* changes
   and *which* `/magpie-setup` command runs.
2. Wait for explicit confirmation (`go`, `yes`, the command
   itself). No confirmation → do nothing; the dashboard already
   delivered the value.
3. On confirmation, invoke the delegated `/magpie-setup`
   sub-action. It owns the plan-before-write, the symlink/lock
   edits, the worktree propagation, and the sandbox-allowlist
   pass. Do not pre-empt or duplicate any of that here.
4. After it returns, re-run [`collect_status.py`](scripts/collect_status.py)
   and show the one-line headline so the user sees the change took
   effect.

## Removals are heavier — hand them to setup deliberately

Adding targets/families is additive and safe. **Dropping** a
target or family removes committed/gitignored symlinks and may
strand overrides, so do not auto-propose it. If the user asks to
drop one, restate it as a `/magpie-setup install` run with the
reduced set (or [`/magpie-setup unadopt`](../setup/uninstall.md) to
remove adoption entirely), describe what disappears, and let the
setup skill carry it out under its own confirmation.

## Self-adoption (`method:local`) caveat

In the framework checkout itself, adoption links *every* skill
under `skills/` across every active target by design — there is no
opt-in family selection and no snapshot to sync. The only
meaningful adjustments are **repairing dangling relays** (re-run
`/magpie-setup`, idempotent) and **adding a new registry target
dir** that the operator created. Skip the family-enable and
drift-sync offers there; `families.opt_in_absent` being empty and
`drift.checked == false` already reflect this.
