<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #6501 — Add retry jitter to HTTP provider
Author: alice-contributor (CONTRIBUTOR)
CI: SUCCESS — all required checks pass
Mergeable: MERGEABLE
Unresolved threads: 0
Existing maintainer reviews: (none)

Diff findings:
  - The retry logic is correct: exponential backoff with full jitter, bounded by max_delay.
  - Unit tests added for all retry scenarios including edge cases (max retries=0, delay overflow).
  - No security concerns found.
  - Code follows the project's AGENTS.md style conventions.
  - No API surface changes; internal implementation only.
  - No DB queries affected.
