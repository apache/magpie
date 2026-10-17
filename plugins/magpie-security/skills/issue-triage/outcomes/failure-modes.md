<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-triage — failure modes

Read from [`SKILL.md` § *Failure modes*](../SKILL.md#failure-modes).

| Symptom | Likely cause | Remediation |
|---|---|---|
| Selector resolves to zero trackers | Either no `needs triage` open (nothing to do — congratulations) or the scope/CVE selector mismatched | Surface and stop; do not fall back to a wider selector |
| Classifier flags `UNCERTAIN` on every tracker | The Step 2 state-gather hit an error (e.g. Gmail down, body field missing) and the classifier has nothing to anchor on | Stop, surface the underlying failure, ask user to retry after the prerequisite is restored |
| `@`-mention routing finds an empty roster | `<project-config>/release-trains.md` is missing the security-team subsection, or `<project-config>/project.md` doesn't declare the routing rules | Stop, point at the missing config; do not guess handles |
| User confirms `all` but a `gh issue comment` call fails mid-loop | Transient GitHub error, rate-limit, or auth expiry | Stop, surface the failed item, instruct the user to retry the remaining items with an explicit selector |
| Bulk-mode subagent reports it called a write tool | Either the subagent prompt was incomplete (write-prevention rule not surfaced) or the subagent ignored the rule | Stop, surface as a bug; the orchestrator marks the apply phase as "do not run" until investigated |
