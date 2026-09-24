<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: `pr-management-code-review`

The `magpie-adversarial-review` plugin is **not** installed.
`.apache-magpie-local/adversarial-review.md`:

```yaml
adversarial_review:
  mode: on-pr-create
  reviewers: [codex]
```

`AGENTS.md` has a `## Review preferences` section naming `/codex:adversarial-review`.
