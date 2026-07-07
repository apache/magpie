<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [ASF SVN — CLI operation catalogue](#asf-svn--cli-operation-catalogue)
  - [Authentication](#authentication)
  - [Working-copy operations](#working-copy-operations)
    - [Checkout](#checkout)
    - [Update](#update)
    - [Status](#status)
    - [Diff](#diff)
    - [Log](#log)
    - [Blame](#blame)
    - [File at revision](#file-at-revision)
  - [Write-path operations](#write-path-operations)
    - [Add and commit](#add-and-commit)
    - [Branch (server-side copy)](#branch-server-side-copy)
    - [Switch working copy to a branch](#switch-working-copy-to-a-branch)
    - [Revert](#revert)
    - [Resolve conflicts](#resolve-conflicts)
  - [Repository introspection](#repository-introspection)
  - [Error handling](#error-handling)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# ASF SVN — CLI operation catalogue

Shared reference for the `svn` CLI invocations the skills use against
ASF SVN repositories. The skills reference this file for recipe shapes;
each inline command substitutes the project-specific values from the
adopting project's manifest.

Placeholder convention used below:

- `<project>` — the ASF project name as it appears on SVN
  (e.g. `httpd`, `kafka`, `airflow`).
- `<asf-svn-root>` — `https://svn.apache.org/repos/asf` (the ASF SVN
  repository root).
- `<branch>` — a branch path relative to the project root
  (e.g. `branches/2.x`, `trunk`).
- `<rev>` — an SVN revision number (e.g. `12345`) or `HEAD`.
- `<wc>` — a local working-copy directory path.

---

## Authentication

This is the SVN equivalent of the `gh auth status` pre-flight every
skill's Step 0 runs on the GitHub tool. SVN caches credentials per-user
under `~/.subversion/auth/` (the
`svn.simple` / `svn.ssl.server` credential stores); a committer who has
authenticated once on the machine has a cached credential there, and
subsequent commands reuse it without re-prompting.

Every skill's Step 0 pre-flight must confirm two distinct things, which
SVN exposes through two different checks. For read-only operations
(log, diff, cat) on world-readable repos, neither is required —
credentials are not needed to read.

1. **Credential authenticates and the path is reachable.** `svn info`
   against the target confirms the cached credential is accepted and
   the URL resolves. **It does not prove write access**:
   `svn.apache.org/repos/asf` and `dist.apache.org/repos/dist` are
   world-readable, so `svn info` exits `0` even for a non-committer.
   Use it only as a reachability + authentication check, never as a
   write-access gate.

2. **The account actually has write authorization.** This is a roster
   fact, not something `svn info` can answer: write access comes from
   the committer's membership in the project's LDAP group (and, for
   `dist`, PMC membership). Resolve it via the `apache-projects` MCP —
   see [`authorization.md`](authorization.md). The authoritative
   write-access gate is the roster check there, not a `svn` command.

```bash
# Check 1 — reachability + authentication (NOT a write-access check).
# Reuses ~/.subversion/auth/ if a credential is already cached.
svn info https://svn.apache.org/repos/asf/<project>/trunk \
  --username <asf-id> 2>&1 | grep "^URL:"

# List the cached credentials SVN already holds (the ~/.subversion/auth view)
svn auth                      # SVN 1.9+; lists cached credential realms

# If no cached credential, authenticate by running an interactive svn
# command and letting svn PROMPT for the password. Do NOT pass the
# password on the command line: anything in argv is visible to other
# users via `ps`, and it is recorded in shell history and process logs.
# On a shared or ephemeral machine that exposure is exactly what you are
# trying to avoid, so keep the secret off argv entirely.
#
# In CI or a sandboxed agent, add --no-auth-cache so the credential is
# NOT persisted to ~/.subversion/auth/. Let svn prompt for the password
# (it reads the prompt from the controlling terminal / stdin); never put
# the secret in argv.
svn info https://svn.apache.org/repos/asf/<project>/trunk \
  --username <asf-id> --no-auth-cache        # svn prompts for the password
```

A non-zero exit or `svn: E170001` (authentication error) on check 1 is a
hard stop — the skill reports the failure and asks the user to
authenticate (populate `~/.subversion/auth/` via an interactive `svn`
command) rather than retrying. A `0` exit confirms only that the
credential is valid and the path is reachable; whether the account may
*write* is established by the roster check in
[`authorization.md`](authorization.md). The ASF SVN password is the
committer's ASF account password (managed at `id.apache.org`), not a
separate token — treat it as a secret and never place it on a command
line.

For `dist.apache.org` write operations (release staging and promotion)
the same two-check pre-flight applies: `svn info` against
`https://dist.apache.org/repos/dist/` confirms reachability and
authentication only (the area is world-readable, so a `0` exit does
**not** prove write access), and the authoritative write-access gate is
PMC membership resolved via [`authorization.md`](authorization.md).

```bash
# Reachability + authentication only — NOT a write-access check.
svn info https://dist.apache.org/repos/dist/dev/<project> \
  --username <asf-id> 2>&1 | grep "^URL:"
```

---

## Working-copy operations

### Checkout

```bash
# Full trunk checkout
svn checkout \
  https://svn.apache.org/repos/asf/<project>/trunk \
  <wc>

# Sparse checkout (files at root only; no recursive subdirectories)
svn checkout --depth files \
  https://svn.apache.org/repos/asf/<project>/trunk \
  <wc>

# Check out a branch
svn checkout \
  https://svn.apache.org/repos/asf/<project>/<branch> \
  <wc>
```

### Update

```bash
# Bring working copy to HEAD
svn update <wc>

# Bring working copy to a specific revision
svn update -r <rev> <wc>
```

### Status

```bash
# Concise status (one line per changed path)
svn status <wc>

# Concise status, suppress unversioned items
svn status -q <wc>

# Machine-readable XML status
svn status --xml <wc>
```

### Diff

```bash
# Diff uncommitted changes in the working copy
svn diff <wc>

# Diff between two revisions (server-side, no working copy needed)
svn diff -r <rev1>:<rev2> \
  https://svn.apache.org/repos/asf/<project>/trunk

# Diff a single file at two revisions
svn diff -r <rev1>:<rev2> \
  https://svn.apache.org/repos/asf/<project>/trunk/path/to/file
```

### Log

```bash
# Last N commits on trunk
svn log -l <N> https://svn.apache.org/repos/asf/<project>/trunk

# Log between two revisions (inclusive)
svn log -r <rev1>:<rev2> \
  https://svn.apache.org/repos/asf/<project>/trunk

# Log with changed-path list (verbose)
svn log --verbose -l <N> \
  https://svn.apache.org/repos/asf/<project>/trunk

# Machine-readable XML log
svn log --xml -l <N> \
  https://svn.apache.org/repos/asf/<project>/trunk
```

### Blame

```bash
svn blame https://svn.apache.org/repos/asf/<project>/trunk/path/to/file

# Machine-readable XML blame
svn blame --xml \
  https://svn.apache.org/repos/asf/<project>/trunk/path/to/file
```

### File at revision

```bash
# Read a file at a specific revision without touching the working copy
svn cat -r <rev> \
  https://svn.apache.org/repos/asf/<project>/trunk/path/to/file
```

---

## Write-path operations

All write-path operations require explicit user confirmation in the
calling skill before execution. This catalogue documents the command
shape; the skill enforces the confirmation gate.

### Add and commit

```bash
# Schedule new files for addition
svn add path/to/new-file path/to/new-dir/

# Schedule a deletion
svn delete path/to/old-file

# Commit (goes directly to the server — no local-only commit)
svn commit <wc> -m "<commit message>"

# Commit only specific paths
svn commit path/to/file1 path/to/file2 -m "<commit message>"
```

### Branch (server-side copy)

```bash
# Create a branch from trunk HEAD
svn copy \
  https://svn.apache.org/repos/asf/<project>/trunk \
  https://svn.apache.org/repos/asf/<project>/branches/<name> \
  -m "Create branch <name> from trunk"

# Create a tag from trunk at a specific revision
svn copy \
  https://svn.apache.org/repos/asf/<project>/trunk@<rev> \
  https://svn.apache.org/repos/asf/<project>/tags/<name> \
  -m "Tag <name> at r<rev>"
```

### Switch working copy to a branch

```bash
svn switch \
  https://svn.apache.org/repos/asf/<project>/<branch> \
  <wc>
```

### Revert

```bash
# Revert all uncommitted changes (recursive)
svn revert -R <wc>

# Revert a specific file
svn revert path/to/file
```

### Resolve conflicts

```bash
# Mark a conflict as resolved after manual edit
svn resolve --accept working path/to/conflicted-file
```

---

## Repository introspection

```bash
# Show working-copy info (URL, revision, author, date)
svn info <wc>

# Show working-copy info as XML
svn info --xml <wc>

# Show repository root URL
svn info --show-item repos-root-url <wc>

# List directory contents on the server
svn list https://svn.apache.org/repos/asf/<project>/

# List branches
svn list https://svn.apache.org/repos/asf/<project>/branches/

# List tags
svn list https://svn.apache.org/repos/asf/<project>/tags/

# Show the URL the working copy is checked out from
svn info --show-item url <wc>
```

---

## Error handling

| Exit / error | Meaning | Remediation |
|---|---|---|
| `svn: E170001` | Authentication failed | Run auth pre-flight; verify ASF committer credentials |
| `svn: E155007` | Not a working copy | Wrong directory; confirm `<wc>` path |
| `svn: E160013` | File/directory not found at revision | Revision may predate the path; check with `svn log` |
| `svn: E200009` | Conflict during update | Run `svn status`, resolve conflicts, then `svn resolve` |
| `svn: E155037` | Commit blocked (pre-commit hook) | Read hook output; fix the violation before retrying |
| Non-zero + no SVN error code | Network or server error | Check `svn.apache.org` status; retry with `--no-auth-cache` removed |

A non-zero exit on the Step 0 auth check is always a hard stop — do
not retry silently.
