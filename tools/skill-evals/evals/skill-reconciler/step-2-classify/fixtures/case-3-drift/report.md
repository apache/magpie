<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Comparing skills/issue-reproducer/SKILL.md (version A)
         vs skills/issue-reproducer/SKILL.md (version B, from branch adopter-enhancements)

== Frontmatter ==
Identical between both copies.

== Section headings ==
Identical section sets in the same order.

== Step content ==
Step 2 — Pick candidate (skill-A ends with):
  "Emit the candidate issue numbers in priority order."

Step 2 — Pick candidate (skill-B adds a paragraph after the above):
  "When two candidates have the same priority score, prefer the older issue —
  its reporter has been waiting longer. Include the issue creation date in the
  priority table so the maintainer can verify the tiebreak."

Step 7 — Verify (skill-A): contains 3 verification bullets.
Step 7 — Verify (skill-B): contains 4 verification bullets — adds:
  "Confirm the reproducer does not write to any path outside a temporary
  directory. A reproducer that modifies project files or system state is not
  a minimal test case."

== Hard rules block ==
skill-A: 4 bullets.
skill-B: 5 bullets — adds:
  "Never run the reproducer with elevated privileges. If the issue description
  suggests root or sudo is required, surface that to the user rather than
  attempting the run."

== Safety-baseline mentions ==
Both copies carry identical injection-guard callout paragraphs.
Both copies carry the same collaborator-trust gate wording.
Both copies carry identical confidentiality-posture statements.
