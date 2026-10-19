<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Body-field format adapters](#body-field-format-adapters)
  - [Adding an adapter](#adding-an-adapter)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Body-field format adapters

A *format adapter* reads and writes the fields of a tracker body whose layout is not the default `### <Name>` sections:
`Name: value` lines, a plain-text CVE file, a layout a project has kept for years.
It implements the [format adapter interface](../contract.md#format-adapters) — the contract's operations, refusals and decision kinds, for the layout's own boundary rule.

This directory is the upstream home for adapters other projects can reuse.
[`_template.py`](_template.py) is the skeleton setup copies when it generates a project's own adapter
(it is itself a working adapter for `Name: value` lines), and every `*.py` here, the template included, runs through the conformance suite:
the generic properties every layout shares, and the adapter's own fixtures in `<name>.cases.jsonl` beside it.

## Adding an adapter

1. Copy `_template.py` to `<layout>.py` and change only its FORMAT section: the boundary rule, `boundary_line`, and a synthetic `SAMPLE_BODY` with its `SAMPLE_FIELDS`.
2. Write `<layout>.cases.jsonl` in the [conformance case format](../contract.md#conformance-suite), from the layout's *structure* only: synthetic values, never report text.
3. Run the suite on it:
   `uv run --directory tools/github-body-field --project . python -m pytest tests/test_conformance.py -k format`.
   With `BODY_FIELD_FORMAT_ADAPTERS=<path>[:<path>…]` the same run covers adapters outside this directory, such as a project's own under `.apache-magpie-overrides/tools/local-tracker/parsers/`.

A project that generated its adapter during `setup` contributes it here through [`setup-override-upstream`](../../../plugins/magpie-setup/skills/override-upstream/SKILL.md).
