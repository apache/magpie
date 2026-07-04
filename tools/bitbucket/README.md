<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Bitbucket forge bridge](#bitbucket-forge-bridge)
  - [Prerequisites](#prerequisites)
  - [Features](#features)
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

**Kind:** implementation

**Vendor:** Atlassian

Bitbucket Cloud and Bitbucket Data Center bridge for Magpie adopters
that use Bitbucket as a forge, pull-request review surface, or Jira-paired Atlassian backend.

This initial bridge provides a read-only foundation for repository
metadata and pull-request discovery/fetching. It is not a complete
`contract:change-request` backend yet; #606 remains open for the
remaining Bitbucket/Jira workflow coverage. Later PRs can extend the
same adapter with write operations, Bitbucket Issues, linked Jira
handoff, branch permissions, and Pipelines status reads.

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
