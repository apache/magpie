<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Invocation: `pr-management-code-review ready`

The `magpie-adversarial-review` plugin is installed.
`.apache-magpie-local/adversarial-review.md`:

```yaml
adversarial_review:
  mode: on-demand
  reviewers: [codex, gemini]
```

`AGENTS.md` has a `## Review preferences` section naming `/codex:adversarial-review`.
