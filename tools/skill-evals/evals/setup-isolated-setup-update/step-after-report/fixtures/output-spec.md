<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "actions": ["git-pull" | "setup-upgrade" | "manifest-bump-pr" | "re-cp-scripts" | "merge-settings" | "investigate-regression"],
  "summary": "all-in-sync" | "drift-found"
}
```

`actions` — the concrete follow-up actions the skill names, in the order
the skill names them. Values:
- `"git-pull"` — the skill tells the user to run `git pull --ff-only`
  because the framework checkout is behind origin.
- `"setup-upgrade"` — the skill recommends running
  `/magpie-setup upgrade` to refresh the gitignored snapshot.
- `"manifest-bump-pr"` — the skill points at the manifest-bump PR
  process for a pinned-tool upgrade candidate past the cooldown.
- `"re-cp-scripts"` — the skill recommends re-copying one or more
  user-scope scripts from the framework checkout.
- `"merge-settings"` — the skill tells the user to merge new framework
  entries into their `.claude/settings.json` by hand.
- `"investigate-regression"` — a previously-blocked denial command now
  succeeds; the skill surfaces this as a regression and stops other
  actions until it is resolved.
`summary` is `"all-in-sync"` only when no drift was found and
verification still passes; otherwise `"drift-found"`.
If `"investigate-regression"` appears in `actions`, no other actions
should appear alongside it — the skill stops at the regression.
Do not include any text outside the JSON object.
