<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [GitHub — issue-body field schema](#github--issue-body-field-schema)
  - [Where the schema is authoritative](#where-the-schema-is-authoritative)
  - [Field roles the skills use](#field-roles-the-skills-use)
  - [Body-field surgery](#body-field-surgery)
  - [Empty-field convention](#empty-field-convention)
  - [Issue-template to CVE 5.x mapping](#issue-template-to-cve-5x-mapping)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# GitHub — issue-body field schema

The skills treat every tracker's **issue body** as a structured
document with named fields, rather than free-form prose. Each field is
a markdown `### <field name>` heading followed by a value block; the
set of field names is the schema the skills read from and write to.

The field names themselves are project-specific (they come from the
project's GitHub issue-template YAML). Generic skill logic refers to
them by **role** — *"the CVE-tool-link field"*, *"the public-advisory
URL field"* — and the role → concrete-name mapping is declared in the
project manifest. For Airflow, see
[`../../<project-config>/project.md`](../../<project-config>/project.md#issue-template-fields).

## Where the schema is authoritative

Three surfaces need to stay in lock-step whenever a field is added,
renamed, or removed:

1. **The GitHub Form YAML** — `.github/ISSUE_TEMPLATE/issue_report.yml`
   in the tracker repo. This is what GitHub renders as the "New
   issue" form and is the machine-readable schema.
2. **The project manifest** — `<project-config>/project.md` declares
   the concrete field name each skill role maps to. Renaming the
   field in the YAML requires updating this mapping.
3. **The skills that write fresh issue bodies** — `security-issue-import`
   emits a heredoc body with the full field set; when the schema
   changes, the heredoc must change in lock-step.

No skill parses the YAML at runtime. The field list is hand-
maintained in the project manifest and in the `security-issue-import`
heredoc, and the three surfaces are kept aligned by convention.

## Field roles the skills use

The generic lifecycle refers to fields by these roles:

| Role | Read by | Written by | Purpose |
|---|---|---|---|
| `issue-description` | dedupe | import | The verbatim inbound report; private to the security team. |
| `public-summary` | CVE JSON generator | release manager (Step 13) | Sanitised one-paragraph public summary for the advisory. |
| `affected-versions` | CVE JSON generator, sync | sync proposes, user confirms | The `>= X, < Y` range that populates CVE 5.x `affected[]`. |
| `security-thread` | dedupe, sync (reporter-notification lookup) | import | Private pointer to the inbound mail thread — the Gmail `threadId`, any PonyMail archive URL, and the root `Message-ID` (archive-independent message handle; backtick-wrapped). **Never** exported to the public CVE record. |
| `public-advisory-url` | CVE JSON generator, sync (gates close) | sync (Step 14) | Public archive URL; tagged `vendor-advisory` in `references[]`. |
| `reporter-credit` | CVE JSON generator | import (placeholder), sync (after reporter confirms) | Credit line as the reporter wants to appear in the public advisory. |
| `pr-with-fix` | sync, CVE JSON generator | fix, sync | URL of the merged `<upstream>` PR. |
| `remediation-developer` | CVE JSON generator | sync (auto-populated from `pr-with-fix` author when set; manual edits preserved) | Person(s) who authored the fix; one credit per line. |
| `cwe` | CVE JSON generator | sync proposes, user confirms | CWE number for the CVE 5.x `problemTypes[]`. |
| `severity` | CVE JSON generator | sync proposes, user confirms | CVSS severity; never copy the reporter's self-assigned value. |
| `cve-tool-link` | sync, security-cve-allocate (blocker check) | security-cve-allocate | Canonical link to the CVE record in the project's CVE tool. |

The concrete field names each role maps to for the adopting project
live in the project manifest.

## Body-field surgery

Skills that update one field without touching the rest use the
following pattern:

1. **Read** the full body (`gh issue view <N> --json body --jq .body`).
2. **Split** on `\n### ` to get per-field sections.
3. **Replace** the target section's value (between its `### <name>\n\n`
   header and the next `### ` or end-of-body).
4. **Join** the sections back together.
5. **Write** the new body via
   `gh issue edit <N> --repo <tracker> --body-file <tmpfile>`.

Never construct the body by string concatenation in a shell command —
literal backticks, `$(…)`, and newlines in the body are silently
corrupted by shell quoting. Always materialise the edited body to a
temp file first.

## Empty-field convention

GitHub's issue-form renderer writes the literal string `_No response_`
into every unfilled body field. The skills honour this convention:

- On **read**, treat `_No response_` as "field unset".
- On **write**, preserve `_No response_` in fields the triager has
  not yet filled (do not collapse them to empty strings or delete
  the heading).
- The CVE JSON generator treats `_No response_` as absence and simply
  omits the corresponding CVE-record element.

## Issue-template to CVE 5.x mapping

The `generate-cve-json` tool maps body-field roles to CVE 5.x record
elements as follows (generic — applies to any project using this
schema):

| Body field role | CVE 5.x element |
|---|---|
| `public-summary` | `descriptions[].value` |
| `affected-versions` | `affected[].versions[].version` / `.lessThan` |
| `cwe` | `problemTypes[].descriptions[].cweId` |
| `severity` | `metrics[].other.content` (textual severity) |
| `public-advisory-url` | `references[]` with `tags: ["vendor-advisory"]` |
| `pr-with-fix` | `references[]` with `tags: ["patch"]` |
| `reporter-credit` | `credits[]` with `type: "finder"` |
| `remediation-developer` | `credits[]` with `type: "remediation developer"` |
| `security-thread` | **not exported** — private-only |
| `cve-tool-link` | **not exported** — points at the tool itself, not at a public URL |

Full implementation lives in the `generate-cve-json` skill / Python
tool (to be relocated under `tools/cve-tool-vulnogram/` in PR 4 of this
refactor series).
