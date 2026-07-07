<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [ASF SVN — release distribution (`dist.apache.org`)](#asf-svn--release-distribution-distapacheorg)
  - [Repository layout](#repository-layout)
  - [Authentication pre-flight](#authentication-pre-flight)
  - [Stage a release candidate](#stage-a-release-candidate)
  - [Verify the staged candidate](#verify-the-staged-candidate)
  - [Promote a release (vote passed)](#promote-a-release-vote-passed)
  - [Prune old releases (2-release retention policy)](#prune-old-releases-2-release-retention-policy)
  - [Update the KEYS file](#update-the-keys-file)
  - [Clean up a failed RC](#clean-up-a-failed-rc)
  - [Write-path confirmation rule](#write-path-confirmation-rule)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# ASF SVN — release distribution (`dist.apache.org`)

Shared reference for the `svn` CLI recipes the skills use against
`dist.apache.org` — the ASF release distribution area, which is an SVN
repository. Every ASF project ships its releases through this area
regardless of where its source code lives. A GitHub-hosted project
still needs these recipes to steward its release flow.

Reference: [ASF Release Distribution Policy](https://infra.apache.org/release-distribution.html).

---

## Repository layout

```text
dist.apache.org/repos/dist/
  dev/
    <project>/        ← release candidates staged here
      <version>-RC<n>/
        <artifact>-<version>.tar.gz
        <artifact>-<version>.tar.gz.asc
        <artifact>-<version>.tar.gz.sha512
        KEYS            ← RM's public key (must be present before vote)
  release/
    <project>/        ← promoted releases live here
      <version>/
        <artifact>-<version>.tar.gz
        ...
  archive/            ← infra-managed; old releases moved here automatically
```

The ASF 2-release retention policy requires that at most the two most
recent releases remain in `dist/release/<project>/`. Older releases
are pruned from the `release` area — they remain available at
`archive.apache.org`.

---

## Authentication pre-flight

All write operations require PMC membership (the authoritative gate;
resolved via the roster check in
[`authorization.md`](authorization.md)) plus a working SVN credential.
At Step 0 of any release-distribution step, run the `svn info`
reachability + authentication check below — but note it is **not** a
write-access check: `dist.apache.org` is world-readable, so a `0` exit
confirms only that the credential is valid and the path resolves, not
that the account may write. The write-access gate is the PMC roster
check, not this command.

```bash
# Reachability + authentication only — NOT a write-access check.
# Let svn prompt for the password; never pass it on argv.
svn info https://dist.apache.org/repos/dist/dev/<project> \
  --username <asf-id> 2>&1 | grep "^URL:"
```

A non-zero exit (e.g. `svn: E170001`) is a hard stop. A `0` exit does
not by itself authorise the write — confirm PMC membership per
[`authorization.md`](authorization.md) first.

---

## Stage a release candidate

Staging copies the locally-signed artefacts into
`dist/dev/<project>/<version>-RC<n>/` via SVN. The RM builds and signs
artefacts locally; the skill emits the paste-ready `svn` command
sequence for the RM to review and run.

```bash
# 1. Ensure the dev/<project> directory exists (first-time only)
svn mkdir \
  https://dist.apache.org/repos/dist/dev/<project> \
  --username <asf-id> \
  -m "Create dev area for <project>"

# 2. Create the RC directory
svn mkdir \
  https://dist.apache.org/repos/dist/dev/<project>/<version>-RC<n> \
  --username <asf-id> \
  -m "Stage <project> <version> RC<n>"

# 3. Import artefacts from a local staging directory
svn import \
  /path/to/local/staging/ \
  https://dist.apache.org/repos/dist/dev/<project>/<version>-RC<n>/ \
  --username <asf-id> \
  -m "Add <project> <version> RC<n> artefacts"
```

Alternatively, for incremental uploads or when the RC directory
already exists:

```bash
# Check out only the RC directory (sparse)
svn checkout --depth empty \
  https://dist.apache.org/repos/dist/dev/<project> \
  dist-dev-wc

# Add the RC subdirectory
svn update --set-depth immediates dist-dev-wc/
svn mkdir dist-dev-wc/<version>-RC<n>
cp /path/to/artefacts/* dist-dev-wc/<version>-RC<n>/
svn add dist-dev-wc/<version>-RC<n>/*
svn commit dist-dev-wc \
  --username <asf-id> \
  -m "Stage <project> <version> RC<n> artefacts"
```

---

## Verify the staged candidate

Before opening the vote, the staging area should contain exactly:

- The source tarball and any binary distributions.
- A `.asc` GPG signature for each artefact.
- A `.sha512` checksum for each artefact.
- The `KEYS` file in `dist/dev/<project>/` (not inside the RC dir).

```bash
# List the RC directory
svn list \
  https://dist.apache.org/repos/dist/dev/<project>/<version>-RC<n>/

# Verify a signature (run locally after downloading)
gpg --verify <artifact>.asc <artifact>

# Verify a checksum (run locally after downloading)
sha512sum -c <artifact>.sha512
```

---

## Promote a release (vote passed)

Promotion moves artefacts from `dist/dev/<project>/<version>-RC<n>/`
to `dist/release/<project>/<version>/` with a server-side `svn move`
— no re-upload of bytes, and the RC path is **removed** from `dev/` in
the same operation (a move, not a copy, so nothing is left staged under
`dev/`).

```bash
# Server-side move from dev to release (atomic, no re-upload).
# This removes the RC from dev/ as it creates the release path.
svn move \
  https://dist.apache.org/repos/dist/dev/<project>/<version>-RC<n> \
  https://dist.apache.org/repos/dist/release/<project>/<version> \
  --username <asf-id> \
  -m "Promote <project> <version> (RC<n> passed vote)"
```

If `svnmucc` is available, it can perform the move atomically with
additional operations (e.g. deleting old releases in the same
transaction):

```bash
svnmucc \
  -U https://dist.apache.org/repos/dist \
  --username <asf-id> \
  -m "Promote <project> <version> and prune <old-version>" \
  mv dev/<project>/<version>-RC<n> release/<project>/<version> \
  rm release/<project>/<old-version>
```

---

## Prune old releases (2-release retention policy)

The ASF release distribution policy requires retaining at most the two
most recent releases in `dist/release/<project>/`. Older releases must
be deleted from the `release` area — ASF infrastructure mirrors them
to `archive.apache.org` automatically.

```bash
# List existing releases
svn list \
  https://dist.apache.org/repos/dist/release/<project>/

# Delete an old release directory
svn delete \
  https://dist.apache.org/repos/dist/release/<project>/<old-version> \
  --username <asf-id> \
  -m "Remove <project> <old-version> per ASF 2-release retention policy (archived at archive.apache.org)"
```

The calling skill presents the list of existing releases and the
proposed deletion(s) to the user for confirmation before running
`svn delete`.

---

## Update the KEYS file

The `KEYS` file must live at `dist/dev/<project>/KEYS` (and its mirror
at `dist/release/<project>/KEYS`) and must contain the RM's public key
before the vote thread opens. The `release-keys-sync` skill manages
the diff and the paste-ready update command:

```bash
# Download the current KEYS file
svn cat \
  https://dist.apache.org/repos/dist/dev/<project>/KEYS \
  > KEYS.current

# After editing KEYS.current to add the new key:
svn checkout --depth files \
  https://dist.apache.org/repos/dist/dev/<project> \
  dist-dev-keys-wc
cp KEYS.current dist-dev-keys-wc/KEYS
svn commit dist-dev-keys-wc/KEYS \
  --username <asf-id> \
  -m "Add <asf-id> public key to KEYS"

# Mirror to release area
svn copy \
  https://dist.apache.org/repos/dist/dev/<project>/KEYS \
  https://dist.apache.org/repos/dist/release/<project>/KEYS \
  --username <asf-id> \
  -m "Sync KEYS from dev to release for <project>"
```

---

## Clean up a failed RC

If a vote fails and a new RC is cut, the failed RC directory should
be removed:

```bash
svn delete \
  https://dist.apache.org/repos/dist/dev/<project>/<version>-RC<n> \
  --username <asf-id> \
  -m "Remove failed RC: <project> <version> RC<n>"
```

---

## Write-path confirmation rule

Every `svn move`, `svn delete`, `svn commit`, and `svnmucc` invocation
in this document is a write-path operation. The calling skill must:

1. Show the exact command(s) to the user.
2. Get explicit confirmation before executing.
3. Report the SVN revision number on success.

Never run a write-path dist operation on autopilot.
