<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie: release build configuration](#apache-magpie-release-build-configuration)
  - [Source archive](#source-archive)
  - [Build invocation](#build-invocation)
  - [Expected artefact list](#expected-artefact-list)
  - [Digest set](#digest-set)
  - [Reproducibility checks](#reproducibility-checks)
  - [Binary-exclude list](#binary-exclude-list)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie: release build configuration

Build invocation, expected artefact set, and digest selection the
`release-rc-cut` and `release-verify-rc` skills read for a Magpie
release. Template: [`projects/_template/release-build.md`](../_template/release-build.md).

Magpie is a source-first project (skills, docs, and Python tooling).
**The source package is the release** per
[release-policy § what is a release](https://www.apache.org/legal/release-policy.html#release-definition).
Magpie ships **no convenience binaries** — the signed source artefact is
the only release artefact.

## Source archive

The canonical source artefact is a reproducible export of the tagged
tree — no VCS metadata, no build output. **Never `zip -r` a working
directory**: that captures `__pycache__/*.pyc` and other test cruft and
produces a non-reproducible artefact (this was the rc1 `-1`). The
export is `git archive` (tracked files at the tag only, honouring the
`export-ignore` rules in [`.gitattributes`](../../.gitattributes))
wrapped by the framework's own
[`reproducible-archive`](../../tools/reproducible-archive/README.md)
tool, which applies every
[reproducible-builds.org archive rule](https://reproducible-builds.org/docs/archives/)
so a voter rebuilding from the tag gets byte-identical bytes regardless
of their `git` version.

| Key | Value |
|---|---|
| `source_archive_method` | `git-archive` |
| `source_archive_format` | `zip` |
| `source_archive_prefix` | `apache-magpie-<version>` |
| `export_ignore_reviewed` | `0.1.0` — reviewed on the `0.1.0-rc2` `[VOTE]` thread; the per-entry rationale lives in [`.gitattributes`](../../.gitattributes) and [`docs/source-release-contents.md`](../../docs/source-release-contents.md) |

```bash
# From the release tag <version>-rcN:
uv run --project tools/reproducible-archive repro-archive build \
  --ref "<version>-rcN" --format zip \
  --prefix "apache-magpie-<version>" \
  -o "apache-magpie-<version>-source.zip"
# prints the commit, SOURCE_DATE_EPOCH and sha512 to record on the planning issue
```

[Apache RAT](https://creadur.apache.org/rat/) (run by
`release-verify-rc`) is the authoritative check on artefact contents;
extend the `export-ignore` set if RAT flags anything on the first RC.

## Build invocation

None. Magpie ships no convenience binaries, so the source archive above
is the whole build.

## Expected artefact list

- `apache-magpie-<version>-source.zip` — canonical source artefact
  (**required**, signed, checksummed). This is what the `[VOTE]` votes
  on, and the only artefact Magpie ships. No convenience binaries.

## Digest set

- `sha512` — **required** (ASF baseline).

`md5` and `sha1` are prohibited for new ASF releases per
[release-distribution § sigs-and-sums](https://infra.apache.org/release-distribution.html#sigs-and-sums)
and are never emitted.

## Reproducibility checks

| Key | Value |
|---|---|
| `reproducibility_source` | `on` — `release-verify-rc` Step 9 rebuilds with `repro-archive build` at the tag and `repro-archive compare`s against the staged `.zip`; anything but `identical` is a `-1` |
| `reproducibility_binaries` | `off` — no binaries |

Automated (CI) release signing is not enabled for Magpie
(`automated_release_signing: off` in
[`release-management-config.md`](release-management-config.md));
the RM signs locally.

## Binary-exclude list

The source artefact must contain no compiled or opaque binary content.
`release-verify-rc` Step 6 always scans its fixed baseline
(`.class`, `.jar`, `.so`, `.dylib`, `.dll`, `.exe`, `.pyc`,
`__pycache__`). Magpie adds no project-specific globs and names no
known-accepted exceptions.
