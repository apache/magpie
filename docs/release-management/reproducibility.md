<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Reproducible source archives, reproducibility checks, and automated signing](#reproducible-source-archives-reproducibility-checks-and-automated-signing)
  - [Why](#why)
  - [The source archive is `git archive` plus `.gitattributes`](#the-source-archive-is-git-archive-plus-gitattributes)
    - [The first-release `.gitattributes` review](#the-first-release-gitattributes-review)
    - [Later releases: drift](#later-releases-drift)
  - [The archive rules from reproducible-builds.org](#the-archive-rules-from-reproducible-buildsorg)
  - [Reproducibility checks](#reproducibility-checks)
    - [Source (`reproducibility_source`)](#source-reproducibility_source)
    - [Binaries (`reproducibility_binaries`)](#binaries-reproducibility_binaries)
    - [Where the checks run](#where-the-checks-run)
  - [Automated release signing (🪶 ASF-specific, optional)](#automated-release-signing--asf-specific-optional)
    - [What the policy requires](#what-the-policy-requires)
    - [One-time setup: `release-prepare automated-signing`](#one-time-setup-release-prepare-automated-signing)
    - [What changes in the lifecycle once it is enabled](#what-changes-in-the-lifecycle-once-it-is-enabled)
    - [What does not change](#what-does-not-change)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Reproducible source archives, reproducibility checks, and automated signing

How the release-management family produces a source artefact that is a function of the tag alone,
how a Release Manager (RM) and every voter confirm that the staged artefacts really are that function,
and, for ASF projects, how that opens the door to CI-signed releases.

The configuration keys this page refers to live in
[`<project-config>/release-build.md`](../../projects/_template/release-build.md)
(`§ Source archive`, `§ Reproducibility checks`) and
[`<project-config>/release-management-config.md`](../../projects/_template/release-management-config.md)
(`§ Signing › Automated release signing`).
The tool that does the mechanical work is
[`tools/reproducible-archive`](../../tools/reproducible-archive/README.md) (`repro-archive`).

## Why

[`PRINCIPLES.md` § 11](../../PRINCIPLES.md#11-releases-are-reproducible-from-signed-source):
releases are reproducible from signed source to the extent the toolchain permits;
where byte-identical output is achievable it is required,
and where it is not, the process documents the divergence and provides a verification path a contributor can run locally.
Reproducibility is what makes a signature worth verifying:
a `+1` on a source artefact means "I confirmed these bytes are the tagged tree", and that is only checkable if the tagged tree yields those bytes again.

The framework learnt this the hard way.
Magpie's own `0.1.0-rc1` got a `-1` because the artefact was a `zip -r` of a working tree:
it carried `__pycache__/*.pyc`, its dangling agent-view symlinks pointed at directories the archive had stripped,
and no voter could regenerate it to compare.
`0.1.0-rc2` switched to `git archive` with `.gitattributes` `export-ignore`, and
[`docs/source-release-contents.md`](../source-release-contents.md) records what ships and why.
This page generalises that fix for every adopter.

## The source archive is `git archive` plus `.gitattributes`

With `source_archive_method: git-archive` (the default in `release-build.md`) the source artefact is not a build output.
It is an export of the tagged tree:

- **only tracked files at the tag** — an untracked `.pyc`, a stray editor backup, a local `.env`, cannot ship;
- **minus the paths marked `export-ignore`** in the repository's root
  [`.gitattributes`](https://git-scm.com/docs/gitattributes#_creating_an_archive) — VCS, CI and editor metadata a source consumer never needs;
- **wrapped by `repro-archive build`**, which applies the reproducible-builds.org archive rules below so that the output is byte-identical on every machine.

`.gitattributes` is therefore part of the release definition and must be **committed before the RC tag is cut**;
`git archive` reads the attributes from the tree it archives, not from the working copy.
That is why the review lands in the prep PR (`release-prepare prep`) and why `release-rc-cut` refuses to cut an RC while the review is outstanding.

### The first-release `.gitattributes` review

`release-prepare prep` Step 2f runs a guided review on the first release
(or whenever `export_ignore_reviewed` is unset in `release-build.md`, or on `--review-archive`).
It is an education step: the goal is that the operator understands *why* each path ships or does not, not that the agent guesses.
The skill:

1. **Lists what would ship today** — `git archive --format=tar HEAD | tar -tf -` — and every top-level entry of `git ls-files`.
2. **Classifies each top-level path** into one of these buckets and says which:

   | Bucket | Typical paths | Default |
   |---|---|---|
   | Source, docs, build descriptors, packaging metadata | `src/`, `docs/`, `pom.xml`, `pyproject.toml`, lock files, `README*` | **ship** |
   | Legal files | `LICENSE`, `NOTICE`, `DISCLAIMER` (incubating), `licenses/` | **ship, never excludable** |
   | Inputs to the checks voters run | RAT excludes (`.rat-excludes`), in-tree validators | **ship** |
   | Foundation / project metadata | `.asf.yaml`, `doap_*.rdf` | ship (project's call; ASF projects conventionally ship them) |
   | VCS metadata | `.gitattributes`, `.gitmodules`, `.mailmap` | exclude (`.gitignore` is the project's call) |
   | CI and bot configuration | `.github/workflows/`, `.github/dependabot.yml`, `.gitlab-ci.yml`, `.travis.yml`, `.circleci/`, `.pre-commit-config.yaml` | exclude |
   | Editor and IDE state | `.idea/`, `.vscode/`, `.devcontainer/` | exclude |
   | Linter and formatter configuration not needed to build | `.lychee.toml`, `.markdownlint.json`, `.typos.toml`, `.zizmor.yml`, `.yamllint`, `.codespellrc` | exclude |
   | Agent-view directories | `.claude/`, `.agents/`, `.kiro/`, `.cursor/` | exclude the relay symlink dirs; keep a single-hop canonical view if shipped files link into it |
   | Large assets not needed to build or verify | screenshots, recordings, demo data | project's call; say what they are for |
   | Release-tooling scratch | `.apache-magpie.session-state.json`, `.apache-magpie.local.lock` | exclude |

3. **Checks references before proposing an exclusion**: `git grep -l '<path>'` over tracked files.
   A path that a shipped file links to (a doc, a validator, a symlink target) must not be excluded,
   or `release-verify-rc` Step 7 will fail the RC with a dangling reference.
   The skill names the referrers and offers the alternative (keep the path, or repoint the reference).
4. **Checks symlinks**: every committed symlink whose target would be stripped is flagged; chained symlinks (link to a link) are flagged because safe extractors reject them.
5. **Proposes the entries**, root-anchored with a leading `/` for root-only files, one rationale comment per entry,
   and shows the before/after archive listing diff (`repro-archive build` twice, `repro-archive compare`).
6. **Records the decision**: `.gitattributes` joins the prep PR's file set, and the prep PR also sets
   `export_ignore_reviewed: <version>` in `release-build.md` so the review does not repeat.

Everything is a proposal; the RM confirms each entry.
The agent never edits `.gitattributes` without that confirmation and never marks the review done on its own.

### Later releases: drift

On every subsequent `release-prepare prep` the skill runs a cheap drift check:
top-level entries added since the last reviewed tag (`git diff --name-only <last-tag> HEAD`, top level only)
that fall in an *exclude* bucket are surfaced as candidates.
`--review-archive` forces the full review again.

## The archive rules from reproducible-builds.org

`git archive` on its own is only deterministic for one `git` version:
the zip writer's compression, the tar's PAX handling and the mtime source have changed between releases,
so two voters with different `git` versions get different bytes from the same tag.
[reproducible-builds.org § Archive metadata](https://reproducible-builds.org/docs/archives/)
lists what has to be pinned for an archive to be reproducible.
`repro-archive build` applies every rule; `repro-archive check` verifies each one on any archive; `repro-archive recipe` prints the equivalent GNU tar / Info-ZIP shell commands.

| Rule | Standard-tool form | `repro-archive` |
|---|---|---|
| One modification time for every member | `tar --mtime="@${SOURCE_DATE_EPOCH}"` / `touch --date="@${SOURCE_DATE_EPOCH}"` | mtime = `SOURCE_DATE_EPOCH`, default the committer timestamp of the ref |
| Locale-independent file ordering | `tar --sort=name`, `find … \| LC_ALL=C sort -z` | per-directory byte order |
| No ownership leakage | `--owner=0 --group=0 --numeric-owner` | uid/gid 0, empty names |
| No umask leakage | `--mode=a=rX,u+w` | `0644` / `0755` |
| No PAX `atime`/`ctime`/PID headers | `--pax-option=exthdr.name=%d/PaxHeaders/%f,delete=atime,delete=ctime` | none written; `check` catches `PaxHeaders.<pid>` |
| gzip carries no timestamp or filename | `gzip -n` | header mtime 0, no name |
| zip carries no extra attributes | `zip -X`, unzip with `TZ=UTC` | no extra fields, UTC DOS time |
| Static libraries deterministic | `ARFLAGS=Dcvr`, `ranlib -D` | belongs in the *binary* build command (`release-build.md § Build invocation`) |

`SOURCE_DATE_EPOCH` is the one input two builders must agree on.
Deriving it from the ref's committer timestamp makes it a property of the tag, which is why `release-rc-cut` records it on the planning issue alongside the commit hash and the sha512.

## Reproducibility checks

Both checks are **optional** and configured in `release-build.md § Reproducibility checks`.
They are `on` for the source archive by default (it costs one rebuild), `off` for binaries by default (most adopters ship none).
They become **mandatory** under automated release signing (below).

### Source (`reproducibility_source`)

`on`: rebuild the source artefact from the tag with `repro-archive build` (same prefix, format and `SOURCE_DATE_EPOCH` as recorded on the planning issue) and `repro-archive compare` it against the staged artefact.

| `compare` verdict | Meaning | Outcome |
|---|---|---|
| `identical` | Byte-for-byte the same file | `PASS` |
| `content-identical` | Same members, same bytes, same modes; only archive metadata differs | `WARN` (RM-key mode: the RM built with a plain `git archive` or a different tool version; switch to `repro-archive build` for the next RC) / `FAIL` (automated signing) |
| `differs` | Members added, removed or changed | `FAIL` — the artefact is not the tagged tree; a `-1` |

`repro-archive check --epoch <SOURCE_DATE_EPOCH>` on the staged artefact runs alongside and reports any rule the staged archive violates.

### Binaries (`reproducibility_binaries`)

| Mode | What runs | Outcome |
|---|---|---|
| `off` | nothing | `SKIP`, stated explicitly in the report |
| `byte-identical` | `export SOURCE_DATE_EPOCH=…` then `binary_rebuild_command` at the tag; `sha512sum` of each rebuilt binary against the staged `.sha512` | any mismatch is `FAIL` |
| `documented-divergence` | the rebuild, then `binary_verification_command` (for example [`diffoscope`](https://diffoscope.org/)) against the staged binary | differences that match `known_divergences` are `WARN` and listed; anything else is `FAIL` |

`documented-divergence` is the honest mode for toolchains that cannot yet produce identical bytes (a JIT-compiled bundle, a signed installer, a platform that embeds the build host).
The known divergences are part of the release documentation, which is exactly what `PRINCIPLES.md § 11` asks for.

### Where the checks run

- **`release-rc-cut` Step 2b** — the RM's self-check right after building, before signing: `check` the artefact, rebuild into a scratch directory, `compare`. Catching a non-reproducible build here saves a whole RC round-trip.
- **`release-verify-rc` Step 9** — every voter's check against the *staged* artefact, in the same read-only pairing loop as signatures and checksums. The report's step summary carries the verdict and the recorded `SOURCE_DATE_EPOCH`.
- **`release-promote` Step 0** — under automated signing only: refuses to promote unless the planning issue carries a `release-verify-rc` reproducibility attestation from a run on trusted hardware.

## Automated release signing (🪶 ASF-specific, optional)

> **Scope.** This section applies to projects whose `project.md` declares `organization: ASF`.
> The skills offer the option only to those projects
> (`organizations/ASF/organization.md` → `release_process.automated_signing`;
> the `independent` organization sets it to `null` and the sub-command is not shown).
> Non-ASF adopters keep the RM-key flow; a foundation with its own CI-signing policy can add an equivalent block to its organization manifest.

### What the policy requires

[Infra § Automated release signing](https://infra.apache.org/release-signing.html#automated-release-signing)
lets an ASF project have CI (for example GitHub Actions) sign the artefacts it builds, **provided that**:

- *all* artefacts being signed can be built reproducibly;
- CI deploys the artefacts to a **staging** environment only;
- the release process contains a **validation step on trusted hardware** (explicitly *not* GitHub Actions) that rebuilds every artefact from source and confirms it is **bit-by-bit identical** to what was staged, before anything is published to end users.

The Apache Security Team must be notified of the request and approve the workflow before it is used
(the request should spell out the trusted-hardware validation; `INFRA-23996` is the background ticket).
The key is requested through an Infra Jira ticket and is provisioned by Infra:
4096-bit RSA, signing-only, private half held by infra-root and made available to the chosen CI system only,
a PGP-encrypted revocation certificate placed in the project's private repository,
and the public key sent to the project or added to its `KEYS`.
[release-policy § release signing](https://www.apache.org/legal/release-policy.html#release-signing)
allows signatures by "the automated release infrastructure, where the underlying implementation MUST follow the principles outlined by the Apache Security Team".

### One-time setup: `release-prepare automated-signing`

The sub-command is a **drafting** step: it produces the artefacts the RM files, and files none of them.

1. **Eligibility gate.** `organization: ASF`; `reproducibility_source: on`; `reproducibility_binaries: byte-identical` for every convenience binary in `expected_artefacts` (or none); the most recent RC's `release-verify-rc` report shows `identical` for every artefact. If the build is not yet demonstrably reproducible the skill stops here and says what to fix first.
2. **Infra Jira ticket draft** requesting the CI signing key, naming the workflow, the staging target (ATR trusted publishing via [`apache/tooling-actions/upload-to-atr`](https://github.com/apache/tooling-actions), pinned by commit SHA), and the trusted-hardware validation step.
3. **Security Team notification draft** for `security@apache.org` (the mail is drafted, never sent — [spec § Boundary 3](spec.md#boundary-3-agent-never-sends-mail-to-dev-users-announce)).
4. **Workflow PR proposal** from the template
   [`projects/_template/workflows/release-candidate.yml`](../../projects/_template/workflows/release-candidate.yml):
   build the source archive with the embedded `repro-archive` script, build binaries under `SOURCE_DATE_EPOCH`, self-check reproducibility in CI, upload to ATR with OIDC. The workflow contains no key material; signing is performed by the infra-managed mechanism agreed on the ticket.
5. **Config diff proposal**: `automated_release_signing: requested` now, `enabled` plus `ci_signing_key_fingerprint` and `ci_signing_infra_ticket` once Infra has provisioned the key and the public block is in `KEYS` (`release-keys-sync` handles the `KEYS` diff).

### What changes in the lifecycle once it is enabled

| Step | RM-key flow | `automated_release_signing: enabled` |
|---|---|---|
| 4 (`release-rc-cut`) | tag, build, `gpg --detach-sign`, `sha512sum` | tag (still signed by the RM) and push; the push triggers the workflow which builds, uploads to ATR, and stages. The skill emits the tag push plus the commands to watch the run and fetch the staged artefact list. |
| 5 (`release-rc-cut`) | `svn import` to `dist/dev/` | performed by CI; the skill records the run URL and staging URL on the planning issue |
| 6 (`release-verify-rc`) | reproducibility step optional | **mandatory**, `compare --require-identical` for every artefact, run on a committer's own hardware; the `--post-to` comment carries a trusted-hardware attestation |
| 10 (`release-promote`) | promote after `vote-passed` | additionally requires the attestation on the planning issue; blocks without it |

### What does not change

- The agent still holds no key of any kind ([spec § Boundary 1](spec.md#boundary-1-agent-never-holds-the-rms-signing-key)) — not the RM's, not the CI key.
- The RM still signs the **tag** with their own key; the RC is still voted on `dev@` by people who downloaded, rebuilt and tested it.
- Nothing is published by the agent or by CI; promotion stays a PMC member's `svn mv` (or ATR finish) after the vote ([spec § Boundary 2](spec.md#boundary-2-agent-never-publishes-the-release)).

## Cross-references

- [`tools/reproducible-archive/README.md`](../../tools/reproducible-archive/README.md) — the tool, rule by rule.
- [`docs/source-release-contents.md`](../source-release-contents.md) — Magpie's own `.gitattributes` decisions, the worked example of the review.
- [`process.md` § Step 2, 4, 5, 6, 10](process.md) — where each piece sits in the 14-step lifecycle.
- [`spec.md`](spec.md) — per-skill contract changes (`release-prepare`, `release-rc-cut`, `release-verify-rc`, `release-promote`).
- [`manual-release-process.md` § 5](manual-release-process.md#5-confirm-the-source-matches-the-tagged-commit) — the same source check written out longhand for a voter without the skill.
- [`atr-release-runbook.md` § GitHub Actions path](atr-release-runbook.md#github-actions-path-reproducible-builds) — the ATR trusted-publishing path the workflow template uses.
- [reproducible-builds.org § Archive metadata](https://reproducible-builds.org/docs/archives/) — the rule set.
- [reproducible-builds.org § `SOURCE_DATE_EPOCH`](https://reproducible-builds.org/docs/source-date-epoch/) — the timestamp convention.
- [Infra § Automated release signing](https://infra.apache.org/release-signing.html#automated-release-signing) — the ASF policy.
- [`apache/tooling-actions`](https://github.com/apache/tooling-actions) — ATR trusted-publishing actions (pin by commit SHA).
