<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #6504 — Add connection retry to SFTP provider
Author: dave-contributor (CONTRIBUTOR)
CI: SUCCESS — all required checks pass
Mergeable: MERGEABLE
Unresolved threads: 2
Existing maintainer reviews:
  - potiuk (MEMBER), REQUEST_CHANGES: "The retry logic uses a fixed sleep interval. Please
    use exponential backoff instead, and add a max_attempts parameter."

Diff findings:
  - The retry implementation looks correct and matches the project's pattern for other providers.
  - Unit tests are comprehensive.
  - No security concerns.
