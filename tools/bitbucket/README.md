<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Bitbucket forge bridge](#bitbucket-forge-bridge)
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

**Capability:** contract:change-request

**Coverage:** `partial-read-only`

**Kind:** implementation

**Vendor:** Atlassian

Bitbucket Cloud and Bitbucket Data Center bridge for Magpie adopters
that use Bitbucket as a forge, pull-request review surface, or Jira-paired Atlassian backend.

This initial bridge implements a `partial-read-only` profile for
repository metadata context and pull-request discovery/fetching under
`contract:change-request`. Partial adapters may implement named
contract verbs, but they do not satisfy the complete contract and must
not be advertised as complete/selectable backends.

Repository metadata reads are currently bridge context for Bitbucket
pull-request workflows, not a complete `contract:source-control`
backend. `contract:tracker` is also intentionally absent until
Bitbucket issue operations or linked Jira handoff coverage exist.
#606 remains open for the remaining Bitbucket/Jira workflow coverage.
Later PRs can extend the same adapter with write operations,
Bitbucket Issues, linked Jira handoff, branch permissions, and
Pipelines status reads.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv`; the bridge uses the Python standard library at runtime.
- **CLIs:** `uv` to run the bridge and its tests; no Bitbucket-specific CLI is required.
- **Credentials / auth:** `BITBUCKET_TOKEN` is required for authenticated Bitbucket API calls. Bitbucket Cloud also needs `BITBUCKET_CLOUD_USER`; Data Center uses `BITBUCKET_AUTH_SCHEME=Bearer` by default.
- **Network:** Bitbucket Cloud reaches `api.bitbucket.org`; Bitbucket Data Center reaches the configured `BITBUCKET_BASE_URL`. Adopters using Data Center must explicitly allow their own Bitbucket host in the secure egress configuration.
- **Optional:** `pytest`, `ruff`, and `mypy` run through `uv` for the test/type/lint harness.

## Features

This first implementation covers read-only operations:

1. **Authentication preflight:** verify the configured Bitbucket backend and credentials can reach the selected repository.
2. **Repository metadata:** fetch normalized repository details from Bitbucket Cloud or Data Center.
3. **Pull-request listing:** list open pull requests as `contract:change-request` proposal summaries.
4. **Pull-request fetch:** fetch one pull request as a normalized proposal object.

The bridge supports two Bitbucket API flavours behind one command
surface:

- `BITBUCKET_KIND=cloud`
- `BITBUCKET_KIND=datacenter`

## Operation coverage

| Contract area | Operation | Coverage | Notes |
|---|---|---|---|
| Repository metadata | `repo get` | Supported read-only context | Reads repository metadata from Bitbucket Cloud or Data Center for Bitbucket PR workflows. This does not make the bridge a complete `contract:source-control` backend. |
| Change requests | `list_open` / `pr list-open` | Supported read-only | Lists open pull requests with pagination. |
| Change requests | `get` / `pr get <id>` | Partial read-only | Fetches PR metadata only. Discussion, commits, diffs, checks, review state, and mergeability are not complete yet. |
| Change requests | `get_discussion` | Not implemented | Follow-up work for #606. |
| Change requests | `post_review` | Not implemented | Follow-up work for #606. |
| Change requests | `land` | Not implemented | Follow-up work for #606. |
| Change requests | `reject` | Not implemented | Follow-up work for #606. |
| Tracker | issue operations | Not implemented | `contract:tracker` remains absent until Bitbucket issue operations or linked Jira handoff coverage exist. |
| CI | Pipelines status | Not implemented | Follow-up work for #606. |

## Invocation

```bash
# Verify Bitbucket configuration and credentials
uv run --project tools/bitbucket magpie-bitbucket auth-check

# Fetch repository metadata
uv run --project tools/bitbucket magpie-bitbucket repo get

# List open pull requests
uv run --project tools/bitbucket magpie-bitbucket pr list-open

# Fetch one pull request
uv run --project tools/bitbucket magpie-bitbucket pr get 123
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
| `BITBUCKET_TOKEN` | authenticated API calls | API token or personal access token accepted by the selected backend. For Bitbucket Cloud, use minimum read scopes for repositories and pull requests. |
| `BITBUCKET_AUTH_SCHEME` | all commands | Authentication scheme. Defaults to `Basic` for Cloud and `Bearer` for Data Center. |
| `BITBUCKET_CLOUD_USER` | Cloud Basic auth | Atlassian account email/user used with `BITBUCKET_TOKEN`. |
| `BITBUCKET_WORKSPACE` | Cloud | Bitbucket Cloud workspace slug. |
| `BITBUCKET_REPO_SLUG` | Cloud and Data Center | Repository slug. |
| `BITBUCKET_BASE_URL` | Data Center | Base URL of the Bitbucket Data Center instance. |
| `BITBUCKET_PROJECT_KEY` | Data Center | Data Center project key. |

## Output contract

Every successful command emits JSON to stdout. Failures return a
non-zero exit code with a human-readable error on stderr.

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

- Bitbucket issue read/write operations, which will add tracker coverage.
- Linked Jira issue handoff through `tools/jira/`.
- Pull-request comment, review, approve, decline, and merge operations.
- Branch restriction and permission reads.
- Bitbucket Pipelines status reads for change-request `status`.
