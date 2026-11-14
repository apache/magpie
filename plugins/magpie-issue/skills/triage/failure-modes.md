<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Failure modes

Companion to [`SKILL.md`](SKILL.md).

| Symptom | Likely cause | Remediation |
|---|---|---|
| Selector resolves to zero issues | Pool empty or selector mismatched | Surface and stop; do not fall back to a wider selector |
| Classifier flags `UNCERTAIN` on every issue | Step 2 state-gather hit an error (e.g., tracker timeout, body missing) and classifier has nothing to anchor on | Stop, surface the underlying failure, ask user to retry after prerequisite is restored |
| `@`-mention routing finds an empty roster | `<project-config>/release-trains.md` missing relevant component roster | Stop, point at the missing config; do not guess handles |
| User confirms `all` but a post call fails mid-loop | Transient tracker error, rate-limit, or auth expiry | Stop, surface the failed item, instruct the user to retry the remaining items with an explicit selector |
| Reproducer hand-off says *"can't run"* | Build broken or runtime unavailable on the current `<default-branch>` | Continue without runtime evidence; the proposal notes the limitation rather than blocking |
| Bulk-mode subagent reports it called a write tool | Subagent prompt was incomplete or ignored the read-only rule | Stop, surface as a bug; orchestrator marks the apply phase as *"do not run"* until investigated |
