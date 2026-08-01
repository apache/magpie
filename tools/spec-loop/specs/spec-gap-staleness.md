<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Spec-gap staleness verification
status: proposed
kind: feature
mode: infra
source: >
  Observed drift: nine "Known gaps" bullets across eight specs described
  capabilities that had already shipped, and the plan beat queued work
  from them. Implemented by tools/spec-loop/PROMPT_plan.md,
  tools/spec-loop/PROMPT_update.md, and new checks in
  tools/spec-validator.
acceptance:
  - The plan beat cannot queue a work item from a Known-gap bullet
    without citing evidence that the gap is still open.
  - Admissible evidence is a call site, current file content, or a
    counted value; the presence of a name is not admissible.
  - A Known-gap bullet may carry a machine-evaluable close condition,
    and the validator fails when that condition is already met.
  - The validator fails when two specs claim different counts for the
    same skill family.
  - Every check is deterministic given a working tree and requires no
    model call.
---

# Spec-gap staleness verification

## What it does

Stops a `## Known gaps` bullet outliving the gap it describes.

A spec's Known-gaps section is not documentation. The spec-loop plan
beat reads it to choose the next work item, so a bullet describing
already-shipped code sends the loop at finished work, and a bullet that
was accurate a month ago is indistinguishable from one accurate today.
Nothing in the toolchain can currently tell the two apart:
`spec-validator` checks frontmatter keys, section presence, SPDX
headers, and the existence of paths named in Validation blocks, but has
no view on whether a gap statement is still true.

This spec adds three mechanisms. An evidence rule on the plan and
update beats refuses to queue work from an unverified gap. An optional
close-condition predicate on a gap bullet makes staleness decidable for
the bullets that have a crisp end state. A cross-spec count check
catches the narrow case of two specs disagreeing about a countable
fact.

## Where it lives

- `tools/spec-loop/PROMPT_plan.md`: the evidence rule. A work item
  derived from a Known-gap bullet must carry a verification line.
- `tools/spec-loop/PROMPT_update.md`: the same rule applied when the
  update beat rewrites a Known-gaps section, so a bullet is retained
  only if it is re-verified.
- `tools/spec-validator/`: `validate_gap_predicates` (HARD on a
  satisfied predicate, SOFT on an unannotated bullet) and
  `validate_cross_spec_counts` (HARD).
- `tools/spec-inventory/`: reused, not changed. `section_bullets`
  already extracts `Known gaps` bullets per spec.
- `tools/spec-loop/.last-sync`: unchanged. It scopes the update beat's
  diff and is not a staleness signal.

## Behaviour & contract

### The evidence rule (plan and update beats)

Before a Known-gap bullet becomes a work item, the beat records one of
exactly three kinds of evidence that the gap is still open:

| Evidence | Shape | Example |
|---|---|---|
| Call site | `file:line` where behaviour is or is not wired | `no call to validate_x in run_validation` |
| File content | current text or absence at a named path | `audit-record-schema.md does not exist` |
| Counted value | a number derived from the tree | `6 skills carry family:repo-health` |

The presence of a name is explicitly **not** admissible. A function
defined but never called, a hook named in a config comment but not
wired, and a grep hit inside a docstring each satisfy a name match
while the described gap remains open or closed independently of it.
Where the distinction is load-bearing, the evidence names the call
site, not the definition.

A bullet the beat cannot verify is neither queued nor deleted. It is
carried forward marked unverified, so the next beat sees that the check
was attempted and failed rather than silently re-deriving work from it.

### Close-condition predicates

A Known-gap bullet may carry a trailing HTML comment stating the
condition under which the gap is closed:

```markdown
- **Branch-name confidentiality validation is missing.** Security-fix
  workflows already require neutral branch names, but no deterministic
  check scans skill/docs examples for CVE IDs or embargoed terms.
  <!-- gap-closes-when: symbol-called:tools/skill-and-tool-validator::validate_branch_name_confidentiality -->
```

An HTML comment is invisible in rendered markdown and rides alongside
its bullet the way SPDX markers already ride alongside file content.

The vocabulary is deliberately three predicates, which is what the nine
observed stale bullets require between them:

| Predicate | Closed when | Evaluation |
|---|---|---|
| `symbol-called:<path>::<name>` | `<name>` is both defined and called within `<path>` | parse call sites, not definitions |
| `path-exists:<path>` | `<path>` exists in the tree | filesystem check |
| `skill-count:<family>=<n>` | exactly `<n>` skills carry `family:<family>` | frontmatter count |

`symbol-called` deliberately requires a call site rather than a
definition, because a defined-but-unwired function is the exact shape
that makes a name match untrustworthy.

Severity is split so that adoption is incremental:

- A predicate that **evaluates to closed** is a HARD violation. The
  bullet is provably describing shipped work.
- A predicate that is **malformed or unresolvable** is a HARD
  violation. A broken check is worse than no check because it reads as
  a passing one.
- A bullet with **no predicate** is a SOFT advisory naming the bullet
  and suggesting either a predicate or the explicit narrative marker
  below. This is today's behaviour plus a nudge, so nothing breaks on
  the day this lands.

