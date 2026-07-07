<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [ATR release runbook (Apache Trusted Releases)](#atr-release-runbook-apache-trusted-releases)
  - [Why ATR](#why-atr)
  - [Status: alpha](#status-alpha)
  - [The three ATR phases vs the 14-step lifecycle](#the-three-atr-phases-vs-the-14-step-lifecycle)
  - [What ATR does *not* change](#what-atr-does-not-change)
  - [State-change boundaries (unchanged from `svnpubsub`)](#state-change-boundaries-unchanged-from-svnpubsub)
  - [Prerequisites](#prerequisites)
  - [One-time setup: the `atr` client](#one-time-setup-the-atr-client)
  - [Step A: Prep + version bump (unchanged)](#step-a-prep--version-bump-unchanged)
  - [Step B: `KEYS` in ATR (Step 3)](#step-b-keys-in-atr-step-3)
  - [Step C: Compose the release candidate (Steps 4-6)](#step-c-compose-the-release-candidate-steps-4-6)
  - [Step D: Vote (Steps 7-9)](#step-d-vote-steps-7-9)
  - [Step E: Finish + announce (Steps 10-11)](#step-e-finish--announce-steps-10-11)
  - [Step F: Archive, audit, post-release bump (Steps 12-14)](#step-f-archive-audit-post-release-bump-steps-12-14)
  - [GitHub Actions path (reproducible builds)](#github-actions-path-reproducible-builds)
  - [Release Manager checklist](#release-manager-checklist)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# ATR release runbook (Apache Trusted Releases)

The **Apache Trusted Releases (ATR)** backend for an Apache release:
compose a signed release candidate in the ATR web platform, let ATR
run the policy checks and drive the `[VOTE]`, then *finish* the
release so it is published to `dist.apache.org` and announced.

This runbook is the ATR counterpart of the
[`svn-release-runbook.md`](svn-release-runbook.md). Both describe the
**same [14-step lifecycle](process.md)** and are driven by the **same
[release-management skills](README.md)** — they differ only in the
*distribution / approval / announce backend* the mechanical middle
runs against:

| | `svnpubsub` runbook | **ATR runbook (this doc)** |
|---|---|---|
| Stage RC | `svn import` to `dist/dev/<rc>/` | **Compose** phase: upload to ATR |
| Run checks | RM/voters run [`release-verify-rc`](../../skills/release-verify-rc/SKILL.md) locally | **Compose** checks run automatically in ATR + local verify |
| Vote | RM sends `[VOTE]`, tallies by hand | **Vote** phase: ATR sends `[VOTE]`, tabulates |
| Promote | `svn mv dist/dev → dist/release` | **Finish** phase: ATR strips `-rcN`, publishes |
| Announce | RM sends `[ANNOUNCE]` | **Finish** phase: ATR-assisted announce |

`atr` is a value of the [`release_dist_backend`](../../projects/_template/release-management-config.md#backends)
switch, alongside `svnpubsub`. The 14 abstract steps are identical;
only the commands the RM (and the skills) emit change.

## Why ATR

The traditional `svnpubsub` flow scatters a release across a signed
tag, a hand-built `.zip`, a detached signature, a checksum, an
`svn import` to `dist/dev/`, a manually-composed `[VOTE]` email, a
manual tally, and an `svn mv` to `dist/release/`. Every one of those
is a place to get the mechanics wrong (bad signature, `md5` instead
of `sha512`, a stray file in the `.zip`, staging to the wrong
bucket).

ATR moves the mechanical middle onto a platform that:

- **Runs the policy checks for you, on upload.** Signature, checksum,
  `LICENSE`, `NOTICE`, and source-header checks fire asynchronously
  the moment a candidate is composed, so the RM gets fast feedback on
  policy compliance *before* asking anyone to vote.
- **Automates the vote.** ATR sends the `[VOTE]` email to `dev@` and
  tabulates the replies over the 72-hour window.
- **Publishes atomically on finish.** Finishing strips the `-rcN`
  tags from filenames, rearranges the directory structure, and
  publishes to `dist.apache.org` — replacing the error-prone
  `svn mv` promotion.

This keeps the release policy-compliant by construction, which is the
point of ATR: releases that are *trusted* because the platform, not a
tired human at 2am, enforced the mechanics.

## Status: alpha

> [!IMPORTANT]
> ATR is an **ASF Tooling** platform still in **alpha**. As of this
> writing the platform runs at the alpha deployment
> **<https://release-test.apache.org/>** (the production host will be
> **release.apache.org**), and the `atr` client and API schema are
> explicitly **not yet stable** — do not pin unattended scripts to
> them. Exact client subcommand names may shift; where this runbook
> gives a command, treat it as the shape of the operation and confirm
> the current verb with `atr --help` and the
> [ATR user guide](https://release-test.apache.org/docs/).
>
> Until Magpie's PMC ratifies ATR as the project's release backend,
> the [`svnpubsub` runbook](svn-release-runbook.md) remains the
> canonical path and this document is the forward-looking target.
> Coordinate on `dev@tooling.apache.org` / `#apache-trusted-releases`
> on ASF Slack before cutting a *real* release through ATR.

## The three ATR phases vs the 14-step lifecycle

ATR organises a release into three phases. They map onto the
[14-step lifecycle](process.md) — and onto the release skills that
own each step — like this:

| ATR phase | Lifecycle steps | Owning skill(s) | What happens |
|---|---|---|---|
| *(pre-phase)* | 1 Plan · 2 Changelog/NOTICE/LICENSE | [`release-prepare`](../../skills/release-prepare/SKILL.md) | Planning issue + version-bump PR. Off-platform; unchanged. |
| *(pre-phase)* | 3 `KEYS` | [`release-keys-sync`](../../skills/release-keys-sync/SKILL.md) | RM's public key added to the committee's `KEYS` **in ATR**. |
| **Compose** | 4 Cut RC · 5 Stage · 6 Verify | [`release-rc-cut`](../../skills/release-rc-cut/SKILL.md), [`release-verify-rc`](../../skills/release-verify-rc/SKILL.md) | Build the source artefact, sign it, upload it to ATR as a draft; ATR runs signature/checksum/license/notice/source-header checks automatically. |
| **Vote** | 7 `[VOTE]` · 8 Window · 9 Tally | [`release-vote-draft`](../../skills/release-vote-draft/SKILL.md), [`release-vote-tally`](../../skills/release-vote-tally/SKILL.md) | ATR sends the `[VOTE]` to `dev@` and tabulates replies over ≥72h. The skills draft the body and cross-check the tally against the PMC roster. |
| **Finish** | 10 Promote · 11 Announce | [`release-promote`](../../skills/release-promote/SKILL.md), [`release-announce-draft`](../../skills/release-announce-draft/SKILL.md) | ATR strips `-rcN`, rearranges the tree, publishes to `dist.apache.org`, and assists the `[ANNOUNCE]`. Records downstream distributions (PyPI, Maven Central). |
| *(post-phase)* | 12 Archive · 13 Audit · 14 Post-bump | [`release-archive-sweep`](../../skills/release-archive-sweep/SKILL.md), [`release-audit-report`](../../skills/release-audit-report/SKILL.md), [`release-prepare`](../../skills/release-prepare/SKILL.md) | Retention sweep, audit-log record, `-SNAPSHOT`/`.dev` bump. Off-platform; unchanged. |

The takeaway: **ATR replaces the mechanics of Steps 5–11**, the
error-prone middle. Steps 1–4 (plan, changelog, keys, *build*) and
12–14 (archive, audit, post-bump) are the same regardless of backend,
and the same skills drive them.

## What ATR does *not* change

- **The source package is still the release.** ATR votes on the
  source artefact; binaries/wheels remain *convenience*
  ([release-policy § what is a release](https://www.apache.org/legal/release-policy.html#release-definition)).
- **The vote is still a `dev@` list vote** with a ≥72h window, ≥3
  binding `+1`, and more `+1` than `-1`
  ([release-policy § release approval](https://www.apache.org/legal/release-policy.html#release-approval)).
  ATR *drives* it; it does not replace the PMC's binding vote.
- **The RM still signs.** ATR verifies signatures; it never holds the
  RM's private key. Signing happens on the RM's machine (or a hardware
  key), exactly as with `svnpubsub`.
- **`announce@apache.org` is still mandatory** for the TLP
  announcement
  ([release-policy § announcements](https://www.apache.org/legal/release-policy.html#release-announcements)).

## State-change boundaries (unchanged from `svnpubsub`)

The two non-negotiable [spec](spec.md) boundaries hold identically on
the ATR backend — ATR changes *where* artefacts live, not *who* acts:

- **The agent never holds, invokes, or proxies the RM's signing
  key.** The build-and-sign of the artefact (Step 4) runs on the RM's
  machine; the agent emits the recipe, the RM runs it and signs.
  ([spec § Boundary 1](spec.md#boundary-1-agent-never-holds-the-rms-signing-key)).
- **The agent never publishes the release.** *Composing* a draft and
  *starting* a vote are RM actions in ATR; *finishing* (publishing) is
  the moment of release and is an RM/PMC action in the ATR UI or via
  the authenticated client. The skills draft; the human confirms and
  clicks/commits.
  ([spec § Boundary 2](spec.md#boundary-2-agent-never-publishes-the-release)).

Concretely: the release skills that emit paste-ready commands
(`release-rc-cut`, `release-promote`) now emit *ATR client* commands
instead of `svn` commands, but they still emit — they do not run the
publishing step themselves.

## Prerequisites

Before you start, confirm:

- **You are a committer on the Magpie committee** and can
  authenticate to ATR with your ASF credentials.
- **Your OpenPGP key is registered in ATR** for the Magpie committee
  (the ATR equivalent of being in the `KEYS` file — see Step B). If
  this is your first release, run
  [`release-keys-sync`](../../skills/release-keys-sync/SKILL.md)
  (Step 3) first.
- **The prep PR is merged** — version strings, `CHANGELOG`,
  `NOTICE`/`LICENSE` reflect `<version>`
  ([`release-prepare`](../../skills/release-prepare/SKILL.md), Step 2).
- **`git`, `gpg`, and Python 3.12+** are installed locally (the `atr`
  client needs 3.12+).

## One-time setup: the `atr` client

The [`atr` client](https://github.com/apache/tooling-releases-client)
lets you drive a release from the machine where the artefacts were
built. Install it once:

```bash
# Option 1 — uv (recommended)
curl -LsSf https://astral.sh/uv/install.sh | sh
uv tool install "apache-trusted-releases @ git+https://github.com/apache/tooling-releases-client"

# Option 2 — pip in a venv
python3 -m venv venv && source venv/bin/activate
pip3 install -U pip setuptools wheel
pip3 install "git+https://github.com/apache/tooling-releases-client"

atr --version
```

Authenticate against the ATR deployment (get the PAT from your
profile page in the ATR web UI):

```bash
atr set asf.uid <your-asf-id>
atr set tokens.pat "<personal-access-token-from-atr-site>"
atr jwt refresh          # exchanges the PAT for a short-lived JWT
```

> [!NOTE]
> Everything the client does is also doable in the ATR **web UI**.
> The web UI is the stable path while the client matures; use the
> client when you want a scriptable/CI-driven release. Both hit the
> same [ATR API](https://release-test.apache.org/api/docs) (e.g.
> `POST /api/release/create`, `POST /api/release/upload`,
> `GET /api/checks/list/...`, `POST /api/release/announce`).

## Step A: Prep + version bump (unchanged)

Identical to the `svnpubsub` flow. Run
[`release-prepare`](../../skills/release-prepare/SKILL.md):

1. It opens the **release-planning issue** (Step 1).
2. It drafts the **version-bump + `CHANGELOG` + `NOTICE`/`LICENSE`
   PR** (Step 2). Merge it before composing the RC.

No ATR interaction yet — this is ordinary repo work.

## Step B: `KEYS` in ATR (Step 3)

On `svnpubsub`, your public key must appear in
`dist/release/magpie/KEYS`. On ATR, the committee's keys live **in the
platform**: ATR stores the `KEYS` set and validates candidate
signatures against it during Compose.

If this is your first Magpie release, run
[`release-keys-sync`](../../skills/release-keys-sync/SKILL.md) to
produce the public-key block, then register it:

```bash
# Register your public key with the Magpie committee in ATR
# (web UI: Committee → Keys → Add key; or the client/API equivalent
#  of POST /api/key/add — confirm the exact verb with `atr --help`)
gpg --armor --export <your-key-fingerprint> > my-public-key.asc
# upload my-public-key.asc via the ATR UI or client
```

The agent drafts the key block and the diff; **you** own the private
key and perform the registration
([spec § Boundary 1](spec.md#boundary-1-agent-never-holds-the-rms-signing-key)).

## Step C: Compose the release candidate (Steps 4-6)

**Compose** is the ATR replacement for `svn import` + local verify.

1. **Build and sign the source artefact locally** — this half is
   unchanged from the [`svnpubsub` runbook Steps 2–5](svn-release-runbook.md#step-2-tag-the-release-candidate).
   [`release-rc-cut`](../../skills/release-rc-cut/SKILL.md) emits the
   recipe from [`release-build.md`](../../projects/_template/release-build.md):

   ```bash
   export VERSION=0.1.0
   export RC=rc1
   export RC_TAG="${VERSION}-${RC}"
   export ARTIFACT="apache-magpie-${VERSION}-source.zip"

   git tag -s "${RC_TAG}" -m "Apache Magpie ${VERSION} ${RC}" HEAD
   git push origin "${RC_TAG}"

   git archive --format=zip \
     --prefix="apache-magpie-${VERSION}/" \
     -o "${ARTIFACT}" "${RC_TAG}"

   gpg --armor --detach-sign "${ARTIFACT}"      # -> ${ARTIFACT}.asc
   sha512sum "${ARTIFACT}" > "${ARTIFACT}.sha512"
   ```

   > The **build and the signature happen on your machine, with your
   > key**. ATR receives an already-signed artefact; it never signs
   > for you.

2. **Create the draft release and upload** to ATR (Compose):

   ```bash
   # Create a draft candidate for magpie <version> and upload the
   # artefact + signature + checksum. Confirm exact subcommands with
   # `atr --help`; these map to POST /api/release/create and
   # POST /api/release/upload.
   atr release create magpie "${VERSION}" --rc "${RC}"
   atr release upload  magpie "${VERSION}" \
     "${ARTIFACT}" "${ARTIFACT}.asc" "${ARTIFACT}.sha512"
   ```

3. **Let the checks run.** On upload, ATR fires asynchronous checks:
   **signature** (against the committee `KEYS`), **checksum**,
   **license**, **notice**, and **source-header** (RAT-style) checks.
   Poll them:

   ```bash
   atr checks list magpie "${VERSION}"     # GET /api/checks/list/...
   ```

   Fix any failing check and re-upload a new revision before voting.
   This is the platform-run equivalent of
   [`release-verify-rc`](../../skills/release-verify-rc/SKILL.md); you
   can *still* run `release-verify-rc` locally for a second,
   independent read (voters can too, in their own dev loop).

> [!IMPORTANT]
> A composed draft is **not** a published release. It lives in ATR's
> draft/candidate area (the ATR analogue of `dist/dev/`). Nothing is
> on the public release mirror until **Finish** (Step E), after the
> vote passes.

## Step D: Vote (Steps 7-9)

ATR automates the mechanics of the `dev@` vote; the PMC still casts
the binding votes.

1. **Draft the `[VOTE]` body** with
   [`release-vote-draft`](../../skills/release-vote-draft/SKILL.md).
   It produces the subject
   (`[VOTE] Release Apache Magpie <version> from <version>-rcN`) and
   body — pointing voters at the ATR candidate page and its check
   results.
2. **Start the vote in ATR.** The RM triggers the vote for the
   composed candidate; ATR sends the `[VOTE]` email to
   `dev@magpie.apache.org` and opens the tabulation. Starting the
   vote is an **RM action** — the agent drafts, the RM starts.
3. **72-hour window** (Step 8). Minimum per
   [release-policy § release approval](https://www.apache.org/legal/release-policy.html#release-approval);
   the Magpie config may lengthen but not shorten it
   ([`release-management-config.md` § Vote](../../projects/_template/release-management-config.md#vote)).
4. **Tally** (Step 9). ATR tabulates the replies; cross-check with
   [`release-vote-tally`](../../skills/release-vote-tally/SKILL.md),
   which classifies each reply binding-vs-non-binding against the
   [`pmc-roster.md`](../../projects/_template/pmc-roster.md) and
   drafts the `[RESULT] [VOTE]`. On any ambiguity the skill refuses to
   count and flags `AMBIGUOUS, needs RM call` — **the binding tally is
   the PMC's, not the platform's**. If the vote fails, bump `RC` and
   return to Step C.

## Step E: Finish + announce (Steps 10-11)

**Finish** is the ATR replacement for the `svn mv dist/dev →
dist/release` promotion and the `[ANNOUNCE]`. **This is the moment of
release.**

1. **Finish the release** in ATR once the vote has passed. Finishing:
   - strips the `-rcN` tag from artefact filenames,
   - rearranges the directory structure into the release layout,
   - **publishes** the artefacts to `dist.apache.org` (the release
     area) via ATR.

   [`release-promote`](../../skills/release-promote/SKILL.md) now
   emits the *Finish* command (the client/API equivalent of the
   promote) instead of the `svn mv`. **Finishing is an RM/PMC action**
   — the agent drafts the command; the human runs it
   ([spec § Boundary 2](spec.md#boundary-2-agent-never-publishes-the-release)).

   ```bash
   # Publish the voted candidate as the release. Confirm the exact
   # verb with `atr --help`.
   atr release finish magpie "${VERSION}"
   ```

2. **Announce** (Step 11).
   [`release-announce-draft`](../../skills/release-announce-draft/SKILL.md)
   drafts the `[ANNOUNCE]` body (subject
   `[ANNOUNCE] Apache Magpie <version> released`) for
   `announce@apache.org`, cc `dev@` — mandatory per
   [release-policy § announcements](https://www.apache.org/legal/release-policy.html#release-announcements)
   — and the site-bump PR against
   [`site-repo.md`](../../projects/_template/site-repo.md). ATR can
   assist the announce; the **agent never sends the mail and never
   merges the site PR**.

3. **Record downstream distributions.** If Magpie ships convenience
   artefacts (e.g. a PyPI package), record each downstream location in
   ATR (`POST /api/distribution/record`) so the release catalog and
   audit trail are complete.

## Step F: Archive, audit, post-release bump (Steps 12-14)

Off-platform and unchanged from `svnpubsub`:

- **Archive sweep** (Step 12) —
  [`release-archive-sweep`](../../skills/release-archive-sweep/SKILL.md)
  applies the retention rule
  ([`release-management-config.md` § Archive](../../projects/_template/release-management-config.md#archive));
  superseded versions move to `archive.apache.org`.
- **Audit log** (Step 13) —
  [`release-audit-report`](../../skills/release-audit-report/SKILL.md)
  appends the per-release record (RM, binding voters, artefacts +
  sigs + checksums, the ATR candidate/finish references, `[ANNOUNCE]`
  archive URL) to the audit log.
- **Post-release version bump** (Step 14) —
  [`release-prepare`](../../skills/release-prepare/SKILL.md) drafts
  the `-SNAPSHOT`/`.dev` bump PR so `main` is open for the next line.

## GitHub Actions path (reproducible builds)

For a project with a **reproducible build**, ATR can compose a
candidate directly from CI using
[`apache/tooling-actions`](https://github.com/apache/tooling-actions),
authenticating to ATR with **GitHub OIDC** (no long-lived token in the
repo). The workflow builds the artefact, uploads it to ATR, and
triggers the checks — the same Compose phase, driven from Actions
instead of the RM's laptop.

This does **not** move the signing key into CI unless the project has
adopted a reproducible-build + trusted-publishing model the PMC has
explicitly signed off on. For Magpie's first releases, prefer the
local `atr` client path above (Step C); revisit CI-driven compose once
the build is demonstrably reproducible. See the
[`tooling-asf-example`](https://github.com/apache/tooling-asf-example)
repository for a worked GitHub Actions example.

## Release Manager checklist

- [ ] `atr` client installed (Python 3.12+) and authenticated
      (`atr set asf.uid` / `atr set tokens.pat` / `atr jwt refresh`)
- [ ] OpenPGP public key registered with the Magpie committee in ATR
- [ ] Prep PR merged; version strings, `CHANGELOG`, `NOTICE`/`LICENSE` correct
- [ ] Signed tag `<version>-<rc>` created and pushed
- [ ] Source artefact built from the tag (`git archive`, no `.git/`, no binaries)
- [ ] `LICENSE` + `NOTICE` present at artefact root
- [ ] Detached `.asc` signature + `.sha512` created locally (no `md5`/`sha1`)
- [ ] Candidate **composed** (uploaded) to ATR
- [ ] All ATR Compose checks green (signature/checksum/license/notice/source-headers)
- [ ] `release-verify-rc` run locally as an independent second read
- [ ] `[VOTE]` drafted; **vote started in ATR** by the RM (≥72h window)
- [ ] Tally cross-checked with `release-vote-tally` against the PMC roster
- [ ] Vote passed (≥3 binding +1, more +1 than -1) **before** finishing
- [ ] Release **finished** in ATR (RM/PMC action) — the moment of release
- [ ] `[ANNOUNCE]` drafted for `announce@apache.org` (RM sends)
- [ ] Site-bump PR opened (RM/PMC merges)
- [ ] Downstream distributions recorded in ATR
- [ ] Archive sweep, audit-log record, post-release bump done

## Cross-references

- [`process.md`](process.md) — the 14-step lifecycle this runbook
  drives against the ATR backend.
- [`svn-release-runbook.md`](svn-release-runbook.md) — the
  `svnpubsub` counterpart; same lifecycle, different backend.
- [`spec.md`](spec.md) — the state-change boundaries (agent never
  holds the key, never publishes) that hold identically on ATR.
- [`README.md`](README.md) — the release-management skill family that
  drives every step.
- [`release-management-config.md`](../../projects/_template/release-management-config.md)
  — where the `atr` distribution backend is selected.
- **ATR platform** —
  [alpha deployment](https://release-test.apache.org/) ·
  [user docs](https://release-test.apache.org/docs/) ·
  [API docs](https://release-test.apache.org/api/docs) ·
  [platform source](https://github.com/apache/tooling-trusted-releases) ·
  [`atr` client](https://github.com/apache/tooling-releases-client) ·
  [GitHub Actions](https://github.com/apache/tooling-actions) ·
  [worked example](https://github.com/apache/tooling-asf-example).
  Discussion: `dev@tooling.apache.org` / `#apache-trusted-releases` on
  ASF Slack.
- [ASF release policy](https://www.apache.org/legal/release-policy.html),
  [release distribution](https://infra.apache.org/release-distribution.html),
  [release signing](https://infra.apache.org/release-signing.html) —
  the canonical foundation references ATR enforces.
