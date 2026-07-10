<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`tools/apache-projects/`](#toolsapache-projects)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `tools/apache-projects/`

**Capability:** contract:project-metadata

**Kind:** implementation

**MCP:** apache-projects — apache/comdev (mcp__apache-projects__*)

**Vendor:** ASF

**Organization:** ASF

ASF project-metadata substrate. Read-only, unauthenticated client
for the official `apache/comdev` `apache-projects-mcp` server, which
wraps the public `projects.apache.org/json` feeds (committee /
committer rosters, people + Apache IDs, podlings, releases, LDAP
groups, repositories). Used by `contributor-nomination` (Apache ID
verification, vendor-neutrality / employer context) and the
roster-resolution paths in the security skills. For ASF projects it
is a mandatory pre-flight prerequisite, installed from the latest
`main` of `apache/comdev`. See [`tool.md`](tool.md) for the
operation catalogue, setup, and the track-`main` install contract.

## Prerequisites

- **Runtime:** Node.js 20+ — the backing tool is the official `apache/comdev` `apache-projects-mcp` server (a Node.js package), run as `node .../index.js`. This directory ships no code of its own.
- **CLIs:** `git` (clone the `apache/comdev` checkout), `npm` (install the server's deps), `node` (run it).
- **Credentials / auth:** None — the server is read-only and unauthenticated; every field it returns is already public.
- **Network:** `projects.apache.org` (the public JSON feeds the server fetches at run time); `github.com` to clone and track `apache/comdev` at `main`.

## Configuration

Adopters select this backend through `<project-config>/project.md` or
their organization defaults under the `project_metadata` block. ASF
projects inherit `project_metadata.kind: apache-projects-mcp` from
`organizations/ASF/organization.md`; non-ASF projects normally set
`project_metadata.kind: none` and supply roster evidence directly.
