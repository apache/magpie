<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — CVE title normalisation](#todo-project-name--cve-title-normalisation)
  - [Strip cascade](#strip-cascade)
  - [Implementation recipe](#implementation-recipe)
  - [Sanity check](#sanity-check)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — CVE title normalisation

The CVE record's `title` field is scoped to the product by the CNA
container (e.g. `Apache <Project>`, `Apache <Project> <Component>
Provider`), so the title pasted into the CVE-tool allocation form
should be the **bare description** — no project prefix, no
redundant version suffix, no reporter-added tag like
`[ Security Report ]`.

The [`security-cve-allocate`](../../.claude/skills/security-cve-allocate/SKILL.md)
skill reads this file for the exact strip cascade to apply to the
tracker title before pasting it into the allocation form.

**If this project's titles are already normalised** (reporters
don't prepend `<Project>:` or add bracketed tags), you can leave
this file with a note to that effect and the skill will skip the
stripping step. Otherwise, list the regex cascade below.

## Strip cascade

TODO: one rule per bullet, applied in order. Typical patterns:

1. Leading bracketed `security` / `important` tag —
   `^[ \t]*(?:\[[^\]]*\b(?:Security|Important)\b[^\]]*\]|\([^)]*\b(?:Security|Important)\b[^)]*\))[ \t:|\-–—]*`
   Matches any square- or round-bracketed leading tag whose body
   contains the word *security* or *important* (case-insensitive) —
   e.g. `[Security Report]`, `(Security Issue)`, `[ Security
   Vulnerability ]`, `[IMPORTANT]`, `(Important — please read)`.
   Followed by an optional separator. Apply with `re.IGNORECASE`.
2. Leading plain tags — `^[ \t]*Security (Report|Issue|Vulnerability|Bug)[ \t:|\-–—]+`
3. Leading `<Project Name>` (optional version, optional separator) — TODO
4. Leading bare product name (optional version) — TODO
5. Re-apply 1 and 2 — after stripping a version prefix the title
   often reveals a nested `Security Issue |` tag.
6. Trailing `in <Project Name>` — TODO
7. Trailing bare version parens — TODO
8. Trailing GHSA ID paren — `[ \t]*\(GHSA-[\w-]+\)\.?[ \t]*$`
9. Trailing known external-tracker IDs (square or round brackets) —
   `[ \t]*(?:\[(?:ZDRES|HUNTR|GHSL)-[\w-]+\]|\((?:ZDRES|HUNTR|GHSL)-[\w-]+\))\.?[ \t]*$`
   Strips trailing IDs from known external trackers — `(ZDRES-223)`,
   `[HUNTR-456]`, `(GHSL-2024-001)` — in either bracket style. Extend
   the alternation per project when a new reporter brand surfaces
   (e.g. `SNYK-…`, `BDSA-…`, internal bug-bounty platforms).
10. Trailing *"split from #NNN"* paren — `[ \t]*\([^)]*split from #\d+[^)]*\)\.?[ \t]*$`
11. Trailing trivia — strip trailing whitespace, trailing `.`,
    collapse internal whitespace.
12. Capitalise — upper-case the first letter; leave the rest alone
    so acronyms stay intact.

## Implementation recipe

TODO: keep the transform inline in the skill, do not create a
separate Python project. A typical cascade looks like:

1. Strip a leading `[ Security Report ]` or similar harness prefix.
2. Strip a leading `<vendor>: <product>:` (e.g. the project's own
   "Apache Foo:" prefix that the CVE tool re-applies).
3. Strip a trailing version-parenthetical like `(<= 1.2.3)`.
4. Strip a leading `Re:` if the original report came in by email and
   was retitled with the reply prefix.

The result is the bare vulnerability description that goes into the
CVE record's `title` field. Document the cascade your project uses
in this file once you settle on it.

## Sanity check

Show the stripped title and the original title side by side in the
security-cve-allocate proposal so the user can spot any over-stripping
before pasting into the CVE tool. If the strip collapses the title
to fewer than 3 words, surface that as a warning and propose a
manual override — over-stripping is worse than leaving one
redundant word in.
