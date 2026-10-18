<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Intervention — Convention pointer

**Fires when:** A PR or issue missing a piece of repo convention the contributor could have found themselves (commit-message format, PR-title prefix, where tests go, required changelog entry).

Render it against the matching `convention_pointers` row (the `pointers` list in the `assess` output):

```bash
uv run --project <framework>/tools/pr-management pr-management mentor render --kind convention-pointer --author <author> --pointer "<trigger>" --out <scratch>/draft.md
```

The renderer refuses a row with no link or label, so a half-rendered comment never reaches the maintainer.
Its `tone` result must be `pass` before you show the draft; otherwise read the `docs` it lists and revise.