Not every gap has an end state a machine can see. A bullet whose gap is
inherently narrative declares that rather than being left silent:

```markdown
<!-- gap-closes-when: none (narrative) -->
```

This is the correct annotation for the eleven "experimental, no adopter
pilot has run" bullets in the current tree. They are status notes whose
truth depends on facts outside the repository, and they should never be
machine-checked. The vocabulary's inability to express them is a
feature: the bullets it cannot describe are the bullets it should not
judge.

### `validate_cross_spec_counts` (HARD)

Extract claims of the form "<count> skills" scoped to a named family
from any spec section, resolve the live count of skills whose
frontmatter carries that `family:`, and compare. Two specs asserting
different counts for one family is a violation regardless of which is
right, because at most one can be. The live count is compared
independently of that, so the case where every spec agrees and all of
them are stale is caught too — which is the more dangerous shape, since
agreement reads as confirmation. Narrow and exact: no prose
inference, no threshold, no false positives.

One caveat the implementation has to face. A count disagreement can mean
the prose is stale, or it can mean membership itself is contested: a
skill may carry `family:` in frontmatter while the prose deliberately
omits it because it is a different kind of thing. The check reports the
discrepancy and names the skills on each side; it does not assume the
frontmatter is right. Deciding membership is a human call, and a HARD
check that presumes an answer will be argued with rather than fixed.

## Out of scope

- Deciding whether an arbitrary prose bullet is true. That needs a
  model call, and a model call in a deterministic validator would break
  the reproducibility the other checks rely on.
- Editing spec text. Every check reports; a human or the update beat
  rewrites.
- **Git-recency staleness detection, refuted by measurement.** An
  earlier draft proposed a SOFT advisory comparing each spec's last
  commit against commits touching the paths in its `Where it lives`
  section. Measured against the eight specs known to carry stale
  bullets, the signal does not separate them: five scored at or below
  the median and two scored zero, while the highest-scoring spec
  (`good-first-issue-sweep.md`, 65 commits ahead) had entirely accurate
  gaps. Re-measuring per bullet with `git blame` failed the same way,
  with eleven specs tied at the history ceiling across both
  populations. The two populations move in opposite directions from
  what the metric assumes: a narrative gap stays true while its area
  churns, and a capability gap goes stale the moment an unrelated PR
  ships the capability without touching the spec. Recorded here so the
  approach is not re-proposed.
- Removing or reworking `tools/spec-loop/.last-sync`.

## Acceptance criteria

1. `PROMPT_plan.md` states the three admissible evidence kinds and that
   a name match is not one of them.
2. `PROMPT_update.md` requires a retained Known-gap bullet to be
   re-verified against the same rule.
3. `validate_gap_predicates` parses all three predicates plus the
   narrative marker, and is registered in the validator orchestrator.
4. A satisfied predicate and a malformed predicate each produce a HARD
   violation; an unannotated bullet produces a SOFT advisory only.
5. `validate_cross_spec_counts` flags a family whose claimed count in
   one spec differs from its claimed count in another.
6. Every check has unit tests covering the firing case, the clean case,
   and the skip case.
7. Running the validator on the live tree reproduces the known
   repo-health family discrepancy, which is three-way rather than
   two-way: `triage-mode.md` claims five skills,
   `repo-health-family.md` claims six, and seven carry
   `family: repo-health` in frontmatter. The seventh,
   `audit-finding-fix`, appears in neither prose list — plausibly
   because it fixes findings rather than producing them. The check
   must report all three numbers and name the disputed skill, not
   pick a winner.

## Validation

```bash
uv run --directory tools/spec-validator --group dev pytest
uv run --directory tools/spec-validator --group dev spec-validate
test -f tools/spec-loop/PROMPT_plan.md
test -f tools/spec-loop/PROMPT_update.md
```

## Known gaps

- **Not yet built.** Both prompt edits and both validator checks are
  proposed here; nothing has shipped.
  <!-- gap-closes-when: symbol-called:tools/spec-validator::validate_gap_predicates -->
- **The existing bullets need a one-off backfill.** Nine bullets across
  eight specs describe shipped capabilities, and eleven more are
  narrative status notes needing the `none (narrative)` marker.
  Annotating them is manual and independent of building the checks.
- **Landing order matters, and only the SOFT rule is safe to land
  first.** The unannotated-bullet advisory is SOFT, so it changes
  nothing on the day it ships. `validate_cross_spec_counts` is HARD and
  acceptance criterion 7 requires it to fire on a violation that exists
  in the tree today, so landing it before the repo-health counts are
  reconciled turns main red for everyone. Reconcile first, then land
  the HARD check.
- **A predicate can drift from its bullet.** Nothing binds the comment
  to the prose above it, so an edit that rewrites a bullet without
  updating its predicate leaves a check that passes while describing
  something else. Mitigated by the HARD malformed-predicate rule but
  not eliminated.
- **The vocabulary will need extending.** Three predicates cover the
  nine observed cases. A fourth shape will appear; each addition is a
  parser branch plus tests, and the bar for adding one should be a real
  bullet that needs it rather than an anticipated one.
