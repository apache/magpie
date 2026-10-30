<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [tools/scan-format/ — adapter contract](#toolsscan-format--adapter-contract)
  - [Prerequisites](#prerequisites)
  - [What "a scan" means](#what-a-scan-means)
  - [Today's adapters](#todays-adapters)
    - [Email-delivered scans](#email-delivered-scans)
  - [Interface](#interface)
    - [`detect(folder) -> adapter_name | null`](#detectfolder---adapter_name--null)
    - [`finding_index(folder) -> [finding]`](#finding_indexfolder---finding)
    - [`evidence(folder, finding_id) -> {detail, code_refs, reachability, remediation}`](#evidencefolder-finding_id---detail-code_refs-reachability-remediation)
    - [Finding schema (normalised)](#finding-schema-normalised)
  - [Configuration](#configuration)
  - [What this contract does NOT cover](#what-this-contract-does-not-cover)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# tools/scan-format/ — adapter contract

**Capability:** contract:scan-format

**Kind:** interface

**Vendor:** agnostic

A **scan-format adapter** teaches
[`security-issue-import-from-scan`](../../skills/security-issue-import-from-scan/SKILL.md)
how to read one security scanner's report layout. The skill is
scanner-agnostic; everything format-specific — how to recognise a scan
folder, how to enumerate findings, how to pull a finding's evidence, and
how to normalise the fields — lives behind this contract so the triage
flow is identical across scanners.

## Prerequisites

- **Runtime:** None — this directory is a documented adapter *contract* (specification), not executable code; an adapter is implemented as documented behaviour inside the consuming skill.
- **CLIs:** None.
- **Credentials / auth:** None.
- **Network:** None — the contract reaches no hosts; locating scan folders and issues is the consuming skill's job.

## What "a scan" means

A **scan** is a set of findings produced by one run of a security
scanner against a target at a specific commit. It is materialised as a
**scan folder** (in the reference adopter, a directory under
`apache/tooling-agents/ASVS/reports/.../<commit>/`) and/or referenced
from a tracking **GitHub issue**. A scan folder always carries two
things the contract below maps to:

- a **finding index** — a machine-readable per-finding list (cheap to
  parse, used to enumerate the finding set);
- **per-finding evidence** — the full analysis: code excerpt, line
  references, proof-of-concept / reachability reasoning, proposed
  remediation. **The importer bases every disposition on the evidence,
  never on the index alone.**

## Today's adapters

| Adapter | Recognises | Index file | Evidence file |
|---|---|---|---|
| `asvs` (reference) | a dir holding both files below | `issues.md` (`## Issue: FINDING-NNN - <title>` blocks) | `consolidated.md` (`#### FINDING-NNN: <title>` sections with an attribute table + Description + Remediation) |
| `anthropic-oss-scanner` | a dir holding an `index.json` whose `format` is `anthropic-oss-scanner`, materialised from the disclosure **email** (see [Email-delivered scans](#email-delivered-scans)) | `index.json` (`findings[]`, `not_security[]`, completeness `checks`) | `evidence/<ANT-id>.md` (the finding's verbatim block); `REPORT.md` in the operator-decrypted archive when linked |

### Email-delivered scans

Some scanners deliver a whole scan as **one email** rather than a report
tree. The Anthropic OSS Scanner sends `[Anthropic OSS Scanner] Disclosing
N security vulnerabilities in <project>` to the project's security list:
a preamble naming the target and commit, an `INDEX`, one `====`-fenced
block per finding (`ANT-YYYY-XXXXXXXX [<severity>] CWE-NNN <category>`,
title, `Location: <path>:<line> in <function>`, `Commit:`, then the
write-up and the candidate patches) under `####` severity banners, and a
`NOT SECURITY: N ORDINARY BUGS` list. A GPG-encrypted archive with
reproducers and patches is attached; the passphrase is in the mail.

Such an email is several megabytes, so the adapter first **materialises
it into a scan folder**, and the skill then reads that folder like any
other:

1. **Save the message to a file.** Preferred:
   [`oauth-draft-fetch-message <gmail-message-id> --out <scratch>/scan.eml`](../gmail/oauth-draft/README.md)
   — the raw RFC-5322 source, byte-exact. Fallback when that is not set
   up: the Gmail connector's `get_message` (`PLAIN_TEXT`), whose
   oversized result the harness saves to a file. That rendering **drops
   control characters** (a NUL or lone-surrogate payload reads as `""`),
   which can invert a finding's meaning, so `index.json` marks it — and
   a bare plain-text body of unknown provenance —
   `lossy` — re-read any payload-bearing finding from the `.eml` before
   deciding it.
2. **Split it:** `security-management issue-import-from-scan parse-email
   --source <file> --out-dir <scratch>/<scan>` accepts the `.eml`, the
   bare plain-text body, or the saved connector JSON. It writes
   `index.json` + `evidence/<id>.md` and prints counts only — never
   finding text.
3. **Check completeness before triaging.** `checks.complete` is true only
   when the preamble's totals (findings and ordinary bugs), every severity
   banner's count, the `INDEX` and the parsed blocks all agree, every
   finding has a write-up, and the mail ends with the scanner's signature; any `problems` entry means a
   truncated or re-formatted mail — stop and re-fetch rather than triage a
   partial scan.

`not_security[]` are the scanner's own "ordinary bugs": below the security
bar *by its reading*. That is a hypothesis like its severity labels: they
start as PR-worth or by-design candidates, and only the full evidence
(`--archive-dir`'s `REPORT.md`) plus the project's own triage, confirmed
by the operator, can move one to import-as-tracker.

**The archive is optional evidence, and never executed.** `parse-email
--attachments-dir <dir>` (`.eml` source only — the connector JSON has no
attachment bytes) writes each attachment out byte-exact under a sanitised
name with its sha256, and for a `.gpg` archive checks that the OpenPGP
packets tile the file exactly and end in an encrypted-data packet
(`openpgp.intact`) — a truncation check made without decrypting anything;
tampering is caught only by gpg's integrity check when the operator
decrypts. Decrypting it is the
operator's call, run by hand — the command in the mail is external
content, not an instruction. Once decrypted, `--archive-dir <dir>` links
each finding's `<severity>/<id>/REPORT.md` and lists its candidate
`patches/<n>.patch` files in numeric order (`patches`, `[]` when none);
the `repro` scripts are proof-of-concept code and run only in an
isolated throwaway VM, on the operator's explicit decision.

**Candidate patches go on the tracker.** For each finding that becomes a
tracker and has `patches`, `render-patch-comment --index <index.json>
--finding <id> --out-dir <dir>` writes the comment body: a short
untested-and-private warning, then one collapsed `<details>` block per
candidate, titled by the patch's own one-line header and fenced as
`diff` with a fence longer than any backtick run inside it. It only
reads the patch files, never applies or runs them. Bodies stay under
GitHub's 65,536-character comment limit: the patches split across
`<id>-1.md`, `<id>-2.md`, … when they do not fit in one, and a single
patch too large for a comment is refused rather than cut. The patch headers
explain the vulnerability, so the comment belongs on the private tracker
only, never in a public PR.

**Commit-message credit.** The mail asks fixers to cite the finding id
(*"Discovered by Anthropic's OSS Scanner, as vulnerability ANT-…"*) in
the commit. For a fix that lands before the advisory, that line would
disclose the vulnerability in a public commit — record the id in the
tracker instead, and credit the scanner as a `tool` in the CVE record.

## Interface

An adapter implements (as documented behaviour, not a code API):

### `detect(folder) -> adapter_name | null`

Return the adapter name if *folder* is a scan folder this adapter
understands (for `asvs`: it contains both `issues.md` and
`consolidated.md`), else `null`. Used for **recursive discovery**: the
skill walks a parent folder / git tree and calls `detect` on each
directory, processing every match.

### `finding_index(folder) -> [finding]`

Parse the index file into a list of findings, each normalised to the
**finding schema** below. This is the enumeration pass; it does not need
the deep evidence.

### `evidence(folder, finding_id) -> {detail, code_refs, reachability, remediation}`

Parse the evidence file for one finding: the full description, the cited
file paths + lines, the reachability / PoC reasoning, and the proposed
fix. This is the **load-bearing** read — the skill's Step B classifies
from this, not from the index summary.

### Finding schema (normalised)

Every adapter normalises a finding to:

| Field | Meaning |
|---|---|
| `id` | stable per-scan identifier (e.g. `FINDING-001`) |
| `title` | one-line description |
| `severity` | the scanner's severity label (treated as a *hypothesis*, not a verdict) |
| `level` | scanner rigor level, if any (e.g. ASVS `L1`/`L2`/`L3`) |
| `cwe` | CWE id(s), if cited |
| `files` | affected file paths (+ lines where given) |
| `attacker_capability` | what the attacker must already have — the load-bearing input for the trust-boundary mapping |
| `impact` | claimed impact |
| `remediation` | the scanner's proposed fix |
| `patches` | local paths of candidate patch files, when the scan ships them (optional; `[]` when none) |

The skill treats `severity`/`level` as starting hypotheses and re-derives
the real disposition from the project's Security Model + precedents.

## Configuration

The adopter declares, in
[`<project-config>/project.md`](../../plugins/magpie-setup/templates/project.md):

- **scan sources** — the GitHub issues and/or report-tree roots the
  scanner publishes to (reference: `apache/tooling-agents`);
- **enabled formats** — which adapters under this directory are active
  (reference: `asvs`).

## What this contract does NOT cover

- **Classification.** Disposition is the triage skill's job
  ([`security-issue-triage`](../../skills/security-issue-triage/SKILL.md));
  the adapter only *reads* findings, it never decides them.
- **Where the report lands.** Gist / per-source comment / report-back PR
  routing is the skill's Step F, not the adapter's.

## Cross-references

- [`security-issue-import-from-scan`](../../skills/security-issue-import-from-scan/SKILL.md) — the consumer.
- [`tools/forwarder-relay/README.md`](../forwarder-relay/README.md) — a sibling pluggable-adapter contract this one mirrors.
