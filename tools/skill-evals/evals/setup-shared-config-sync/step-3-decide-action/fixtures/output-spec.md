<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "in-sync" | "push-only" | "commit-then-push" | "pull-then-commit-then-push" | "bootstrap" | null,
  "pull_needed": true | false,
  "error": null | "not-a-git-repo" | "lock-held"
}
```

`action` is `null` when `error` is non-null.
`pull_needed` is `true` only for the `"pull-then-commit-then-push"` path.
`action` is `"bootstrap"` when `~/.claude-config` is **entirely absent** — the
skill clones the default private remote if it exists, or creates it if not,
rather than stopping (`error` is `null` in this case).
`error` is `"not-a-git-repo"` only when the path **exists but is not a git repo**
(a stray directory the skill must not clobber); `"lock-held"` when `.sync.lock`
is held by another process.
Do not include any text outside the JSON object.
