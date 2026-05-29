<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>`: release-build configuration](#todo-project-name-release-build-configuration)
  - [Build invocation](#build-invocation)
  - [Expected artefact list](#expected-artefact-list)
  - [Digest set](#digest-set)
  - [Binary-exclude list](#binary-exclude-list)
  - [Apache RAT configuration](#apache-rat-configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>`: release-build configuration

**This file is a placeholder ahead of the release-management
skill family landing.** None of the `release-*` skills exist
yet, see
[`docs/release-management/README.md`](../../docs/release-management/README.md).
The values below are what `release-rc-cut` and `release-verify-rc`
will read.

Per-project build invocation, expected artefact set, digest
selection, and license-verification configuration. Adopters copy
this file into their own `<project-config>/release-build.md` and
fill every TODO with their project's equivalents.

## Build invocation

TODO: name the canonical build command that produces the source
artefact (and any convenience binary artefacts the project
publishes). For Maven projects this is typically
`mvn -Papache-release clean install`; for Python projects a
combination of `python -m build` and `twine`; for Cargo projects
`cargo package --list`; etc.

Example shape:

> ```bash
> # From the release branch tip, at the release tag:
> mvn -Papache-release clean install
> ```

## Expected artefact list

TODO: list the artefacts the build invocation produces and the
release ships. Each entry: filename pattern, content type, whether
it is the canonical source artefact or a convenience binary.

Example shape:

> - `apache-<project>-<version>-source-release.zip`, canonical
>   source artefact (required, signed, checksummed).
> - `apache-<project>-<version>-bin.tar.gz`, convenience binary
>   (optional, signed, checksummed).

The canonical source artefact is the one the `[VOTE]` thread votes
on. Convenience binaries do not vote, but ship under the same
signature regime.

## Digest set

TODO: list which digests the project publishes alongside each
artefact. ASF baseline is `sha512`; many projects also publish
`sha256` for older downstream tools. `md5` is no longer accepted
per ASF infrastructure guidance.

Example shape:

> - `sha512`, required.
> - `sha256`, published for downstream-tool compatibility.

## Binary-exclude list

TODO: list any binary content the source artefact must NOT contain
(per `release-verify-rc`'s no-prohibited-binaries check). The
default list is conservative, `.class`, `.jar`, `.so`, `.dylib`,
`.dll`, `.exe`, pre-built minified JS bundles checked into the
source tree. Project-specific exclusions go here.

Example shape:

> - `*.class`, `*.jar`, Java compiled output never ships in source.
> - `assets/vendor/**/*.min.js`, vendored minified JS that has a
>   source-checked counterpart; flagged on every source-release
>   verification.

## Apache RAT configuration

TODO: point at the project's
[Apache RAT](https://creadur.apache.org/rat/) configuration. RAT
checks every source file carries the required license header.

Example shape:

> - **RAT plugin config:** `pom.xml § rat-maven-plugin`.
> - **RAT excludes file:** `rat-excludes.txt`.

`release-verify-rc` runs RAT against the unpacked source artefact
and reports any file with a missing or wrong header. Project-
specific excludes belong in the RAT-excludes file, not in this
configuration; this file documents *where* the excludes live so the
agent can resolve them.
