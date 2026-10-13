<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# release-keys-sync evals

Behavioral evals for the `release-keys-sync` skill.

## Suites (2 cases total)

| Suite | Step | Cases | What it covers |
|---|---|---|---|
| step-0-preflight | Step 0 (pre-flight check) | 1 | clean pass: the `keys-sync verdict` output (fingerprint not in KEYS) is surfaced as the step's JSON |
| step-2-svn-commands | Step 2 (draft KEYS block and command sequence) | 1 | Ed25519 key on a non-ASF GitHub-hosted KEYS: the `keys-sync render` output (git clone, commit, push, PR) is surfaced as the step's JSON |

## Where the scripted cases went

The fingerprint lookup and UID comparison, the strength floor and the Step 2 KEYS block, command sequence and keyserver reminder are code:
[`release-verify list-keys`](../../../release-verify/README.md) reads the KEYS file and the fetched key in a throwaway `GNUPGHOME`,
and [`release-management keys-sync`](../../../release-management/README.md#keys-sync) decides and renders (the strength floor was `keys-sync/scripts/check_key.py`).
The model-graded cases that covered them — `step-0-preflight` cases 2–3, `step-1-key-fetch` cases 1–3 (the whole suite) and `step-2-svn-commands` cases 1 and 3 —
are pytest cases with the same scenarios and assertions, named after each former case, in
[`tests/test_keys_sync.py`](../../../release-management/tests/test_keys_sync.py).

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

## Grading the prose step (`assertions.json`)

Step 2 emits free-form prose (the KEYS block, the command sequence, the
keyserver reminder), so its `expected.json` asserts *properties* via
`has_*` keys rather than exact text. The `assertions.json` in
`step-2-svn-commands/fixtures/` maps each such key to a predicate, so
`--cli` mode grades the case automatically. The same predicates, verbatim,
grade the rendered output of the former cases 1 and 3 in pytest.
