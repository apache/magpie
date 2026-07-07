<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "in-sync" | "push-only" | "commit-then-push" | "pull-then-commit-then-push" | null,
  "pull_needed": true | false,
  "error": null | "not-a-git-repo" | "lock-held"
}
```

`action` is `null` when `error` is non-null.
`pull_needed` is `true` only for the `"pull-then-commit-then-push"` path.
`error` is `"not-a-git-repo"` when the directory is missing or is not a git repo;
`"lock-held"` when `.sync.lock` is held by another process.
Do not include any text outside the JSON object.
