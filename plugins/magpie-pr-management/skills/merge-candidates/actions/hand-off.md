<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Handing the remainder to code-review

The `too-large`, `path-denied` and `path-unmatched` drops are not noise: they are the deep-review queue — substantive changes that want a line-level read.
After the candidates, name the PRs in `handoff.prs` (clickable) and recommend the review skill: *"N ready PRs need a full read — run `pr-management-code-review`, or `pr-management-code-review pr:<N>` for one."*
This is a pointer, not an invocation: the maintainer decides. Quick-merge skims the trivial top of the ready queue, code-review reads the rest, and triage fills it.
