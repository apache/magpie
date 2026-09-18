<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This is a first adoption. Step 1 settled the floor as `magpie-setup`,
`magpie-utilities`, `magpie-agent-guard` and `magpie-pr-management` — the
maintainer added the last one. Step 2 wrote the lock; there was no previous
lock. Steps 4a and 4b have finished.

The glob found `CONTRIBUTING.md`, `README.md` and
`.github/PULL_REQUEST_TEMPLATE.md`. The maintainer un-ticked `README.md` as
marketing copy and confirmed the other two.

`CONTRIBUTING.md` line 42 reads: "Every pull request needs approvals from two
committers before it may be merged." The framework default for
`pr-management-triage` is one approval.

`CONTRIBUTING.md` line 88 reads: "We close pull requests after 30 days without
author response." The framework default stale window for
`pr-management-stale-sweep` is 90 days.

`.github/PULL_REQUEST_TEMPLATE.md` contains only a checklist of things the
author should confirm. Nothing in it contradicts a framework default.

The maintainer accepted the two-approval deviation and rejected the 30-day
one, saying the 30-day sentence is aspirational and nobody follows it.

The repository also has a `RELEASE.md` describing a vote process that differs
from the framework's release defaults. It was not among the confirmed
documents and the release family is not in the floor.
