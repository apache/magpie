<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`tools/change-request/`](#toolschange-request)
  - [Prerequisites](#prerequisites)
  - [What this is](#what-this-is)
  - [Relationship to `contract:source-control`](#relationship-to-contractsource-control)
  - [Today's adapters](#todays-adapters)
  - [Interface](#interface)
    - [`list_open(filter) to [proposal_summary]`](#list_openfilter-to-proposal_summary)
    - [`get(id) to proposal`](#getid-to-proposal)
    - [`get_discussion(id) to discussion`](#get_discussionid-to-discussion)
    - [`post_review(id, verdict, body) to ok`](#post_reviewid-verdict-body-to-ok)
    - [`land(id, strategy) to landed_ref`](#landid-strategy-to-landed_ref)
    - [`reject(id, reason) to ok`](#rejectid-reason-to-ok)
    - [`status(id) to {state, checks, mergeable}`](#statusid-to-state-checks-mergeable)
  - [Generic lifecycle verbs](#generic-lifecycle-verbs)
  - [Skills that consume this contract](#skills-that-consume-this-contract)
  - [ASF defaults](#asf-defaults)
  - [Configuration](#configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/change-request/`

**Capability:** contract:change-request

**Kind:** interface

**Vendor:** agnostic

## Prerequisites

- **Runtime:** None — this directory is a Markdown contract spec; no executable code ships here. It is read by the framework, not run.
- **CLIs / credentials / network:** Provided entirely by the resolved adapter — the sibling backend named by `change_request.backend` in `project.md`. The ASF default is GitHub (`tools/github/`); the SVN-first defaults are `tools/jira-patch/` and `tools/mail-patch/`, both of which land through the `contract:source-control` adapter (`tools/asf-svn/`). See each adapter for its concrete prerequisites.

## What this is

The framework's **change-proposal** adapter contract: the seam that
lets a project drive PR-shaped review-and-merge work over a backend
that is *not* a GitHub pull request. Today every `pr-management-*`
skill is hardwired to `gh pr` — `gh pr list`, `gh pr view`,
`gh pr diff`, `gh pr review`, `gh pr merge` are woven directly into
the skill bodies. That is fine for the ASF's GitHub-hosted projects,
but it forecloses three large classes of adopter:

- **JIRA-tracker projects.** `contract:tracker` abstracts the *issue*
  side across GitHub and Atlassian, but Jira has no pull-request
  model. A project whose issues live in JIRA and whose code lives in
  SVN has patches attached to issues, not PRs — and no seam to plug
  them into `pr-management-*`.
- **SVN-first ASF projects.** They lack both the PR object and the
  hosted review surface. A committer applies a contributor's patch
  with `svn patch` and commits it; the "review thread" is a JIRA
  comment stream or a `dev@` mail thread.
- **`[PATCH]` mail-thread projects.** The oldest review mechanism at
  the ASF (and in the wider open-source world) is a patch posted to
  the developer list. It has a diff, a discussion, and a lifecycle,
  but no forge behind it at all.

This contract models **the unit that is forge-shaped today (a pull
request)** as a backend-neutral *change proposal*: a diff plus
metadata, a review discussion, and a lifecycle — decoupled from the
backend that stores them. It declares the verbs the generic skill
bodies call; the concrete `gh pr` invocation, the JIRA REST calls,
or the mbox parsing stay inside each adapter directory.

The contract is read by the framework, not by humans during normal
operation. New adopters declare `change_request.backend: <adapter>`
in `projects/<project>/project.md`; the skills resolve that to a
sibling directory under `tools/` and call the verbs named here.
Adopters on GitHub inherit the `gh pr` behaviour verbatim.

> **Naming.** [Issue #669](https://github.com/apache/magpie/issues/669)
> proposed this contract under the working name
> `contract:change-proposal`. It ships as `contract:change-request`
> to match the name introduced by
> [#678](https://github.com/apache/magpie/pull/678), which first
> registered the contract in the vendor-neutrality scorer. The two
> names denote the same seam; `change-request` is canonical.

## Relationship to `contract:source-control`

Change-request is the **review + merge gate**; source-control is the
**branch / commit / diff / push** substrate underneath it. They are
distinct contracts because their backends differ:

- On GitHub the merge gate *is* the forge — `gh pr merge` both lands
  the diff and closes the proposal in one call, so `tools/github/`
  implements both contracts.
- On an SVN-first project the merge gate and the commit substrate
  are two different systems. `land` on the `jira-patch` and
  `mail-patch` adapters **delegates the actual commit to
  `contract:source-control`** (`tools/asf-svn/` → `svn patch` +
  `svn commit`), then records the outcome back on the review surface
  (a JIRA transition, a `dev@` reply). The change-request adapter
  owns the *proposal lifecycle*; source-control owns the *bytes on
  the trunk*.

The `land` verb is the only place the two contracts touch. Every
other verb (`list_open`, `get`, `get_discussion`, `post_review`,
`reject`, `status`) is pure change-request.

## Today's adapters

| Adapter | Directory | Vendor | Status | `land` path |
|---|---|---|---|---|
| GitHub pull request | [`tools/github/`](../github/) | GitHub | Shipping | `gh pr merge` (forge lands + closes) |
| JIRA patch | [`tools/jira-patch/`](../jira-patch/) | Atlassian | Shipping | delegates to `contract:source-control` (`svn patch` + `svn commit`) |
| `dev@` `[PATCH]` thread | [`tools/mail-patch/`](../mail-patch/) | email | Shipping | delegates to `contract:source-control` (`svn patch` + `svn commit`) |
| GitLab merge request | `tools/gitlab-mr/` *(planned)* | GitLab | Placeholder | `glab mr merge` |
| Gerrit change | `tools/gerrit/` *(planned)* | Gerrit | Placeholder | `git review` / submit |
| None | `tools/change-request-none/` *(planned)* | — | Placeholder | raises `NotApplicable`; the skill degrades to read-only |

Three adapters ship today across three distinct backend vendors
(GitHub, Atlassian, email), so the contract is vendor-neutral by the
`MIN_VENDORS = 2` criterion the vendor-neutrality score applies. The
three placeholder rows are named — with a one-line `land` note each —
so an adopter who needs GitLab, Gerrit, or an explicit no-backend
declaration can author the adapter without re-deriving the contract.

## Interface

Every change-request adapter exposes seven verbs. The names here are
the generic verbs the skills use; an adapter is free to name its
internal CLIs whatever fits its backend, as long as the skill-facing
surface uses these names. Output shapes are described in conceptual
terms — an adapter may return a language-native object as long as the
consuming skill can read the named fields.

### `list_open(filter) to [proposal_summary]`

Enumerate the open change proposals matching a filter.

- **When it fires.** Step 1 of `pr-management-triage` (and the
  queue-fill step of every `pr-management-*` skill) — the sweep that
  pulls the candidate set before classification.
- **Inputs.** `filter` — a dict of the queue narrowers the skills
  support: `author`, `label`/`component`, `age`, `review-for-me`,
  `stale`. The adapter translates these into its backend's query
  language (a GitHub GraphQL search, a JQL `attachment is not EMPTY`
  clause, a PonyMail `[PATCH]`-subject search).
- **Output.** An array of `proposal_summary` records, each at
  minimum: `id`, `title`, `author`, `created`, `updated`,
  `state` (a generic lifecycle verb, below), `labels[]`, and a
  `permalink` the human can open. Ordering is newest-updated-first.
- **No-op case.** The `none` adapter returns `[]`; the skill reports
  an empty queue and exits. An empty return and a no-access return
  are indistinguishable by design — the skill surfaces the gap
  without distinguishing the reason.

### `get(id) to proposal`

Fetch one proposal's diff plus metadata.

- **When it fires.** Whenever a skill pulls a single proposal out of
  a group for individual handling, or resolves `pr:N` directly.
- **Inputs.** `id` — the adapter's opaque proposal identifier
  (`123` for a GitHub PR number, `PROJECT-456` for a JIRA issue key
  carrying a patch, an mbox `message_id` for a `[PATCH]` thread).
- **Output.** A `proposal` object extending `proposal_summary` with:
  `diff` (unified-diff text, or a resolvable URL for very large
  diffs), `base` (the target branch/trunk path), `commits[]` where
  the backend has them (`[]` for a bare patch), `mergeable` (tri-state:
  `clean` / `conflicting` / `unknown`), and `checks` (see `status`).
- **No-op case.** Returns `null` when the id is well-formed but the
  proposal no longer exists (deleted PR, deleted JIRA attachment,
  purged archive). Skills surface the gap; they do not retry.

### `get_discussion(id) to discussion`

Read the review conversation attached to the proposal.

- **When it fires.** Any step that needs the review history —
  last-comment-by-viewer, unresolved-thread count, stale-reviewer
  detection, mentor context.
- **Inputs.** `id`, as for `get`.
- **Output.** A `discussion` object: `comments[]` of
  `{author, date, body, kind}` where `kind` is one of `comment`,
  `review`, `approval`, `change-request`; plus `participants[]` and
  `unresolved_count`. The adapter normalises its backend's native
  shapes — GitHub review threads, JIRA comment stream, mail replies —
  onto this one shape.
- **No-op case.** Returns an empty discussion (`comments: []`) when
  the proposal has no review activity yet.

### `post_review(id, verdict, body) to ok`

Post a review verdict + body onto the proposal.

- **When it fires.** The confirmation step of `pr-management-triage`
  (a *comment* disposition) and `pr-management-code-review` /
  `pr-management-quick-merge` (an *approve* / *request-changes*
  verdict). The skills always draft-then-confirm before this fires;
  the adapter never gates — the skill does.
- **Inputs.** `id`; `verdict` — one of `comment`, `approve`,
  `request-changes`; `body` — the review markdown.
- **Output.** `ok` sentinel (failure raises). On GitHub this is
  `gh pr review`; on `jira-patch` it is a JIRA comment (with the
  verdict encoded as a label transition); on `mail-patch` it is a
  drafted reply through `contract:mail-create` (never auto-sent).
- **No-op case.** The `none` adapter raises `NotApplicable`; the
  skill falls back to surfacing the drafted review to the maintainer
  as copy-paste text.

### `land(id, strategy) to landed_ref`

Merge / apply the proposal and close it in its accepted state. **This
is the only verb that touches `contract:source-control`.**

- **When it fires.** The merge step — never from `pr-management-triage`
  (triage never merges); from `pr-management-quick-merge` on explicit
  per-PR confirmation, and from the maintainer's own merge command.
- **Inputs.** `id`; `strategy` — one of `merge`, `squash`, `rebase`
  (backends that cannot honour the requested strategy fall back to
  their only supported one and report which they used).
- **Output.** `landed_ref` — the resulting commit SHA / revision the
  land produced, so the skill can cross-link it on the proposal and
  on any tracking issue.
- **Backend behaviour.**
  - `github`: `gh pr merge --<strategy>` — the forge both lands the
    diff and closes the PR atomically.
  - `jira-patch` / `mail-patch`: **delegates to
    `contract:source-control`.** The adapter fetches the diff via
    `get`, calls the source-control adapter's `apply` + `commit`
    (`tools/asf-svn/` → `svn patch <file>` then `svn commit`), and on
    success records the landed revision back onto the review surface
    (a JIRA *Resolved/Fixed* transition, a `dev@` "applied in rNNNNN"
    reply). Conflict handling and apply-idempotency live in the
    source-control adapter, not here.
- **No-op case.** The `none` adapter raises `NotApplicable`; the
  skill emits the paste-ready backend command for the maintainer to
  run by hand (the framework's deliberately-deferred Agentic Autonomous posture —
  no skill lands autonomously).

### `reject(id, reason) to ok`

Decline the proposal without landing it.

- **When it fires.** The *close* disposition of `pr-management-triage`
  (stale / superseded / out-of-scope PRs), after draft-then-confirm.
- **Inputs.** `id`; `reason` — the closing rationale captured from
  the triage discussion.
- **Output.** `ok` sentinel. On GitHub `gh pr close` with the reason
  as a comment; on `jira-patch` a *Won't Fix* / *Rejected* transition
  carrying the reason; on `mail-patch` a drafted reply with **no
  commit** (the absence of a `land` is the rejection).
- **No-op case.** The `none` adapter raises `NotApplicable`.

### `status(id) to {state, checks, mergeable}`

Read the CI / mergeable status of the proposal.

- **When it fires.** Classification in `pr-management-triage` (the
  CI-rerun / mark-ready gates) and the all-gates-green attestation in
  `pr-management-quick-merge`.
- **Inputs.** `id`.
- **Output.** `state` (a generic lifecycle verb); `checks` — one of
  `passing`, `failing`, `pending`, `none`; `mergeable` — `clean` /
  `conflicting` / `unknown`.
- **Graceful degradation.** Backends without a CI/mergeable concept
  (a bare `[PATCH]` mail thread; a JIRA patch with no attached
  pipeline) return `checks: none`, `mergeable: unknown`. Skills treat
  `none`/`unknown` as *"do not gate on backend status"* and fall back
  to a human judgement prompt rather than blocking — this is the
  answer to #669's *"graceful degradation for non-GitHub CI /
  mergeable status"* open question.

## Generic lifecycle verbs

The skills speak in generic verbs about a proposal's lifecycle. The
adapter maps its backend's native states onto these verbs.

| Verb | Meaning | GitHub-native | JIRA-patch-native | mail-patch-native |
|---|---|---|---|---|
| `open` | Proposed, awaiting first review. | `OPEN`, no reviews | issue *Open* + patch attached | `[PATCH]` posted, no replies |
| `under-review` | Review in progress; comments present, no verdict. | `OPEN` + comments | issue *In Review* | thread has replies, no LGTM |
| `changes-requested` | A reviewer asked for changes. | `CHANGES_REQUESTED` | *Needs work* label | reply requesting changes |
| `approved` | Cleared to land, not yet landed. | `APPROVED` | *Reviewed* label | `LGTM` reply |
| `landed` | Applied to the target branch/trunk. Terminal, success. | `MERGED` | *Resolved/Fixed* | "applied in rNNNNN" reply |
| `rejected` | Declined without landing. Terminal, failure. | `CLOSED` unmerged | *Won't Fix* | reply, no commit |
| `superseded` | Replaced by a newer proposal. Terminal. | `CLOSED` + successor link | *Duplicate* | newer `[PATCH vN]` |
| `unknown` | Adapter cannot determine state. | n/a | n/a | n/a |

The map is **adapter-internal**. Skills never write `MERGED` or
*Won't Fix* — they write `landed` and `rejected`, and the adapter
resolves the native transition. An adapter that needs a finer
internal model may add sub-states, as long as the contract-facing
verbs are what the skills see.

## Skills that consume this contract

The change-request contract is the backend seam for the
`pr-management-*` family. Today the call sites are `gh pr`; this
contract is the interface those call sites resolve through.

| Skill | Verbs used |
|---|---|
| [`pr-management-triage`](../../skills/pr-management-triage/SKILL.md) | `list_open`, `get`, `get_discussion`, `status`, `post_review` (comment), `reject` (close). **Never** `land` — triage does not merge. |
| [`pr-management-code-review`](../../skills/pr-management-code-review/SKILL.md) | `get`, `get_discussion`, `post_review` (approve / request-changes). |
| [`pr-management-quick-merge`](../../skills/pr-management-quick-merge/SKILL.md) | `list_open`, `get`, `status`, `post_review` (approve), `land` (on per-PR confirmation). |
| [`pr-management-mentor`](../../skills/pr-management-mentor/SKILL.md) | `get`, `get_discussion`, `post_review` (comment). |
| [`pr-management-stats`](../../skills/pr-management-stats/SKILL.md) | `list_open` (read-only queue metrics). |

`pr-management-triage` is refactored in this PR to name the contract
verbs and document the GitHub binding as the *resolution* of those
verbs (see its **Change-request contract binding** section). The
remaining `pr-management-*` skills continue to call `gh pr` directly;
their call sites resolve to the same GitHub adapter, and a later PR
routes their prose through the verbs the way this one does for triage.

## ASF defaults

| Project shape | `change_request.backend` | `land` resolution |
|---|---|---|
| GitHub-hosted (Airflow, most TLPs) | `github` | `gh pr merge` |
| JIRA + SVN | `jira-patch` | `svn patch` + `svn commit` via `tools/asf-svn/` |
| `dev@` `[PATCH]` workflow | `mail-patch` | `svn patch` + `svn commit` via `tools/asf-svn/` |

GitHub is the default because it is what the shipping `pr-management-*`
skills are tested against. The two SVN-first adapters exist so that a
JIRA-tracker or patch-by-mail project can adopt the same skills; both
route their terminal `land` through the project's declared
`contract:source-control` adapter rather than owning the commit.

## Configuration

Every adopter declares its change-request backend in
`projects/<project>/project.md` under the `change_request` block:

```yaml
# change_request — proposed-change review + merge gate
# ASF default: github (gh pr)
change_request:
  backend: github            # github | jira-patch | mail-patch | gitlab | gerrit | none
  land_via: forge            # forge (backend lands) | source-control (delegate to VCS adapter)
  review_channel: forge      # forge | jira-comment | mailing-list
  default_strategy: squash   # merge | squash | rebase — the strategy `land` requests
  gates:                     # which status signals block a land; omitted signals are advisory
    - checks
    - mergeable
```

Field-by-field:

- **`backend`** — names the adapter directory the skills resolve to.
  The ASF default is `github` (resolves to `tools/github/`).
  SVN-first adopters pick `jira-patch` or `mail-patch`; both set
  `land_via: source-control`.
- **`land_via`** — where the terminal `land` commits. `forge` (the
  GitHub default) means the backend both lands and closes;
  `source-control` means `land` delegates the commit to the
  project's `contract:source-control` adapter (`tools/asf-svn/` for
  ASF SVN) and only records the outcome on the review surface.
- **`review_channel`** — where review comments live: `forge` (PR
  threads), `jira-comment`, or `mailing-list`. Drives which surface
  `get_discussion` and `post_review` read/write.
- **`default_strategy`** — the merge strategy `land` requests.
  Backends that cannot honour it fall back and report which strategy
  they used.
- **`gates`** — the `status` signals that block a land. A backend
  that returns `checks: none` / `mergeable: unknown` for a listed
  gate degrades that gate to advisory (see `status` graceful
  degradation).

The contract does not constrain how an adapter implements any of
these — only that the settings are present and respected. Adapters
may add backend-specific sub-keys under `change_request.<backend>:`
(e.g. `change_request.jira_patch.attachment_field`,
`change_request.mail_patch.patch_subject_prefix`).

Adapter selection is **purely declarative**. The skill bodies do not
branch on `backend` — they call the verbs, and dispatch into the
adapter happens at the contract boundary. Adding `gitlab` later is a
new `tools/gitlab-mr/` directory, not a change to the skills.
