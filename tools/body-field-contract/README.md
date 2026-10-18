<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/body-field-contract/`](#toolsbody-field-contract)
  - [Prerequisites](#prerequisites)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/body-field-contract/`

**Capability:** contract:body-field

**Kind:** interface

**Vendor:** agnostic

How every reader and writer finds the `### <Name>` fields of a tracker issue body, stated once and independent of language:
what a field boundary is, which code blocks count, which heading is the field, what is ambiguous and must be refused,
the four operations an implementation provides (list fields, extract, replace, normalise) with their refusals,
and the two writer operations (escape text, escape body) that keep untrusted text from ever becoming a field.

A tracker whose reports use another layout reads them through a *format adapter* ([`formats/`](formats/README.md), the upstream home for them; [format adapter interface](contract.md#format-adapters)).

See [`contract.md`](contract.md) for the rules and [`conformance/cases.jsonl`](conformance/cases.jsonl) for the shared conformance cases,
which `tools/github-body-field/tests/test_conformance.py` runs against every implementation in the repository.

| Implementation | Language |
|---|---|
| [`tools/github-body-field/`](../github-body-field/README.md) | Python (reference) |
| [`tools/vetted-ops/`](../vetted-ops/README.md) | Python (byte-identical copy) |
| [`tools/local-tracker/`](../local-tracker/README.md) | Python (byte-identical copy; escape text and escape body) |
| [`tools/jira/`](../jira/README.md) | Python (byte-identical copy, after mapping wiki headings; escape body) |
| [`groovy/`](groovy/BodyFieldParser.groovy) | Groovy (basic implementation, every operation) |
| [`tools/security-management/`](../security-management/README.md) | Python (writer only: escape text, the import's inert block) |

## Prerequisites

- **Runtime:** None for the contract itself (Markdown and JSON Lines fixtures).
  The Groovy implementation in [`groovy/`](groovy/BodyFieldParser.groovy) needs the Groovy runtime only (it was checked with Groovy 6.0.0 on JVM 27); it has no other dependency and pulls nothing with `@Grab`.
- **CLIs / credentials / network:** None. The conformance runner lives in `tools/github-body-field/tests/` and runs offline under its pytest.
- **Optional:** `groovy` on `PATH`, for the runner's Groovy check; without it that check skips with the reason.
