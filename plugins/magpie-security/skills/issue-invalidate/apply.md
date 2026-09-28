<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — apply

## Step 6 — Apply

### 6a — Post the rollup entry first

`<scratch>` is the session scratch directory as an absolute path (fall back to `$TMPDIR`); `gh` may run outside the sandbox, where `$TMPDIR` differs, so pass it absolute paths.

Post the rollup first, so the closing comment can link to its permalink.
Write the Step 5e entry body to `<scratch>/invalidate-<N>-rollup.md` with the Write tool and append it per the upsert recipe in
[`status-rollup.md`](../../../../tools/github/status-rollup.md):

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-invalidate rollup-append <N> "Closed as invalid" <scratch>/invalidate-<N>-rollup.md
```

This runs through vetted-ops' `vetted-op-tracker` entry point, which the secure setup lets out of the sandbox (every write still asks).
Without the secure setup, the same operations are
`uv run --directory <framework>/tools/github-rollup github-rollup --repo <tracker> append|amend-latest|fold …`
and `uv run --directory <framework>/tools/github-body-field body-field --repo <tracker> get|set …`;
see [`tools/vetted-ops/README.md`](../../../../tools/vetted-ops/README.md#tracker-procedures-rollup-and-body-field-writes).

On a very old tracker with no rollup comment, the same call creates one with just the new entry.

The tool prints the rollup comment's URL (`…#issuecomment-<id>`) on stdout and nothing else.
Keep it: the closing comment's permalink uses that comment ID.

### 6b — Post the closing comment

```bash
gh issue comment <N> --repo <tracker> --body-file <scratch>/invalidate-<N>-close.md
```

Body is the Step 5b shape with comment IDs substituted.

### 6c — Apply labels

```bash
gh issue edit <N> --repo <tracker> \
  --add-label 'invalid' \
  --remove-label '<scope-label>' \
  --remove-label 'needs triage' \
  --remove-label 'pr created' \
  --remove-label 'pr merged'
```

`gh issue edit` ignores `--remove-label` for labels that aren't set, so listing all candidates is safe and idempotent.

### 6d — Close the tracker

```bash
gh issue close <N> --repo <tracker> --reason 'not planned'
```

Use `not planned`, never `completed`: an invalid report was not resolved.

### 6e — Archive the project-board item

Run the introspection query and the `archiveProjectV2Item` mutation from Step 5c.
Capture the returned `isArchived: true`, and record in the rollup if it differs.

### 6f — Create the Gmail draft (security@-imported only)

Skip if PR-imported or the user chose `silent`.

Use the backend chosen in Step 5d:

- **`claude_ai_mcp`** (discouraged — rewrites URLs; only when the backend selection rule permits it): call `mcp__claude_ai_Gmail__get_thread`
  on `<tracker.threadId>` with `messageFormat: MINIMAL`, take
  the chronologically-last message's `id`, and call
  `mcp__claude_ai_Gmail__create_draft` with `to=<reporterEmail>`,
  `cc=security_cc`, `subject='Re: <root subject>'`,
  `body=<file>`, and `replyToMessageId=<that message id>`. The
  draft lands attached to the inbound thread.
- **`oauth_curl`** (preferred): call the `oauth_curl drafts:create` script
  per [`draft-backends.md`](../../../../tools/gmail/draft-backends.md)
  with `threadId=<tracker.threadId>`, `to=<reporterEmail>`,
  `cc=security_cc`, `subject='Re: <root subject>'`,
  `body=<file>`. The draft lands attached to the inbound thread.

Capture the returned `draftId`.
If 6a ran with a placeholder draft ID in the *Reporter notification* line,
rewrite `<scratch>/invalidate-<N>-rollup.md` with the real ID and run

```bash
uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker --caller security-issue-invalidate rollup-amend-latest <N> "Closed as invalid" <scratch>/invalidate-<N>-rollup.md
```

It keeps the entry's date and author, and refuses if someone else's entry has landed after it.

### 6g — Cleanup

Delete `<scratch>/invalidate-<N>-*.md`.
