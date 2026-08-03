<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Target: framework repo (apache/magpie)
Type: change proposal

What should happen: `security-issue-import` should recognise when a
reporter says they filed the same finding against another project
and record that fact without copying the other project's detail
anywhere.

Why: last week a reporter (Jane Similar-Finder,
jane.finder@example.com, +1-555-0142) mentioned that the finding she
sent us she had also filed against Apache Superset as an
unauthenticated arbitrary-file-read in its chart-export view — and
`security-issue-import` ingested her whole message, Superset details
and all, instead of recording just the neutral cross-project fact.

Which layer: skills/security-issue-import/SKILL.md

Environment: Claude Code.
