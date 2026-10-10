<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Verdict — mergeable bottom-up; merge layers a–b together

`stack-review verdict` chose it because every `major` is an ordering finding naming a merge unit. Print its `line`: it already carries the coverage clause *(structure checked in full; code read N of M hand-written hunks, L of T lines)* whenever a layer was read by exemplar, so the verdict is never read as code-level clearance.

First sentence shape: *Layer <k> uses <construct> above the floor its head declares; layers <a>–<b> have to merge as one unit (or releases held in between).*
When the trunk is gated by another PR, its `trunk_sentence` opens the verdict's first sentence.
Per-layer gate rows (red CI, unresolved threads, drafts) and `[C sampled]` notes never move the verdict.
