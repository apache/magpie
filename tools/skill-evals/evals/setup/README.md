<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# setup evals

Behavioral evals for the `setup` skill.

## Suites (92 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-verify-drift | verify.md § Check 3 (drift) | 5 | clean, method/URL mismatch, ref mismatch, svn-zip SHA-512 mismatch, local lock missing |
| verify-default-set | verify.md § Committed default set | 4 | no committed `enabledPlugins` block (absent, not a fault), every floor member present (current), some but not all present (stale — the only fault this check reports), a lock whose floor was enlarged to four (stale, naming the fourth) |
| uninstall-default-set | uninstall.md § Committed default set | 3 | committed block is exactly the floor (all three removed, nothing kept), a mixed block with other Magpie and other-vendor plugins (only the floor removed, everything else kept), a lock whose floor was enlarged to four (all four removed — no entry orphaned behind a deleted marketplace) |
| step-overrides-surface | overrides.md § Step 0b | 4 | adopted no flag (offer choice), --local flag (personal), not adopted (personal only), both surfaces exist |
| step-override-bypass | agentic-overrides.md § One-shot defaults run | 3 | `--no-overrides` flag + override exists, `--no-overrides` + no override, no flag + override exists |
| step-m3-baseline-pick | install.md § Step M3 — Pick the families | 3 | the baseline (`magpie-setup`, `magpie-agent-guard`, `magpie-utilities`) is pre-ticked beside the family the user's own words named; a user un-ticking the two recommended ones is obeyed; and an explicit `skill-families:` list is used verbatim, gaining only `magpie-setup` — the skill doing the installing, and the one plugin that is never dropped |
| step-m4-install-gates | install.md § Step M4 — Install what the user picked | 7 | the CLI runs the picked installs (`--scope user`, no `-y`); the four gates that send the step to printing — a sandboxed plugin store rejecting the write, a `from:` naming someone else's marketplace, a harness with no install CLI, an install stopping for a marketplace-declared command; and the two scope requests — *this repo only* (`--scope local`) and *the whole project*, which is adoption and hands off rather than passing `--scope project` |
| step-m5-no-repo-offer | install.md § Step M5 — Recap and what comes next | 4 | An install writes nothing repo-side on any harness and is complete as it stands: Claude Code fresh, Codex, Gemini (no offer in any of them), plus the one case where adoption legitimately comes up — the user asked for the team to get it on clone |
| step-adopt-settings-merge | adopt.md § Merge rules | 5 | no `.claude/settings.json` (create), file with unrelated keys (merge, preserve them), existing `enabledPlugins` with non-floor and non-Magpie entries (add only the missing floor members, remove nothing), existing pinned `apache-magpie` marketplace definition (left alone), malformed JSON (refuse, never rewrite) |
| lock-marketplace-parse | locks.md § `method: marketplace` | 5 | ahead of floor, a .dev floor met by the release after it, 0.9.0 against a 0.10.0 floor (the string-ordering trap), a missing floor plugin, and a git-tag lock that still pins |
| adopt-write-floor | adopt.md § Step 2 | 4 | a fresh adopt with an extra family installed that stays out of the floor, a maintainer adding one deliberately, a .dev version recorded verbatim, and Gemini still getting a lock with no derived wiring |
| adopt-review-process | adopt.md § Step 4c | 5 | a fresh adopt finding two deviations in the confirmed documents where one is accepted and one rejected, and a release policy left alone because that family is not in the floor; a re-adoption reviewing only the one family the floor diff added; a re-adoption that adds no family, where edited process documents are still not re-read; a sentence that would weaken a merge confirmation gate, dropped and named while a label deviation beside it is written; and a repo whose only candidate document the maintainer un-ticks, skipping the step |
| setup-prefill-from-floor | install.md § Step M0b | 4 | adopted (propose the floor), unadopted (framework defaults), a foreign marketplace called out, and a snapshot lock falling through |
| preflight-floor | preflight-block.md § Pre-flight | 8 | at floor (silent), below floor (update), plugin missing (install), foreign marketplace (ask first, run nothing), no `claude` CLI (print), unadopted (propose setup), `apache/magpie` in an alarming context (update anyway, unasked), unreadable `claude plugin list --json` (silent, treated as unknown not absent) |
| upgrade-adoption-split | upgrade.md § Step 0b | 4 | not adopted (nothing staged), adopted (floor raised and staged), already ahead (floor unchanged), snapshot method (falls through) |
| verify-floor | verify.md § Adoption floor | 4 | no lock (not a fault), ahead of floor with extra plugins (not a fault), a shortfall (a fault), a floor plugin the marketplace no longer ships (a fault, not installed around) |
| step-reconcile | reconcile.md § The sweep | 3 | a clean sweep on a pinned-snapshot install (anchor present, config resolved — stamp written, nothing proposed), a renamed step heading stranding an override's anchor (one re-anchor proposal named), a marketplace install whose plugin cache is sandbox-denied (anchor resolution left `unchecked`, config resolution still completes) |
| step-verify | verify.md § 12. Latest available plugin version | 2 | a dev-to-dev delta where the marketplace clone is one dev build ahead of an installed plugin (`update_available` carries the newer dev version — pins decision 7: nothing strips `.devN`), and a sandbox-denied marketplace clone (`update_available: null` **and** `unchecked: ["latest-version"]`, distinguishing *nothing newer* from *could not look*) |
| step-config-stamp | config.md § Step 3b | 4 | `config` on an already-adopted project where Step 3 wrote the skill's last missing file this run, which records `acknowledged.skills` locally and never touches the committed lock; `config` on an unadopted one, whose entries land in `.apache-magpie-local/reconciled.json`'s `skills` map with `version`/`at` regardless of whether this run touched a file; the R2 skip on a repo where nothing has ever been configured or adopted (`write_stamp: false`); and an already-adopted project where the one skill in scope was already fully configured *before* this run, so nothing is recorded even though the lock exists (`write_stamp: false` for a different reason — the narrowed acknowledged-write trigger) |
| step-config-adversarial | config.md § Step 3c | 5 | a named `config adversarial-review` run pre-ticks every available backend except `self` and offers command files only for installed non-Claude, non-Copilot harnesses (Copilot gets the invocation); a plain `config` run and a run entered from a skill's pre-flight offer nothing; no offer without the plugin; and an offer with nothing pre-ticked when only `self` is available |
| step-adopt-stamp | adopt.md § 4d | 1 | a re-adoption that migrates an earlier `config` run's local `skills` map into the committed lock, adds the skill 4a/4b/4c just configured, and records the version Step 2 actually read off the machine rather than the (higher, ratcheted) `min_version` it kept |
| step-upgrade-stamp | upgrade.md § Step 5 | 1 | two overrides after a snapshot refresh — one whose target skill, anchors, and `requires_config` all resolve (stamped), and one with intact anchors but an unresolved `requires_config` entry (a finding, deliberately left unstamped rather than reported false-clean) |
| step-unknown-subaction | SKILL.md § Unrecognised sub-action | 4 | a one-letter typo (`upgrede` — ask, suggest `upgrade`, run nothing), an exact name (`reconcile` — run it), no close match (`frobnicate` — ask with the list only), and a prefix shared by two sub-actions (`un` — suggest both) |

