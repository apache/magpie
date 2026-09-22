<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The probe scripts

One script per probe, named `probe-<n>-<slug>.sh`. Each is
deterministic, side-effect-free, and prints a single line of the shape
the skill's interpretation tables match on:

```text
PROBE: <slug> → ✓|✗|⊘|⚠ (<evidence>)
```

They live here rather than inline in `SKILL.md` because a script runs
without entering the agent's context. Inline, the six of them cost 2,971
tokens on every invocation of the skill; here they cost nothing, and they
can be run and tested on their own.

## Adding a probe

When the [troubleshooting
catalogue](../../../../../docs/setup/sandbox-troubleshooting.md) grows an
entry, add a probe for it:

1. **A script here** — short, deterministic, side-effect-free, printing
   the `PROBE:` line above. One failure mode per script: a probe that
   conflates two restrictions makes the report ambiguous when it fails.
2. **An interpretation table in `SKILL.md`** — three to five rows
   mapping result strings to ✓ / ✗ / ⊘ / ⚠.
3. **A remediation link** to the catalogue section that fixes it. Link
   it; do not paraphrase it. The catalogue is the single source of
   truth.

The probes and the catalogue move in lock-step — a probe with no
catalogue entry has nothing to tell the operator to do.
