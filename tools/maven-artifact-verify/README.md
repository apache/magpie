<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [`maven-artifact-verify`](#maven-artifact-verify)
  - [The checks it implements](#the-checks-it-implements)
  - [Prerequisites](#prerequisites)
  - [How to use](#how-to-use)
  - [Wiring](#wiring)
  - [Boundary conditions](#boundary-conditions)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# `maven-artifact-verify`

**Capability:** substrate:release

**Harness:** agnostic

**Organization:** ASF

Verifies **locally staged JVM release-candidate artefacts** — the
`.pom` files, the main jars and their companion `-sources.jar` /
`-javadoc.jar` — the way `release-verify-rc` verifies a staged source
artefact today. Implements the blocking checks 1–3 proposed in
[apache/magpie#1173](https://github.com/apache/magpie/issues/1173);
the Nexus staging-repository check (check 4) is implemented by
[`tools/asf-nexus`](../asf-nexus/README.md) and `release-verify-rc`
Step 6c, and the informational checks (5–7) are later PRs on that
issue.

Until this tool exists, `release-verify-rc` handles a jar in exactly
one direction: as *contraband inside the source tree* (Step 6's
prohibited-binary baseline). The published jar — the artefact Maven
Central actually serves to users — is never opened or validated. This
tool closes that gap for the checks that [ASF Incubator distribution
policy](https://incubator.apache.org/guides/distribution.html) and
[Maven Central's publishing
requirements](https://central.sonatype.org/publish/requirements/) make
blocking.

## The checks it implements

1. **POM licence entry** — every staged `.pom` declares ALv2 in its
   `<licenses>` block, plus `<developers>` and `<scm>`. An element
   absent from the POM itself resolves against the chain of locally
   staged parent POMs (with cycle protection, up through
   grandparents): the first ancestor declaring the element is judged
   as-is, so a staged parent carrying a non-ALv2 licence fails the
   child too. `<scm>` resolves per field, the way Maven merges it: a
   child declaring only `<scm><tag>` still inherits `url` /
   `connection` from the nearest ancestor declaring them, and an
   empty or tag-only declaration never fails the child on its own. An
   element no staged ancestor declares when the chain
   ends at a POM with no `<parent>` — including a POM with no
   `<parent>` at all — is a `FAIL`, the same judgement Maven Central
   applies. `INHERITED-UNVERIFIED` — a warning that names what to
   verify, never a failure of a correct POM — is reserved for a chain
   that cannot be fully resolved offline. A cyclic parent chain is a
   `FAIL` instead: Maven refuses to build one, so it cannot be a
   correct POM inheriting from the ASF parent.
2. **Incubator disclaimer in `<description>`** — podlings only
   (`--podling`). Accepts the standard disclaimer text and the
   `DISCLAIMER-WIP` variant, tolerating whitespace and line-wrapping
   differences inside the XML element. Matching is deliberately keyed
   to the core both texts share ("is an effort undergoing incubation
   at The Apache Software Foundation … has yet to be fully endorsed by
   the ASF") rather than to one full verbatim text. An inherited
   description is judged the same way as a local one.
3. **Companion jars** — for every main jar, both `-sources.jar` and
   `-javadoc.jar` exist and each carries its own `.asc` signature and
   checksum files (the digest set is configurable, default `sha512`).
   Checksum files are verified against the companion jar's actual
   bytes (`hashlib`, still offline); `.asc` signatures are checked
   for presence only — offline signature verification needs GPG and
   the release key, which `release-verify-rc` Step 2 runs against the
   main artefacts, and the Step 6b recipe extends to the companions.

The overall `status` is `FAIL` when any check fails, `WARN` when only
`INHERITED-UNVERIFIED` results remain, `PASS` otherwise, and `SKIP`
when the staged set contains no `.pom` and no `.jar` at all — a
non-JVM project's RC runs the tool and skips cleanly.

## Prerequisites

- **Runtime** — Python 3.11+ (stdlib only; can run as
  `python3 -m maven_artifact_verify` or via `uv run --project`).
- **CLIs** — None beyond the runtime.
- **Credentials / auth** — None.
- **Network** — fully offline; reads local files only.

## How to use

```bash
# From a staged RC directory (e.g. dist/dev/<project>/<rc-tag>/):
uv run --project tools/maven-artifact-verify maven-artifact-verify \
  <staged-dir> --digests sha512 [--podling]
```

`--podling` gates check 2; pass it when the RC's source artefact ships
a `DISCLAIMER` / `DISCLAIMER-WIP` file (the same signal a voter checks
by hand today). Prints one JSON report on stdout; exit code 0 unless a
check `FAIL`ed (then 1) or the arguments are wrong (2).

## Wiring

| Skill | Uses |
|---|---|
| `release-verify-rc` | Step 6b emits the command above when the staged listing contains jars and classifies the RC from its JSON report |

## Boundary conditions

Encoded from the issue's boundary-conditions section, so the tool does
not fail correct releases:

- `packaging=pom` modules have no jar and are exempt from check 3
  (they still get checks 1 and 2).
- Placeholder companion jars are a Maven-Central-sanctioned pattern;
  check 3 only verifies presence, signatures and checksums, and never
  opens a jar to judge its content (that is informational check 7, a
  later PR).
- Classified jars (`-tests`, `-shaded`, `-linux-x86_64`, …) are
  neither mains nor companions: a jar whose classifier is not
  `sources`/`javadoc` and that no staged POM declares is reported in
  `unmatched_jars`, never failed in either direction.
- The `-tests` jar of a project does not need its own sources/javadoc
  companions; only POM-declared main jars do.
- Inherited POM elements: `<licenses>`, `<developers>`, `<scm>` and
  `<description>` are commonly inherited from the ASF parent POM
  (`org.apache:apache`). Resolution walks the locally staged parent
  chain (cycle-protected, up through grandparents) — the tool is
  offline by design and never fetches a parent from a remote
  repository. A complete staged chain that supplies the element
  decides `PASS`/`FAIL` on its own content; a complete chain that
  supplies nothing — like a POM with no `<parent>` at all — is a hard
  `FAIL`; and only a chain that cannot be fully resolved offline
  falls back to `INHERITED-UNVERIFIED` rather than guessing.

## Tests

```bash
uv run --project tools/maven-artifact-verify pytest
```

The fixtures build synthetic POMs and jars (plain strings and
`zipfile` output) at test time, so the repository carries no binary
test blobs.
