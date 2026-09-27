<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-invalidate — apply

## Step 6 — Apply

### 6a — Post the rollup entry first

`<scratch>` is the session scratch directory as an absolute path (fall back to `$TMPDIR`); `gh` may run outside the sandbox, where `$TMPDIR` differs, so pass it absolute paths.

Posting the rollup before the closing comment lets the closing
comment link to the rollup's permalink. Append to the existing
rollup comment via the upsert recipe in
[`status-rollup.md`](../../../../tools/github/status-rollup.md):

```bash
EXISTING=$(gh api repos/<tracker>/issues/comments/<rollup-comment-id> --jq .body)
cat > <scratch>/invalidate-<N>-rollup.md <<EOF
${EXISTING}

<new <details> block from Step 5e>
EOF
gh api -X PATCH repos/<tracker>/issues/comments/<rollup-comment-id> \
  -F body=@<scratch>/invalidate-<N>-rollup.md \
  --jq .html_url
```

If no rollup comment exists (very old trackers predating the
rollup convention), create one fresh with just the new entry —
same as the *create* branch of the upsert recipe.

Capture the rollup permalink for use in the closing comment.

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

`gh issue edit` ignores `--remove-label` for labels that aren't
set, so listing all candidates is safe and idempotent.

### 6d — Close the tracker

```bash
gh issue close <N> --repo <tracker> --reason 'not planned'
```

`not planned` is the right close reason — `completed` would
imply the issue was resolved, which is misleading for an
invalid disposition.

### 6e — Archive the project-board item

Run the introspection query + `archiveProjectV2Item` mutation
from Step 5c. Capture the returned `isArchived: true` and
record in the rollup if it differs from expected.

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

Capture the returned `draftId`. Update the rollup entry's
*Reporter notification* line with the actual draft ID
(re-PATCH the rollup comment if the draft ID was a placeholder
when 6a ran).

### 6g — Cleanup

Delete `<scratch>/invalidate-<N>-*.md`.
