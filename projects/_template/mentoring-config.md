<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — mentoring (Agentic Mentoring) configuration](#todo-project-name--mentoring-agentic-mentoring-configuration)
  - [Identifiers](#identifiers)
  - [Convention pointers](#convention-pointers)
  - [Out-of-scope topics](#out-of-scope-topics)
  - [AI-attribution footer](#ai-attribution-footer)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — mentoring (Agentic Mentoring) configuration

**This file is a placeholder ahead of the Agentic Mentoring skill landing.**
The skill does not exist yet (Agentic Mentoring is proposed per
[`docs/modes.md`](../../docs/modes.md#mentoring)).
The keys below match the
[Agentic Mentoring spec](../../docs/mentoring/spec.md#adopter-contract)
and are the values the future skill will read.

Copy this file into your own
`<project-config>/mentoring-config.md` and replace every
`<placeholder>` with your project's value.

## Identifiers

| Key | Value | Notes |
|---|---|---|
| `mentoring_invocation_command` | `/magpie-pr-management-mentor` | Slash command the mentoring sweep invokes. Leave as-is unless your project has renamed the skill. |
| `maintainer_team_handle` | `@<github-org>/<maintainer-team-slug>` | GitHub team the skill `@`-mentions when handing off. Example: `@apache/airflow-committers`. |
| `max_agent_turns` | `2` | Hard cap on automated reply turns before forced hand-off. Tune up only if your project has a verified-low false-positive rate on the trigger heuristics. |

## Convention pointers

Triggers that the future skill will detect, mapped to the docs
link the comment should reference instead of paraphrasing.
Replace the example links with the equivalent docs in your
project — keep the trigger names if they apply, drop the row
if a particular trigger isn't relevant to your project.

| Trigger | Link | One-line label |
|---|---|---|
| Missing version on bug report | `<version-discovery-doc-url>` | Short link text describing how to find a release version |
| Missing repro | `<contributor-quickstart-doc-url>` | Short link text for "how to file a reproducible report" |
| First-time contributor PR setup | `<pr-opening-doc-url>` | Short link text for "how to open a PR" |

## Out-of-scope topics

The skill always hands off to a human when the thread touches
topics where AI judgement is inappropriate. Adjust the list
for your project; the defaults below are typical of an Apache
project.

- Security-sensitive design (CVE-adjacent, embargoed work)
- Deprecation timing (which release will drop X)
- License questions (compatibility, header policy)
- Architectural taste on a project-specific subsystem (e.g.
  for a project with a plugin / extension model, decisions
  about how a specific plugin should be structured)

## AI-attribution footer

```markdown
---

_Note: This comment was drafted by an AI-assisted mentoring tool and may contain mistakes. Once you have addressed the points above, a <PROJECT> maintainer — a real person — will take the next look. We use this [two-stage process](<two_stage_process_doc_url>) so that our maintainers' limited time is spent where it matters most: the conversation with you._
```

Replace `<two_stage_process_doc_url>` with the project's
documented mentoring / triage policy and `<PROJECT>` with the
project's display name (read from
[`<project-config>/project.md`](project.md)).
