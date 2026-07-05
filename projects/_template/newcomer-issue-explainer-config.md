<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [newcomer-issue-explainer config](#newcomer-issue-explainer-config)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# newcomer-issue-explainer config

Required by [`magpie-newcomer-issue-explainer`](../../skills/newcomer-issue-explainer/SKILL.md).
Copy this file into your `<project-config>/` directory and fill in the
values for your project before invoking the skill.

```yaml
# Where contributors should ask follow-up questions.
# Must be an absolute URL or a clear route such as "reply on this issue".
# Placeholder values (containing angle brackets) are rejected at runtime.
questions_channel: <discussion-channel-url-or-description>

# Keywords in issue titles or bodies that trigger a security-sensitive decline.
# The defaults below cover common patterns; extend for your project.
out_of_scope_topics:
  - security
  - CVE
  - vulnerability
  - embargoed
  - authentication
  - authorization
  - privilege escalation

# Literal markdown appended verbatim to every drafted explanation.
# Must disclose AI authorship. Replace with your project's preferred wording.
ai_attribution_footer: |
  ---
  *This explanation was drafted by an AI assistant and reviewed by a
  maintainer before posting. Please ask if anything is unclear.*
```
