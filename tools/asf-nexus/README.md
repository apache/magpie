<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`tools/asf-nexus/`](#toolsasf-nexus)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# `tools/asf-nexus/`

**Capability:** contract:release-staging

**Kind:** implementation

**Vendor:** Nexus Repository Manager (ASF-hosted)

**Organization:** ASF

Read-only adapter for the **Nexus staging repository** — the half of an
ASF JVM release that `dist.apache.org` does not model. A JVM release
candidate is voted on in two places at once: the `dist/` tree carries
the voted source artefact (the [`tools/asf-svn`](../asf-svn/) side), and
the jars downstream consumers actually resolve come from a staging
repository at `repository.apache.org` that is later promoted to Maven
Central. This adapter implements **check 4** of
[apache/magpie#1173](https://github.com/apache/magpie/issues/1173):
verify that the staged repo is `closed` (not `open`), that its
coordinates and version match the RC under vote, and that every
artefact in it carries its `.asc` signature and checksums with a
complete companion set.

See [`tool.md`](tool.md) for the capability surface and the read-only
guarantee, [`operations.md`](operations.md) for the endpoint contract
(which paths are anonymous, which need credentials, and the exact
recipes), and [`staging-verification.md`](staging-verification.md) for
the classification rules the calling skill applies to the probe
output.

## Prerequisites

- **Runtime:** Bash / coreutils — this is a doc-only adapter; skills
  invoke `curl` (and `jq` where noted) per the recipes in
  [`operations.md`](operations.md). No Python, no other runtime.
- **CLIs:** `curl`, `jq` (optional — only the authenticated recipes
  parse JSON with it; the anonymous recipes only need `curl` and
  `grep`).
- **Credentials / auth:** none for the anonymous read paths
  (`/content/repositories/<staging-repo>/`). The authenticated
  staging-API reads (`/service/local/staging/...`) need ASF Nexus
  credentials; store them as a netrc-format file at
  `~/.config/apache-magpie/asf-nexus/netrc` (`chmod 600`) and read
  them with `curl --netrc-file`, so the secret never appears in
  argv — never a `-u user:pass` on the command line, and never in
  the project tree. `~/.config/` is denied to the sandboxed agent by
  design, so the authenticated recipes are for the RM's own
  terminal; a voter (or the sandboxed agent itself) runs the
  anonymous path and reports `STATE-UNVERIFIED` instead of failing
  anything.
- **Network:** `repository.apache.org` — read-only `GET`s only. The
  adapter never closes, drops, or promotes a staging repository, and
  never performs a write request of any kind.

## Configuration

`release-verify-rc` Step 6c sources the staging repository id from
`release-build.md § JVM artefact checks` → `nexus_staging_repo` (a
repository id such as `orgapachefoo-1024`, or the full
`content/repositories/<id>` URL), falling back to the planning issue
body when the RM passed `--post-to`. Non-ASF adopters leave the key
unset and the step skips cleanly — `repository.apache.org` is ASF
infrastructure and there is nothing for them to probe.

The adopter-facing configuration block is declared in
[`projects/_template/release-build.md`](../../plugins/magpie-setup/templates/release-build.md#jvm-artefact-checks).