## Run

`--cli` is required or nothing is graded; use `--directory`, not
`--project`, and run from the repo root.

```bash
# All cases
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/

# Single suite
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/step-override-bypass/

# Single case
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/setup/step-override-bypass/fixtures/case-1-flag-override-exists
```

## Notes

- `step-verify-drift` cases are fully auto-comparable: all three output
  fields (`status`, `severity`, `remediation`) are enumerated strings.
- `verify-default-set` cases are fully auto-comparable: `status` and
  `is_fault` are an enumerated string and a boolean, and `missing` is a
  plain list. Case 1 (absent) is the one that matters most — it checks
  that the skill states the optionality strongly enough that `is_fault`
  comes back `false` for a block that was never committed.
- `uninstall-default-set` cases are fully auto-comparable: `plugins_removed`,
  `plugins_kept`, and `keys_preserved` are plain lists, and `file_deleted` is
  a boolean. Both cases report only the raw shape of
  `.claude/settings.json` (its top-level keys and the contents of
  `enabledPlugins`), never which entries the answer should sort into which
  list — the model has to apply the floor-removal rule itself. Case 2
  (mixed) is the one that matters most — it checks that non-floor Magpie
  plugins and other vendors' plugins both survive untouched alongside an
  unrelated top-level key.
- `step-overrides-surface` tests the new `--local` flag and personal-
  vs-shared surface selection introduced by the `magpie-local-convention`
  work item.  The default surface when the repo is adopted and no flag is
  passed is `"offer-choice"`; `override_path` reports the personal default.
