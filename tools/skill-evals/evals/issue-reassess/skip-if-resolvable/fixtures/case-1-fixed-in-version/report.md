<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue: PROJ-4470 — CLI --dry-run still writes the state file
Reporter: mkowalski (2023-11-02)
Status: Open

Recent comments (newest last):

  [2024-01-14] mkowalski (CONTRIBUTOR):
    Still happening on 3.0.2, any chance someone can look at this?

  [2024-06-30] rhalvorsen (MEMBER):
    This was fixed in 3.2.1 by #4521 (the dry-run guard now wraps the
    state writer). Issue was left open by mistake — closing can happen
    whenever someone with permissions gets to it.

  [2024-07-01] mkowalski (CONTRIBUTOR):
    Confirmed on 3.2.1, thanks!
