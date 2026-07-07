<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [SVN source-release runbook (signed `.zip` to `dist/dev/`)](#svn-source-release-runbook-signed-zip-to-distdev)
  - [What a "release" is](#what-a-release-is)
  - [Where this fits in the 14-step lifecycle](#where-this-fits-in-the-14-step-lifecycle)
  - [Prerequisites](#prerequisites)
  - [Step 1: Set the release variables](#step-1-set-the-release-variables)
  - [Step 2: Tag the release candidate](#step-2-tag-the-release-candidate)
  - [Step 3: Build the source `.zip` from the tag](#step-3-build-the-source-zip-from-the-tag)
  - [Step 4: Sign the `.zip` (detached `.asc`)](#step-4-sign-the-zip-detached-asc)
  - [Step 5: Generate the SHA-512 checksum](#step-5-generate-the-sha-512-checksum)
  - [Step 6: Verify your own artefacts before staging](#step-6-verify-your-own-artefacts-before-staging)
  - [Step 7: Stage to `dist/dev/` over SVN](#step-7-stage-to-distdev-over-svn)
  - [What happens after staging](#what-happens-after-staging)
  - [Release Manager checklist](#release-manager-checklist)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# SVN source-release runbook (signed `.zip` to `dist/dev/`)

A copy-paste command sequence for the **mechanical core** of an
Apache release on the `svnpubsub` distribution backend: take a
tagged revision, package it as a source `.zip`, sign it, checksum
it, and stage it to `dist.apache.org/repos/dist/dev/` for the
`[VOTE]`.

> [!NOTE]
> This is the **`svnpubsub`** backend. For the **Apache Trusted
> Releases (ATR)** backend — compose a signed candidate in the ATR
> platform, let it run the checks and drive the vote, then *finish*
> to publish — see the
> [ATR release runbook](atr-release-runbook.md). Same 14-step
> lifecycle, same skills, different distribution backend.

This runbook is the hands-on companion to the
[`release-rc-cut`](../../skills/release-rc-cut/SKILL.md) skill
(lifecycle Steps 4–5). The skill *emits* this command set tailored
to the adopter's [`release-build.md`](../../projects/_template/release-build.md);
this document is the same set written out longhand so a Release
Manager (RM) can run a release by hand, or sanity-check what the
skill produced. Every command runs **on the RM's own machine, with
the RM's own signing key, under the RM's own ASF credentials** — the
agent never holds the key and never publishes
([spec § Boundary 1 / Boundary 2](spec.md)).

## What a "release" is

Per the
[ASF release policy § what is a release](https://www.apache.org/legal/release-policy.html#release-definition):

- **The source package is the release.** Everything else
  (convenience binaries, wheels, images) is just that —
  *convenience*. The `[VOTE]` votes on the source `.zip`.
- It must be a **clean source snapshot of a tagged revision** — the
  exact tree at `<version>-rcN`, with no VCS metadata and no
  compiled output.
- It must contain **`LICENSE`** and **`NOTICE`** at the artefact
  root (this repo already carries both — `git archive` includes
  them automatically).
- It must be **cryptographically signed** by the RM with a
  **detached** signature (`.asc`), and accompanied by a **SHA-512**
  checksum. `MD5` and `SHA-1` are prohibited for new releases per
  [release-distribution § sigs-and-sums](https://infra.apache.org/release-distribution.html#sigs-and-sums).
- It must be **distributed via `dist.apache.org`** (svnpubsub),
  staged under `dist/dev/` for the vote and only moved to
  `dist/release/` after the vote passes.

## Where this fits in the 14-step lifecycle

This runbook covers Steps 4–5 of the
[14-step process](process.md):

| Step | Owner skill | This runbook |
|---|---|---|
| 1–2 Plan + version bump | [`release-prepare`](../../skills/release-prepare/SKILL.md) | prerequisite |
| 3 `KEYS` reconciliation | [`release-keys-sync`](../../skills/release-keys-sync/SKILL.md) | prerequisite |
| **4 Cut RC: tag + build + sign** | [`release-rc-cut`](../../skills/release-rc-cut/SKILL.md) | **Steps 2–6 below** |
| **5 Stage to `dist/dev/`** | [`release-rc-cut`](../../skills/release-rc-cut/SKILL.md) | **Step 7 below** |
| 6 Pre-flight verify | [`release-verify-rc`](../../skills/release-verify-rc/SKILL.md) | downstream |
| 7–9 Vote + tally | [`release-vote-draft`](../../skills/release-vote-draft/SKILL.md), [`release-vote-tally`](../../skills/release-vote-tally/SKILL.md) | downstream |
| 10 Promote `dist/dev/ → dist/release/` | [`release-promote`](../../skills/release-promote/SKILL.md) | downstream |

> [!IMPORTANT]
> This runbook stops at `dist/dev/`. Moving the artefacts to
> `dist/release/` is **the moment of release** and happens **only
> after the vote passes** — see
> [`release-promote`](../../skills/release-promote/SKILL.md). Never
> `svn import`/`svn mv` into a `dist/release/` path from here; that
> path is on a hard denylist in the release skills for good reason.

## Prerequisites

Before you start, confirm:

- **Your GPG key is in the project `KEYS` file** at
  `https://dist.apache.org/repos/dist/release/magpie/KEYS`, and the
  matching public key is on a keyserver
  ([release-signing FAQ](https://infra.apache.org/release-signing.html)).
  If this is your first release, run
  [`release-keys-sync`](../../skills/release-keys-sync/SKILL.md)
  (Step 3) first.
- **You can write to the project's SVN dist area.** ASF committers
  can write to `dist/dev/`; `dist/release/` is PMC-only (that gate
  bites at promote time, not here).
- **The prep PR is merged** — version strings, `CHANGELOG`,
  `NOTICE`/`LICENSE` reflect `<version>`
  ([`release-prepare prep`](../../skills/release-prepare/SKILL.md),
  Step 2).
- **`git`, `gpg`, `svn`, and a SHA-512 tool** are installed locally.

## Step 1: Set the release variables

```bash
# --- edit these three lines, then paste the rest verbatim ---
export VERSION=0.1.0            # the release version, no rc suffix
export RC=rc1                   # the release-candidate number
export ASF_ID=yourapacheid      # your committer id (for svn auth)

# Derived names — do not edit.
export RC_TAG="${VERSION}-${RC}"
export ARTIFACT="apache-magpie-${VERSION}-source.zip"
export STAGE_DIR="$(pwd)/stage/${RC_TAG}"
```

## Step 2: Tag the release candidate

Cut a **signed** tag at the commit you are releasing, and push it.
(If the [`release-rc-cut`](../../skills/release-rc-cut/SKILL.md)
skill already emitted and you already pushed this tag, skip to Step
3.)

```bash
git tag -s "${RC_TAG}" -m "Apache Magpie ${VERSION} ${RC}" HEAD
git push origin "${RC_TAG}"      # 'origin' = your remote for apache/magpie
```

> Tagging from `HEAD` assumes you are on the exact release commit.
> Double-check `git log -1` first.

## Step 3: Build the source `.zip` from the tag

`git archive` produces a deterministic snapshot of **only the
tracked files** at the tag — no `.git/` directory, no untracked
build output. The `--prefix` puts everything under a versioned top
folder so the unpacked tree is `apache-magpie-<version>/`.

```bash
git archive --format=zip \
  --prefix="apache-magpie-${VERSION}/" \
  -o "${ARTIFACT}" \
  "${RC_TAG}"
```

Quick sanity check that `LICENSE` and `NOTICE` are present at the
root:

```bash
unzip -l "${ARTIFACT}" | grep -E "apache-magpie-${VERSION}/(LICENSE|NOTICE)$"
```

> [!NOTE]
> To keep files like `.github/` or CI config out of the source
> release, mark them `export-ignore` in `.gitattributes` — `git
> archive` honours it. The license-header pass
> ([Apache RAT](https://creadur.apache.org/rat/), run by
> [`release-verify-rc`](../../skills/release-verify-rc/SKILL.md) in
> Step 6) is the authoritative check on what the artefact must
> contain.

## Step 4: Sign the `.zip` (detached `.asc`)

```bash
gpg --armor --detach-sign "${ARTIFACT}"
# produces ${ARTIFACT}.asc
```

No `--passphrase` on the command line — let your GPG agent prompt.
The signature must be **detached** and **armored** (`.asc`), never
an inline or binary `.sig`.

## Step 5: Generate the SHA-512 checksum

```bash
# Linux / coreutils:
sha512sum "${ARTIFACT}" > "${ARTIFACT}.sha512"

# macOS (produces a -c-compatible file):
# shasum -a 512 "${ARTIFACT}" > "${ARTIFACT}.sha512"
```

SHA-512 is the baseline. Do **not** generate `md5` or `sha1` — they
are prohibited for new ASF releases.

## Step 6: Verify your own artefacts before staging

Catch a bad signature or a typo'd checksum before voters do:

```bash
gpg --verify "${ARTIFACT}.asc" "${ARTIFACT}"
sha512sum -c "${ARTIFACT}.sha512"     # macOS: shasum -a 512 -c
```

Both must report success (`Good signature` / `OK`).

## Step 7: Stage to `dist/dev/` over SVN

Assemble the three files into a clean staging directory, then
import that directory to the RC path under `dist/dev/`. The svnpubsub
machinery mirrors it to the public `dist.apache.org` host
automatically.

```bash
mkdir -p "${STAGE_DIR}"
cp "${ARTIFACT}" "${ARTIFACT}.asc" "${ARTIFACT}.sha512" "${STAGE_DIR}/"

svn import "${STAGE_DIR}" \
  "https://dist.apache.org/repos/dist/dev/magpie/${RC_TAG}/" \
  --username "${ASF_ID}" \
  -m "Stage Apache Magpie ${VERSION} ${RC} for vote"
```

Confirm it landed:

```bash
svn list "https://dist.apache.org/repos/dist/dev/magpie/${RC_TAG}/"
# expect: apache-magpie-<version>-source.zip(.asc)(.sha512)
```

The staging URL the `[VOTE]` email points voters at is:

```text
https://dist.apache.org/repos/dist/dev/magpie/<VERSION>-<RC>/
```

> [!IMPORTANT]
> The target URL **must** contain `dist/dev/`. Never stage to a
> `dist/release/` path here — promotion is a separate, post-vote,
> PMC-gated step ([`release-promote`](../../skills/release-promote/SKILL.md)).

## What happens after staging

1. **Verify** the staged RC end-to-end — signatures against the
   project `KEYS` (not your keyring), checksums, license headers,
   `NOTICE`/`LICENSE` presence:
   [`release-verify-rc`](../../skills/release-verify-rc/SKILL.md)
   (Step 6).
2. **Open the `[VOTE]`** thread on `dev@magpie.apache.org`:
   [`release-vote-draft`](../../skills/release-vote-draft/SKILL.md)
   (Step 7). Voting window ≥ 72 h, needs 3 binding `+1` and more
   `+1` than `-1`
   ([release-policy § approval](https://www.apache.org/legal/release-policy.html#release-approval)).
3. **Tally** the result:
   [`release-vote-tally`](../../skills/release-vote-tally/SKILL.md)
   (Step 9). On failure, bump the RC number and rerun this runbook
   from Step 2.
4. **Promote** `dist/dev/ → dist/release/` once the vote passes —
   the moment of release:
   [`release-promote`](../../skills/release-promote/SKILL.md)
   (Step 10).

## Release Manager checklist

- [ ] GPG key present in `dist/release/magpie/KEYS` and on a keyserver
- [ ] Prep PR merged; version strings, `CHANGELOG`, `NOTICE`/`LICENSE` correct
- [ ] Signed tag `<version>-<rc>` created and pushed
- [ ] Source `.zip` built from the tag (`git archive`, no `.git/`, no binaries)
- [ ] `LICENSE` + `NOTICE` present at artefact root
- [ ] Detached `.asc` signature created
- [ ] `.sha512` checksum created (no `md5`/`sha1`)
- [ ] `gpg --verify` and `sha512sum -c` both pass locally
- [ ] Artefacts imported to `dist/dev/magpie/<version>-<rc>/`
- [ ] `svn list` confirms the three files landed
- [ ] **Did not** touch any `dist/release/` path
- [ ] Staging URL handed to `release-verify-rc` / `release-vote-draft`

## Cross-references

- [`process.md`](process.md) — the 14-step lifecycle this runbook
  covers Steps 4–5 of.
- [`spec.md`](spec.md) — the state-change boundaries (agent never
  holds the key, never publishes).
- [`release-rc-cut`](../../skills/release-rc-cut/SKILL.md) — the
  skill that emits this command set from
  [`release-build.md`](../../projects/_template/release-build.md).
- [`release-keys-sync`](../../skills/release-keys-sync/SKILL.md),
  [`release-verify-rc`](../../skills/release-verify-rc/SKILL.md),
  [`release-promote`](../../skills/release-promote/SKILL.md) — the
  upstream and downstream skills.
- [ASF release policy](https://www.apache.org/legal/release-policy.html)
  — canonical; § [what is a release](https://www.apache.org/legal/release-policy.html#release-definition)
  and § [release approval](https://www.apache.org/legal/release-policy.html#release-approval).
- [ASF release distribution](https://infra.apache.org/release-distribution.html)
  — `dist/dev/` + `dist/release/` mechanics, mirror propagation,
  § [sigs-and-sums](https://infra.apache.org/release-distribution.html#sigs-and-sums).
- [ASF release signing](https://infra.apache.org/release-signing.html)
  — `KEYS` file and signing-key onboarding.
</content>
