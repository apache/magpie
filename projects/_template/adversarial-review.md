<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Adversarial review](#adversarial-review)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Template — `setup config` writes this to .apache-magpie-local/adversarial-review.md
     (personal) after running `adversarial-review detect`; `setup adopt` may
     promote a copy to .apache-magpie-overrides/ (project default). A
     personal file overrides the project's as a whole. -->

# Adversarial review

Which other models read a change before Magpie opens a PR for it, and when.
The tool and its behaviour are described in
[`tools/adversarial-review`](../../tools/adversarial-review/README.md).

```yaml
adversarial_review:
  # on-pr-create: every PR-creating skill runs the reviewers before the push.
  # on-demand:    only when asked (the per-harness command, or with-reviewers:).
  # off:          never — except the security family, which runs them
  #               whenever at least one reviewer is listed.
  mode: on-pr-create
  # Any of: codex, copilot, gemini, claude. The model running the current
  # harness is skipped automatically, so listing it is harmless.
  reviewers: []
  # Per reviewer. Below the 10-minute cap a harness puts on one shell call.
  timeout_minutes: 8
  # Optional per-backend model overrides, e.g.
  #   copilot: gpt-5
  models:
```