- `step-override-bypass` cases are fully auto-comparable: `decision` and
  `safety_baseline` are enumerated strings, and `reason` is checked by
  deterministic `regex` predicates in `assertions.json`
  (`has_bypass_reason` for the skip cases, `has_apply_reason` for the
  apply case) — no grader or MANUAL step is required.
  The two predicates discriminate on *direction*, not on the flag name.
  Keying on `no-overrides` would be useless here: the flag name appears
  in a correct reason and in a reason arguing the exact opposite, so such
  a pattern passes either way. Each predicate therefore requires the
  matching verb (skipped/not-consulted versus applied/consulted) and
  rejects the opposing phrasing. When editing them, check both
  directions — that a right answer still passes *and* that a reason
  arguing the other decision fails.
- `preflight-floor` cases 4 and 7 are the security pair, and 7 is the
  half that makes the pair discriminating. Case 4 alone cannot prove the
  prose drives the answer: a safety-tuned grader derives "a non-standard
  marketplace deserves flagging" from the fixture, so deleting the `url`
  rule leaves it green. Case 7 tests the **permissive** half of the same
  boundary — a freshly cloned repo the user does not own, unfamiliar
  plugin names, but `url: apache/magpie` — where the rule entails
  `update`, run unasked, and commonsense argues for `ask-first`. No
  grader reaches `update` there by commonsense, so the prose is the only
  possible source of the answer. Mutation check: delete the `url`
  paragraph from step 3 of `tools/dev/preflight-block.md` and case 7
  flips to `ask-first`. Neither case may regress.
- `preflight-floor`'s `commands` field is what the pre-flight **runs**,
  not what it displays; `commands_shown` is what it prints. Cases 4 and 5
  therefore assert `"commands": []` — "nothing ran" is asserted directly
  rather than riding on the `action` enum alone.
- `preflight-floor` cases 2 and 3 grade their free-text `reason` with
  the `mention_restart` regex predicate in `assertions.json` rather than
  by string match. The `mention_` prefix is load-bearing:
  `runner.py`'s `is_structural_expected` recognises only keys prefixed
  `has_` or `mention_`, so a plural `mentions_restart` would fall
  through to key-intersection comparison and the predicate would
  silently never fire.
- `verify-default-set` case 4 and `uninstall-default-set` case 3 are the
  enlarged-floor pair. Both name a lock carrying four plugins rather than
  the three `adopt` seeds, because every one of these checks reads the
  lock's `plugins` list, in floor order, and not a fixed count. A
  regression to a hard-coded three shows up as a fourth entry left behind
  in `enabledPlugins` after its marketplace definition was removed — a
  broken committed file for every contributor. Their reports state the
  lock explicitly: the lock is the input to these checks, so a fixture
  that omitted it would leave the floor to be guessed.
- `verify-floor` cases 1 and 2 are the pair that keeps the floor a
  recommendation: a repo that never adopted, and a contributor ahead of
  the floor with extra families installed, must both come back
  `is_fault: false`.
- `step-verify` cases are fully auto-comparable: `update_available` is a
  plain list (or `null`) and `unchecked` is a plain list of enumerated
  strings. Case 1 is the pair member that pins the dev-build rule from
  the reconciliation design's decision 7 — the marketplace clone is a
  newer `.devN` build, not a release, and must still be reported as an
  update. Case 2 is the pair member that keeps *unreadable* distinct
  from *up to date*: a sandbox-denied clone must answer
  `update_available: null` with `unchecked: ["latest-version"]`, never
  an empty list that a reader could mistake for "checked, nothing
  found."
