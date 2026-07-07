<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie: release build configuration](#apache-magpie-release-build-configuration)
  - [Build invocation](#build-invocation)
  - [Expected artefact list](#expected-artefact-list)
  - [Digest set](#digest-set)
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

## Build invocation

The canonical source artefact is a deterministic `git archive` of the
tagged tree — no VCS metadata, no build output:

```bash
# From the release tag <version>-rcN:
git archive --format=zip \
  --prefix="apache-magpie-<version>/" \
  -o "apache-magpie-<version>-source.zip" \
  "<version>-rcN"
```

Files that must not ship in the source release (CI config, editor
metadata) are marked `export-ignore` in the root
[`.gitattributes`](../../.gitattributes), so `git archive` drops them.
[Apache RAT](https://creadur.apache.org/rat/) (run by
`release-verify-rc`) is the authoritative check on artefact contents;
extend the `export-ignore` set if RAT flags anything on the first RC.

## Expected artefact list

- `apache-magpie-<version>-source.zip` — canonical source artefact
  (**required**, signed, checksummed). This is what the `[VOTE]` votes
  on, and the only artefact Magpie ships. No convenience binaries.

## Digest set

- `sha512` — **required** (ASF baseline).

`md5` and `sha1` are prohibited for new ASF releases per
[release-distribution § sigs-and-sums](https://infra.apache.org/release-distribution.html#sigs-and-sums)
and are never emitted.

## Binary-exclude list

The source artefact must contain no compiled or opaque binary content.
Conservative default denylist for `release-verify-rc`:
`.class`, `.jar`, `.so`, `.dylib`, `.dll`, `.exe`, `.pyc`.
