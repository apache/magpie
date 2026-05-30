<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Tool: Vulnogram](#tool-vulnogram)
  - [What this tool provides](#what-this-tool-provides)
  - [How the generic skills address the CVE tool](#how-the-generic-skills-address-the-cve-tool)
  - [Confidentiality](#confidentiality)
  - [Per-project configuration](#per-project-configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tool: Vulnogram

This directory documents the **Vulnogram** tool adapter — the set of
capabilities the skills use when the adopting project declares Vulnogram
as its **CVE tool** (the CNA-side system for allocating CVE IDs,
maintaining CVE 5.x records, and pushing those records to `cve.org`).

Vulnogram is the ASF's hosted CNA tool at
[`cveprocess.apache.org`](https://cveprocess.apache.org/). Every ASF
project reusing this framework will typically declare
`cve_tool: vulnogram` in its manifest; for the currently active
project see
[`../../<project-config>/project.md`](../../<project-config>/project.md#cve-tooling).

## What this tool provides

The skills use Vulnogram for three capabilities plus a CVE-JSON
generator and an API client. Each has its own reference file in this
directory:

| Capability | File | What it covers |
|---|---|---|
| Allocation | [`allocation.md`](allocation.md) | PMC-gated allocation URL + form-fill recipe + non-PMC relay flow |
| Record management | [`record.md`](record.md) | Record URL template, `#source` tab paste flow, `DRAFT` → `REVIEW` → `PUBLIC` state machine, reviewer-comment-via-email signal |
| CVE-5.x JSON generator | [`generate-cve-json/`](generate-cve-json/) | Python project (`uv run`-managed) that reads a tracker body and emits a paste-ready CVE-5.x JSON record in the shape Vulnogram expects |
| API client (default record-write path) | [`oauth-api/`](oauth-api/) | Python project that PUTs the CVE JSON to `cveprocess.apache.org` over the operator's ASF-OAuth session cookie. Replaces the manual `#source` paste in the release-manager checklist. See [`record.md` → *Two record-write paths*](record.md#two-record-write-paths--api-default-and-copy-paste-fallback). |

The generator is kept here (rather than under `.claude/skills/`)
because its output shape — in particular the `CNA_private` envelope
with the `DRAFT` / `REVIEW` / `PUBLIC` state machine — is a
Vulnogram-specific opinionation on top of the standard CVE-5.x schema.
A different CNA tool would need a different generator (or a different
wrapper around the generic schema builders).

## How the generic skills address the CVE tool

The generic `security-issue-sync`, `security-cve-allocate`, and
`security-issue-deduplicate` skills frame their CVE-tool-facing steps
in project-tool-agnostic terms — *"regenerate the CVE artifact via
the project's CVE tool"*, *"walk the user through the allocation
flow"*, *"capture the reviewer-comment signal"*. They then delegate
to the project's declared `cve_tool`:

- For adopters declaring `cve_tool: vulnogram`, the skills delegate
  to the recipes in this directory and to the generator under
  `generate-cve-json/`.
- For a hypothetical project using a different CNA tool (a private
  Vulnogram instance, an in-house CNA system, a commercial CVE
  management platform), that project would:
  1. create a sibling `tools/<cve-tool-name>/` directory with
     `tool.md` / `allocation.md` / `record.md` / a generator;
  2. flip `cve_tool` in its manifest;
  3. keep the generic skill logic unchanged.

## Confidentiality

Vulnogram links are internal during the allocation + drafting window:

- Before an advisory is sent, links to
  `cveprocess.apache.org/cve5/<CVE-ID>` **must not** appear on public
  surfaces (the public `<upstream>` PR body, public mailing-list
  posts, anything else non-security-team-visible) — see the
  *"Confidentiality of the tracker repository"* and *"Linking CVEs"*
  sections of [`../../AGENTS.md`](../../AGENTS.md).
- After publication the CVE record is world-readable at
  [`cve.org`](https://cve.org); the Vulnogram URL stays useful as the
  security team's edit surface but the public-facing link switches to
  `cve.org`.

## Per-project configuration

Every Vulnogram adapter invocation needs three project-scoped values.
For the adopting project these are declared in
[`../../<project-config>/project.md`](../../<project-config>/project.md#cve-tooling):

| Key | What it controls |
|---|---|
| `asf_org_id` | The CVE 5.x `assignerOrgId` (ASF's UUID). |
| `cna_private_owner` | The `CNA_private.owner` field — identifies the project slug inside the ASF CNA queue. |
| `cna_private_userslist` | The advisory-delivery list; lands in `CNA_private.userslist`. |

Vendor/product (for the CVE record's `vendor` / `product` fields),
the package name, and the collection URL come from the project
manifest's *Identity* section and the `generate-cve-json` CLI flags.
