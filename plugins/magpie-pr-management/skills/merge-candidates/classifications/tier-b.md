<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tier B — low-risk code

At least one file matches only `tier_b_allow_globs` (test-only files, example code) and every other file matches Tier A.
No production code path changes, but a test can still assert the wrong thing: read the assertions, not just the shape.
A mixed docs + tests PR is Tier B; its `reason` says so ("mixed Tier A + Tier B → Tier B overall").
`tier:A` on the command line leaves Tier B out.
