---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
skill: <skill-name>
date: YYYY-MM-DD
target_repo: <owner>/<repo>
profile: asf
reporter: <github-handle>
---

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Pilot report template](#pilot-report-template)
  - [Instructions](#instructions)
- [Pilot report: \<skill-name\> on \<owner/repo\>](#pilot-report-skill-name-on-ownerrepo)
  - [Skill or family](#skill-or-family)
  - [Target repo and profile](#target-repo-and-profile)
  - [Blocked preflights](#blocked-preflights)
  - [False positives](#false-positives)
  - [Confirmation points](#confirmation-points)
  - [Privacy and adapter notes](#privacy-and-adapter-notes)
  - [Proposed spec changes](#proposed-spec-changes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Pilot report template

Copy this file into your project notes, fill in each section, and share
it back with the framework maintainers (or keep it local).  Pilot
reports are the primary feedback channel for moving a skill family from
`experimental` to `stable`.

Pilot reports alone do not satisfy the contributor-sentiment gate. After
at least two release cycles of Magpie use, also run the
[`contributor-sentiment`](../skills/contributor-sentiment/SKILL.md) skill
to generate a machine-readable gate report covering thread tone,
time-to-first-reply, first-PR retention, and reviewer load. See
[`docs/contributor-sentiment.md`](contributor-sentiment.md) for the full
methodology and promotion rule.

To validate a filled-in report file, run:

```bash
uv run --project tools/pilot-report-validator pilot-report-validate <your-report.md>
```

---

## Instructions

1. Copy this file to a convenient location (e.g.
   `<project-notes>/pilot-report-<skill>-<date>.md`).
2. Fill in the frontmatter block at the very top of the file (keep it
   at the top, above the table of contents, so the validator detects it)
   and each section below.
3. Replace placeholder text in *italics* with your findings.
4. For any section where nothing applies, write: **None observed.**
5. For proposed spec changes, reference the spec file path and section
   where possible.

---

# Pilot report: \<skill-name\> on \<owner/repo\>

## Skill or family

*Which skill or skill family was piloted — e.g. `pairing-self-review`,
`mentoring`, `repo-health`. If you ran a full family sweep, list each
skill you exercised.*

## Target repo and profile

*The repository tested against (`owner/repo`) and the project profile
used (`asf`, `non-asf`, or `custom`). If your project-config directory
is public, link to it here.*

## Blocked preflights

*List any preflights the skill ran that blocked, were skipped, or
produced a confusing result. Include the preflight name or description
and why it triggered.*

*If none: **None observed.***

## False positives

*Findings the skill surfaced that were incorrect, irrelevant, or
misleading. Include the finding summary and why it was a false positive.
Distinguish clearly between "wrong finding" and "right finding but
unhelpful wording".*

*If none: **None observed.***

## Confirmation points

*Steps where the skill prompted for maintainer confirmation before
proceeding. Note any that felt misplaced — too early, too late, or
absent when one was expected.*

*If no issues: **All confirmation points felt appropriate.***

## Privacy and adapter notes

*Any Privacy-LLM gate activations, adapter mismatches, credential
preflight issues, or unexpected external-content handling. Note which
adapter path was exercised (e.g. GitHub Issues, GitHub PR, Gmail,
PonyMail) and whether the data-not-instructions boundary held.*

*If none: **None observed.***

## Proposed spec changes

*Specific changes to propose to the skill spec or adopter-contract docs.
For each proposal, note the spec file path and section, the current
wording, and the suggested change.*

*If none: **No changes proposed at this time.***
