<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Disposition vocabulary

Companion to [`SKILL.md`](SKILL.md). The two disposition classes and the
threshold defaults behind them.

The skill uses **exactly two** disposition classes:

| Class | When to propose | Follow-up action |
|---|---|---|
| `REQUEST-UPDATE` | Issue is dormant past the warn threshold but **not** yet past the close threshold; reporter has not recently responded | Post a nudge comment asking the reporter to confirm the issue is still relevant on the current `<default-branch>`; no state change yet |
| `CLOSE-STALE` | Issue is dormant past the close threshold **and** has already received a `REQUEST-UPDATE` nudge with no response, **or** is dormant past a hard-close threshold with no nudge needed | Post a pre-close notice and, on a second explicit confirmation, close the issue |

The two thresholds (`warn_days` and `close_days`) default to
[`<project-config>/stale-sweep-config.md`](../../../../projects/_template/stale-sweep-config.md)'s
values when it exists, else framework defaults (90 / 180 days); either may
be overridden inline at invocation time.
