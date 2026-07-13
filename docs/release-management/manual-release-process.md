<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Manual release process — the 0.1.0 hybrid path (SVN-dist + ATR-vote)](#manual-release-process--the-010-hybrid-path-svn-dist--atr-vote)
  - [Which backend this is](#which-backend-this-is)
  - [The sequence, as run for 0.1.0](#the-sequence-as-run-for-010)
    - [0. Prep (Steps 1–2)](#0-prep-steps-12)
    - [1. Set variables](#1-set-variables)
    - [2. Tag, build, sign, checksum (Step 4)](#2-tag-build-sign-checksum-step-4)
    - [3. Stage to SVN `dist/dev` (Step 5, canonical download)](#3-stage-to-svn-distdev-step-5-canonical-download)
    - [4. Compose in ATR + verify (Step 6)](#4-compose-in-atr--verify-step-6)
    - [5. Vote via ATR (Steps 7–9)](#5-vote-via-atr-steps-79)
    - [6. Finish over SVN — *not* ATR (Step 10, the moment of release)](#6-finish-over-svn--not-atr-step-10-the-moment-of-release)
    - [7. Announce + post-release (Steps 11–14)](#7-announce--post-release-steps-1114)
  - [Manual verification — what a voter runs before `+1`](#manual-verification--what-a-voter-runs-before-1)
    - [1. Fetch the artefacts and `KEYS`](#1-fetch-the-artefacts-and-keys)
    - [2. Verify the signature against the project `KEYS`](#2-verify-the-signature-against-the-project-keys)
    - [3. Verify the checksum](#3-verify-the-checksum)
    - [4. Unpack and inspect the tree](#4-unpack-and-inspect-the-tree)
    - [5. Confirm the source matches the tagged commit](#5-confirm-the-source-matches-the-tagged-commit)
    - [6. License headers (Apache RAT)](#6-license-headers-apache-rat)
    - [7. Optional — reproduce the project's own checks from pristine source](#7-optional--reproduce-the-projects-own-checks-from-pristine-source)
  - [Caveats hit during rc1 / rc2](#caveats-hit-during-rc1--rc2)
  - [Release Manager checklist](#release-manager-checklist)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Manual release process — the 0.1.0 hybrid path (SVN-dist + ATR-vote)

A concrete, **as-executed** record of how Apache Magpie `0.1.0` was cut
by hand, kept as a practical runbook for the next Release Manager (RM).

Where [`svn-release-runbook.md`](svn-release-runbook.md) and
[`atr-release-runbook.md`](atr-release-runbook.md) describe each backend
*abstractly*, this document is the **specific sequence actually run for
`0.1.0`** — real commands, real URLs, and the rough edges hit during the
`rc1` / `rc2` iterations — so the next release does not re-discover them.

> [!NOTE]
> **These manual steps are a fallback.** The normal path is to let the
> [release-management skills](README.md) drive the release — the RM asks
> their agent to *"cut rc1 for 0.1.1"*, *"verify the latest release
> candidate"*, *"draft the vote email"*, and so on, and each skill emits
> the exact command to run (the agent never signs or publishes — you do).
> Reach for the longhand below when you have no agent to hand, want to
> hand-check what a skill produced, or need to understand what a step is
> actually doing under the hood.

## Which backend this is

Magpie's [`release-management-config.md`](../../projects/magpie/release-management-config.md)
currently pins a **hybrid**:

- `release_dist_backend = svnpubsub` — the signed source artefact is the
  canonical download, hosted on `dist.apache.org` over SVN.
- `release_vote_backend = atr` — the mandatory `dev@` `[VOTE]` is composed
  and tabulated by the [Apache Trusted Releases](atr-release-runbook.md)
  platform (alpha, at `https://release-test.apache.org/`).

So the artefacts live in **two** places during a vote: the SVN `dist/dev`
staging dir (the canonical download the `[VOTE]` points at) **and** the ATR
candidate, which runs the policy checks and drives the vote. Promotion
(**Finish**) is done over SVN, *not* through ATR — ATR does not host or
publish Magpie releases while it is alpha. This flips to full ATR
(`release_dist_backend = atr`) only after the PMC ratifies ATR and it
leaves alpha.

The two non-negotiable boundaries still hold: **the RM signs every
artefact on their own machine**, and **the RM/PMC — never the agent —
performs the publishing move.**

## The sequence, as run for 0.1.0

### 0. Prep (Steps 1–2)

The version-bump + `CHANGELOG` + `NOTICE`/`LICENSE` prep PR was merged so
`main` reflected `0.1.0`. The RC was cut from that commit
(`0.1.0-rc2` = commit `1890a13d`).

### 1. Set variables

```bash
export VERSION=0.1.0
export RC=rc2                              # rc1 was superseded — see Caveats
export ASF_ID=potiuk
export RC_TAG="${VERSION}-${RC}"           # 0.1.0-rc2
export ARTIFACT="apache-magpie-${VERSION}-source.zip"
export STAGE_DIR="$(pwd)/stage/${RC_TAG}"
```

Note the artefact filename carries **no** `-rcN` suffix — the RC identity
lives only in the tag and the staging directory name, so promotion is a
clean directory move (Step 6) with no rename.

### 2. Tag, build, sign, checksum (Step 4)

```bash
git tag -s "${RC_TAG}" -m "Apache Magpie ${VERSION} ${RC}" HEAD
git push origin "${RC_TAG}"

git archive --format=zip \
  --prefix="apache-magpie-${VERSION}/" \
  -o "${ARTIFACT}" "${RC_TAG}"

gpg --armor --detach-sign "${ARTIFACT}"        # -> ${ARTIFACT}.asc
sha512sum "${ARTIFACT}" > "${ARTIFACT}.sha512" # macOS: shasum -a 512
```

`git archive` honours `export-ignore` in
[`.gitattributes`](../../.gitattributes); what ends up in (and out of) the
`.zip` — and why — is documented in
[`source-release-contents.md`](../source-release-contents.md). The
`0.1.0-rc2` source SHA-512 was:

```text
991218c7ecbe66a5ccf4b6e5b55cedee33382d8f38d1bd8683a45303771e8d43cd106acd371931801450ed77d993c9c778fd03f0c231eb892adb7f8b21af3568
```

Verify your own artefacts before staging:

```bash
gpg --verify "${ARTIFACT}.asc" "${ARTIFACT}"
sha512sum -c "${ARTIFACT}.sha512"
```

### 3. Stage to SVN `dist/dev` (Step 5, canonical download)

```bash
mkdir -p "${STAGE_DIR}"
cp "${ARTIFACT}" "${ARTIFACT}.asc" "${ARTIFACT}.sha512" "${STAGE_DIR}/"

svn import "${STAGE_DIR}" \
  "https://dist.apache.org/repos/dist/dev/magpie/${RC_TAG}/" \
  --username "${ASF_ID}" \
  -m "Stage Apache Magpie ${VERSION} ${RC} for vote"

svn list "https://dist.apache.org/repos/dist/dev/magpie/${RC_TAG}/"
```

For `0.1.0-rc2` this was
`https://dist.apache.org/repos/dist/dev/magpie/0.1.0-rc2/`. **Never** stage
to a `dist/release/` path — that is the post-vote, PMC-gated move (Step 6).

### 4. Compose in ATR + verify (Step 6)

Upload the **same** signed artefacts to ATR so it runs the checks
(signature / checksum / license / notice / source-headers), then poll:

```bash
atr release start magpie "${VERSION}"
atr upload magpie "${VERSION}" "${ARTIFACT}"        "${ARTIFACT}"
atr upload magpie "${VERSION}" "${ARTIFACT}.asc"    "${ARTIFACT}.asc"
atr upload magpie "${VERSION}" "${ARTIFACT}.sha512" "${ARTIFACT}.sha512"
atr check status magpie "${VERSION}" --verbose
```

ATR is alpha — treat client verbs as the *shape* of the operation and
confirm with `atr --help`; the web UI is the stable path. Run
[`release-verify-rc`](../../skills/release-verify-rc/SKILL.md) locally too,
as an independent second read.

### 5. Vote via ATR (Steps 7–9)

ATR sends the `[VOTE]` to `dev@magpie.apache.org` and tabulates over the
≥72h window. The body points voters at the **SVN `dist/dev`** URL for
downloads (the canonical location in hybrid mode). For `0.1.0-rc2` the
`[VOTE]` referenced:

| Field | Value |
|---|---|
| Candidate page (ATR) | `https://release-test.apache.org/vote/magpie/0.1.0` |
| Artefacts / downloads (SVN) | `https://dist.apache.org/repos/dist/dev/magpie/0.1.0-rc2/` |
| Tag | `https://github.com/apache/magpie/releases/tag/0.1.0-rc2` |
| Changelog | `https://github.com/apache/magpie/blob/0.1.0-rc2/CHANGELOG.md` |
| KEYS | `https://dist.apache.org/repos/dist/release/magpie/KEYS` |

Cross-check the tally with
[`release-vote-tally`](../../skills/release-vote-tally/SKILL.md) against
[`pmc-roster.md`](../../projects/magpie/pmc-roster.md) — the binding tally
is the PMC's, not the platform's. Needs ≥3 binding `+1` and more `+1` than
`-1`. If the vote fails, bump `RC` and return to Step 2.

### 6. Finish over SVN — *not* ATR (Step 10, the moment of release)

In hybrid mode, promotion is a PMC-gated SVN move, not an ATR *finish*:

```bash
svn mv \
  "https://dist.apache.org/repos/dist/dev/magpie/${RC_TAG}/" \
  "https://dist.apache.org/repos/dist/release/magpie/${VERSION}/" \
  --username "${ASF_ID}" \
  -m "Release Apache Magpie ${VERSION}"

# Tag the final (non-rc) release at the same commit:
git tag -s "${VERSION}" -m "Apache Magpie ${VERSION}" "${RC_TAG}^{}"
git push origin "${VERSION}"
```

`dist/release/` is PMC-only — that write gate bites here, by design.

### 7. Announce + post-release (Steps 11–14)

- `[ANNOUNCE]` to `announce@apache.org`, cc `dev@` (mandatory) — drafted by
  [`release-announce-draft`](../../skills/release-announce-draft/SKILL.md);
  the RM sends it.
- Archive sweep, audit-log record, and the post-release `.dev` bump PR
  ([`release-archive-sweep`](../../skills/release-archive-sweep/SKILL.md),
  [`release-audit-report`](../../skills/release-audit-report/SKILL.md),
  [`release-prepare`](../../skills/release-prepare/SKILL.md)).

## Manual verification — what a voter runs before `+1`

Any voter (and the RM, as a self-check) verifies the staged RC end-to-end
during the vote window.

**The easy path is the agent:** with the release skills adopted, just ask
it to *"verify the latest release candidate"* — that runs
[`release-verify-rc`](../../skills/release-verify-rc/SKILL.md), which does
every step below (signatures against `KEYS`, checksums, RAT license
headers, `NOTICE`/`LICENSE`, prohibited-binary scan, version-string
consistency) and emits a PASS / PASS-WITH-WARNINGS / FAIL report. It is
read-only — a fine thing to run in your own dev loop before you vote.

The by-hand steps below are the **fallback**: use them when you have no
agent set up, want an independent second read, or need to see exactly what
a failing check is complaining about. Everything is checked against the
**SVN `dist/dev`** copy (the canonical download in hybrid mode) and the
project `KEYS`, not against anything the RM asserts.

### 1. Fetch the artefacts and `KEYS`

```bash
export VERSION=0.1.0 RC=rc2
export BASE="https://dist.apache.org/repos/dist/dev/magpie/${VERSION}-${RC}"
export ARTIFACT="apache-magpie-${VERSION}-source.zip"

curl -fLO "${BASE}/${ARTIFACT}"
curl -fLO "${BASE}/${ARTIFACT}.asc"
curl -fLO "${BASE}/${ARTIFACT}.sha512"
curl -fLO "https://downloads.apache.org/magpie/KEYS"   # the download-page KEYS
```

### 2. Verify the signature against the project `KEYS`

```bash
gpg --import KEYS
gpg --verify "${ARTIFACT}.asc" "${ARTIFACT}"
```

Expect `Good signature`. Confirm the signing key's **fingerprint is one
listed in `KEYS`** — a good signature from a key that is *not* in `KEYS`
does not count. (A `WARNING: This key is not certified with a trusted
signature` note is normal; you are verifying provenance against `KEYS`, not
your web of trust.)

### 3. Verify the checksum

```bash
sha512sum -c "${ARTIFACT}.sha512"     # macOS: shasum -a 512 -c
```

Expect `OK`. Only SHA-512 is provided — `md5`/`sha1` are prohibited and
their absence is correct, not a gap.

### 4. Unpack and inspect the tree

```bash
unzip -q "${ARTIFACT}"
cd "apache-magpie-${VERSION}/"

# LICENSE + NOTICE present at the root:
ls LICENSE NOTICE

# No VCS metadata, compiled output, or prohibited binaries:
find . \( -name '*.pyc' -o -name '__pycache__' -o -name '*.jar' \
       -o -name '*.so' -o -name '*.dll' -o -name '*.class' \) -print
# expect: no output
```

Also eyeball version-string consistency (`pyproject.toml`, `CHANGELOG.md`)
and that the source-archive contents match
[`source-release-contents.md`](../source-release-contents.md) — the
metadata/config files that ship are expected, not stray.

### 5. Confirm the source matches the tagged commit

The `[VOTE]` states the RC was built from a specific tag and commit
(`0.1.0-rc2` = commit `1890a13d`). Verify the artefact is *exactly* that
tree — nothing slipped in or dropped between the commit and the `.zip`:

```bash
# Fetch the repo and confirm the tag resolves to the [VOTE]'s commit hash:
git clone https://github.com/apache/magpie.git magpie-check
cd magpie-check
git rev-parse "${VERSION}-${RC}^{commit}"      # expect: the [VOTE] hash (1890a13d…)

# Rebuild the source archive from that tag with the same prefix, then diff
# the unpacked trees (zip metadata may differ; the file *contents* must not):
git archive --format=zip --prefix="apache-magpie-${VERSION}/" \
  -o /tmp/rebuilt.zip "${VERSION}-${RC}"

mkdir -p /tmp/from-tag /tmp/from-rc
unzip -q /tmp/rebuilt.zip                   -d /tmp/from-tag
unzip -q "../${ARTIFACT}"                   -d /tmp/from-rc
diff -r /tmp/from-tag /tmp/from-rc          # expect: no output
```

Expect **no differences**. Any diff means the artefact does not match the
commit under vote — a `-1`-worthy discrepancy; report it on the thread with
the `diff` output. (If your `git` version happens to produce byte-identical
`git archive` output you can compare `sha512sum` of the two zips directly,
but the tree `diff` is the version-independent check.) If the tag is signed,
`git tag -v "${VERSION}-${RC}"` also confirms it has not moved.

### 6. License headers (Apache RAT)

Run [Apache RAT](https://creadur.apache.org/rat/) over the unpacked tree
with the **shipped** `.rat-excludes` (this is exactly why that file is in
the archive):

```bash
# Representative invocation; matches .github/workflows/rat.yml, which passes
# .rat-excludes via --input-exclude-file. Confirm the flag for your RAT
# version with `java -jar apache-rat.jar --help`.
java -jar apache-rat-<version>.jar --input-exclude-file .rat-excludes -d .
```

Expect **0 unapproved licences**. `release-verify-rc` wraps this so you do
not have to fetch the RAT jar by hand.

### 7. Optional — reproduce the project's own checks from pristine source

```bash
uv sync --group dev
prek run --all-files        # or: uv run --group dev pytest
```

A clean run from the unpacked `.zip` confirms the source artefact is
self-contained and buildable — a stronger signal than the artefact checks
alone.

Only after these pass should a voter post `+1` (binding voters: your `+1`
carries the release). Report any failure on the `[VOTE]` thread with the
exact command and output.

## Caveats hit during rc1 / rc2

Real friction from the `0.1.0` iterations, recorded so the next RM expects
it. Most trace to ATR being **alpha**; none blocked the release.

- **The `[VOTE]` email was part-template, part-manual.** ATR's generated
  template was incomplete for the hybrid case, so the `rc2` body was
  assembled by hand from the ATR template plus manual edits (the first send
  used the wrong template and had to be resent). Tracked upstream as
  [`tooling-releases-client#38`](https://github.com/apache/tooling-releases-client/issues/38).
  **Content of the `[VOTE]` email is the PMC's responsibility regardless of
  which tool generates it** — proof-read every send. File template gaps
  against ATR so every ASF project benefits.
- **Two download locations can confuse voters.** Because the artefacts sit
  in both the ATR candidate page *and* SVN `dist/dev`, a voter may ask
  whether the two agree. In hybrid mode the **SVN `dist/dev` copy is
  canonical**; say so in the `[VOTE]` body and point downloads there.
- **KEYS URL on the download page.** The `[VOTE]` linked
  `https://dist.apache.org/repos/dist/release/magpie/KEYS`, but the
  file the public **release download page** must use is
  `https://downloads.apache.org/magpie/KEYS`. Use the `downloads.apache.org`
  URL for anything user-facing.
- **Redundant / missing bits in the template.** The tag was listed twice
  (once with, once without the commit hash) and an SVN revision for the
  `dist/dev` copy would help reviewers pin exactly what they fetched.
  Prefer listing the commit hash once and dropping duplicate lines.
- **Developer-facing files in the source `.zip`.** Reviewers flagged
  `.asf.yaml`, `.claude/`, `.github/…`, `.rat-excludes`, `doap_Magpie.rdf`,
  and the `.gitignore` files as unexpected. They ship intentionally;
  [`source-release-contents.md`](../source-release-contents.md) now records
  what each is and why.

## Release Manager checklist

- [ ] Prep PR merged; version strings, `CHANGELOG`, `NOTICE`/`LICENSE` correct
- [ ] Public key in `KEYS` and on `keys.openpgp.org`; registered in ATR
- [ ] Signed tag `<version>-<rc>` created and pushed
- [ ] Source `.zip` built from the tag; `gpg --verify` + `sha512sum -c` pass
- [ ] Staged to `dist/dev/magpie/<version>-<rc>/`; `svn list` confirms 3 files
- [ ] Same artefacts uploaded to ATR; all Compose checks green
- [ ] `release-verify-rc` run locally as a second read
- [ ] `[VOTE]` body proof-read (downloads → SVN `dist/dev`, KEYS → `downloads.apache.org`); vote started in ATR (≥72h)
- [ ] Tally cross-checked against the PMC roster; ≥3 binding +1, more +1 than -1
- [ ] Promoted `svn mv dist/dev → dist/release` (PMC) — the moment of release
- [ ] Final non-rc tag `<version>` created and pushed
- [ ] `[ANNOUNCE]` sent to `announce@apache.org`; archive sweep, audit, post-bump done

## Cross-references

- [`process.md`](process.md) — the abstract 14-step lifecycle.
- [`svn-release-runbook.md`](svn-release-runbook.md) — the SVN-dist
  mechanics (Steps 4–5) this path uses for staging and promotion.
- [`atr-release-runbook.md`](atr-release-runbook.md) — the ATR flow and the
  hybrid-mode note; the forward-looking full-ATR target.
- [`source-release-contents.md`](../source-release-contents.md) — what the
  source `.zip` contains and why.
- [`release-management-config.md`](../../projects/magpie/release-management-config.md)
  — where the hybrid backend keys are pinned.
- [ASF release policy](https://www.apache.org/legal/release-policy.html),
  [release distribution](https://infra.apache.org/release-distribution.html),
  [release signing](https://infra.apache.org/release-signing.html).
