<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: SBOM pipeline (one CycloneDX SBOM per distributable artifact)
status: proposed
kind: feature
mode: infra
source: >
  tools/sbom-pipeline/README.md (contract:sbom-pipeline, #1900). The
  contract is written; no adapter, tool or skill implements it yet.
acceptance:
  - Every distributable artifact, and the source release, has exactly one
    CycloneDX 1.7 JSON SBOM of its own, complete without any other SBOM.
  - Two builds of the same source produce byte-identical SBOMs.
  - Content embedded from another ecosystem is described in the
    container's SBOM as a nested assembly, never by reference.
  - validate reports C1–C11 as passed, failed or for review, naming the
    offending bom-ref.
---

## What it does

Defines what a project's SBOMs must contain so that every distributable
artifact a project ships, whatever its ecosystem, carries one CycloneDX 1.7
JSON SBOM describing exactly what is inside it and what it needs from its
environment, and so that the source release carries one describing the
files that do not share the project's terms.

The contract fixes what the SBOMs say, not which generator writes them:
per-ecosystem adapters plug a project's existing generators into one
pipeline whose shared steps (`embed`, `normalize`, `validate`) are a single
deterministic tool.

## Where it lives

- `tools/sbom-pipeline/README.md` — the contract: rules 1–7, the
  operations, conformance checks C1–C11, the planned adapters and
  consumers, and the open questions.
- `contract:sbom-pipeline` is registered in
  `tools/skill-and-tool-validator` (known capabilities),
  `tools/vendor-neutrality-score` (`VENDOR_BACKED`, ❌ until two adapters
  ship), `docs/labels-and-capabilities.md` and the generated
  `.github/labeler.yml` rule.
- Planned, not present: `tools/sbom-pipeline-<ecosystem>/` adapters
  (maven, gradle, js, python, go, rust) and the `sbom-pipeline-integrate`
  and `sbom-pipeline-verify` skills.

## Behaviour & contract

- **One SBOM per artifact.**
  An artifact's SBOM is complete on its own; there is no combined SBOM
  for a project.
- **Subject.**
  `metadata.component` carries the artifact's `type`, `name`, `version`,
  SPDX `licenses`, the project's configured `supplier`, and a `purl` in
  the artifact's own ecosystem with the qualifiers that tell it apart from
  the release's other artifacts, so no two artifacts share a subject
  `purl`.
- **Components.**
  Each has a deterministic `bom-ref` (its `purl`, else `name@version`,
  prefixed by the containing component's `bom-ref` when nested), and the
  `dependencies` graph covers every component.
  Build- and test-only dependencies are left out; a generator that cannot
  leave them out marks them `scope: excluded` and `normalize` removes them.
- **Assemblies.**
  Embedded content is nested under the component that contains it.
  A nested component's external requirement points at the artifact's own
  top-level component when the artifact embeds it, and is otherwise
  hoisted to the top level with `isExternal: true`, one entry per distinct
  requirement.
- **Reproducibility.**
  `serialNumber` is a version 5 UUID derived from the subject's `purl`, a
  build-produced SBOM has `version` `1`, `metadata.timestamp` comes from
  `SOURCE_DATE_EPOCH`, every array of objects is sorted by a canonical key
  and every array of strings lexically, and nothing host-specific is
  recorded.
- **Distribution.**
  An SBOM is published next to or inside its artifact, as the artifact's
  own channel dictates; one beside a download-area artifact carries its
  own checksums and signature.
- **Source release.**
  The source SBOM lists, as file components, every file whose license or
  copyright differs from the project's own; its inventory comes from the
  source tree and is cross-checked against `LICENSE` and `NOTICE`.
  Rule 7 is provisional until the source release's `purl` type is settled.

## Out of scope

- Choosing a generator for a project: the adapters name examples only.
- Vulnerability data (VEX) and SPDX output.
- Publishing an aggregate SBOM for a whole project.

## Acceptance criteria

- The README defines rules 1–7, the eight operations and checks C1–C11,
  each check reported as passed, failed or for review.
- `contract:sbom-pipeline` is a known capability in the validator, has a
  vendor-neutrality row, and a labeler rule.
- No adapter claims `status: available` without a README declaring what
  "Adding an adapter" requires.

## Validation

```bash
uv run --project tools/skill-and-tool-validator skill-and-tool-validate
uv run --project tools/vendor-neutrality-score vendor-neutrality-score --markdown
```

## Known gaps

- **No adapter, tool or skill implements the contract yet.**
  Every adapter and both consumer skills are `planned`.
  <!-- gap-closes-when: path-exists:tools/sbom-pipeline-maven -->
- **Open questions in the contract are unresolved.**
  The source release's `purl` type, the supplier configuration key, and
  where generator versions are recorded.
  <!-- gap-closes-when: none (narrative) -->
