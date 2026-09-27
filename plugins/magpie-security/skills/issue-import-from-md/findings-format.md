<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-md — findings-file format and parsing

## Step 1 — Parse the file into findings

The expected per-finding shape:

```markdown
# <Title — one short imperative phrase>

## Details
<Multi-paragraph technical description. May reference file paths,
line numbers, function names. Often the longest section.>

## Location
[<file/line label>](<URL into the public source>)

## Impact
<One sentence. The threat actor's gain: arbitrary code execution,
data exfiltration, privilege escalation, etc.>

## Reproduction steps
1. <numbered list>
2. ...

## Recommended fix
<Suggested remediation. Free-form prose.>

---
**Severity:** HIGH|MEDIUM|LOW|UNKNOWN
**Status:** Open
**Category:** <free-text — Insecure Deserialization / RCE, SSRF, Broken Access Control, etc.>
**Repository:** <owner>/<repo>
**Branch:** <ref>
**Date created:** YYYY-MM-DD
```

Findings are separated by `---` on its own line (with blank lines
around it). The metadata block at the end of each finding is
itself preceded by `---`.

Parsing recipe:

1. Read the whole file.
2. Split on the regex `(?m)^---\s*$` to get raw blocks.
3. Drop blocks that are pure whitespace.
4. Group adjacent blocks: a "finding" is the block ending in the
   `**Severity:**` metadata line, plus the immediately preceding
   block (which carries `# Title` through `## Recommended fix`).
   Equivalently: walk blocks pairwise, treating
   `(narrative-block, metadata-block)` as one finding.
5. For each finding, extract the per-section payload:
   - `# Title` → the line after `# ` until newline.
   - Each `## <Section>` → everything until the next `## ` heading
     or the end of the narrative block.
   - Metadata: per-line `**Field:** value` extraction.
6. Validate per finding:
   - `# Title` is non-empty.
   - `**Severity:**` is one of `HIGH`, `MEDIUM`, `LOW`, `UNKNOWN`
     (case-insensitive); anything else → record as `UNKNOWN` and
     surface a one-line warning.
   - `**Repository:**` matches `<owner>/<repo>` shape; if absent,
     fall back to `<upstream>` (from `<project-config>/project.md`)
     and warn.
   - `## Details`, `## Impact`, and `## Reproduction steps` are
     present and non-empty. If any are missing, surface a warning
     but do not skip the finding (the importer can fill in
     `_No response_` for the corresponding tracker body field).

Record into the observed-state bag a list of `findings`, each with:

- `index` (1-based, matches the proposal table number).
- `title` (raw).
- `details`, `location_url`, `location_label`, `impact`,
  `repro_steps`, `recommended_fix` (string payloads).
- `severity`, `status`, `category`, `repository`, `branch`,
  `date_created` (metadata).

---
