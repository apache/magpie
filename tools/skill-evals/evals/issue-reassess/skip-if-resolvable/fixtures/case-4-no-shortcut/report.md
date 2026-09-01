<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: PROJ-4412 — Scheduler leaks a thread on config reload
Reporter: dnwosu (2024-02-27)
Status: Open

Recent comments (newest last):

  [2024-03-03] dnwosu (CONTRIBUTOR):
    Thread count grows by one on every SIGHUP; heap dump attached.

  [2024-05-19] tvasquez (CONTRIBUTOR):
    Any update on this? We see the same on 3.1.

  [2025-01-08] dnwosu (CONTRIBUTOR):
    Still reproducible on 3.3.0 with the attached script.
