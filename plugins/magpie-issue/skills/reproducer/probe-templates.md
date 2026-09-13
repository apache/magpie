<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Probe templates — cross-family probes

Companion to [`SKILL.md`](SKILL.md). Procedural detail for Step 9:
running a small probe across the family of types or operator
variants the reproducer's expression belongs to.

## When to probe

The probe pattern applies when the reproducer's central expression
exercises a behaviour that is **defined for multiple backing types
or via multiple operator variants** in the project's language /
runtime.

Examples (project-dependent — define families per project in the
adopter override file or here):

- **Type families.** A range/index expression in a language with
  `List`, `Object[]`, primitive arrays, and `String` as
  index-supporting backings. A path-navigation expression with
  multiple backing models (in-memory graph vs lazy DOM vs streamed
  source).
- **Operator-variant families.** Safe-navigation operators with
  multiple variants (`?.`, `??.`, `?[..]`). Spread operators with
  multiple variants. Comparison operators with multiple variants.

When the reproducer's central expression is a member of such a
family, probe the rest of the family. The cost is small (~50-line
script); the signal is consistently useful — a project-wide spec
gap, an additional bug in a sibling type, or confirmation that
the asymmetry spans the whole operator family.

## When NOT to probe

Skip when:

- The reproducer's expression isn't family-typed (a one-off
  function call with no type-variant cousins).
- The probe would duplicate work already in the reporter's
  multi-case reproducer (the reporter already covered the family).
- The user passed `--no-probe` (e.g., running through a campaign
  where the campaign skill aggregates family analysis at a higher
  level).

## Probe template structure

A probe is a single script that exercises the same expression
across every family member and emits a comparison table:

```groovy
def probes = [
    'Member A' : { -> /* construct backend A, exercise the expression */ },
    'Member B' : { -> /* same expression on backend B */ },
    // ... one entry per family member
]
probes.each { name, body ->
    def outcome
    try {
        outcome = body()
    } catch (Throwable t) {
        outcome = "THREW: ${t.class.simpleName}: ${t.message}"
    }
    println String.format("%-20s | %s", name, outcome)
}
```

The exact syntax depends on the project's runtime; the structure
is universal:

- One entry per family member.
- Each entry is a thunk that constructs the backing instance and
  runs the expression.
- A `try { ... } catch (...) { THREW }` wrapper so a member that
  throws doesn't abort the probe.
- Tabular output with one row per member.

Project-specific probe templates live in
[`tools/probe-templates/<runtime>/`](../../../../tools/probe-templates/)
(forthcoming as part of the issue-management contribution). Each
template is a runnable script with placeholders for the expression
under test.

## Saving the probe and its output

Per the
[`<project-config>/reproducer-conventions.md`](../../../../projects/_template/reproducer-conventions.md)
layout, the probe artefacts live alongside the main reproducer:

```text
~/work/<project>-reassess/<campaign-id>/<ISSUE-KEY>/
├── reproducer.<ext>
├── run.log
├── verdict.json
├── cross-type-probe.<ext>           ← probe script
├── cross-type-probe.log             ← probe output
└── cross-type-probe-findings.md     ← optional, when worth a separate write-up
```

Replace `cross-type-` with `operator-variants-` (or similar) when
the probe is across an operator family rather than a type family.

## Recording in the verdict

The probe results go into `verdict.json` under
`cross_type_probe` or `operator_variants_probe`:

```json
"cross_type_probe": {
  "file": "cross-type-probe.<ext>",
  "log": "cross-type-probe.log",
  "summary": "<one-line roll-up — e.g. '3/4 backings throw; primitive array returns wrong value'>",
  "findings": "<optional longer prose when worth recording>"
}
```

Full schema in
[`verdict-composition.md`](verdict-composition.md#probe-sub-schemas).

## New-bug-in-sibling-type

If the probe surfaces a *new* bug in a sibling type that the
original report didn't mention — for example, the reporter
described a bug in `List` slicing and the probe shows
`primitive-array` slicing has a different, separately-broken
behaviour — that often warrants its own new issue.

The handling:

1. The **original issue's verdict** stays focused on the
   original reporter's claim. The new finding does NOT
   reclassify the original issue.
2. The `verdict.json.cross_type_probe.findings` field flags the
   new finding with enough context (the family member, the
   expression, the wrong behaviour) for a maintainer to file a
   new issue if they agree.
3. The campaign-level aggregation in
   [`issue-reassess-stats`](../reassess-stats/SKILL.md)
   surfaces new-bug candidates across the campaign as a
   "candidates for new issues" section in its dashboard.

This separation matters: combining the original issue's verdict
with sibling-type findings would confuse what's being judged. The
original report is judged on its own terms; sibling findings get
their own track.

## Sanity check

After the probe runs, re-read the output table against the
reproducer's claim:

- **Is the original report's behaviour present in the table?** It
  should be — the probe should cover the original case. If it
  doesn't, the probe is missing a member.
- **Are the family members exhaustive?** Family taxonomies live in
  the project's documentation. If the probe missed a member,
  expand the probe before drawing conclusions.
- **Is the asymmetry meaningful?** Sometimes family members
  behave differently *by design* (different types have different
  invariants). A probe surfacing such a difference isn't a bug;
  it's a feature. The judgement is the maintainer's at
  campaign-report time.

## Cross-references

- [`SKILL.md`](SKILL.md) — orchestration; this file expands Step 9.
- [`extraction.md`](extraction.md) — picking the candidate; the
  same expression that's adapted in the reproducer is the one
  probed.
- [`verdict-composition.md`](verdict-composition.md) — schema for
  the `cross_type_probe` / `operator_variants_probe` sub-objects.
- [`<project-config>/reproducer-conventions.md`](../../../../projects/_template/reproducer-conventions.md) —
  where probe artefacts live in the evidence package.
