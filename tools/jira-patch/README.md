<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`tools/jira-patch/`](#toolsjira-patch)
  - [Prerequisites](#prerequisites)
  - [What this maps](#what-this-maps)
  - [Operations](#operations)
    - [Reviewed-attachment pinning](#reviewed-attachment-pinning)
    - [Attribution](#attribution)
  - [Configuration](#configuration)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/jira-patch/`

**Capability:** contract:change-request

**Kind:** implementation

**Vendor:** Atlassian

**Organization:** ASF

JIRA-patch change-request adapter — the backend that lets a
JIRA-tracker, SVN-hosted project drive the `pr-management-*` skills
over **patches attached to JIRA issues** instead of GitHub pull
requests. It implements the [`tools/change-request/`](../change-request/)
contract for projects whose proposed changes arrive as a `.patch`
file on a JIRA issue and are committed to an SVN trunk.

This adapter owns the **proposal lifecycle** (the JIRA issue + its
attached patch + its comment stream); it does **not** own the commit.
Its `land` verb delegates the actual apply-and-commit to the project's
[`contract:source-control`](../asf-svn/) adapter — `svn patch`
followed by `svn commit` against `svn.apache.org` — and then records
the landed revision back on the JIRA issue. This split is why
change-request and source-control are separate contracts: on an
SVN-first project the review gate (JIRA) and the commit substrate
(SVN) are two different systems.

The read/write JIRA plumbing is the existing [`tools/jira/`](../jira/)
tracker bridge (JQL search, `comment`, `transition`, `label`,
`attach`). This adapter adds the change-request *semantics* on top of
those verbs; it does not re-implement the JIRA REST client.

## Prerequisites

- **Runtime:** Bash — doc-only adapter; skills invoke the `tools/jira/`
  bridge and the `tools/asf-svn/` recipes, no local package of its own.
- **CLIs:** the `jira` bridge (JIRA REST over `curl`) and `svn`
  (for the delegated `land`).
- **Credentials / auth:** JIRA API token for the project's Atlassian
  site (read for `list_open`/`get`/`get_discussion`, write for
  `post_review`/`reject`), plus ASF committer credentials for the
  SVN commit that `land` delegates to `tools/asf-svn/`. The adapter
  never commits under its own identity — it uses the running
  committer's `svn` auth, exactly as a manual `svn commit` would, so
  patch-author-vs-committer attribution is preserved (see
  [Attribution](#attribution)).
- **Network:** the project's JIRA host (e.g. `issues.apache.org/jira`)
  and `svn.apache.org` for the delegated land.

## What this maps

The JIRA-patch backend resolves the change-request as: **a JIRA issue
carrying a patch attachment is one change proposal.** The issue key is
the proposal `id`; the newest `.patch`/`.diff` attachment is the diff
under review; the issue's comment stream is the review discussion.
What lands is never "the newest attachment at land time": it is the
attachment that was reviewed, pinned by its JIRA attachment id and the
SHA-256 of its bytes (see [Reviewed-attachment pinning](#reviewed-attachment-pinning)).

## Operations

Each change-request verb resolves onto the JIRA + SVN surfaces as
follows. The verb names are the contract's; the right column is this
adapter's concrete resolution.

| Verb | JIRA-patch resolution |
|---|---|
| `list_open(filter)` | JQL: `project = <KEY> AND status = Open AND attachments IS NOT EMPTY` (plus the filter's author/component/age narrowers), via `jira search`. One `proposal_summary` per issue that carries a patch attachment. |
| `get(id)` | `jira issue <KEY>` for metadata; download the newest `.patch`/`.diff` attachment for the `diff`, and return its JIRA `attachment_id` and the `sha256` of the downloaded bytes alongside it. `base` is the trunk path from `change_request.jira_patch.trunk_url`; `commits` is `[]` (a bare patch has none); `mergeable` is `unknown` until an `svn patch --dry-run` is run. |
| `get_discussion(id)` | The issue's comment stream, normalised to `{author, date, body, kind}`. A comment carrying the configured approval token maps to `kind: approval`. |
| `post_review(id, verdict, body)` | `jira comment <KEY> --body-file <draft>`; the `verdict` is additionally encoded as a `jira transition` / `jira label` move (`approve` → *Reviewed*, `request-changes` → *Needs work*). The comment ends with the pin line `Reviewed attachment: <attachment_id> sha256:<hex>` for the attachment `get` returned, so the review names exactly the bytes it covers. |
| `land(id, strategy)` | **Delegates to `contract:source-control`.** Requires the reviewed `attachment_id` and `sha256` (see [Reviewed-attachment pinning](#reviewed-attachment-pinning)); downloads that attachment by id, and refuses unless its SHA-256 matches the recorded one and it is still the newest `.patch`/`.diff` on the issue. Only then calls the source-control adapter's apply + commit (`svn patch <file>` then `svn commit` against the trunk working copy — see [`tools/asf-svn/source-control.md`](../asf-svn/source-control.md)), then transitions the issue to *Resolved/Fixed* and comments the landed revision. `strategy` is advisory — SVN applies a patch as a single commit, so `squash` is the only honoured strategy and the adapter reports that. |
| `reject(id, reason)` | `jira transition <KEY> "Won't Fix"` (or the configured rejected transition) with `reason` as a closing comment. No commit — the absence of a `land` is the rejection. |
| `status(id)` | `checks: none`, `mergeable` from an `svn patch --dry-run` (`clean` / `conflicting`). JIRA has no CI gate unless a pipeline is wired to the issue; skills degrade the `checks` gate to advisory (see the contract's `status` graceful-degradation note). |

### Reviewed-attachment pinning

A JIRA issue keeps accepting attachments after review, so "the newest
patch" can change between the review and the commit. The adapter pins
the reviewed bytes instead:

1. **At review time** `get` records the `attachment_id` of the patch it
   downloaded and the SHA-256 of those bytes, and `post_review` writes
   both into the review comment as the line
   `Reviewed attachment: <attachment_id> sha256:<hex>`.
2. **At land time** the caller passes the `attachment_id` and `sha256`
   from the approving review it is acting on: the review the landing
   committer posted in this session, or the pin line of an approval
   comment whose author is a project committer. A pin line in a comment
   by anyone else is ignored, since any JIRA user can comment.
3. `land` downloads the attachment **by that id**, never by recency,
   hashes the downloaded bytes, and **refuses** — no `svn patch`, no
   commit, no transition — when:
   - no reviewed `attachment_id` / `sha256` is supplied;
   - the attachment id no longer exists on the issue;
   - the SHA-256 of the downloaded bytes differs from the recorded one;
   - a newer `.patch`/`.diff` attachment was added after the reviewed
     one (the proposal changed after review; it goes back to review).
4. The refusal names the reviewed and the current attachment ids so the
   maintainer can re-run the review on the new patch. Landing a patch
   that was not reviewed is never a fallback.

The landing comment repeats the pin line, so the record shows which
reviewed bytes became the landed revision.

### Attribution

The delegated `land` preserves **patch-author vs. committer**
attribution the way ASF SVN commits always have: the `svn commit`
runs under the landing committer's identity, and the commit message
credits the patch author (`Patch by <author>.` / `This closes #<KEY>.`
per the project's convention). The adapter reads the patch author
from the JIRA issue reporter / attachment uploader and templates it
into the commit message; it never impersonates the author's SVN
identity. This is the answer to #669's *"patch-author vs. committer
attribution"* open question for the JIRA-patch backend.

## Configuration

Declared under the change-request block in
`projects/<project>/project.md`:

```yaml
change_request:
  backend: jira-patch
  land_via: source-control        # land delegates to the VCS adapter
  review_channel: jira-comment
  default_strategy: squash        # SVN applies a patch as one commit
  jira_patch:
    site_url: https://issues.apache.org/jira
    project_key: <KEY>            # the JIRA project the proposals live in
    trunk_url: https://svn.apache.org/repos/asf/<project>/trunk
    approval_token: "+1"          # comment token that counts as an approval
    rejected_transition: "Won't Fix"
    resolved_transition: "Resolved"
```

- **`site_url` / `project_key`** — locate the JIRA project whose
  patch-bearing issues are the proposals.
- **`trunk_url`** — the SVN trunk the delegated `land` applies the
  patch to.
- **`approval_token`** — the comment string `get_discussion` reads as
  a `kind: approval`.
- **`rejected_transition` / `resolved_transition`** — the JIRA
  workflow transitions `reject` and `land` drive.

Backend-specific keys live under `change_request.jira_patch.*`; the
generic keys (`backend`, `land_via`, `review_channel`,
`default_strategy`) are the contract's.

## Cross-references

- Contract: [`tools/change-request/`](../change-request/)
- JIRA REST plumbing: [`tools/jira/`](../jira/)
- Delegated land: [`tools/asf-svn/source-control.md`](../asf-svn/source-control.md)
- Issue: [#669](https://github.com/apache/magpie/issues/669)
