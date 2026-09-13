<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Release audit record schema

Canonical field definitions for the per-release audit record produced by
`release-audit-report`. A record is **complete** when every required field
is populated with a real value (not the `MISSING` sentinel). Required
fields left as `MISSING` are **schema violations** that the skill surfaces
explicitly so the Release Manager can decide whether to publish the
incomplete record or gather the missing data first.

## Required fields

Every complete audit record must carry all of the following.

| Field | Type | Source | Description |
|---|---|---|---|
| `version` | string | trigger argument | Release version string (e.g. `2.11.0`). |
| `rc_label` | string | planning issue body | RC label used for the promoted artefacts (e.g. `rc1`). |
| `vote_thread_url` | URL | planning issue body | Archive URL of the `[VOTE]` mailing-list thread. |
| `result_thread_url` | URL | planning issue body | Archive URL of the `[RESULT] [VOTE]` reply. |
| `artefacts` | list | planning issue body | RC artefact list — filename, SHA-512 checksum, and `.asc` signature file for each release artefact. |
| `promote_revision` | string | planning issue body | Distribution backend reference for the promotion step (e.g. SVN revision `r12345`, or the backend-equivalent identifier when `release_dist_backend ≠ svnpubsub`). |
| `announce_archive_url` | URL | planning issue body | Archive URL of the `[ANNOUNCE]` mailing-list post. |
| `vote_binding_plus1` | integer | planning issue or `[RESULT]` thread | Count of binding `+1` votes. |
| `vote_binding_minus1` | integer | planning issue or `[RESULT]` thread | Count of binding `-1` votes. |
| `binding_voters` | list of strings | PMC roster × `[RESULT]` thread | PMC roster handles of every binding voter (no personal email addresses). |

## Optional fields

Optional fields are omitted when not applicable. A field that exists in
source data but falls outside the public audit-log scope appears as
`REDACTED` with a one-line reason (see the privacy boundary in
[`docs/release-management/spec.md`](../../../../docs/release-management/spec.md)).

| Field | Type | Description |
|---|---|---|
| `product_name` | string | Human-readable product name (defaults to `<project>` from config). |
| `cve_ids` | list of strings | Public CVE identifiers closed by this release (e.g. `CVE-2024-12345`). Include only public IDs — the audit log must not reference embargoed CVE detail. |
| `notes` | string | Free-form notes from the Release Manager, recorded verbatim. |

## Schema validation

When the assembled record has one or more required fields with value
`MISSING`, each such field is a **schema violation**. The `schema_violations`
list in the Step 2 JSON output names every violation in the form
`"<field> — required field is MISSING"`.

An incomplete record (non-empty `schema_violations`) is surfaced to the
Release Manager before the audit-log PR is proposed. The RM decides
whether to gather the missing data and re-run, or to publish the
incomplete record with the `MISSING` markers visible in the audit log
(the PR body lists every missing field explicitly).

A `schema_violations` list does **not** block the PR proposal — the
human reviewer remains in the loop and makes the final call.

## Privacy boundary

The audit log is committed to the adopter repo and is public by default.
Fields that would require quoting non-public content (security tracker
bodies, embargoed CVE detail, reporter mail, pre-disclosure severity
scores) must appear as `REDACTED` instead of `MISSING`. See the
[privacy boundary](../../../../docs/release-management/spec.md) for the
authoritative rule.
