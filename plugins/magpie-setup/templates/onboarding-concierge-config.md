<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — onboarding-concierge configuration](#todo-project-name--onboarding-concierge-configuration)
  - [Out-of-scope topics](#out-of-scope-topics)
  - [AI-attribution footer](#ai-attribution-footer)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — onboarding-concierge configuration

Copy this file into your own `<project-config>/onboarding-concierge-config.md`
and replace every `<placeholder>` with your project's value.

| Key | Value | Notes |
|---|---|---|
| `contributing_guide_url` | `<contributing-guide-url>` | Absolute `https://` URL of the project's primary contributing guide. Linked in every answer. |
| `maintainer_team_handle` | `@<github-org>/<maintainer-team-slug>` | GitHub team the skill `@`-mentions on hand-off. Example: `@apache/airflow-committers`. |
| `ai_attribution_footer` | *(see below)* | Literal markdown appended to every drafted answer. |

## Out-of-scope topics

Topics that always trigger hand-off regardless of how the question is phrased.
Remove rows that do not apply to your project; add rows for project-specific
surfaces that AI should not improvise on.

- `security` — vulnerability reports, CVE allocation, embargoed work
- `deprecation` — timing decisions for removing or changing APIs
- `license` — license compatibility, header policy
- `architecture` — design-taste questions about project structure or evolution

## AI-attribution footer

```markdown
---

_Note: This reply was drafted by an AI-assisted mentoring tool and may
contain mistakes. Once you have addressed the points above, a
<PROJECT> maintainer — a real person — will take the next look.
We use this [two-stage process](<two_stage_process_doc_url>) so that our
maintainers' limited time is spent where it matters most: the conversation
with you._
```

Replace `<two_stage_process_doc_url>` with your project's documented
mentoring/triage policy URL and `<PROJECT>` with the project's display name
(read from `<project-config>/project.md`).
