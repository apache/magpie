<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: PROJ-4488 — Nested list literal drops the last element
Reporter: a.sato (2022-03-19)
Status: Open

Recent comments (newest last):

  [2022-03-20] a.sato (CONTRIBUTOR):
    Minimal repro attached.

  [2023-02-11] lgarza (MEMBER):
    See PROJ-1207; same root cause (the parser lookahead off-by-one),
    which was resolved in 2.9. This one should be closed as a duplicate.
