<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/asf-svn/`](#toolsasf-svn)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/asf-svn/`

**Capability:** contract:source-control

**Organization:** ASF

ASF SVN tool adapter — the Subversion counterpart to
[`tools/github/`](../github/). Where the GitHub tool covers forge
issues, project boards, and Git-backed source control, this adapter
covers the SVN surfaces that every ASF project uses regardless of
where its source code lives:

- **SVN source control** ([`source-control.md`](source-control.md)) —
  the VCS binding for `svn.apache.org`-hosted working copies, with
  centralized-model divergences documented against the abstract
  contract in `tools/github/source-control.md`.
- **SVN operations** ([`operations.md`](operations.md)) — `svn` CLI
  recipes and the canonical `svn.apache.org/repos/asf/<project>`
  layout (trunk / branches / tags).
- **Release distribution** ([`release-distribution.md`](release-distribution.md)) —
  `dist.apache.org`-aware helpers: stage a candidate under
  `dist/dev/<project>`, promote to `dist/release/<project>` on a
  successful vote, and prune old releases per ASF policy. This is the
  ASF-specific payoff — `dist.apache.org` is SVN for every ASF
  project, so even a GitHub-hosted project needs this adapter to
  steward its release flow.
- **Authorization / roster** ([`authorization.md`](authorization.md)) —
  resolve committer and PMC membership from the ASF authorization
  model (`asf-authorization-template`, LDAP groups) via the
  [`apache-projects`](../apache-projects/) MCP, so skills know who may
  commit or cut a release.
- **Website / docs publishing** (optional)
  ([`publishing.md`](publishing.md)) — for projects that publish their
  site through SVN (svnpubsub / staging), a publish helper that reduces
  to a confirmed `svn commit` to the site path.
- **Tool overview** ([`tool.md`](tool.md)) — the full capability table
  and guidance on when to combine this adapter with other tools.

A project opts into this tool by naming it in its manifest under
*Tools enabled*. It can be combined freely with other tool adapters —
for example: GitHub issues + `asf-svn` source control + `asf-svn`
release distribution is a valid mix for a GitHub-hosted ASF project
that ships through `dist.apache.org`.

## Prerequisites

- **Runtime:** Bash / coreutils — this is a doc-only adapter; skills
  invoke the `svn` binary and standard POSIX utilities directly; no
  local package.
- **CLIs:** `svn` (Apache Subversion 1.14+), `svnmucc` (optional,
  used for atomic multi-URL operations in release promotion), `jq`
  (for parsing `svn info --xml` and roster JSON from
  `projects.apache.org`).
- **Credentials / auth:** A cached SVN credential with write access to
  the target repository — every skill's Step 0 runs the auth
  pre-flight in [`operations.md#authentication`](operations.md#authentication).
  Read-only operations (checkout, log, diff) do not require
  credentials for world-readable repos.
- **Network:** `svn.apache.org` (ASF project source), `dist.apache.org`
  (ASF release distribution — SVN over HTTPS); read operations are
  offline after the initial checkout except for `svn update`.
- **Optional:** `apache-projects` MCP ([`tools/apache-projects/`](../apache-projects/))
  for roster lookups against `projects.apache.org` — used by
  [`authorization.md`](authorization.md) when LDAP is not directly
  queryable from the agent environment.

## Configuration

An adopting project enables this tool per capability in its
[`<project-config>/project.md`](../../projects/_template/project.md)
manifest under *Tools enabled* — one row per capability, naming
`asf-svn` for the capabilities it fulfils (see
[`tool.md`](tool.md#when-to-use-this-tool-alongside-another) for the
combination rules):

| Config key | Value | Meaning |
|---|---|---|
| `tools_enabled.source_control` | `asf-svn` | SVN working copies on `svn.apache.org` (else `github` / another VCS tool) |
| `tools_enabled.release_distribution` | `asf-svn` | releases ship through `dist.apache.org` (required for every ASF project) |
| `tools_enabled.website_publishing` | `asf-svn` | *optional* — set only if the project's site lives in SVN (svnpubsub); omit otherwise |
| `tools_enabled.tracker` | `github` / `jira` / … | not provided by this tool — SVN is not a forge; pair with a tracker tool |

The concrete project name, SVN repository URLs, and `dist` paths are
substituted from the adopter's `<project-config>` at run time; this
adapter carries only placeholders (`<project>`, `<asf-id>`).
