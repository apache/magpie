<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Install method: `marketplace`.

No override files. Every configured skill's `requires_config:` entries
resolve and every anchor resolves. No security import skill is configured.

Installed skills (with their caller names): `shepherd`
(`pr-management-shepherd`), `audit-finding-fix` (`audit-finding-fix`),
`pr-triage` (`pr-management-triage`).
`declined.skills` in the personal layer's `reconciled.json` is empty.

Existing vetted-ops policy:
`.apache-magpie-overrides/tools/vetted-ops/config.toml`
The policy is valid TOML and has this `[callers]` section:

```toml
[callers]
"pr-management-shepherd" = ["git-stage", "git-commit"]
"pr-management-triage" = ["pr-list", "pr-view", "pr-comment", "pr-add-label"]
"project-release-notes" = ["pr-list"]
```

Tracker backend: `github`.

The framework's vetted-ops README provides this example (excerpt):

```toml
[callers]
"audit-finding-fix"     = ["git-fetch", "git-worktree-add", "git-stage", "git-commit",
                           "git-push-branch"]
"pr-management-shepherd" = ["git-fetch", "git-worktree-add", "git-worktree-sync",
                            "git-stage", "git-commit", "git-push-branch", "git-pr-create"]
"pr-management-triage"  = ["pr-list", "pr-view", "pr-comment"]
```

No policy changes have been confirmed during this run.
