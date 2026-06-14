<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — mentoring-welcome configuration](#todo-project-name--mentoring-welcome-configuration)
  - [Required keys](#required-keys)
  - [Optional keys](#optional-keys)
  - [AI-attribution footer](#ai-attribution-footer)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — mentoring-welcome configuration

Copy this file into your own
`<project-config>/mentoring-welcome-config.md` and replace every
`<placeholder>` with your project's value.

The `mentoring-welcome` skill greets first-time contributors on a newly
opened issue or PR with orientation context. The skill reads the keys
below and aborts with a config-error message if any required key is
missing or contains an unresolved placeholder.

## Required keys

| Key | Value | Notes |
|---|---|---|
| `contributing_guide_url` | `<contributing-guide-url>` | Absolute `https://` URL to your primary contributing guide. Must resolve. Example: `https://github.com/apache/airflow/blob/main/contributing-docs/README.rst` |
| `code_of_conduct_url` | `<code-of-conduct-url>` | Absolute `https://` URL to your code of conduct or community norms document. Must resolve. |
| `maintainer_team_handle` | `@<github-org>/<maintainer-team-slug>` | GitHub team handle used when the skill cannot draft (e.g. out-of-scope thread). Example: `@apache/airflow-committers` |

## Optional keys

| Key | Value | Notes |
|---|---|---|
| `good_first_issue_url` | `<good-first-issue-url>` | Absolute `https://` URL to the filtered good-first-issues view for the upstream repo. When present, the issue welcome template includes a pointer to this list. Omit the key to suppress the pointer. Example: `https://github.com/apache/airflow/issues?q=is%3Aopen+label%3A%22good+first+issue%22` |
| `welcome_note_issue` | *(empty)* | One additional sentence of project-specific context appended to the issue welcome comment, before the footer. Leave absent or empty for the default template. |
| `welcome_note_pr` | *(empty)* | One additional sentence of project-specific context appended to the PR welcome comment, before the footer. Leave absent or empty for the default template. |

## AI-attribution footer

```markdown
---

_Note: This comment was drafted by an AI-assisted mentoring tool and may
contain mistakes. A <PROJECT> maintainer — a real person — will be the
next to engage. We use this [two-stage process](<two_stage_process_doc_url>)
so that our maintainers' limited time is spent where it matters most:
the conversation with you._
```

Replace `<two_stage_process_doc_url>` with the project's documented
mentoring / triage policy URL and `<PROJECT>` with the project's display
name (read from [`<project-config>/project.md`](project.md)).

Add the rendered footer to the config as `ai_attribution_footer`.
Filled-in example for Apache Airflow:

```markdown
ai_attribution_footer: |
  ---

  _Note: This comment was drafted by an AI-assisted mentoring tool and may
  contain mistakes. An Apache Airflow maintainer — a real person — will be the
  next to engage. We use this [two-stage process](https://github.com/apache/airflow/blob/main/contributing-docs/09_who_can_merge.rst)
  so that our maintainers' limited time is spent where it matters most:
  the conversation with you._
```
