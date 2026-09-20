<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Reproducible releases](#reproducible-releases)
  - [What was wrong](#what-was-wrong)
  - [Decisions](#decisions)
    - [The source artefact is a function of the tag](#the-source-artefact-is-a-function-of-the-tag)
    - [What ships is decided once, in the open, and committed before the tag](#what-ships-is-decided-once-in-the-open-and-committed-before-the-tag)
    - [The record: commit, SWHID, origin, epoch, digest](#the-record-commit-swhid-origin-epoch-digest)
    - [Convenience artefacts are the project's, and reproducibility is their acceptance test](#convenience-artefacts-are-the-projects-and-reproducibility-is-their-acceptance-test)
    - [The vote text carries the verification path](#the-vote-text-carries-the-verification-path)
    - [Automated signing is an ASF option, gated on all of the above](#automated-signing-is-an-asf-option-gated-on-all-of-the-above)
  - [What was built](#what-was-built)
  - [Alternatives considered](#alternatives-considered)
  - [Known limits](#known-limits)
  - [Related work outside this repository](#related-work-outside-this-repository)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Reproducible releases

| | |
|---|---|
| **Status** | Built, in [apache/magpie#1296](https://github.com/apache/magpie/pull/1296). The ASF automated-signing option is designed and wired but no project has exercised it end to end; the ATR side of the SWHID comparison depends on ATR exposing the value it computes. |
| **Created** | 2026-09-20 |
| **Origin** | Magpie's own `0.1.0-rc1` got a `-1` for a source artefact nobody could regenerate; the follow-up asked for the full reproducible-builds.org treatment, an education step for what a source release should contain, and a path to CI-signed releases. |

A signature proves who packed an archive. It says nothing about whether the
archive is the tree that was voted on. Reproducibility is what closes that
gap: if two people can regenerate the same bytes from the same tag, the
release manager's machine stops being a trust boundary. This design makes
that property the default for the source artefact, the acceptance test for
anything shipped besides it, and the precondition for letting CI sign.

## What was wrong

- The release skills said *"build the artefact"* and left the how to each
  project. Magpie's own first RC was a `zip -r` of a working tree: it carried
  `__pycache__`, dangling agent-view symlinks, and a shape no voter could
  reproduce. `git archive` fixed the contents, but its bytes still depend on
  the `git` version that runs it, so two voters could not compare digests.
- Nothing in the process asked a project, once, what belongs in its source
  release. `.gitattributes` `export-ignore` was known folklore, not a step.
- "Binary" meant one global rebuild command in the config and a hard-coded
  list of the framework's own validators in `release-verify-rc`. Both were
  Magpie-specific; neither fitted a project shipping wheels, jars and a
  container image.
- The `[VOTE]` mail told voters where the artefacts were and nothing about
  how to check them. ATR's default vote text links only the candidate page.

## Decisions

### The source artefact is a function of the tag

The source archive is exported from the tag, never packed from a working
tree, and the export is normalised by a tool the framework ships
([`tools/reproducible-archive`](../../tools/reproducible-archive/README.md))
rather than by whatever `tar`, `zip`, `gzip` or `git` the release manager
has. The tool applies every rule on
[reproducible-builds.org § Archive metadata](https://reproducible-builds.org/docs/archives/)
— one `SOURCE_DATE_EPOCH` (the tag's committer time), locale-independent
ordering, uid/gid 0, `a=rX,u+w` modes, no PAX `atime`/`ctime`, `gzip -n`,
`zip -X` — and pins the two inputs the page does not mention that still vary
between machines: the builder's `core.autocrlf` / `core.eol` (which `git
archive` would apply to `text` files) and the archive writer itself. It is
stdlib-only and single-file so a CI workflow or a project that does not adopt
Magpie can embed it verbatim.

The reproducibility of the *source* is the property that matters most, not
the least. The `xz` compromise was a source tarball that did not match the
repository at its stated commit; a distribution that could rebuild the
tarball from the tag and compare would have caught it. Convenience binaries
are the place where "build it yourself" is the traditional advice; the source
archive is where nobody used to check, because it looked like it could not be
tampered with.

### What ships is decided once, in the open, and committed before the tag

`git archive` reads `export-ignore` from the tree it archives, so the
decision about what a source release contains has to be in the tree before
the RC tag exists. That put the review into `release-prepare prep`, as an
education step on the first release: list what would ship, classify every
top-level path (source, legal files, inputs to the checks voters run,
foundation metadata, VCS / CI / editor / lint / agent-view metadata, scratch),
check references before proposing an exclusion, confirm each entry with the
release manager, land `.gitattributes` in the prep PR, and record that the
review happened. `release-rc-cut` refuses to cut while it is outstanding.
Later releases get a drift check on new top-level paths.

### The record: commit, SWHID, origin, epoch, digest

Every RC records, on the planning issue and in the `[VOTE]`:

- the commit the tag points to, and the URL of the repository it lives in;
- the [Software Heritage identifier](https://swhid.org/) of the archive's
  expanded content, `swh:1:dir:<sha1>`, with `origin=<repo URL>` and
  `anchor=swh:1:rev:<commit>` qualifiers;
- `SOURCE_DATE_EPOCH` and the sha512 of the archive.

The SWHID is the load-bearing one. A directory SWHID is computed exactly as
git computes a tree id — from names, modes and contents alone — so it is
intrinsic to the files: a voter recomputes it from the staged bytes without
git, ATR computes the same value at compose time, and it equals `git
rev-parse <tag>^{tree}` unless `.gitattributes` altered the export (in which
case the difference is itself the record of what was left out). Unlike a
digest of the archive it does not depend on the container, so a `.tar.gz`
and a `.zip` of the same tree carry the same SWHID, and a convenience
artefact can name the source SWHID it was built from. Recording the SWHID
next to the commit and the origin, rather than the commit alone, gives a
reference that outlives the repository's hosting and that ATR can be checked
against directly.

### Convenience artefacts are the project's, and reproducibility is their acceptance test

What a project ships besides the source — a binary tarball, wheels, jars, a
container image, a chart — is project-specific by nature, so the framework
assumes none. `release-build.md § Convenience artefacts` declares each one
with its own build command, staging target, reproducibility mode, vote scope
and publish channel, and every lifecycle step reads the list: `rc-cut` builds
and stages, `verify-rc` rebuilds and compares, `vote-draft` lists,
`promote` publishes, `announce-draft` names channels.

A convenience artefact is *good* only if it is demonstrably built from the
voted source. A binary cannot be reviewed, only rebuilt; rebuilding from the
tag under the same `SOURCE_DATE_EPOCH` and comparing — bit for bit, or with
every difference written down — is the one check that establishes what it
contains. `release-promote` withholds the publish command for an artefact
whose `verify-rc` rebuild did not reproduce, and never holds the source
promotion back for it: the source is the release, the artefact is a courtesy,
and a courtesy that cannot be verified is withheld, not shipped.

### The vote text carries the verification path

Every `[VOTE]` body carries a *How to verify this candidate* section: the
record above, the agentic one-liner (`verify-rc`), the project's
human-readable verification page at the RC tag, the convenience artefacts and
their vote scope, the ATR candidate page, and the voter-obligation sentence
from the release policy. Under ATR the drafted body is what the release
manager supplies to the platform; the default text is not allowed to stand.

### Automated signing is an ASF option, gated on all of the above

[Infra § Automated release signing](https://infra.apache.org/release-signing.html#automated-release-signing)
lets an ASF project have CI sign what it builds, provided every signed
artefact is reproducible, CI stages only, and a committer re-validates every
artefact bit-for-bit on trusted hardware before publication. The framework
offers it only under `organization: ASF` (resolved from the organization
manifest, `null` elsewhere), as a one-time drafting sub-command that produces
the Infra ticket, the Security Team notification and a workflow PR with no
key material, and it changes the lifecycle only once enabled: the RM pushes a
signed tag, CI builds and stages, `verify-rc` becomes mandatory at a
byte-identical bar with the committer's own trusted-hardware assertion, and
`promote` blocks without that attestation. The agent still holds no key.

## What was built

| Piece | Where |
|---|---|
| `repro-archive build` / `check` / `compare` / `swhid` / `recipe` / `epoch` | [`tools/reproducible-archive`](../../tools/reproducible-archive/README.md) |
| `§ Source archive`, `§ Convenience artefacts`, `§ Source-tree validators`, `§ Reproducibility checks` | [`projects/_template/release-build.md`](../../projects/_template/release-build.md) |
| `vote_verification_doc_url`, `reproducibility_doc_url`, `vote_verification_skill`, `automated_release_signing` | [`projects/_template/release-management-config.md`](../../projects/_template/release-management-config.md) |
| First-release `.gitattributes` review (prep Step 2e); `automated-signing` sub-command | [`release-prepare`](../../skills/release-prepare/SKILL.md) |
| Reproducible source build, per-artefact builds, self-check (Step 2b), CI-signed flow (Step 2c), the record | [`release-rc-cut`](../../skills/release-rc-cut/SKILL.md) |
| Config-driven Step 7 validators; Step 9 rebuild-and-compare with SWHID check | [`release-verify-rc`](../../skills/release-verify-rc/SKILL.md) |
| *How to verify* section with the record and the artefact list | [`release-vote-draft`](../../skills/release-vote-draft/SKILL.md) |
| Per-artefact publish, reproducibility gate, trusted-hardware gate | [`release-promote`](../../skills/release-promote/SKILL.md) |
| Rationale for adopters and voters | [`docs/release-management/reproducibility.md`](../release-management/reproducibility.md) |
| CI workflow template (ASF automated signing) | [`projects/_template/workflows/release-candidate.yml`](../../projects/_template/workflows/release-candidate.yml) |

## Alternatives considered

- **Plain `git archive` as the build command.** Correct contents, but the
  bytes depend on the `git` version: the zip writer's compression and the
  tar's PAX handling have changed between releases. A voter on another
  version gets `content-identical`, never `identical`, and cannot compare
  digests with the RM or with ATR. Kept as the documented fallback recipe
  (`repro-archive recipe` prints the GNU tar / Info-ZIP equivalent).
- **Shell recipe instead of a Python tool.** The reproducible-builds.org
  recipe needs GNU tar ≥ 1.28 and Info-ZIP flags that macOS's stock tools
  lack, and a shell script cannot be unit-tested against git's own tree
  hashing. The tool is stdlib-only and single-file so it costs nothing to
  embed; the shell recipe stays available.
- **One global `binary_rebuild_command`.** Fitted a project with one binary
  and none with several; said nothing about where each goes or whether it is
  in the vote. Replaced by the per-artefact list.
- **Holding the source promotion until every convenience artefact
  reproduces.** Rejected: the source is the release and its vote is what
  passed; a courtesy artefact that cannot be verified is withheld on its own.
- **Extracting the archive and running `swh identify` / `asfswhid` for the
  SWHID.** Same value, but it adds a dependency and an extraction step to a
  tool that already has every member in memory. The in-memory tree hashing is
  tested against `git write-tree` over the extracted tree, so the two agree
  by construction; a voter who prefers `asfswhid` gets the same identifier.
- **Recording only the commit and repository URL.** A commit id identifies a
  repository object; the SWHID of the expanded content identifies what
  shipped, survives a repository move, is the same across archive formats,
  and is what ATR computes. Both are recorded; the SWHID is the one to compare.
- **Offering automated signing to every organization.** The policy, the key
  provisioning and the approval body are ASF Infra's. Other organizations can
  add an equivalent block to their manifest; without one the option does not
  exist in the skills.

## Known limits

- **Compression bytes.** `identical` requires the same deflate output. zlib's
  output at a given level has been stable for years, but zlib-ng or a
  different Python build can differ. The SWHID and `compare`'s
  `content-identical` verdict are container-independent; the record carries
  both so a voter can tell "different bytes, same tree" from "different tree".
- **`export-subst`.** Deterministic for a given commit but it rewrites
  content, so the archive's SWHID differs from the repository tree's; the
  note `repro-archive build` prints says which case applies.
- **Registry-staged artefacts.** Container images and packages staged in a
  registry are compared by digest against a local rebuild; the mechanics of
  pulling by digest are the project's, not the framework's.
- **The ATR comparison** depends on ATR showing its SWHID for the candidate;
  the value is computed today but not yet exposed in the interface.

## Related work outside this repository

- [apache/tooling-actions#37](https://github.com/apache/tooling-actions/pull/37),
  an `upload-source-to-atr` action that builds a `git archive | gzip -n`
  source archive on CI, computes its SWHID with
  [`asfswhid`](https://github.com/apache/tooling-asfswhid), signs it and
  uploads to ATR. Same rules, same identifier; the discussion there is where
  the "SWHID next to the commit" decision comes from, and where binaries were
  agreed to be each project's concern — which is what `§ Convenience
  artefacts` encodes.
- [reproducible-builds.org § Archive metadata](https://reproducible-builds.org/docs/archives/)
  and [§ `SOURCE_DATE_EPOCH`](https://reproducible-builds.org/docs/source-date-epoch/).
- [SWHID specification](https://swhid.org/) (ISO/IEC 18670:2025) and the
  [Software Heritage persistent identifiers](https://docs.softwareheritage.org/devel/swh-model/persistent-identifiers.html)
  documentation.
