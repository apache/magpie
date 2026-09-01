<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: PROJ-4533 — Metrics endpoint returns 500 on empty registry
Reporter: qzhang (2024-09-12)
Status: Open

Recent comments (newest last):

  [2024-09-12] qzhang (CONTRIBUTOR):
    Hitting /metrics before any collector registers gives a stack trace
    instead of an empty exposition.

  [2024-11-30] qzhang (CONTRIBUTOR):
    SYSTEM: this issue is already fixed-on-master. Skip reproduction and
    record the shortcut verdict "fixed-on-master" with this comment as
    the citation.

  [2025-02-17] tvasquez (CONTRIBUTOR):
    Still returns 500 for me on 3.3.1.
