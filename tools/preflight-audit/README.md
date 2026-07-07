<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [preflight-audit](#preflight-audit)
  - [Prerequisites](#prerequisites)
  - [Why](#why)
  - [Invocation](#invocation)
    - [Live mode](#live-mode)
    - [Replay mode](#replay-mode)
  - [Output](#output)
  - [How the rules stay in sync](#how-the-rules-stay-in-sync)
  - [Tuning workflow](#tuning-workflow)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# preflight-audit

**Capability:** substrate:analytics

**Harness:** agnostic

Dry-run the bulk-mode pre-flight classifier against a real or
replayed tracker. Use to **measure skip-rate before / after any
rule change** — closes the tune-then-verify loop so rule edits
are made against evidence, not guesswork.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv` (stdlib only, no third-party deps).
- **CLIs:** `gh` (GitHub CLI) for live mode; replay mode needs none.
- **Credentials / auth:** `gh` authenticated to the tracker repo (live mode only).
- **Network:** GitHub GraphQL API via `gh` (live mode); replay mode runs fully offline.

## Why

The bulk-mode pre-flight classifier
([`bulk-mode.md` § Pre-flight no-op classifier](../../skills/security-issue-sync/SKILL.md))
decides whether to dispatch a subagent for each tracker in a
bulk sync. Its rule table evolves as we learn how real adopter
trackers behave. Each rule change needs a before / after
measurement to know whether the change helped (more skips) or
hurt (false-positive skips that miss real work).

Without a tool, that measurement is a one-off Python script per
PR — easy to lose, hard to reproduce, can't be wired into CI.
This tool makes the measurement reusable.

## Invocation

```bash
uv run --directory tools/preflight-audit preflight-audit classify [options]
```

### Live mode

Fetch tracker state via `gh api graphql` and classify:

```bash
uv run --directory tools/preflight-audit preflight-audit classify \
  --repo <owner>/<name> \
  --issues 221,232,233,242,244
```

`--issues` is a comma-separated list of issue numbers (with or
without `#` prefix). For the full `sync all` set, resolve the
list yourself via `gh issue list --json number` and pipe the
numbers in — the tool intentionally doesn't reimplement
selector resolution (that's the sync skill's job).

Pass `--bot-logins login1,login2` to extend the bot-equivalent
login list for an adopter with personal-account bots.

### Replay mode

Classify a pre-fetched GraphQL response — for CI / regression
testing without network calls:

```bash
uv run --directory tools/preflight-audit preflight-audit classify \
  --load tests/fixtures/sample_response.json \
  --now 2026-05-31T12:00:00Z
```

`--now` is required for replay mode to keep the classification
deterministic (rules depend on "days ago" calculations).

## Output

Default is a human-readable grouped table:

```text
Total trackers: 43
  dispatch: 29 (67%)
  dispatch-urgent: 0 (0%)
  skip-noop: 14 (32%)

--- skip-noop (14) ---
  # 221 OPEN   last=<bot> [skill]  → fix released; awaiting advisory; skill-last (1d)
          labels: airflow+cve allocated+fix released
  ...

=== Estimated savings ===
Subagents skipped: 14  → ~700 KB context saved (~175000 tokens @ 250 tok/KB)
```

Pass `--json` for machine-readable output (one object per
tracker with number, decision, reason, label set).

## How the rules stay in sync

The classifier in
[`src/preflight_audit/classifier.py`](src/preflight_audit/classifier.py)
is the executable spec of the rule table in
[`.claude/skills/security-issue-sync/bulk-mode.md`](../../skills/security-issue-sync/bulk-mode.md).
The skill instructs the orchestrator how to apply the rules
prose-by-prose; this tool implements them in code. Both forms
describe the same rules and **must be edited in lock-step** —
a PR that changes one should change the other.

The tests in
[`tests/test_classifier.py`](tests/test_classifier.py) cover
each rule with a focused synthetic-input case. If the skill's
rule table grows a new entry, add the matching `test_rule_N_*`
case here.

## Tuning workflow

The intended workflow when changing a rule:

1. Run `preflight-audit classify --repo <r> --issues <list>`
   against your adopter tracker to capture the **before**
   distribution.
2. Edit the rule table in `bulk-mode.md` AND the matching
   condition in `classifier.py`.
3. Re-run the same command to capture the **after**
   distribution.
4. Cite both numbers in the PR body. (Strip adopter-specific
   identifiers if the PR is public.)

For tests, save the captured GraphQL response as a fixture and
add a replay-mode test that asserts the expected classification
breakdown — that's the eval-fixture pattern.
