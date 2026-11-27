<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Batches of private-tracker writes — one confirmation per batch](#batches-of-private-tracker-writes--one-confirmation-per-batch)
  - [Problem](#problem)
  - [Decision](#decision)
  - [Manifest schema](#manifest-schema)
  - [Validation rules](#validation-rules)
  - [What stays individually confirmed](#what-stays-individually-confirmed)
  - [How approval maps to harness prompts](#how-approval-maps-to-harness-prompts)
  - [Selecting another checkout's policy](#selecting-another-checkouts-policy)
  - [Alternatives](#alternatives)
  - [Risks](#risks)
  - [Follow-ups](#follow-ups)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Batches of private-tracker writes — one confirmation per batch

**Status:** built (`vetted-op-tracker-batch`, `vetted-op-tracker-batch-unprompted`, `vetted-op-read batch-check`, the `[approval]` policy table, `--policy-from` on the batch entry points); skill adoption partial, see [Follow-ups](#follow-ups).
**Family:** `tools` (vetted-ops), `security` (the skills that call it).
**Capability:** `substrate:sandbox`, `capability:intake`, `capability:reconciliation`.

## Problem

Every write a security skill makes to the private tracker goes through a vetted operation, and every write dispatcher sits behind an `ask` permission rule.
One call is one prompt.
An import of 16 scanner findings needed about 16 creates, 16 label edits, 16 rollup entries and some 26 more rollup entries:
roughly 74 prompts, each showing a command line the maintainer cannot usefully review one at a time.
Prompt fatigue is a security problem of its own: a maintainer who clicks through 74 prompts will click through the one that mattered.

The writes are not all alike.
A label, a rollup entry or a board move on the private tracker is seen only by the security team.
An email draft, a comment on a public `apache/*` repository, an advisory comment or a CVE-record push leaves the team.
The first kind can be reviewed as a group; the second must stay one confirmation per action.

A related defect blocked the obvious workaround of applying from a subagent:
a subagent's Bash `cd` does not persist, and agent-guard refuses `cd … && uvx …` (the `excluded-chain` guard).
Main's `--policy-from <dir>` (apache/magpie#2376) answers that for the single-call dispatchers, confined to checkouts the operator lists;
the batch entry points take the same option under the same rules.

## Decision

1. **A manifest of private-tracker writes, checked whole, run in order.**
   A skill writes a JSON manifest into the vetted-ops workspace naming the operations and their positional parameters,
   exactly as it would pass them to `vetted-op` one call at a time.
   `vetted-op-read --caller <skill> batch-check <manifest>` checks every entry against the approved policy and prints a summary and a digest; it runs nothing and never prompts.
   The skill shows the user that summary as its proposal.
   `vetted-op-tracker-batch --caller <skill> --expect <digest> <manifest>` checks the manifest again, refuses a digest that does not match, and runs the entries in order, stopping at the first failure.
2. **Two entry points of their own, so each can have its own permission rule.**
   The prompt comes from the harness, not from vetted-ops (see [How approval maps to harness prompts](#how-approval-maps-to-harness-prompts)).
   Claude Code evaluates `ask` before `allow`, so a `batch` subcommand of `vetted-op-tracker` would always be caught by that dispatcher's `ask` rule and could never be allowed on its own.
   Separate console scripts keep the boundary where the rest of vetted-ops keeps it: on the entry point, which a permission rule can name and argv cannot change.
   `vetted-op-tracker-batch` runs a policy set to `batch` or `none` and is always on `ask`.
   `vetted-op-tracker-batch-unprompted` takes the same arguments but refuses, before it reads the manifest, any policy not set to `none`; it is the only one an adopter may `allow`.
   One script accepting both modes would let an `allow` written for a `none` project run, unprompted, the policy of another approved project set to `batch`,
   selected with `--policy-from` or `cd`; with the split, an unprompted run can only ever act on a policy whose adopter chose `none`.
3. **A policy knob that turns batching on.**
   `[approval] private_tracker_writes` is `each` (the default: the batch entry point refuses, everything prompts per call, as before), `batch`, or `none`.
   It lives in the policy because the policy is what the user approves byte for byte; the agent cannot turn batching on.
4. **`--policy-from <dir>`, as main defines it,** on `batch-check` and both batch entry points (see [Selecting another checkout's policy](#selecting-another-checkouts-policy)).

## Manifest schema

```json
{
  "version": 1,
  "ops": [
    {"op": "issue-create-labeled", "params": ["/ws/title-a.txt", "/ws/body-a.md", "[\"needs triage\",\"security issue\"]"]},
    {"op": "issue-add-label",      "params": ["12", "scope:core"]},
    {"op": "rollup-append",        "params": ["12", "import", "/ws/rollup-12.md"]}
  ]
}
```

- Exactly the keys `version` (must be `1`) and `ops`; each entry exactly `op` and `params`. Any other key refuses the manifest, so it cannot carry a caller, a repository or an option.
- `params` are strings, positional, the same values a single call takes. Body and title files are workspace paths, as for a single call.
- 1 to 200 entries. A longer run is split into several batches, each with its own summary.
- No references between entries. An entry cannot use a number an earlier entry created; a skill that creates trackers and then labels them runs two batches (see [Alternatives](#alternatives)).

The manifest file is checked like a body file: a `.json` file under the policy's workspace, owner-only, no symlink on its path, read once from the descriptor that was checked.

## Validation rules

All of these run before the first write; one failure refuses the whole batch and nothing runs.

1. The approved policy sets `private_tracker_writes` to `batch` or `none`, and declares a tracker.
2. The manifest parses and matches the schema.
3. Every operation is in `BATCHABLE`, a closed list in [`batch.py`](../../tools/vetted-ops/src/vetted_ops/batch.py):
   the `issue-*` writes on the tracker, `comment-update`, `milestone-create` / `milestone-close`,
   the rollup and body-field procedures, and the three `board-*` writes.
   An operation outside it is refused by name, even when the caller is granted it.
4. The caller (`--caller`, once, on the command line) is granted every operation in the policy.
5. Every entry passes the same parameter validation and the same builder as a single call (`_validate_params`, `build_argv`): enums against the policy, no parameter starting with `-`, bodies read from the workspace.
6. The built command addresses the tracker, checked on the argv itself:
   `gh issue … --repo <tracker>`, `gh api repos/<tracker>/…`, a procedure plan pinned to the tracker, a board mutation on the policy's `board_project_id`, or a non-GitHub tracker backend's call.
7. The digest matches `--expect` (the 16-character prefix or the whole digest).
   It is SHA-256 over the destination — the policy file's hash (so the approved copy itself), the tracker, the tracker backend, the board id, the resolved workspace and the batching mode —
   then the manifest bytes, every body and title it names, and every entry's built command (the `gh` argv, the procedure and its parameters, or the backend call).
   The same manifest checked under one approved policy is refused under another, and what runs is exactly what `batch-check` summarised.
8. On GitHub, the forge confirms the tracker is private (`gh api repos/<tracker> --jq .private` is `true`) and, when a board operation is present, that the board is not public.
   The policy's word is not taken for it: a tracker pointed at a public repository by mistake would otherwise publish a batch of pre-disclosure text in one confirmation.

The run prints one header line per entry before it runs it (bodies by size, never by content), lets each operation's own output through (an `issue-create-labeled` prints its `number`, `node_id` and `url`),
and ends with one JSON line: `{"batch": "done", …}`, or, with the failing operation's exit code,
`{"batch": "stopped", "succeeded": [1 … k], "unknown": k+1, "op": …, "not_run": [k+2 …]}`.
The failing entry is **unknown**, never "not run": a write can land and still exit non-zero (a timeout, a dropped connection, a procedure whose write went through before a later step failed).
Body and title files are deleted only once every entry succeeded; after a stop every one of them stays, so a recovery manifest validates.
The manifest itself is deleted after any run, so it cannot be rerun blindly: a rerun would repeat the entries that succeeded.
Recovery: the skill first reads the tracker (vetted reads, no prompt) to learn whether the unknown entry took effect,
then proposes a new manifest with the not-run entries, plus the unknown one only if it did not take effect, and checks it again.

## What stays individually confirmed

Never batched, refused by name if they appear in a manifest:

- every write to the public upstream repository (`pr-*`, `repo-issue-*`, `run-rerun*`, `workflow-approve`);
- `advisory-comment` (GitHub advisory comments);
- `cve-allocate` and `cve-record-update` (the CVE tool; a pushed record is public once published);
- `tracker-publish` (the local-files tracker's push to its remote);
- everything `vetted-op-git` does;
- email: Gmail drafts are not vetted operations at all and stay drafts the user sends by hand.

A skill that mixes the two kinds splits them: tracker writes into the batch, the rest one call at a time in the order the skill already prescribes.

## How approval maps to harness prompts

vetted-ops never prompts.
The confirmation is the harness's: under Claude Code, a `Bash(...)` command matching an `ask` rule prompts, one matching an `allow` rule runs, and `ask` wins over `allow`.
The setup skills write one `ask` and one `sandbox.excludedCommands` entry per write dispatcher and launcher, and an `allow` only for `vetted-op-read`.
So the knob's three values mean:

| `private_tracker_writes` | `vetted-op-tracker-batch` (always `ask`) | `vetted-op-tracker-batch-unprompted` | Prompts for a 74-write import |
|---|---|---|---|
| `each` (default) | refuses | refuses | 74 |
| `batch` | runs a checked batch | refuses | one per batch: 2 or 3 |
| `none` | runs a checked batch | runs a checked batch; `allow`, written by the adopter | 0 for the tracker writes |

vetted-ops cannot tell whether a prompt was shown, so it cannot enforce `none` by itself.
What it enforces is the pairing: the only entry point an `allow` may name refuses every policy that is not `none`.
Whatever approved policy the caller selects (`--policy-from`, `cd`), an unprompted run needs one whose adopter chose `none`.
The prompt under `batch` shows the command line, which names the manifest and the digest; the content was shown by `batch-check` just before, and `--expect` binds the run to it.
A user who approves the prompt approves the summary whose digest it carries, not a path whose content could change.

The framework's settings (`.claude/settings.json`, `tools/sandbox-lint/expected.json`) ask for both batch entry points in both launcher forms and exclude them from the sandbox, as for every write dispatcher.
sandbox-lint treats `vetted-op-tracker-batch` like every write dispatcher (`ask`, never `allow`),
requires an excluded `vetted-op-tracker-batch-unprompted` to match an `ask` **or** an `allow` rule, and fails an `allow` on any other write dispatcher.
The Codex rules renderer prints both as `prompt`; an adopter on `none` changes the unprompted lines by hand.
Setup may offer `none`; writing its `allow` rule is a follow-up of the setup skills.

**The trade-off of `none`.**
Under `none` an agent can write anything the caller is granted to the private tracker without the user seeing a prompt:
rewrite an issue body, close an issue, move or archive board items, post a tracker comment that `@`-mentions team members.
Nothing leaves the team, and nothing reaches a public surface, but a prompt-injected session (the import reads untrusted reports) can vandalise tracker state, and the only record is the rollup and GitHub's issue history.
`batch` keeps a human look at a summary per batch; `none` trades that for zero prompts.
The default is `each`; the setup skills may offer `none`, alongside this trade-off.

## Selecting another checkout's policy

The batch entry points discover their policy like the single-call dispatchers: from the working directory, or from main's `--policy-from <dir>`.
An earlier draft of this change had its own `--project-root`, which accepted any absolute directory; review flagged it, since an unprompted dispatcher that takes any directory can probe the host for directories and approved policies, or read through another project's policy.
It was dropped for `--policy-from`, which accepts only a checkout the operator lists in their own `operator-git.toml`, compared as text before anything on disk is touched,
and acts only on an approved policy there that lists that checkout for its upstream (`git_ops.policy_from_checkout`, `git_ops.check_policy_from_upstream`).
A repeated `--policy-from` is refused, since argparse would keep the last one.

The caller still chooses which listed, approved policy applies (one project's instead of another's), as it does with `cd`.
Two things keep that choice from widening approval.
The unprompted entry point refuses any selected policy not set to `none`, so an `allow` written for one project cannot run another project's `batch` policy without its prompt.
And the digest binds the policy's hash and destination, so a summary the user approved under one policy cannot be run under another.
Relative body and manifest paths still resolve against the process's working directory, so a subagent passes absolute paths.

## Alternatives

- **A `batch` subcommand of `vetted-op-tracker`.** Needs no new permission rules, but its `ask` would shadow any `allow`, so `none` could not exist. Rejected for the entry-point reason above.
- **`vetted-op batch`.** The general write dispatcher would then run batches containing public writes unless the subcommand re-implemented the whole refusal; a separate entry point refuses them by construction.
- **References between entries** (`"number": "@1"` for the number entry 1 created). Saves one prompt in an import, but the summary would show placeholders instead of the trackers that change, and a failed create would leave dangling references. Two batches cost one extra prompt and keep every value literal.
- **A dry run on the batch entry point instead of `batch-check`.** Under `ask` it would prompt too, making two prompts per batch. `batch-check` is a read on the allowlisted entry point; it loads only the approved policy and refuses `--config`, so it cannot be pointed at a planted policy's workspace.
- **Rely on harness "don't ask again" grants.** Claude Code can remember a rule for a session, but the remembered rule is a prefix of the first command, broad (it would cover every later `vetted-op-tracker …` call) or useless (an exact command), and it leaves no reviewable summary.
- **Batch outbound actions too.** Rejected by the request and by the confidentiality rules: a public comment, an email or a published record cannot be taken back, and each needs its own look.

## Risks

- **The summary is only as good as its reading.** A 150-entry summary invites the same fatigue as 150 prompts. Skills keep batches to one phase of one run and show the summary grouped by tracker.
- **A batch stopped half way leaves a half-applied state, and the failing entry's state is unknown.** The report names what succeeded, the unknown entry and what did not run; the skill reads the tracker before re-proposing anything. The manifest is deleted after the run, so a blind rerun (which would duplicate creates) fails, while the body files stay for the recovery manifest.
- **One script for both modes** (rejected after review): an `allow` written for a `none` project would have run any other approved project's `batch` policy unprompted.
- **Secondary rate limits.** Dozens of writes in a row can hit GitHub's content-creation limits; the batch stops at the first failure and reports it like any other.
- **`none` and prompt injection,** discussed above.
- **Digest prefix.** 16 hex characters (64 bits) bind the run to the summary against an accidental or agent-made change between check and run; finding a second manifest with the same prefix is not practical within a session.

## Follow-ups

- Skill adoption beyond `security-issue-sync` bulk apply, `security-issue-import` Step 7 and `security-issue-import-from-scan` Step F:
  `security-issue-triage` Step 6 (several triage-proposal comments), `security-issue-deduplicate` and `security-issue-invalidate` (their `apply.py` plans already list tracker writes and can emit a manifest), `security-issue-import-from-md` and `-from-pr`.
- The setup skills (`setup config`, `isolated-setup-install` Step V, `isolated-setup-verify`, `isolated-setup-update`) propose the knob and, for `none`, write and verify the `allow` rule for `vetted-op-tracker-batch-unprompted`; today they wire both batch entry points on `ask` only.
