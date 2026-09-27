<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Magpie setup overrides](#magpie-setup-overrides)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Magpie setup overrides

Adopter overrides for the `magpie-setup` family's own behaviour — the checks
it runs, not the skills it installs. Copy this file into your
`<project-config>/` directory.

**Every key is optional, and the documented default applies when a key or the
whole file is absent.** This file exists so a project can disagree with a
default without editing a skill.

---

```yaml
magpie_setup:

  # `setup verify` flags a git worktree as stale when both its file
  # modification time and its branch activity are older than this. Raise it on
  # a project where long-lived worktrees are normal; a stale worktree is only
  # ever reported, never removed.
  worktree_stale_days: 7
```
