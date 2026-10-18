<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Verdict — not mergeable as a stack

`stack-review verdict` chose it because at least one `blocking`. Print its `line`: it already carries the coverage clause *(structure checked in full; code read N of M hand-written hunks, L of T lines)* whenever a layer was read by exemplar, so the verdict is never read as code-level clearance.

First sentence shape: *Layer <k> does not contain layer <k-1> — cascade rebase needed* or *layer <k> removes `<name>` its own tree still uses.*
When the trunk is gated by another PR, its `trunk_sentence` opens the verdict's first sentence.
Per-layer gate rows (red CI, unresolved threads, drafts) and `[C sampled]` notes never move the verdict.
