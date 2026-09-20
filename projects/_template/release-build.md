<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>`: release-build configuration](#todo-project-name-release-build-configuration)
  - [Source archive](#source-archive)
  - [Build invocation](#build-invocation)
  - [Expected artefact list](#expected-artefact-list)
  - [Digest set](#digest-set)
  - [Reproducibility checks](#reproducibility-checks)
  - [Binary-exclude list](#binary-exclude-list)
  - [Apache RAT configuration](#apache-rat-configuration)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>`: release-build configuration

Per-project source-archive recipe, build invocation, expected
artefact set, digest selection, reproducibility checks, and
license-verification configuration. Read by `release-rc-cut` and
`release-verify-rc` (see
[`docs/release-management/README.md`](../../docs/release-management/README.md)).
Adopters copy this file into their own
`<project-config>/release-build.md` and fill every TODO with their
project's equivalents.

## Source archive

The canonical source artefact is the one the `[VOTE]` votes on.
By default it is **not** produced by the project's build tool but
exported straight from the tagged git tree with `git archive`,
which packs only tracked files and honours the `export-ignore`
attributes in the repository's root `.gitattributes`. The
framework's [`reproducible-archive`](../../tools/reproducible-archive/README.md)
tool wraps that export and applies every rule from
[reproducible-builds.org § Archive metadata](https://reproducible-builds.org/docs/archives/)
(one `SOURCE_DATE_EPOCH` mtime, sorted members, uid/gid 0,
`a=rX,u+w` modes, no PAX `atime`/`ctime`, `gzip -n`, `zip -X`), so a
voter rebuilding from the tag gets byte-identical bytes. See
[`docs/release-management/reproducibility.md`](../../docs/release-management/reproducibility.md).

| Key | Value | Notes |
|---|---|---|
| `source_archive_method` | `git-archive` | `git-archive` (default; `release-rc-cut` emits `repro-archive build`) or `custom` (the source artefact comes out of `build_command` below and `.gitattributes` is not consulted) |
| `source_archive_format` | `tar.gz` | `tar.gz` or `zip` |
| `source_archive_prefix` | `apache-<project>-<version>` | top-level directory inside the archive |
| `export_ignore_reviewed` | *(unset)* | set to the `<version>` at which the first-release `.gitattributes` review (`release-prepare prep` Step 2f) was completed; while unset, `release-rc-cut` blocks on an unreviewed archive |

**What to `export-ignore`.** VCS, CI and editor metadata that a
source consumer never needs (`.github/workflows/`,
`.pre-commit-config.yaml`, linter configs, `.idea/`, agent-view relay
symlinks). **Never** exclude `LICENSE`, `NOTICE`, `DISCLAIMER`
(incubating), the build descriptors, the RAT excludes file, or any
path a shipped file links to. `release-prepare prep` runs a guided
review of every top-level path on the first release and proposes the
entries with a rationale comment each; `release-verify-rc` Step 7
fails the RC if an exclusion strips a still-referenced path.

## Build invocation

TODO: name the canonical build command that produces any
**convenience binary** artefacts the project publishes (and the
source artefact too, when `source_archive_method: custom`). For
Maven projects this is typically `mvn -Papache-release clean install`;
for Python projects `python -m build`; for Cargo projects
`cargo package`; etc. Leave it empty for a source-only project.

For a reproducible binary build, pass the tag's `SOURCE_DATE_EPOCH`
through (`repro-archive epoch --ref <tag>`) so embedded timestamps
are fixed, and apply the build-tool equivalents of the archive rules
(`ARFLAGS=Dcvr` / `ranlib -D` for static libraries, `gzip -n`, a
pinned toolchain). See § Reproducibility checks below.

Example shape:

> ```bash
> # From the release branch tip, at the release tag:
> export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct <version>-<rcN>)"
> mvn -Papache-release -Dproject.build.outputTimestamp="${SOURCE_DATE_EPOCH}" clean install
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

## Reproducibility checks

Optional checks that `release-rc-cut` (Step 2b, RM self-check) and
`release-verify-rc` (Step 9, any voter) run to confirm the staged
artefacts are a function of the tag alone. Per
[`PRINCIPLES.md` § 11](../../PRINCIPLES.md#11-releases-are-reproducible-from-signed-source),
byte-identical output is required where the toolchain permits it and
a documented verification path is required where it does not.

| Key | Value | Allowed values |
|---|---|---|
| `reproducibility_source` | `on` | `on` (default when `source_archive_method: git-archive`) — rebuild from the tag with `repro-archive build`, `repro-archive compare` against the staged artefact; `off` |
| `reproducibility_binaries` | `off` | `off` (default; source-only projects), `byte-identical` (rebuild with `binary_rebuild_command`, sha512 must match), `documented-divergence` (run `binary_verification_command`; differences outside `known_divergences` fail) |
| `binary_rebuild_command` | *(unset)* | command that rebuilds every convenience binary from the tag; `SOURCE_DATE_EPOCH` is exported before it runs |
| `binary_verification_command` | *(unset)* | for `documented-divergence`: a command that compares a rebuilt binary with the staged one and prints the differing paths (e.g. `diffoscope`) |
| `known_divergences` | *(empty)* | for `documented-divergence`: paths or patterns that are expected to differ, one per line, each with the reason |

An ASF adopter that wants
[automated release signing](https://infra.apache.org/release-signing.html#automated-release-signing)
must run with `reproducibility_source: on` and, for every binary it
signs, `reproducibility_binaries: byte-identical` — the policy requires
artefacts that "can be built reproducibly" and a validation step on
trusted hardware that confirms them "bit-by-bit identical" before
publication. In that mode the checks are mandatory and
`release-promote` refuses to promote without the recorded validation.

## Binary-exclude list

TODO: configure `release-verify-rc` Step 6's prohibited-binary check.

The skill always scans a **fixed baseline**: `.class`, `.jar`,
`.so`, `.dylib`, `.dll`, `.exe`, `.pyc`, and `__pycache__`
directories. List here:

1. **Additional prohibited globs** the source artefact must also not
   contain (appended to the Step 6 `find` beyond the baseline).
2. **Known-accepted exceptions** — specific paths that match a
   prohibited pattern but must ship; Step 6 classifies those as
   `EXPECTED-BINARY` rather than `PROHIBITED-BINARY`.

Example shape:

> - `assets/vendor/**/*.min.js` — additional prohibited glob
>   (vendored minified JS; flagged on every source-release
>   verification).
> - `third-party/some-native.so` — known-accepted exception (ships
>   with a documented source counterpart).

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
