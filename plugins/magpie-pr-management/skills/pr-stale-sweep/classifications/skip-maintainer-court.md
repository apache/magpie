<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `SKIP-MAINTAINER-COURT`

**Fires when** the author's most recent human comment `@`-mentions a maintainer or the committers team and no maintainer has replied since — the same test as pre-filter F5c in `pr-management-triage`.
[`stale-sweep classify`](../../../../../tools/pr-management/src/pr_management/stale_sweep/classify.py) decided it. A mentioned login it could not resolve is decided as a maintainer (skip) and listed under `needs`; save the permission read and classify again.

**Action:** none. The recap reminds the maintainers that they owe this author a response.

## Why

The next move is a maintainer's. Nudging or closing for "inactivity" punishes the contributor for maintainer silence.
