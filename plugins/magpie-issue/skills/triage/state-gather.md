<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Gather per-issue state (Step 2)

Companion to [`SKILL.md`](SKILL.md). The full Step 2 checklist of
per-issue inputs the classifier needs.

For each issue in the list, gather (in parallel where the tracker
permits batched reads) the inputs the classifier needs.

1. **Issue body + last 10 comments + metadata** — title, status,
   resolution, fixVersion, component / area labels, reporter
   identity, assignee (if any), age, last-update timestamp.

2. **Component / area mapping** — extract from labels and map to
   the project's components via
   [`<project-config>/scope-labels.md`](../../../../projects/_template/scope-labels.md).
   The component drives the `@`-mention routing in Step 4.

3. **Linked-PR state** — open or merged PRs that reference this
   issue may materially shift the disposition:
   - Open PR with proposed fix → strong signal for `BUG` (the team
     has converged enough to write code).
   - Merged PR for the issue, but the issue is still open →
     strong signal for `ALREADY-FIXED`.

4. **Reproducer hand-off (optional)** — if the issue carries a
   code example and the classification hinges on whether the
   example still fails on `<default-branch>`, invoke
   [`issue-reproducer`](../reproducer/SKILL.md) for this
   issue and include the resulting `verdict.json` in the state
   bag for the classifier.

5. **Cross-reference search** — for `DUPLICATE` detection, search
   the tracker for issues with similar text (title keywords,
   component overlap, code-pointer overlap). A STRONG match
   against an open or closed issue is the most direct route to a
   `DUPLICATE` proposal.

6. **Recent-fix scan** — for `ALREADY-FIXED` detection, search
   `<upstream>`'s git log since the issue's filing date for
   commits referencing the issue key (e.g., `git log --grep=<KEY>`)
   or touching the cited code locations. This `git log` is the **Git
   binding** of the framework's source-control capability
   ([`tools/github/source-control.md`](../../../../tools/github/source-control.md));
   a project on a non-Git VCS enabled under *Tools enabled → Source
   control* substitutes that tool's history-read binding (`hg log`,
   `svn log`, …) for the same abstract operation.
