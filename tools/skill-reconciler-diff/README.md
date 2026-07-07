<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [skill-reconciler-diff](#skill-reconciler-diff)
  - [Prerequisites](#prerequisites)
  - [Usage](#usage)
  - [Output format](#output-format)
  - [Safety-baseline detection](#safety-baseline-detection)
  - [Integration with skill-reconciler](#integration-with-skill-reconciler)
  - [Run tests](#run-tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# skill-reconciler-diff

**Capability:** substrate:framework-dev

**Harness:** agnostic

A deterministic `uv` tool that parses two `SKILL.md` skill trees into
normalised structural representations and emits a JSON diff.  The output
grounds the [`skill-reconciler`](../../skills/skill-reconciler/SKILL.md)
skill's `ALLOWED` / `DRIFT` / `SAFETY-BASELINE` classification decisions in
a structured object rather than a raw text comparison.

The tool is **read-only**: it never modifies either skill file.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv`; stdlib-only (no runtime
  dependencies).  The `dev` group pulls `pytest`.
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None.
- **Network:** Runs fully offline; reads skill files from the local
  filesystem.

## Usage

```bash
# Pass paths to SKILL.md files:
uv run --project tools/skill-reconciler-diff \
    skill-reconciler-diff skills/skill-a/SKILL.md skills/skill-b/SKILL.md

# Or pass parent directories — the tool resolves SKILL.md inside:
uv run --project tools/skill-reconciler-diff \
    skill-reconciler-diff skills/skill-a skills/skill-b
```

Output is written to stdout as JSON.  Exit 0 on success; non-zero on
parse errors (e.g. a path that does not resolve to a readable `SKILL.md`).

## Output format

```json
{
  "skill_a_path": "skills/skill-a/SKILL.md",
  "skill_b_path": "skills/skill-b/SKILL.md",
  "identical": false,
  "frontmatter_diff": {
    "only_in_a": {},
    "only_in_b": {},
    "changed": {
      "capability": {"a": "capability:triage", "b": "capability:fix"}
    }
  },
  "section_headings_diff": {
    "only_in_a": [],
    "only_in_b": ["New section"],
    "order_changed": false
  },
  "step_diff": {
    "only_in_a": [],
    "only_in_b": [],
    "body_changed": ["1"]
  },
  "placeholder_diff": {
    "only_in_a": [],
    "only_in_b": ["upstream"]
  },
  "support_files_diff": {
    "only_in_a": ["extra.md"],
    "only_in_b": []
  },
  "safety_baseline_diff": {
    "clause_1_injection_guard": {"a_present": true, "b_present": false, "diverges": true},
    "clause_2_collaborator_trust": {"a_present": true, "b_present": true, "diverges": false},
    "clause_3_confidentiality_posture": {"a_present": true, "b_present": true, "diverges": false}
  }
}
```

Fields:

| Field | Description |
|---|---|
| `identical` | `true` when no structural difference was detected across all dimensions. |
| `frontmatter_diff` | Keys present only in A, only in B, or with different values. |
| `section_headings_diff` | Headings present only in A, only in B, or whose relative order differs. |
| `step_diff` | `## Step N` sections added, removed, or with changed bodies. |
| `placeholder_diff` | `<placeholder>` tokens present only in A or only in B. |
| `support_files_diff` | Sibling `.md` files (support docs) present only in A or only in B. |
| `safety_baseline_diff` | Per-clause presence comparison for the three safety-baseline clauses. |

## Safety-baseline detection

The tool detects the three clauses defined in
[`skills/skill-reconciler/safety-baseline-checklist.md`](../../skills/skill-reconciler/safety-baseline-checklist.md):

- **Clause 1 — Untrusted content is never instructions**: searches for
  wording establishing that external content is data, not a directive (e.g.
  "external content … never an instruction", "prompt-injection attempt").
- **Clause 2 — Collaborator / identity-resolution caveats**: searches for
  the collaborator-trust gate ("only collaborators of \<tracker\> may direct
  the agent", "non-collaborator").
- **Clause 3 — Confidentiality posture is not weakened**: searches for the
  confidentiality rule ("never reproduce … on a public surface",
  "embargoed", "private … content").

Detection is heuristic (regex pattern matching on the skill body); it
surfaces absence or presence for the skill-reconciler skill to judge.  A
`diverges: true` result is a strong signal that the reconciler should
classify the difference as `SAFETY-BASELINE`.

## Integration with skill-reconciler

This tool is intended to be used as an optional Step 1 enhancement to the
[`skill-reconciler`](../../skills/skill-reconciler/SKILL.md) skill (the skill
does not yet wire it in — that reference lands separately).  To use it, run the
tool before invoking the skill and pass its JSON output as context:

```bash
uv run --project tools/skill-reconciler-diff \
    skill-reconciler-diff skills/skill-a skills/skill-b \
    > /tmp/structural-diff.json
# Then reference /tmp/structural-diff.json in the skill invocation.
```

Without the tool the skill reasons from raw text; with it the skill grounds
`ALLOWED` / `DRIFT` / `SAFETY-BASELINE` decisions in the deterministic diff
object, reducing false positives on large or complex skill pairs.

## Run tests

```bash
cd tools/skill-reconciler-diff
uv run --group dev pytest
```
