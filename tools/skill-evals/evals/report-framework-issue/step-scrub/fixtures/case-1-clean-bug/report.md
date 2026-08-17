<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Target: framework repo (apache/magpie)
Type: bug

What's broken: `list-skills` prints the `pr-management` family header
once per skill instead of once per family when two or more
pr-management skills sort adjacent.

Which layer: skills/list-skills/scripts/list_skills.py

How to reproduce: run the listing script in a checkout that has two
or more `pr-management-*` skills installed.

Expected vs actual: expected a single `pr-management` header above
the group; actual repeats the header before every skill in it.

Environment: Claude Code, macOS 14, framework pin method:local.
