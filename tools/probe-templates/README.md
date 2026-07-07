<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Probe templates](#probe-templates)
  - [Prerequisites](#prerequisites)
  - [Layout](#layout)
  - [What a probe template looks like](#what-a-probe-template-looks-like)
  - [Contributing a runtime](#contributing-a-runtime)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Probe templates

**Capability:** substrate:sandbox

**Harness:** agnostic

Runnable cross-family probe scripts that the
[`issue-reproducer`](../../skills/issue-reproducer/SKILL.md)
skill copies from when its Step 9 (optional cross-family probe)
runs against an issue.

The probe pattern, contract, and recording schema are in the
skill's [`probe-templates.md`](../../skills/issue-reproducer/probe-templates.md)
companion. This directory holds runtime-specific reference
implementations.

## Prerequisites

- **Runtime:** None of its own — this directory holds per-runtime probe template files (today `groovy/`). Running a probe needs the matching language runtime (e.g. a Groovy interpreter for the `groovy/` templates).
- **CLIs:** Whatever runs the target runtime's scripts; nothing else.
- **Credentials / auth:** None.
- **Network:** Runs fully offline/local.

## Layout

```text
tools/probe-templates/
├── README.md                        (this file)
└── <runtime>/                       (one subdirectory per supported runtime)
    └── *.template                   (probe template files with placeholders)
```

Adopters with JVM-language projects copy from `<runtime>/` where
`<runtime>` matches their language. Adopters whose runtime is not
covered contribute their own per-runtime templates back via PR.

## What a probe template looks like

A probe template is a small runnable script that exercises the
same expression across every member of a type or operator family
and emits a comparison table. The structure is universal across
runtimes:

```text
# Pseudocode (each runtime renders this in its own syntax):
probes = {
    "Member A": () => { construct backend A, exercise the expression }
    "Member B": () => { same expression on backend B }
    # ... one entry per family member
}
for name, body in probes:
    try:
        outcome = body()
    catch e:
        outcome = "THREW: " + type(e) + ": " + message(e)
    print(name + " | " + outcome)
```

The expression under test is a placeholder; users substitute it
when running against a specific issue.

## Contributing a runtime

The framework treats every per-runtime subdirectory as **first-class**.
Today the `groovy/` subdirectory ships in the framework; `python/`,
`kotlin/`, `java/`, `rust/`, and other-language subdirectories are
welcome and awaiting contribution. None of them require framework-side
support beyond adding the subdirectory — the per-runtime probe scripts
are runnable standalone.

Adopters with a new runtime should:

1. Add a subdirectory `tools/probe-templates/<runtime>/` matching
   the runtime's conventional short name (lowercase, hyphenated).
2. Add at least one template file per supported family type:
   - `range-index-cross-type.<ext>.template`
   - `gpath-cross-backend.<ext>.template`
   - `operator-variants-safe-nav.<ext>.template`
3. Each template file has a header comment naming the family being
   probed, the placeholders the user substitutes, and an example
   invocation.
4. Open a PR against `apache/magpie`.

Note: not every language has every family. A typed compiled language
without an operator-overloading subsystem may have no
`operator-variants-*` templates; that's fine — the framework only
loads templates that exist.

## Cross-references

- [`issue-reproducer/probe-templates.md`](../../skills/issue-reproducer/probe-templates.md) —
  the skill-side procedural detail.
- [`issue-reproducer/verdict-composition.md`](../../skills/issue-reproducer/verdict-composition.md) —
  schema for the `cross_type_probe` and `operator_variants_probe`
  sub-objects.
- [`<project-config>/reproducer-conventions.md`](../../projects/_template/reproducer-conventions.md) —
  where probe artefacts live in the per-issue evidence package.
