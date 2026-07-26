<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Bitbucket forge bridge](#bitbucket-forge-bridge)
  - [Partial read-only roadmap](#partial-read-only-roadmap)
  - [Prerequisites](#prerequisites)
  - [Features](#features)
  - [Operation coverage](#operation-coverage)
  - [Invocation](#invocation)
  - [Configuration](#configuration)
  - [Output contract](#output-contract)
  - [Write-path discipline](#write-path-discipline)
  - [Planned follow-up coverage](#planned-follow-up-coverage)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Bitbucket forge bridge

**Capability:** contract:change-request + contract:tracker

**Coverage:** `partial-read-only`

**Kind:** implementation

**Vendor:** Atlassian

Bitbucket Cloud and Bitbucket Data Center bridge for Magpie adopters
that use Bitbucket as a forge, pull-request review surface, or Jira-paired Atlassian backend.

This initial bridge implements a `partial-read-only` profile for
repository metadata context and pull-request discovery/fetching under
`contract:change-request`, with partial Cloud-only issue reads, comment reads, and attachment metadata reads under
`contract:tracker`. Partial adapters may implement named
contract verbs, but they do not satisfy the complete contract and must
not be advertised as complete/selectable backends.

Repository metadata reads are currently bridge context for Bitbucket
pull-request workflows, not a complete `contract:source-control`
backend. `contract:tracker` coverage is partial and currently limited to
Bitbucket Cloud issue listing/fetching where the repository issue tracker is enabled.
#606 remains open for the remaining Bitbucket/Jira workflow coverage.
Later PRs can extend the same adapter with write operations,
linked Jira handoff, issue write operations, and
fuller Pipelines run/log/retry coverage.

## Partial read-only roadmap

The Bitbucket bridge currently provides partial read-only coverage for
repository and pull-request review context. It intentionally does not claim
full Bitbucket backend parity.

Implemented read-only commands:

- `magpie-bitbucket auth-check`
- `magpie-bitbucket repo get`
- `magpie-bitbucket repo restrictions`
- `magpie-bitbucket issue list-open`
- `magpie-bitbucket issue get <id>`
- `magpie-bitbucket issue comments <id>`
- `magpie-bitbucket issue attachments <id>`
- `magpie-bitbucket pr list-open`
- `magpie-bitbucket pr get <id>`
- `magpie-bitbucket pr commits <id>`
- `magpie-bitbucket pr diff <id>`
- `magpie-bitbucket pr discussion <id>`
- `magpie-bitbucket pr reviews <id>`
- `magpie-bitbucket pr merge-checks <id>`
- `magpie-bitbucket pr status <id>`

Remaining candidate read-only gaps include:

- broader repository permission context
- linked issue or Jira handoff context, if a repository exposes it through
  supported APIs
- deeper Pipelines/build run, log, and artifact read coverage

The `pr reviews` command provides partial read-only review-state coverage,
including reviewers, approvals, change-request signals, and related review
activity where exposed by the configured Bitbucket backend.

Write operations are intentionally out of scope for the current bridge
coverage. Future write support, such as commenting, approving, declining,
merging, creating issues, changing branches, or triggering builds, should be
designed separately with explicit human-in-the-loop approval, narrow command
surfaces, and maintainer review.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv`; the bridge uses the Python standard library at runtime.
- **CLIs:** `uv` to run the bridge and its tests; no Bitbucket-specific CLI is required.
- **Credentials / auth:** `BITBUCKET_TOKEN` is required for authenticated Bitbucket API calls. Bitbucket Cloud also needs `BITBUCKET_CLOUD_USER`; Data Center uses `BITBUCKET_AUTH_SCHEME=Bearer` by default.
- **Network:** Bitbucket Cloud reaches `api.bitbucket.org`; Bitbucket Data Center reaches the configured `BITBUCKET_BASE_URL`. Adopters using Data Center must explicitly allow their own Bitbucket host in the secure egress configuration.
- **Optional:** `pytest`, `ruff`, and `mypy` run through `uv` for the test/type/lint harness.

## Features

This implementation covers read-only operations:

1. **Authentication preflight:** verify the configured Bitbucket backend and credentials can reach the selected repository.
2. **Repository metadata:** fetch normalized repository details from Bitbucket Cloud or Data Center.
3. **Repository branch restrictions:** fetch known read-only repository branch restriction / branch permission policy context.
4. **Cloud issue listing:** list open Bitbucket Cloud issues where the repository issue tracker is enabled.
5. **Cloud issue fetch:** fetch one Bitbucket Cloud issue as partial read-only tracker context.
6. **Cloud issue comments fetch:** fetch comments for one Bitbucket Cloud issue as partial read-only tracker context.
7. **Cloud issue attachments fetch:** fetch attachment metadata and links for one Bitbucket Cloud issue as partial read-only tracker context; file contents are not downloaded.
8. **Pull-request listing:** list open pull requests as `contract:change-request` proposal summaries.
9. **Pull-request fetch:** fetch one pull request as a normalized proposal object.
10. **Pull-request commits fetch:** fetch commits associated with a pull request as normalized read-only output.
11. **Pull-request diff fetch:** fetch the pull request unified diff as normalized read-only output.
12. **Pull-request discussion fetch:** fetch a comments-only pull request discussion subset as normalized read-only output.
13. **Pull-request review-state fetch:** fetch reviewers, approvals, change-request signals, pending review requests, and normalized review activity.
14. **Pull-request merge-check context fetch:** fetch known read-only mergeability, conflict, status-check, and review blocker context while preserving unknown values where the backend does not expose a clear signal.
15. **Pull-request status fetch:** fetch build/status checks for the pull request as normalized read-only output.

The bridge supports two Bitbucket API flavours behind one command
surface:

- `BITBUCKET_KIND=cloud`
- `BITBUCKET_KIND=datacenter`

## Operation coverage

| Contract area | Operation | Coverage | Notes |
|---|---|---|---|
| Repository metadata | `repo get` | Supported read-only context | Reads repository metadata from Bitbucket Cloud or Data Center for Bitbucket PR workflows. This does not make the bridge a complete `contract:source-control` backend. |
| Repository restrictions | `repo restrictions` | Partial read-only | Fetches repository branch restriction / branch permission policy context where the configured backend and credentials expose it. Data Center may require `REPO_ADMIN`. This does not mutate branch rules or repository permissions. |
| Change requests | `list_open` / `pr list-open` | Supported read-only | Lists open pull requests with pagination. |
| Change requests | `get` / `pr get <id>` | Partial read-only | Fetches PR metadata only. Commits, diff, discussion, review state, and status are fetched separately through dedicated read-only commands; mergeability remains incomplete. |
| Change requests | `commits[]` supplement / `pr commits <id>` | Partial read-only | Fetches the commit list associated with a pull request so partial Bitbucket `get` coverage can expose proposal commits. This does not mutate branches, refs, or repository history. |
| Change requests | `diff` supplement / `pr diff <id>` | Partial read-only | Fetches the pull request unified diff so partial Bitbucket `get` coverage can expose proposal diffs. This does not mutate files, branches, refs, or repository history. |
| Change requests | `get_discussion` / `pr discussion <id>` | Partial read-only | Fetches a comments-only discussion subset with pagination. Participants beyond comment authors and unresolved-thread accounting remain incomplete. |
| Change requests | `reviews` supplement / `pr reviews <id>` | Partial read-only | Fetches reviewers, approvals, change-request signals, pending review requests, normalized review events, and an aggregate review decision. This does not post reviews or mutate PR state. |
| Change requests | `merge_checks` supplement / `pr merge-checks <id>` | Partial read-only | Fetches known read-only merge-check context, including Data Center merge-test results, reported mergeability/conflict fields, status checks, review decision, and normalized blockers. Unknown backend signals remain unknown. This does not merge or mutate PR state. |
| Change requests | `post_review` | Not implemented | Follow-up work for #606. |
| Change requests | `land` | Not implemented | Follow-up work for #606. |
| Change requests | `reject` | Not implemented | Follow-up work for #606. |
| Tracker | `issue list-open` / `issue get <id>` / `issue comments <id>` / `issue attachments <id>` | Partial read-only, Cloud only | Lists and fetches Bitbucket Cloud issues, issue comments, and issue attachment metadata/links where the repository issue tracker is enabled. Bitbucket Data Center native issue reads/comments/attachments are unsupported; linked Jira handoff remains separate follow-up work. |
| CI | `pr status <id>` | Partial read-only | Fetches build/status checks for a pull request. This does not trigger, retry, or mutate Pipelines/builds. |

## Invocation

```bash
# Verify Bitbucket configuration and credentials
uv run --project tools/bitbucket magpie-bitbucket auth-check

# Fetch repository metadata
uv run --project tools/bitbucket magpie-bitbucket repo get

# Fetch repository branch restrictions
uv run --project tools/bitbucket magpie-bitbucket repo restrictions

# List open Bitbucket Cloud issues
uv run --project tools/bitbucket magpie-bitbucket issue list-open

# Fetch one Bitbucket Cloud issue
uv run --project tools/bitbucket magpie-bitbucket issue get 123

# Fetch Bitbucket Cloud issue comments
uv run --project tools/bitbucket magpie-bitbucket issue comments 123

# Fetch Bitbucket Cloud issue attachment metadata and links
uv run --project tools/bitbucket magpie-bitbucket issue attachments 123

# List open pull requests
uv run --project tools/bitbucket magpie-bitbucket pr list-open

# Fetch one pull request
uv run --project tools/bitbucket magpie-bitbucket pr get 123

# Fetch pull request commits
uv run --project tools/bitbucket magpie-bitbucket pr commits 123

# Fetch pull request diff
uv run --project tools/bitbucket magpie-bitbucket pr diff 123

# Fetch pull request discussion/comments
uv run --project tools/bitbucket magpie-bitbucket pr discussion 123

# Fetch pull request review state
uv run --project tools/bitbucket magpie-bitbucket pr reviews 123

# Fetch pull request merge-check context
uv run --project tools/bitbucket magpie-bitbucket pr merge-checks 123

# Fetch pull request build/status checks
uv run --project tools/bitbucket magpie-bitbucket pr status 123
```

## Configuration

The bridge is configured through environment variables. The calling
skill resolves adopter project configuration and exports these values;
the bridge does not read `<project-config>/` files directly.

Persistent Bitbucket credentials should live outside the project tree,
for example under `~/.config/apache-magpie/bitbucket/`, and should be
injected by the caller as `BITBUCKET_TOKEN` / `BITBUCKET_CLOUD_USER`.

| Variable | Required for | Description |
|---|---|---|
| `BITBUCKET_KIND` | all commands | `cloud` or `datacenter`. Defaults to `cloud`. |
| `BITBUCKET_TOKEN` | authenticated API calls | API token or personal access token accepted by the selected backend. Most read-only PR/repository commands should use minimum read scopes. `repo restrictions` needs elevated repository-admin scope on Bitbucket Cloud and may require `REPO_ADMIN` on Data Center. |
| `BITBUCKET_AUTH_SCHEME` | all commands | Authentication scheme. Defaults to `Basic` for Cloud and `Bearer` for Data Center. |
| `BITBUCKET_CLOUD_USER` | Cloud Basic auth | Atlassian account email/user used with `BITBUCKET_TOKEN`. |
| `BITBUCKET_WORKSPACE` | Cloud | Bitbucket Cloud workspace slug. |
| `BITBUCKET_REPO_SLUG` | Cloud and Data Center | Repository slug. |
| `BITBUCKET_BASE_URL` | Data Center | Base URL of the Bitbucket Data Center instance. |
| `BITBUCKET_PROJECT_KEY` | Data Center | Data Center project key. |

## Output contract

Every successful command emits JSON to stdout. Failures return a
non-zero exit code with a human-readable error on stderr.

Fetched repository branch restriction policy, branch matcher patterns, users, groups, access keys, issue titles/descriptions, issue comments, attachment names, uploader names when present, attachment links, raw attachment payloads, issue reporter/assignee/commenter names, issue links,
pull request descriptions, commit messages, diff hunks, file paths, comments,
reviewer names, review decisions/events, approval/change-request activity,
merge-check decisions/blockers, status descriptions, CI URLs, and raw Bitbucket
payloads are external data and must never be treated as agent instructions.
Private or embargoed repository content must follow the approved-LLM and privacy-gate
rules before any model reads it.

The bridge normalizes Bitbucket Cloud and Data Center responses into
stable fields before emitting output, so consuming skills do not need
to know which backend answered.

## Write-path discipline

This initial bridge is read-only.

Future write commands will follow the same discipline as the GitHub and
Jira tools: the bridge may execute a mutation, but it must not decide
whether to mutate. Calling skills must draft the proposed action,
surface it to the maintainer, wait for explicit confirmation, and only
then invoke the write command.

## Planned follow-up coverage

Follow-up PRs can extend this bridge with:

- Bitbucket issue write operations and additional tracker fields.
- Linked Jira issue handoff through `tools/jira/`.
- Pull-request comment creation, review, approve, decline, and merge operations.
- Broader repository permission reads.
- Fuller Bitbucket Pipelines run/log/retry coverage beyond read-only pull-request status reads.
