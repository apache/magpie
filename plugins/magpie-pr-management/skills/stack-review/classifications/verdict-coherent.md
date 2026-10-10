<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Verdict — coherent

`stack-review verdict` chose it because no `blocking` and no `major` finding. Print its `line`: it already carries the coverage clause *(structure checked in full; code read N of M hand-written hunks, L of T lines)* whenever a layer was read by exemplar, so the verdict is never read as code-level clearance.

First sentence shape: *The chain is linear and current, every layer contains the one below, and no removed definition is used across a layer boundary.*
When the trunk is gated by another PR, its `trunk_sentence` opens the verdict's first sentence.
Per-layer gate rows (red CI, unresolved threads, drafts) and `[C sampled]` notes never move the verdict.
