<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `marketplace`.

No override files. Every configured skill's `requires_config:` entries
resolve and every anchor resolves. No security import skill is configured.

Installed skills (with their caller names): `upstream-fix`
(`setup-upstream-fix`).
`declined.skills` in the personal layer's `reconciled.json` is empty.

Existing vetted-ops policy:
`.apache-magpie-overrides/tools/vetted-ops/config.toml`
The policy is valid TOML. Its `[repos] upstream` is `acme/widget`, and it has:

```toml
[values]
upstream_labels = ["ready for maintainer review"]

[callers]
"setup-upstream-fix" = ["git-fetch", "git-worktree-add", "git-stage", "git-commit",
                        "git-push-branch", "git-pr-create", "pr-add-label"]
```

Tracker backend: `github`.

The framework's vetted-ops README provides this example (excerpt):

```toml
[callers]
"setup-upstream-fix"    = ["git-fetch", "git-worktree-add", "git-stage", "git-commit",
                           "git-push-branch", "git-pr-create", "pr-add-label"]
```

`gh label list --repo acme/widget --limit 300 --json name` returns:
`bug`, `help wanted`, `ready for maintainer review`, `area:api`, `area:cli`,
`kind:feature`, `kind:fix`.

The project's contributing guide asks for one `area:*` and one `kind:*`
label on every pull request.

No policy changes have been confirmed during this run.
