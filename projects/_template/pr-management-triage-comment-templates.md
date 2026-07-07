<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — pr-management-triage comment templates](#todo-project-name--pr-management-triage-comment-templates)
  - [Project-specific URLs](#project-specific-urls)
  - [Quality-criteria marker string](#quality-criteria-marker-string)
  - [AI-attribution footer](#ai-attribution-footer)
  - [Template body overrides](#template-body-overrides)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — pr-management-triage comment templates

This file is the **per-project comment-body library** for the
[`pr-management-triage`](../../skills/pr-management-triage/SKILL.md) skill.
It supplies the project-specific values the framework needs to
render its default template bodies — project URLs, the
AI-attribution footer wording, and the project display name —
plus any template body the project intentionally overrides.

The framework's
[`comment-templates.md`](../../skills/pr-management-triage/comment-templates.md)
ships the default bodies for every triage template; the skill
reads this file for the URLs / wording and renders the
framework defaults with them. **Do not duplicate the framework
default bodies here** — it just creates a drift surface; if
your project's wording matches the default, leave the
[Template body overrides](#template-body-overrides) section
empty.

Copy this file into your own
`<project-config>/pr-management-triage-comment-templates.md`
and replace every `<placeholder>` with your project's value.

## Project-specific URLs

| Placeholder | Project value |
|---|---|
| `<quality_criteria_url>` | `<docs-base-url>/<pr-quality-criteria-doc>#<anchor>` |
| `<two_stage_triage_rationale_url>` | `<docs-base-url>/<two-stage-triage-doc>#<anchor>` |
| `<project_display_name>` | `<Project Name>` |
| `<merge_conflicts_rebase_url>` | `<docs-base-url>/<rebase-guide-doc>` |
| `<static_checks_url>` | `<docs-base-url>/<static-checks-doc>` |
| `<testing_url>` | `<docs-base-url>/<testing-doc>` |
| `<docs_building_url>` | `<docs-base-url>/<docs-building-doc>` |
| `<helm_tests_url>` | `<docs-base-url>/<helm-tests-doc>` |
| `<k8s_tests_url>` | `<docs-base-url>/<k8s-tests-doc>` |
| `<provider_testing_url>` | `<docs-base-url>/<provider-testing-doc>` |
| `<project_communication_channel>` | `<your-chat-platform-label>` |
| `<project_communication_url>` | `<your-chat-platform-url>` |

Drop rows for placeholders the framework templates don't use
on your project (e.g. `<helm_tests_url>` / `<k8s_tests_url>` /
`<provider_testing_url>` only apply if your CI-check map maps
to those categories).

## Quality-criteria marker string

The framework uses a literal string to detect already-triaged
PRs (searches the PR body and comments for it). **Do not
paraphrase**: the same exact string must appear verbatim in
every triage feedback body the skill writes, and the
`pr-management-stats` skill uses the same marker for
"is this PR triaged" detection.

Under the default
[`triage_feedback_channel: pr-body`](pr-management-config.md),
the violations feedback for `draft` / `comment` / `close` is
**folded into the PR description** (a `pr-triage-fold` managed
block) rather than posted as a comment — so the marker appears in
the PR body. The block still carries the
`Pull Request quality criteria` link text, so the same marker
detection works in both channels. See
[`comment-templates.md#body-fold-rendering`](../../skills/pr-management-triage/comment-templates.md#body-fold-rendering).

| Concept | Value |
|---|---|
| Triage-marker visible link text | `Pull Request quality criteria` |
| Body-fold block marker tokens (framework-fixed) | `pr-triage-fold` / `/pr-triage-fold` |

## AI-attribution footer

The verbatim block appended to every contributor-facing
comment. Customise the **wording** for the project but keep
the **structure** (italicised meta-block, link to two-stage-
triage rationale).

```markdown
---

_Note: This comment was drafted by an AI-assisted triage tool and may contain mistakes. Once you have addressed the points above, a <PROJECT> maintainer — a real person — will take the next look at your PR. We use this [two-stage triage process](<two_stage_triage_rationale_url>) so that our maintainers' limited time is spent where it matters most: the conversation with you._
```

`<PROJECT>` and `<two_stage_triage_rationale_url>` are
expanded from the [Project-specific URLs](#project-specific-urls)
table (`<project_display_name>` and
`<two_stage_triage_rationale_url>` respectively).

When a body is folded into the PR description instead of posted
as a comment (the default `pr-body` channel), the framework uses
the parallel `<ai_attribution_footer_body>` variant — same
`<PROJECT>` / `<two_stage_triage_rationale_url>` substitutions,
worded for a description edit. See
[`comment-templates.md#body-fold-rendering`](../../skills/pr-management-triage/comment-templates.md#body-fold-rendering).

## Template body overrides

Leave this section empty unless your project needs a body
that differs from the framework default for a specific
template. The framework's
[`comment-templates.md`](../../skills/pr-management-triage/comment-templates.md)
documents every template with its default body and the
placeholder-resolution contract — the skill picks the
default automatically.

If your project does need to override a body, add a `###
<template-name>` subsection here with the body verbatim
(keeping all framework-required marker strings — e.g. the
`Pull Request quality criteria` link text in any
contributor-facing triage comment, or the `ready for
maintainer review confirmation` marker in the
`request-author-confirmation` body). Document **why** the
override exists in a sentence above the body so the next
adopter — or your future self on a framework upgrade — can
decide whether the override is still needed.

For workflow-level variants (e.g. the `confirmation_handback_mode:
maintainer-sweep` variant of `request-author-confirmation`),
configure them via
[`<project-config>/pr-management-config.md`](pr-management-config.md)
instead of body-overriding here — the framework picks the
matching body automatically.
