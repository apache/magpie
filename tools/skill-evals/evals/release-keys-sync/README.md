<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-keys-sync evals

Behavioral evals for the `release-keys-sync` skill.

## Suites (9 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-0-preflight | Step 0 (pre-flight check) | 3 | clean pass (proceed), fingerprint already in KEYS (noop), key rolled with different UID (blocked) |
| step-1-key-fetch | Step 1 (fetch and validate key) | 3 | RSA 4096-bit key found and passes strength check, key not found on keyserver, weak RSA 1024-bit key fails floor |
| step-2-svn-commands | Step 2 (draft KEYS block and command sequence) | 3 | standard ASF svnpubsub commands, Ed25519 key on non-ASF GitHub-hosted KEYS, RSA key expiring within 90 days triggers advisory |

## Run

```bash
# All cases
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/release-keys-sync/

# Single suite
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/release-keys-sync/step-0-preflight/fixtures/

# Single case
uv run --directory tools/skill-evals skill-eval --cli "claude -p" \
    evals/release-keys-sync/step-0-preflight/fixtures/case-1-clean-pass
```

## Grading the prose steps (`assertions.json`)

Step 2 emits free-form prose (the KEYS block, svn command sequence,
keyserver reminder), so its `expected.json` files assert *properties*
via `has_*` keys rather than exact text. The `assertions.json` in
`step-2-svn-commands/fixtures/` maps each such key to a predicate, so
`--cli` mode grades these cases automatically.

Predicate types used: `regex` (local, deterministic) for checking that
key structural tokens appear in each field; `non_empty` for verifying
the reminder string is non-empty; `field_true` for `proposed`. The
`has_expiry_warning` predicate is a `regex` on `keyserver_upload_reminder`
that checks for expiry-advisory language (case-3 only).

## Key-strength boundary

The strength floor check (Step 1, case-3) is a hard decision: `"fail"`
is the expected `strength_check` value for RSA 1024-bit and `"pass"` for
RSA 4096-bit. These are exact-match fields and never go to the prose
grader.
