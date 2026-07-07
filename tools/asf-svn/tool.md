<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Tool: ASF SVN](#tool-asf-svn)
  - [What this tool provides](#what-this-tool-provides)
  - [When to use this tool alongside another](#when-to-use-this-tool-alongside-another)
  - [Centralized-model note](#centralized-model-note)
  - [Write-path confirmation](#write-path-confirmation)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Tool: ASF SVN

This directory documents the **ASF SVN** tool adapter — the set of
capabilities the skills use when the adopting project declares ASF SVN
as its source-control and/or release-distribution backend.

A project opts into this tool by naming it in its manifest under
*Tools enabled*. For the adopting project see
[`../../<project-config>/project.md`](../../<project-config>/project.md#tools-enabled).

## What this tool provides

ASF SVN is not a forge: it has no issue tracker, no pull-request
surface, and no project board. The capabilities it *does* provide
map to the following reference files:

| Capability | File | What it covers |
|---|---|---|
| Source control (VCS) | [`source-control.md`](source-control.md) | The version-control operations the dev-loop skills run against a Subversion working copy — checkout/update/diff/status/log/blame/file-at-revision/commit — with centralized-model divergences documented against the abstract Git binding |
| CLI operations | [`operations.md`](operations.md) | `svn` CLI recipes the skills invoke, the canonical `svn.apache.org/repos/asf/<project>` layout (trunk / branches / tags), and the credentials auth pre-flight every skill's Step 0 runs |
| Release distribution | [`release-distribution.md`](release-distribution.md) | `dist.apache.org`-aware helpers: stage a release candidate under `dist/dev/<project>`, promote to `dist/release/<project>` on a successful vote, prune old releases per the ASF 2-release retention policy |
| Authorization / roster | [`authorization.md`](authorization.md) | Resolve ASF committer and PMC membership from `asf-authorization-template`, LDAP groups, and the `apache-projects` MCP roster so skills know who may commit or cut a release |
| Website / docs publishing (optional) | [`publishing.md`](publishing.md) | For projects whose site lives in SVN: the svnpubsub / staging publish flow, which reduces to a confirmed `svn commit` to the site path. Unconfigured for projects that publish their site another way |

Capabilities **not** provided by this tool (because SVN is not a
forge):

- Issue tracker (body fields, labels, lifecycle labels, comments) — pair
  with [`tools/github`](../github/) or [`tools/jira`](../jira/) for these.
- Project board / Projects V2 — pair with a forge tool.
- Pull-request surface — SVN uses direct commits to the trunk (or
  branches); patch-based review flows are handled outside SVN.

## When to use this tool alongside another

The source-control capability and the release-distribution capability
are **separable from each other and from any forge tool**:

- A project on **GitHub + dist.apache.org** (the most common ASF
  setup) enables `tools/github` for issues / PRs / source control and
  `tools/asf-svn` only for release distribution. The `dist.*` recipes
  in `release-distribution.md` are the operative part.
- A project with **source on svn.apache.org** enables `tools/asf-svn`
  for source control (the binding in `source-control.md`) and whatever
  tracker tool it uses for issues.
- A project on **svn.apache.org + dist.apache.org** enables
  `tools/asf-svn` for both capabilities and pairs with a tracker tool
  for issues.

Declare the mix in the project manifest under *Tools enabled* — one
row per capability, naming the tool that fulfils it:

```yaml
tools_enabled:
  source_control: asf-svn       # or: github
  release_distribution: asf-svn
  website_publishing: asf-svn   # optional; omit if the site is not in SVN
  tracker: github               # or: jira
```

## Centralized-model note

SVN is a **centralized** VCS. Skills that assume a distributed model
(local commits, cheap branches, `fetch`/`push` split) must adapt when
this tool is in use. The concrete divergences are documented in
[`source-control.md`](source-control.md):

- There are no local commits: `svn commit` goes directly to the server.
- Branches and tags are directory copies on the server
  (`trunk/`, `branches/<name>/`, `tags/<name>/`), not first-class
  refs.
- There is no `fetch`/`push` split: `svn update` synchronises the
  working copy with the server.
- `git worktree` has no direct equivalent: multiple working copies are
  created with `svn checkout` into separate directories.

## Write-path confirmation

All write-path operations (`svn commit`, `svnmucc`, dist promotion,
dist prune) stay gated on explicit user confirmation in the calling
skill, exactly as the GitHub tracker write paths are. This tool
documents *what* the command is; the skill enforces *whether* it runs.
