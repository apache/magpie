<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Slop — note only

Fewer signals than the early-exit threshold, but at least one hard signal or two soft ones: print one line right after the scan and continue the review without interruption — do not modify the already-displayed headline:

> `⚠ [suspicious] — <comma-separated fired signal IDs>`

## Why the threshold is conservative

The threshold is deliberately conservative. A PR that looks suspicious
but doesn't cross the 2-hard-signal or 1-hard-3-soft threshold proceeds
with the normal review. The separate `[suspicious]` line emitted after
the scan is the only signal (no interruption, no menu).

When the maintainer says `[R]eview anyway` after an early exit, that
choice is noted and the full review runs normally. The slop detection
does not influence the findings or disposition of the subsequent
review.

Do not raise slop signals as findings inside the normal review. If the
maintainer chose `[R]eview anyway`, they made a deliberate choice. The
normal review covers the code; the slop detection covered the
structural envelope.
