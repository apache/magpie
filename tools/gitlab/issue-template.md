<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [GitLab Issue Template](#gitlab-issue-template)
  - [Markdown Guidelines](#markdown-guidelines)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# GitLab Issue Template

Schema for GitLab issues and merge request bodies.

## Markdown Guidelines

GitLab Flavored Markdown (GLFM) is used across all issue and MR descriptions:
- **Checkboxes**: Formatted as `- [ ]` and `- [x]`.
- **References**: Issues are referenced with `#ID` and MRs with `!ID`.
- **Labels**: Scoped labels often use `::` (e.g., `workflow::in-review`).

Ensure that the adapter correctly parses these specific constructs
when reading issue bodies.
