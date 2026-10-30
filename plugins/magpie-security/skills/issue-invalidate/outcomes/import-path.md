<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — Step 2 import paths

Read from [`SKILL.md` Step 2](../SKILL.md#step-2--detect-import-path); `<sm> import-path` applies it.

| Body field shape | Import path | Email-draft step |
|---|---|---|
| Real `<mail-archive-url>` URL or any URL | `security@`-imported (public-archive case) | Draft on the original Gmail thread; locate via the rollup-comment `threadId` reference. |
| `No public archive URL — tracked privately on Gmail thread <threadId>` (sentinel from [`security-issue-import`](../../issue-import/SKILL.md) Step 7) | `security@`-imported (Gmail-only case) | Draft on the named `<threadId>`. |
| **Multiple lines** — primary reporter thread plus one or more forwarder/relay threads (huntr.com, GHSA, HackerOne, ASF-security relay) | `security@`-imported, with a relay second thread | Draft on the **primary reporter thread** per [`tools/gmail/threading.md` — Selecting the inbound thread when multiple are recorded](../../../../../tools/gmail/threading.md#selecting-the-inbound-thread-when-multiple-are-recorded). The relay thread is for back-channel relay only; the invalid-close reply goes to the primary. |
| `N/A — opened from public PR <upstream>#<N>; no security@ thread` (sentinel from [`security-issue-import-from-pr`](../../issue-import-from-pr/SKILL.md)) | PR-imported | **Skip** the email-draft step. No reporter exists to notify. |
| `N/A — imported from markdown file …` or `N/A — imported from scan …` (sentinels from [`security-issue-import-from-md`](../../issue-import-from-md/SKILL.md) and [`security-issue-import-from-scan`](../../issue-import-from-scan/SKILL.md)) | Internal audit | **Skip** the email-draft step. No reporter exists to notify. |
| Empty / `_No response_` / unrecognised | Indeterminate | Surface to the user; ask whether the tracker has a Gmail thread the skill should reply on, or whether the close is silent (no email). |
