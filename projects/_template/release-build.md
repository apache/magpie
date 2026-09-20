<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>`: release-build configuration](#todo-project-name-release-build-configuration)
  - [Source archive](#source-archive)
  - [Build invocation](#build-invocation)
  - [Convenience artefacts](#convenience-artefacts)
  - [Source-tree validators](#source-tree-validators)
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

TODO: name the build command that produces the **source artefact**
when `source_archive_method: custom` (a project whose source release is
assembled by its build tool rather than exported from the tag, e.g.
`mvn -Papache-release clean install` with the assembly plugin). Leave
it empty when the source archive comes from `git-archive` (the
default) — the convenience artefacts, if any, are declared per
artefact under § Convenience artefacts, not here.

Whatever runs here runs at the release tag with the tag's
`SOURCE_DATE_EPOCH` exported (`repro-archive epoch --ref <tag>`), so
embedded timestamps are fixed.

Example shape:

> ```bash
> # From the release branch tip, at the release tag:
> export SOURCE_DATE_EPOCH="$(git log -1 --format=%ct <version>-<rcN>)"
> mvn -Papache-release -Dproject.build.outputTimestamp="${SOURCE_DATE_EPOCH}" clean install
> ```

## Convenience artefacts

Optional, and **project-specific by nature**: the framework knows how
to export, sign, verify and promote a source archive, but what a
project ships *besides* the source — a binary tarball, wheels, jars,
a container image, a Helm chart, an npm package — and where that goes
is the project's own decision. Declare each one here; every
`release-*` skill reads the list and emits the project's own
commands at the right lifecycle step. Leave the list empty for a
source-only project and the skills say so instead of guessing.

Per [release-policy § what must every ASF release contain](https://www.apache.org/legal/release-policy.html#what-must-every-release-contain)
the **source package is the release**; convenience artefacts are
compiled from it for users who will not build from source, are
signed and checksummed under the same regime, and are published only
after the source vote passes. **A convenience artefact is "good" only
if it is demonstrably built from the voted source**: a voter cannot
review a binary, so the one check that establishes what it contains
is rebuilding it from the tag and comparing — bit-for-bit
(`byte-identical`) or with every difference explained
(`documented-divergence`). An artefact that cannot be reproduced
either way is not ready to publish, whatever the vote said about the
source. That is why each entry carries its own reproducibility mode
and why `release-promote` refuses to emit a publish command for an
artefact whose `release-verify-rc` rebuild did not reproduce.

One entry per artefact:

```yaml
convenience_artefacts:
  - name: apache-<project>-<version>-bin.tar.gz     # filename as staged; <version> is rendered
    kind: binary-tarball          # binary-tarball | wheel | sdist | jar | container-image | helm-chart | npm-package | other
    build_command: |              # run at the release tag, SOURCE_DATE_EPOCH exported; must be deterministic
      mvn -Papache-release -Dproject.build.outputTimestamp="${SOURCE_DATE_EPOCH}" -DskipTests clean package
    staging: dist-dev             # dist-dev (alongside the source, default) | atr | registry-staging
    stage_command: null           # registry-staging only, e.g. `twine upload -r testpypi …`, `mvn nexus-staging:deploy`, `docker push <registry>/<image>:<version>-rcN`
    reproducibility: byte-identical   # byte-identical | documented-divergence (default: reproducibility_binaries)
    verification_command: null    # documented-divergence only, e.g. `diffoscope <staged> <rebuilt>`
    known_divergences: []         # documented-divergence only: path/pattern + reason, one per line
    vote_included: false          # true = the [VOTE] explicitly covers this artefact too (the source is always voted on)
    publish_channel: dist-release # dist-release | pypi | maven-central | container-registry | helm-repo | npm | github-release | other
    publish_command: null         # run by the RM after the vote, e.g. `twine upload dist/*`, `mvn nexus-staging:release`, `docker push …`; dist-release needs none (promoted with the source)
```

How each skill uses the list:

| Skill | Uses |
|---|---|
| `release-rc-cut` | Step 2 emits each `build_command` after the source archive, under the same `SOURCE_DATE_EPOCH`; Step 2b emits the per-artefact rebuild-and-compare self-check; Sections 3–4 sign and checksum every artefact; Step 3 emits `stage_command` for `registry-staging` entries |
| `release-verify-rc` | Step 9 rebuilds every artefact and compares per its `reproducibility` mode — the check that decides whether the artefact is good |
| `release-vote-draft` | Lists the artefacts, where each is staged, which are `vote_included`, and how to rebuild-and-compare them |
| `release-promote` | After the source promotion and the final tag, emits each `publish_command` — only for artefacts whose verify-rc rebuild reproduced |
| `release-announce-draft` | Names the channels the artefacts were published to |

Keep `expected_artefacts` (below) in sync: it is the flat list of
filenames the RC stages (source + every convenience artefact whose
`staging` is `dist-dev` or `atr`).

## Source-tree validators

Optional. Commands `release-verify-rc` Step 7 runs from the unpacked
source archive to confirm that every internal reference resolves
(links, symlink targets, generated indexes) after `export-ignore`
stripped what it strips. Leave empty when the project ships no such
checks; Step 7 then runs only the dangling-symlink scan.

Example shape:

> ```yaml
> source_tree_validators:
>   - "uv run --project tools/symlink-lint symlink-lint ."
>   - "uv run --project tools/skill-and-tool-validator skill-and-tool-validate"
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
| `reproducibility_binaries` | `off` | the default `reproducibility` mode for entries under § Convenience artefacts that do not set their own: `off` (no convenience artefacts, or checks disabled), `byte-identical` (rebuild with the entry's `build_command`, bytes must match), `documented-divergence` (run the entry's `verification_command`; differences outside its `known_divergences` fail) |

A project with convenience artefacts should run them at
`byte-identical` wherever the toolchain allows, and at
`documented-divergence` — with the divergences written down — where
it does not; `off` means the artefacts are published on trust, which
[`PRINCIPLES.md` § 11](../../PRINCIPLES.md#11-releases-are-reproducible-from-signed-source)
does not accept as a steady state.

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
