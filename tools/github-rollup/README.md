<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [github-rollup](#github-rollup)
  - [Prerequisites](#prerequisites)
  - [Configuration](#configuration)
  - [Why](#why)
  - [Invocation](#invocation)
    - [`append <issue> --action "<label>" ...`](#append-issue---action-label-)
    - [`list <issue>`](#list-issue)
    - [`latest <issue>`](#latest-issue)
  - [Failure modes](#failure-modes)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# github-rollup

**Capability:** contract:tracker

**Kind:** implementation

**Vendor:** GitHub

Append to (or create) the status-rollup comment on a GitHub
issue **without bringing the rollup body into agent context**.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv` (`uv run --directory tools/github-rollup github-rollup …`); stdlib-only, no third-party dependencies.
- **CLIs:** `uv`; `gh` — the script shells out to it for all GitHub access (the default `@user` comes from `gh api user`).
- **Credentials / auth:** an authenticated `gh` session (`gh auth status` must pass) — the comment read / append / PATCH all go through `gh`.
- **Network:** `api.github.com` via `gh`.

## Configuration

This helper has no persistent config file of its own. Callers pass the
target issue from `<project-config>/project.md` → `tracker_repo`; the
status-rollup comment format is the GitHub tracker convention documented
in `tools/github/status-rollup.md` and reused by security lifecycle
skills.

## Why

Every skill that updates a `<tracker>` issue (import receipt,
sync passes, CVE allocation, dedupe, fix-PR announcements) folds
its status update into one rollup comment per tracker. The
existing recipe in
[`tools/github/status-rollup.md`](../github/status-rollup.md)
walks the agent through: fetch the comment, concatenate
`<old body>` + ruler + new entry, PATCH the comment. That loops
the full rollup body — which grows monotonically and is the
single largest comment on a long-running tracker — through agent
context every sync pass.

This tool does the read / append / PATCH in a subprocess. Only a
one-line confirmation lands on the agent's stderr. The body never
crosses the boundary.

## Invocation

```bash
uv run --directory tools/github-rollup github-rollup <subcommand> ...
```

### `append <issue> --action "<label>" ...`

Append a new entry to the rollup comment on `<issue>`. Creates
the rollup if none exists. Required: `--action <label>` (the
right-hand field of the entry's summary line). Body comes from
either `--entry-body "<text>"` or `--entry-body-file <path>`
(`-` reads stdin).

Optional flags:

- `--user @handle` — override the summary's `@user` field
  (default: the authenticated `gh` user from `gh api user`).
- `--now <ISO8601>` — override the date used in the summary
  (default: real now). Useful for deterministic replay tests.
- `--dry-run` — print the decision (create vs append) without
  writing.

### `list <issue>`

Print every entry's summary line in order (or `--json` for a
machine-readable array of `{date, user, action}`). Exit 3 if the
issue has no rollup yet.

### `latest <issue>`

Print just the body of the most recent entry. Useful for
*"what did the last sync do?"* in a follow-up script. Exit 3
if the rollup or entries are missing.

## Failure modes

| Exit | Meaning |
|---|---|
| 0 | Success (or `--dry-run` planned). |
| 2 | CLI argument error (mutually-exclusive flags, missing required). |
| 3 | Issue has no rollup yet, or rollup has no entries (for `latest`). |
| other | `gh` returned non-zero; the underlying stderr is forwarded. |
