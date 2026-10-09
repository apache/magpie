<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `comment` — deliver the violations without a state change

1. **Ready label, when `details.strip_ready_label` is set** — remove it first (a 422 is benign):

   ```bash
   gh pr edit <N> --repo <upstream> --remove-label "ready for maintainer review"
   ```

2. **Deliver the note** — [`deliver-note.md`](deliver-note.md), action `comment`.

When `details.merit_discussion` is set the label stays, and the preview must say so, quoting the maintainer-opened unresolved thread(s) that kept it — when the action was degraded from `draft` (`details.degraded_from`), say that too.
The security-language note ([row 7b](../classifications/security-language-signal.md)) uses this file as well, with its own body.
