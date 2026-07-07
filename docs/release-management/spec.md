<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Release-management (spec)](#release-management-spec)
  - [Status](#status)
  - [Cross-cutting commitments](#cross-cutting-commitments)
    - [Boundary 1: Agent never holds the RM's signing key](#boundary-1-agent-never-holds-the-rms-signing-key)
    - [Boundary 2: Agent never publishes the release](#boundary-2-agent-never-publishes-the-release)
    - [Boundary 3: Agent never sends mail to `dev@`, `users@`, `announce@`](#boundary-3-agent-never-sends-mail-to-dev-users-announce)
    - [Boundary 4: Agent never auto-flips state labels](#boundary-4-agent-never-auto-flips-state-labels)
  - [Per-skill specifications](#per-skill-specifications)
    - [`release-prepare`](#release-prepare)
    - [`release-keys-sync`](#release-keys-sync)
    - [`release-rc-cut`](#release-rc-cut)
    - [`release-verify-rc`](#release-verify-rc)
    - [`release-vote-draft`](#release-vote-draft)
    - [`release-vote-tally`](#release-vote-tally)
    - [`release-promote`](#release-promote)
    - [`release-announce-draft`](#release-announce-draft)
    - [`release-archive-sweep`](#release-archive-sweep)
    - [`release-audit-report`](#release-audit-report)
  - [Adopter contract](#adopter-contract)
  - [Eval](#eval)
  - [Open questions](#open-questions)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Release-management (spec)

## Status

Proposed. No `release-*` skill code yet. This document defines the
runtime contract the future skills must satisfy. The lifecycle they
execute against is in [`process.md`](process.md); the family overview
is in [`README.md`](README.md). The pattern matches
[Mentoring](../mentoring/spec.md), spec lands first so the contract,
state-change boundaries, and adopter knobs are reviewable
independently from skill code.

This spec is binding on future PRs that add `release-*` skill code.
A skill PR that violates a cross-cutting commitment below is a
review-blocker, not a style nit.

## Cross-cutting commitments

Every skill in this family inherits the four boundaries below. They
are non-negotiable.

### Boundary 1: Agent never holds the RM's signing key

The agent does not load, hold in memory, proxy, or invoke the
Release Manager's GPG private key, the GPG passphrase, the
hardware-token PIN, or any equivalent credential. Skills that need
a signature emit a paste-ready command sequence; the RM runs every
`gpg --detach-sign`, `git tag -s`, or token-backed operation on
their own machine, as themselves.

This mirrors
[`security-cve-allocate`](../../skills/security-cve-allocate/SKILL.md):
the skill emits the Vulnogram URL + paste-ready JSON, the human
submits the record. It satisfies
[RFC-AI-0004 Principle 1](../rfcs/RFC-AI-0004.md#principle-1--human-in-the-loop-on-every-state-change).

Practical consequences:

- No skill in this family stores, requests, or reads from
  `GPG_PASSPHRASE`, a passphrase file, a smartcard reader, or a
  key-server private endpoint.
- The
  [adopter contract § signing](#adopter-contract) declares the key
  fingerprint the RM is expected to use; the skill verifies the
  *public* counterpart appears in the project's `KEYS` and refuses
  to advance if it does not. It never sees the private side.
- Verification skills (`release-verify-rc`) use
  `gpg --verify <artefact>.asc <artefact>` against the project's
  KEYS file as their only signature operation. They never sign.
- Signing happens on hardware the RM personally controls. ASF
  policy requires the release-signing private key to live only on
  hardware the committer has physical possession of and full
  administrative control over; it MUST NOT be placed on, or used
  from, ASF-owned infrastructure
  ([release-policy.html](https://www.apache.org/legal/release-policy.html)).
  The skill states this in its hand-off text; it cannot enforce it.

### Boundary 2: Agent never publishes the release

The two operations that constitute publication are:

- `svn mv https://dist.apache.org/repos/dist/dev/<project>/<rc> https://dist.apache.org/repos/dist/release/<project>/<version>` (Step 10).
- The `[ANNOUNCE]` email send to `announce@apache.org` and the
  site-bump PR merge (Step 11).

Neither is performed by the agent. `release-promote` emits the
`svn` command set; the RM runs it under their own ASF credentials.
`release-announce-draft` emits the email body and opens (not
merges) the site-bump PR; the RM sends, a committer merges.

This boundary holds even with full per-skill permission grants. A
permission to run `svn` against `dist.apache.org` does not grant
permission to run the *promotion* svn move; that step is identified
by destination path (`dist/release/`) and is on a hard skill-side
denylist, not a permission denylist. Removing it requires editing
the skill, not the permission set.

### Boundary 3: Agent never sends mail to `dev@`, `users@`, `announce@`

Agentic Drafting skills (`release-vote-draft`, `release-announce-draft`,
`release-vote-tally` for the `[RESULT]` reply) emit email bodies as
markdown blocks the RM copies into their mail client. No skill in
the family is wired to an outbound SMTP path, an MCP send-mail
endpoint, or a CLI that posts to mailing lists. This holds even
when the adopter ships a send-mail MCP for other skill families
(e.g. security-issue-import drafting reporter replies); the
release-management skill must explicitly *not* enumerate that
capability.

The boundary is read-side too: skills may *read* mail archives
(PonyMail) to tally votes, but a read-mail capability for the
project's PonyMail archive does not extend to a write-mail
capability anywhere.

### Boundary 4: Agent never auto-flips state labels

The planning issue's status label (see
[`process.md` § Label reference](process.md#label-reference)) is
moved by the RM, not the skill. Every skill *proposes* the next
label transition in its output (e.g.
`release-vote-tally` proposes `vote-passed` or `rc-rolled`); the
RM applies it on the issue. This mirrors the security family's
discipline that
[`security-issue-triage`](../../skills/security-issue-triage/SKILL.md)
opens a discussion comment, never flips the label.

Rationale: labels are the lifecycle's audit trail. A label flip
the RM cannot defend after the fact is worse than a slow flip.

## Per-skill specifications

Each spec below names: scope, triggers, inputs, outputs, state-
change boundary specifics, hand-off conditions, and adopter knobs
the skill reads.

### `release-prepare`

**Mode:** Agentic Drafting. **Steps owned:** 1, 2, 14.

**Scope.** Drafts the planning issue, the prep PR (version bump +
changelog + NOTICE/LICENSE), and the post-release `-SNAPSHOT` bump
PR.

**Triggers.**

1. RM runs `/release-prepare <version>` to open the planning
   issue.
2. RM runs `/release-prepare prep <version>` to draft the prep PR
   after the planning issue is open and Step 1's scope is locked.
3. RM runs `/release-prepare post <version>` after Step 11 to
   bump the development branch.

**Inputs.**

- `<project-config>/release-trains.md`, train identity for the
  target version.
- Merged-PR set between the previous release tag and the current
  HEAD, fetched via `gh pr list` filtered by the configured base
  branch.
- `<project-config>/release-management-config.md`, Category-X
  dependency list to refuse on (per
  [ASF licensing-howto](https://www.apache.org/legal/resolved.html)).
- The previous release's `NOTICE` and `LICENSE` files for diff.

**Outputs.**

- A planning-issue body (markdown), labelled `release-planning`.
- A prep PR (separate invocation), labelled `prep-pr-open`.
- A post-release bump PR (third invocation), unlabelled.

**State-change boundary.** The skill opens the planning issue and
opens the PRs *as drafts*. The RM marks them ready and merges. The
skill never marks ready, never merges, never closes.

**Hand-off conditions.**

- A Category-X dependency appears in the prep diff → hand off to
  the RM with the dependency list; skill refuses to advance.
- The merged-PR set is empty (no changes since previous release)
  → hand off; the RM decides whether to skip the release.
- A `NOTICE` diff includes a removed attribution that the
  remaining file does not justify (still-vendored third-party
  code, missing notice) → hand off.

**Adopter knobs.**

| Key | Purpose |
|---|---|
| `release_planning_issue_template` | Markdown template path under `<project-config>/`. |
| `release_branch_base` | Default base branch for the prep PR (`main`, `master`, `<release-train>-stable`). |
| `category_x_dependencies` | Pinned list of Category-X identifiers; skill refuses if any appear. |
| `version_manifest_files` | Files the version bump touches (e.g. `pom.xml`, `pyproject.toml`). |

### `release-keys-sync`

**Mode:** Agentic Drafting. **Steps owned:** 3.

**Scope.** Draft the diff that adds the RM's public key to the
project's `KEYS` file under `dist/release/<project>/KEYS`, emit the
`svn` commit sequence, remind the RM to upload to a public
keyserver, and validate that the key meets the ASF strength floor
(RSA at least 2048-bit, or an equivalently strong algorithm).

**Triggers.**

- RM runs `/release-keys-sync` during release prep; the skill
  detects whether the configured RM key fingerprint is already in
  `KEYS` and is a no-op if so.

**Inputs.**

- `<project-config>/release-management-config.md`,
  `rm_key_fingerprint`.
- Current `KEYS` file from `dist/release/<project>/KEYS`.
- RM's public key block (fetched from a keyserver
  `keys.openpgp.org` / `keyserver.ubuntu.com` by fingerprint;
  fingerprint is the only input the agent uses).

**Outputs.**

- A markdown diff showing the `KEYS` block to append.
- A paste-ready `svn checkout` + `edit` + `svn commit` command
  sequence the RM executes under their ASF credentials.

**State-change boundary.** No commit, no key fetch into a held
keyring. The skill formats the public-key block; the RM commits.
The skill never operates on the private key half.

**Hand-off conditions.**

- The fingerprint configured in
  `<project-config>/release-management-config.md` does not exist
  on the keyserver → hand off; the RM uploads it first or
  corrects the configured fingerprint.
- The configured fingerprint is already in `KEYS` but for a
  different uid (key rolled) → hand off; the RM decides whether
  to replace or append.
- The configured key is weaker than the ASF floor (an RSA key
  below 2048-bit) → hand off; the RM generates a conforming key
  before the release proceeds.

**Adopter knobs.**

| Key | Purpose |
|---|---|
| `keys_file_url` | `https://dist.apache.org/repos/dist/release/<project>/KEYS` (overridable for non-ASF adopters). |
| `keyserver` | Default `keys.openpgp.org`; overridable per project. |
| `rm_key_fingerprint` | Set per-RM (often in `.apache-magpie-overrides/user.md`, not project config). |

### `release-rc-cut`

**Mode:** Agentic Drafting. **Steps owned:** 4, 5.

**Scope.** Emit the paste-ready command sequence to tag the RC,
build artefacts, sign each artefact, generate checksums, and stage
to the adopter's distribution backend (default `svn import` to
`dist/dev/<project>/<version>-rcN/`; alternatives resolved from
`release_dist_backend` per
[`process.md` § Adopter backends](process.md#adopter-backends)).

**Triggers.**

- RM runs `/release-rc-cut <version> rc<N>` after the prep PR is
  merged.

**Inputs.**

- `<project-config>/release-build.md`, build invocation, digest
  set (`sha512`, optionally `sha256`), binary-exclude list.
- Current HEAD of the configured release branch.
- The RC number (from the trigger).

**Outputs.**

- A four-section markdown block: (1) `git tag -s` command,
  (2) build command, (3) `gpg --detach-sign` for each expected
  artefact, (4) `sha512sum > artefact.sha512` for each artefact.
- A second markdown block with the backend-shaped staging command
  sequence. For `svnpubsub` (ASF default): `svn import` into
  `dist/dev/<project>/<version>-rcN/`. For `github-releases`:
  `gh release create <version>-rcN --draft` plus
  `gh release upload <version>-rcN <artefact>` per artefact. For
  `s3`: `aws s3 cp --recursive <local> s3://<bucket>/<version>-rcN/`.
  For `self-hosted`: the command template at
  `release_publish_command_template` rendered with `<version>` and
  `<rcN>` substituted.

The checksum commands emit `.sha512` (and `.sha256` where the
adopter's `release-build.md` requests it) only; `MD5` and `SHA-1`
are prohibited for new releases. Signatures are detached `.asc`
files (`gpg --detach-sign --armor`), never a binary `.sig`. Both
prohibitions hold per
[release-distribution § sigs-and-sums](https://infra.apache.org/release-distribution.html#sigs-and-sums).

**State-change boundary.** The skill writes nothing to disk and
runs nothing locally. The RM runs every command on their own
machine, with their own key, in their own checkout, with their
own ASF credentials.

**Hand-off conditions.**

- The RC tag already exists on the remote → hand off; the RM
  decides whether to delete (rare) or bump RC.
- The build command in `<project-config>/release-build.md`
  exits non-zero in the RM's run, the skill never sees this
  directly; the RM reports failure back, and the skill records
  it on the planning issue.

**Adopter knobs.** Inherits `<project-config>/release-build.md`
verbatim, see the
[`projects/_template/release-build.md`](../../projects/_template/release-build.md)
scaffold.

### `release-verify-rc`

**Mode:** Agentic Triage / Agentic Pairing. **Steps owned:** 6.

**Scope.** Read-only verification of a staged RC. Designed to run
in two contexts: (1) the RM's pre-flight self-check before
posting the `[VOTE]` thread, and (2) any voter's Agentic Pairing-mode dev
loop before posting `+1`.

**Triggers.**

- RM or committer runs `/release-verify-rc <version>-rcN` against
  a staged RC URL.

**Inputs.**

- The staging URL (from the trigger).
- `<project-config>/release-build.md`, expected artefact list,
  digest set, binary-exclude rules, RAT (license-header)
  configuration path.
- The project's `KEYS` file from `dist/release/<project>/KEYS`.

**Outputs.**

- A pass/fail report per check (signatures, checksums, license
  headers via Apache RAT, NOTICE / LICENSE presence + diff vs
  previous release, no prohibited binaries, version-string
  consistency).
- A summary classification: `PASS`, `PASS-WITH-WARNINGS`, `FAIL`.

The report is a mechanical aid, not a vote. A `PASS` does not
discharge a voter's own ASF obligation to download, build, and
test the candidate on their own hardware before posting a binding
`+1`; the skill states this in the report header.

**State-change boundary.** Read-only. The skill posts no comments
unless explicitly invoked with `--post-to <planning-issue>`, in
which case it proposes a comment for the RM's confirmation before
posting.

**Hand-off conditions.**

- A signature fails to verify against the project's `KEYS`, the
  skill reports `FAIL` and refuses to mark the check ambiguous.
  The RM rolls a new RC.
- A binary appears that the binary-exclude list neither permits
  nor names, the skill reports `FAIL` and points at the file;
  the RM decides whether to exclude or pull the binary.

**Adopter knobs.** Inherits `<project-config>/release-build.md`.

### `release-vote-draft`

**Mode:** Agentic Drafting. **Steps owned:** 7.

**Scope.** Draft the `[VOTE]` email body to `dev@<project>` from
the planning issue's metadata.

**Expedited releases.** A vote window shorter than the ASF 72h
baseline is permitted only in exceptional circumstances (e.g. a
critical security fix). When `vote_window_hours` is below 72, the
skill requires an explanation of why the release is expedited in
the `[VOTE]` body and flags the RM's obligation to report the
deviation in the project's next board report, per
[release-policy.html § release approval](https://www.apache.org/legal/release-policy.html#release-approval).
The skill never silently drafts a sub-72h `[VOTE]`.

**Triggers.**

- RM runs `/release-vote-draft <version>-rcN` after the RC is
  staged and `release-verify-rc` reports `PASS`.

**Inputs.**

- Planning issue body.
- Staging URL, tag URL, KEYS URL, changelog URL.
- `<project-config>/release-management-config.md`, vote-window
  length (overrides the
  [`release-policy.html § release approval`](https://www.apache.org/legal/release-policy.html#release-approval)
  baseline if the project demands a longer window; the baseline is
  the floor, never the ceiling).
- `<project-config>/canned-responses.md`, `[VOTE]` body template
  if the project has one; otherwise the skill uses a default
  template that mirrors the
  [`release-policy.html § release approval`](https://www.apache.org/legal/release-policy.html#release-approval)
  reference body.

**Outputs.**

- A markdown block containing the `[VOTE]` subject line and body.
- A second markdown block for the planning-issue comment summarising
  the vote-open state (proposed, not auto-posted).

**State-change boundary.** No mail send. No issue comment without
explicit RM confirmation.

**Hand-off conditions.**

- `release-verify-rc` did not run, or ran with `FAIL`, skill
  refuses to draft the `[VOTE]` and hands off; the RM either
  passes verification first or explicitly overrides
  (`--skip-verify-check`, logged on the planning issue).

**Adopter knobs.**

| Key | Purpose |
|---|---|
| `vote_window_hours` | Hours the vote remains open; floor per ASF policy. |
| `vote_subject_template` | Subject-line template (`[VOTE] Release <project> <version>-rcN`). |
| `vote_dev_list` | Mailing list (`dev@<project>.apache.org`). |

### `release-vote-tally`

**Mode:** Agentic Triage. **Steps owned:** 9.

**Scope.** After the approval window closes, fetch the approval
signal from the adopter's `release_approval_mechanism` backend,
classify each reply / approval as `+1` / `0` / `-1`, classify each
approver as binding or non-binding against the configured
roster, propose the result body (mailing-list `[RESULT] [VOTE]`
or backend-equivalent).

**Fractional votes.** A fractional vote (`+0.9`, `+0.5`) is not
ambiguous: it is determinately non-binding per ASF voting
convention. The skill classifies it as non-binding directly and
does not mark it `AMBIGUOUS`. The skill also counts only the
explicit `+1` replies it parses from the thread; it never
attributes an implicit `+1` to the Release Manager.

**Triggers.**

- RM runs `/release-vote-tally <version>-rcN` after the configured
  approval window (`vote_window_hours` for `dev-list-vote`,
  `approval_window_hours` for non-list mechanisms) has elapsed.

**Inputs.**

- Approval signal: mail thread (`dev-list-vote`), Discussion
  thread + reactions (`github-discussion`), PR review approvals
  (`pr-approval`), or signed off-band roster file
  (`maintainer-roster`). Backend resolved from
  `release_approval_mechanism`.
- Approver roster: `<project-config>/pmc-roster.md` for ASF (the
  `release_approver_roster_path` default), or
  `<project-config>/release-approvers.md` (or adopter-named path)
  for non-ASF. Both files share the same schema.
- `<project-config>/release-management-config.md`, vote-pass rule
  (baseline for `dev-list-vote`:
  [`release-policy.html § release approval`](https://www.apache.org/legal/release-policy.html#release-approval)
  three binding `+1` minimum, more binding `+1` than `-1`; project
  override permitted only to *strengthen*, never to weaken; for
  non-list mechanisms, the backend-specific rule keys
  (`approval_pr_min_approvals` etc.) play the same role).

**Outputs.**

- Per-reply classification table: from-address, binding flag,
  vote value, ambiguous flag, raw vote line.
- Tally summary: binding `+1` count, binding `-1` count,
  non-binding counts, ambiguous count, pass/fail per the
  configured rule.
- A `[RESULT] [VOTE]` email body (markdown block).
- The proposed next label (`vote-passed` or `rc-rolled`).

**State-change boundary.** No mail send. No label flip. The
classification is the agent's; the decision is the RM's.

**Hand-off conditions.**

- An ambiguous vote (`+1 with one caveat`, `+1 if X is
  added`), the skill marks `AMBIGUOUS, needs RM call` and
  refuses to count. The RM resolves by replying to the voter on
  the thread; the skill re-runs after the resolution lands.
  (A fractional vote is not ambiguous, it is classified
  non-binding directly, see the *Fractional votes* note above.)
- A binding voter cannot be resolved against
  `pmc-roster.md`, the skill flags and hands off; the RM
  updates the roster or corrects the from-address.

**Adopter knobs.**

| Key | Purpose |
|---|---|
| `mail_archive` | Archive backend; default `ponymail`. |
| `mail_archive_url_template` | URL template the skill uses to fetch the thread. |
| `vote_pass_rule_overrides` | Optional stricter rule (e.g. require five binding +1); never weakens the ASF baseline. |
| `result_subject_template` | Subject line for `[RESULT] [VOTE]` (`[RESULT] [VOTE] Release <project> <version>-rcN`). |

### `release-promote`

**Mode:** Agentic Drafting. **Steps owned:** 10.

**Scope.** Emit the backend-shaped promotion command set after a
passing vote. For `svnpubsub` (ASF): `svn mv dist/dev → dist/release`
plus commit message. For `github-releases`:
`gh release edit <version> --draft=false`. For `s3`:
`aws s3 mv --recursive s3://<bucket>/<version>-rcN/ s3://<bucket>/<version>/`.
For `self-hosted`: the promote half of `release_publish_command_template`.

**Triggers.**

- RM runs `/release-promote <version>-rcN` after `release-vote-tally`
  has reported `vote-passed`.

**Inputs.**

- Staging URL (`dist/dev/<project>/<version>-rcN/`).
- Target URL (`dist/release/<project>/<version>/`).
- The `[RESULT] [VOTE]` archive URL (for the commit message).
- `<project-config>/release-management-config.md`,
  `release_dist_url_template`.

**Outputs.**

- A markdown block with the `svn` command sequence (`svn mv`,
  `svn commit -m`, expected mirror-propagation note).
- A proposed next label: `promoted`.

The mirror-propagation note also records the earliest time the
download page may be updated and the `[ANNOUNCE]` sent: ASF policy
requires at least one hour after the promote commit
([release-policy.html](https://www.apache.org/legal/release-policy.html)).

**State-change boundary.** This skill is the
[Boundary 2](#boundary-2-agent-never-publishes-the-release)
demonstration. The agent does not run the `svn mv`. The promotion
target URL is identified by `dist/release/` prefix and is on a
hard skill-side denylist; removing it requires a skill PR.

**Hand-off conditions.**

- The planning issue does not carry `vote-passed`, skill refuses
  to advance; the RM either reruns `release-vote-tally` or
  explains the override on the planning issue.
- The target URL already contains the version (e.g. a previous
  promote attempt half-landed), skill refuses and hands off; the
  RM resolves with ASF infra.
- The RM is a committer but not on the PMC roster, the
  `dist/release/` tree is PMC-write-only by default
  ([release-policy.html](https://www.apache.org/legal/release-policy.html));
  the skill emits an "ask a PMC member to publish" hand-off
  instead of the `svn mv` command set.

### `release-announce-draft`

**Mode:** Agentic Drafting. **Steps owned:** 11.

**Scope.** Draft the announcement artefact and the site-bump PR
on the configured site repo. The announcement artefact shape
depends on `release_announce_backend`: `[ANNOUNCE]` email body for
`announce-list` (ASF default), GitHub Release page body for
`github-release-notes`, blog-post markdown for `site-post`,
webhook message body for `discord-channel`. The site-bump PR is
emitted only when `site_repo` is configured.

**Triggers.**

- RM runs `/release-announce-draft <version>` after the promote
  step is confirmed (planning issue carries `promoted`).

**Inputs.**

- Planning issue body.
- The `dist/release/<project>/<version>/` URL.
- The previous release's announcement body, fetched from the
  `announce@apache.org` archive, for tone and format consistency.
- `<project-config>/site-repo.md`, site repo path, files to
  update (download page, release notes index, current-version
  banner).
- `<project-config>/release-management-config.md`,
  `announce_subject_template`.

**Outputs.**

- A markdown block with the `[ANNOUNCE]` subject + body.
- A draft PR opened against the configured site repo with the
  download-page / release-notes / banner updates.

ASF constraints the drafted artefacts must satisfy, all stated in
the output so the RM cannot miss them: the `[ANNOUNCE]` goes out no
sooner than one hour after the Step 10 promote commit; it is sent
from an `@apache.org` address (the announce list rejects other
senders); the body links the project Download Page rather than a
direct `dist.apache.org` URL; and the site-bump PR's download links
resolve through the `closer.lua` mirror redirector
([release-policy.html](https://www.apache.org/legal/release-policy.html),
[release-distribution](https://infra.apache.org/release-distribution.html)).

**State-change boundary.** No mail send. The PR is opened as
draft; the agent never marks ready and never merges.

**Hand-off conditions.**

- The site repo does not exist or the agent lacks write access,
  hand off; the RM either opens the PR manually from the drafted
  diff or grants access.
- The previous announcement body cannot be fetched (archive
  unreachable), the skill drafts from the default template and
  flags the missing-precedent on the planning issue.

### `release-archive-sweep`

**Mode:** Agentic Triage. **Steps owned:** 12.

**Scope.** Scan `dist/release/<project>/`, identify releases past
retention per the project's rule, propose the `svn mv` to
`archive.apache.org` (or the project's configured archive
location).

**Triggers.**

- RM runs `/release-archive-sweep` periodically (e.g. after each
  release; or on schedule).

**Inputs.**

- Current listing of `dist/release/<project>/`.
- `<project-config>/release-management-config.md`,
  `archive_retention_rule` (default per
  [`release-distribution`](https://infra.apache.org/release-distribution.html):
  only the latest version of each supported release line stays on
  `dist/release/`; project overrides may add lines but never
  remove the latest-of-each-line floor).
- The configured archive URL template
  (`https://archive.apache.org/dist/<project>/` by default).

**Outputs.**

- A table of releases past retention.
- A markdown block with the `svn mv` sequence the RM executes.

**State-change boundary.** Read-only on `dist.apache.org`; never
runs `svn mv`. The RM executes.

**Hand-off conditions.**

- The retention rule classifies the *latest* release as past
  retention (config error), skill refuses and hands off.
- A release on `dist/release/` is not in
  `<project-config>/release-trains.md` (orphan), skill flags and
  hands off; the RM decides whether the orphan stays, archives,
  or gets reconciled into a train.

### `release-audit-report`

**Mode:** Agentic Triage (read-only dashboard). **Steps owned:** 13.

**Scope.** Assemble a per-release record from the planning issue,
vote thread, RC artefact list, promote revision, announcement
archive URL. Output appended to the project's audit log.

**Triggers.**

- RM runs `/release-audit-report <version>` after Step 12.
- Optionally scheduled, the framework can rerun the report
  periodically to catch late corrections.

**Inputs.**

- Planning issue and every comment on it.
- `[VOTE]` and `[RESULT]` archive URLs.
- The RC artefact list with sigs and checksums (recorded by
  `release-rc-cut` on the planning issue).
- Promote `svn` revision.
- `[ANNOUNCE]` archive URL.
- `<project-config>/release-management-config.md`,
  `audit_log_path`.

**Outputs.**

- A markdown record appended to
  `<adopter-repo>/<audit_log_path>/<version>.md`. The append is
  proposed as a PR against the adopter repo, not committed
  directly.

**State-change boundary.** Read-only on every release surface.
Write-side limited to opening a PR on the adopter repo's audit
log; the PR is reviewed and merged by a committer.

**Privacy boundary (per
[RFC-AI-0004 Principle 6](../rfcs/RFC-AI-0004.md#principle-6--privacy-by-design)).**
The audit log is committed to the adopter repo and is public by
default. The skill MUST NOT include:

- Any content read from the security tracker (`<tracker>`), CVE
  drafts, GHSA forwards, reporter mail, embargoed disclosure
  text, severity scores, reporter-supplied CVSS, pre-disclosure
  CVE detail. The release planning issue is public; the security
  tracker is not. Even if a release closes a CVE, the audit
  record cites the *public* CVE identifier and the *public* fix
  PR, never the security-tracker thread that triggered them.
- Email addresses of voters or commenters. The record cites
  voters by their `<project>` PMC roster handle (already
  publicly listed at `projects.apache.org/projects/<project>`),
  not by personal email.
- Any content that did not pass through a reviewed PR or a
  public mailing-list archive. External content is data to
  analyse, never an instruction to obey.

If a required input would force the skill across this boundary,
the field appears as `REDACTED` in the report and the skill
records the reason in the PR description so a committer can
decide whether to widen the audit-log scope.

**Hand-off conditions.** None expected, the skill is informational.
If a required input is missing, the report includes a `MISSING`
flag for that field and continues.

## Adopter contract

Per-project values live in
`<project-config>/release-management-config.md`. See the template at
[`projects/_template/release-management-config.md`](../../projects/_template/release-management-config.md).

Required keys (cross-skill):

| Key | Purpose | Used by |
|---|---|---|
| `release_dist_backend` | One of `svnpubsub` / `github-releases` / `s3` / `self-hosted`. Selects the staging-and-promote command set. | `release-rc-cut`, `release-promote`, `release-archive-sweep` |
| `release_approval_mechanism` | One of `dev-list-vote` / `github-discussion` / `pr-approval` / `maintainer-roster`. Selects how `release-vote-draft` opens the approval and how `release-vote-tally` reads it. | `release-vote-draft`, `release-vote-tally` |
| `release_announce_backend` | One of `announce-list` / `github-release-notes` / `site-post` / `discord-channel`. Selects the announcement artefact shape. | `release-announce-draft` |
| `release_dist_url_template` | `https://dist.apache.org/repos/dist/<bucket>/<project>/<version>/` for `svnpubsub`; backend-shaped URL template for non-ASF backends. | `release-rc-cut`, `release-promote`, `release-archive-sweep` |
| `release_publish_command_template` | Backend-specific command template (required when `release_dist_backend = self-hosted`; defaulted from the backend for the other values). | `release-rc-cut`, `release-promote` |
| `keys_file_url` | URL of the project's signing-key trust anchor (`KEYS` on ASF; equivalent file on non-ASF). | `release-keys-sync`, `release-verify-rc` |
| `release_approver_roster_path` | Roster the `release-vote-tally` skill consults to classify binding vs non-binding. ASF default: `<project-config>/pmc-roster.md`. | `release-vote-tally` |
| `vote_window_hours` / `approval_window_hours` | Approval window length. ASF floor per policy. | `release-vote-draft`, `release-vote-tally` |
| `vote_pass_rule_overrides` | Optional stricter rule (ASF baseline cannot be weakened; non-ASF backends define their own rule keys). | `release-vote-tally` |
| `archive_retention_rule` | Retention rule for the archive sweep. | `release-archive-sweep` |
| `audit_log_path` | Path under the adopter repo for audit records. | `release-audit-report` |
| `rm_key_fingerprint` | RM's key fingerprint (often per-user, in `.apache-magpie-overrides/user.md`). | `release-keys-sync` |
| `category_x_dependencies` | Pinned Category-X identifiers; refuses prep PR if any appear. | `release-prepare` |

The contract is the single per-adopter knob set. Skills consult
the file, fall back to documented defaults if a key is missing,
and refuse to proceed if a *required* key is missing (refusal
text names the key). Backend-specific required keys (per the
backend table in
[`projects/_template/release-management-config.md`](../../projects/_template/release-management-config.md))
are required only when the corresponding backend is selected.

ASF TLP releases are pinned to `release_approval_mechanism =
dev-list-vote` (mandatory per
[`release-policy.html § release approval`](https://www.apache.org/legal/release-policy.html#release-approval))
and `release_announce_backend = announce-list` (mandatory per
[`release-policy.html § announcements`](https://www.apache.org/legal/release-policy.html#release-announcements)).
`release-vote-tally` and `release-announce-draft` refuse to run an
ASF TLP release against any other value; non-ASF adopters set the
keys their workflow uses.

## Eval

Skill behaviour in this family is probabilistic; correctness lives
in distributions, not unit tests. Every skill in this family
ships with eval cases and a grading methodology *before* it
leaves `experimental`. A skill without an eval is unreleased,
regardless of how well it performs in a demo. This complements
[RFC-AI-0004 Principle 4](../rfcs/RFC-AI-0004.md#principle-4--conversational-correctable-agentic-skills)
on conversational correctability.

Eval expectations per skill:

| Skill | Eval focus | Grading signal |
|---|---|---|
| `release-prepare` | Version-bump correctness across `version_manifest_files`; Category-X denylist hits; changelog draft on real release history | Diff matches hand-rolled bump; denylist refuses on seeded violations; changelog covers ≥90% of merged PRs in window |
| `release-keys-sync` | KEYS-block diff correctness for first-time RM | Public block matches `gpg --export --armor <fp>` byte-for-byte; never proposes a private key fragment |
| `release-rc-cut` | Paste-ready recipe completeness; signed-tag + detached-sig + checksum command set | Recipe reproduces a known-good RC end-to-end on a fixture project; no missing or extra commands |
| `release-verify-rc` | False-negative rate on tampered fixtures (mutated sig, missing checksum, prohibited binary, missing LICENSE/NOTICE, RAT failure) | Catches 100% of seeded defects; false-positive rate <5% on known-good RCs |
| `release-vote-draft` | `[VOTE]` body conformance to ASF policy; subject template correctness | Body includes mandatory checklist; subject matches `vote_subject_template`; never schedules window shorter than `vote_window_hours` |
| `release-vote-tally` | Binding/non-binding classification accuracy on real vote threads; AMBIGUOUS detection rate | Classification matches PMC ground truth on a labelled corpus; `AMBIGUOUS, needs RM call` fires on every adversarial case (lazy +1, conditional +1, retracted vote) |
| `release-promote` | `svn mv` command-set correctness | Commands replay against a sandbox `svn` mirror produce the expected target layout |
| `release-announce-draft` | `[ANNOUNCE]` body completeness; site-PR scope correctness | Body cites canonical URLs (release, KEYS, sigs); site PR touches only files in `site_pr_files` |
| `release-archive-sweep` | Retention-rule application accuracy | Identifies the exact set of past-retention releases on a fixture `dist/release/<project>/` listing; refuses on `latest_of_supported_line` violation |
| `release-audit-report` | Field coverage; `MISSING` flag accuracy | Report includes every required field where source data exists; `MISSING` only fires when source data is genuinely absent |

Eval corpora are project-specific (real `[VOTE]` threads, real
RC artefact lists), so each adopter is expected to contribute
fixtures from their own release history. The framework ships a
seed corpus per skill (synthetic but realistic) so a new adopter
can run a baseline eval before recording their own.

## Open questions

Surfaced here so reviewers can weigh in before any skill is
built.

- **Should `release-verify-rc` ship as an Agentic Pairing skill from day
  one, or land as Agentic Triage and graduate later?** Current draft: ship
  Agentic Triage-marked with explicit Agentic Pairing-mode invocation
  (`/release-verify-rc --pairing`) so the same code path serves
  the RM's project-side self-check and the voter's developer-side
  pre-flight. The framework's Agentic Pairing-mode definition is still
  proposed ([`docs/modes.md` § Pairing](../modes.md#pairing)); this
  question is best resolved alongside the Agentic Pairing spec, not in
  isolation.
- **Where do non-ASF adopters' release-distribution analogues
  plug in?** Current draft: `release_dist_url_template` is generic
  enough to point at a GitHub Releases URL or a self-hosted
  artefact store, but the `svn`-shaped commands in
  `release-rc-cut` and `release-promote` assume an svnpubsub
  workflow. A non-ASF adopter may need a parallel template
  (`release_dist_command_template`) that swaps `svn` for `aws s3
  mv` or `gh release upload`. Defer to first non-ASF pilot.
- **`release-audit-report` audit-log location: in the adopter
  repo, or in a separate audit repo?** Current draft: adopter
  repo (`<adopter>/<audit_log_path>/`). A separate audit repo
  is the right call for projects with audit-trail isolation
  requirements; the skill can support both by accepting either a
  path inside the adopter repo or a URL to a separate repo, but
  the second case requires extra credentials and is deferred.
- **Agentic Autonomous eligibility for the prep PR's `-SNAPSHOT` bump
  (Step 14)?** Current draft: not eligible. The Step 14 PR is
  mechanical (`<version>-SNAPSHOT` bump on a single manifest
  file) but per
  [`docs/modes.md` § Agentic Autonomous](../modes.md#agentic-autonomous),
  Agentic Autonomous is off until Agentic Pairing has run stable for two
  quarters. Revisit when Agentic Autonomous sequencing changes; the
  bump is a plausible first eligible class given its mechanical
  shape and reversibility.
- **Publishing to distribution areas beyond `dist/release/`, and
  validating them.** Some projects also publish a release to
  language package indexes (PyPI, npm, Maven Central) or container
  registries as part of the same cycle. The current family scopes
  to the ASF `dist/` svnpubsub area only. A future skill could
  draft and verify those secondary publications. Out of scope for
  this first docs PR; tracked here so it is not lost.

## Cross-references

- [`README.md`](README.md), [`process.md`](process.md), within
  this family.
- [`projects/_template/release-management-config.md`](../../projects/_template/release-management-config.md), adopter contract scaffold.
- [`docs/modes.md` § Drafting](../modes.md#drafting), [§ Triage](../modes.md#triage), modes the skills inhabit.
- [`docs/security/README.md`](../security/README.md), precedent
  for a multi-skill ASF-process family with shared state-change
  discipline.
- [`docs/mentoring/spec.md`](../mentoring/spec.md), precedent for
  spec-before-code.
- [`docs/rfcs/RFC-AI-0004.md`](../rfcs/RFC-AI-0004.md), the
  principles every boundary inherits.
- [ASF release policy](https://www.apache.org/legal/release-policy.html), [ASF release distribution](https://infra.apache.org/release-distribution.html), [ASF release signing](https://infra.apache.org/release-signing.html), [ASF licensing-howto](https://www.apache.org/legal/resolved.html), [Apache RAT](https://creadur.apache.org/rat/), canonical foundation references.
