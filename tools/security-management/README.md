<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [`security-management`](#security-management)
  - [Prerequisites](#prerequisites)
  - [How to use](#how-to-use)
  - [Shared rules](#shared-rules)
  - [Commands](#commands)
    - [`issue-import`](#issue-import)
  - [Tests](#tests)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# `security-management`

**Capability:** substrate:analytics

**Harness:** agnostic

The deterministic core of the `security-*` skills.
Each skill family is a subcommand; this layer ships [`security-issue-import`](../../plugins/magpie-security/skills/issue-import/SKILL.md).
The tool takes what the agent saved — search results, the redacted report text, the confirmed plan — and decides or renders everything rule-shaped:
the Step 1 pre-filter, the batched `threadId` dedup, the forwarder pre-screen, the tracker body and its sanitiser, the rollup entry, the rejections-ledger record,
the fix-already-public reply, the receipt-draft matrix, the confirmation-reply grammar and the recap.
The agent keeps the judgement: classification, field extraction, third-party PII identification, fuzzy duplicates, prior rejections, canned-response choice and injection flagging.

**It runs nothing.**
No command invokes `gh`, a mail backend, `pii-redact` or `pii-reveal`, posts, drafts or touches the network.
Report text arrives already redacted, and redaction tokens (`N-…`, `E-…`) pass through unchanged.
A render that would emit something the skill must refuse (a rollup label holding `<`, `>` or `·`, a ledger record missing a key)
exits `2` with `{"ok": false, "refused": "<why>"}`.

## Prerequisites

- **Runtime:** Python 3.11+, stdlib only; run with `uv run --project <framework>/tools/security-management`.
  It imports two stdlib-only workspace members instead of copying their rules:
  [`github-body-field`](../github-body-field/README.md) (what a `### Field` section is) and
  [`generate-cve-json`](../cve-tool-vulnogram/generate-cve-json/README.md) (the bot/AI credit policy).
- **CLIs:** None.
- **Credentials / auth:** None.
- **Network:** None.

## How to use

Untrusted text reaches the tool only through a file the agent wrote with its Write tool, never through argv:

```bash
uv run --project <framework>/tools/security-management security-management issue-import render-body \
  --input <scratch>/body-<threadId>.json
```

Every command prints one JSON object; rendered text is in its `text` field.

## Shared rules

`security_management.shared` holds what every import skill applies; it has no CLI of its own.

| Module | Rule |
|---|---|
| `body` | `sanitise`: the well-formedness check (fence lines, `<details>`, `<!--`), heading demotion outside fences, empty fence pairs dropped, images and `<img` defused outside code. `render`: one `### <heading>` per field role, headings from `tracker.body_fields`, empty fields `_No response_`, `Severity` `Unknown`, the injection callout only when the model sets it. |
| `rollup` | Entry bodies at column 0, one-line values, the action label refused when it holds `<`, `>` or `·`, and handed back shell-quoted. |
| `refs` | `bare_refs` / `linkify` for `#NNN` and `owner/repo#NNN` outside code, ported from `pr-management`'s `_BARE_REF`. |
| `titles` | `strip_mail_prefixes`, `strip_pr_title`, `md_title`. |
| `grammar` | `parse_reply`: the confirmation grammar; anything unplaceable goes to `ambiguous_tokens` for the agent to ask back. |
| `keyword` | The `tr -cd` allowlist for search keywords, read from a file, never starting with `-`. |
| `shell` | `dq` / `w`, a copy of `release-management`'s. |

## Commands

### `issue-import`

| Command | Prints |
|---|---|
| `governance --config <security-intake-config.md>` | `reporter_acknowledgement_model`, `window_days`, `config_file_found`; `manual` / `90` when the file or the `disclosure_governance` block is absent, a `warnings` entry for a value outside the vocabulary. |
| `prefilter --threads F` | Per thread: `decision` (`keep` / `drop`), `rule` (1 GHSA relay, 2 CVE-tool bookkeeping, 3 anything else), `class`, `pretag`; `dropped` and `counts`. Every message must match rule 2 to drop; a missing subject or sender keeps; `named_thread_id` is never dropped. |
| `dedup-queries --thread-ids F` | `batches` of at most six ids, OR'd into `query`; `rejected_ids` that are not plain ids. |
| `dedup-attribute --thread-ids F --hits F` | `tracked` (id → hits), `untracked`; at 100 hits `truncated`, no `untracked`, and `rerun` batches. |
| `relay-prescreen --message F --forwarders F` | `invoke_subskill`: false only when no enabled adapter's `sender_pattern` / `preamble_match` (first 400 characters) matches; an unresolved or invalid pattern invokes. |
| `keyword --file F [--kind keywords\|email-local]` | `cleaned`, `empty`. |
| `title --input F` | `title`: the subject without its mail prefixes. |
| `linkify --input F` | `text` with every bare reference linked into `repo`, and the `bare_refs` found. |
| `render-body --input F` | The body `text`, `sanitised`, `malformed_indicator`, `fields` as github-body-field parses them, `fields_ok`, `extra_fields`, `reporter_credit_is_bot`, `bare_refs`. |
| `render-rollup --input F` | `label`, `label_shell`, `text`: the import entry, with the receipt line for a draft, a bundle, a converged disposition or a suppression, and the malformed-body note. |
| `render-ledger --input F` | The `<!-- rejection v1 -->` record; values on one line, `archive` `unresolved (archive lag)` when not given. |
| `render-fix-public-reply --input F` | The thank-without-credit reply, `merged on` / `opened on` per PR, one PR or a list. |
| `ack-decision --input F` | `draft_created`, `draft_auto_ack_tagged`, `suppressed_reason`, `rollup_note`, `rollup_receipt`, `proposal_note`, `route`, `window_days` — the Step 7 item 4 matrix. |
| `render-recap --state F` | `issues_created`, `drafts_waiting` (a shared draft once), `skipped` (full `owner/repo#NNN`), `cve_tool_bookkeeping_dropped` (pre-filtered included), `text`. |
| `parse-reply --input F` | `action`, `import_items`, `skip_items`, `reject_with_canned`, `reject_with_public_fix`, `edits`, `overrides`, `keep`, `non_import_confirmed`, `ambiguous_tokens`, `ambiguous_items`. |

## Tests

```bash
uv run --directory tools/security-management pytest -q
```

The cases of the retired model-graded `security-issue-import` suites `step-0-preflight`, `step-6-confirm` and `step-7-apply`
are pytest cases named after each former case, in `tests/test_issue_import.py` and `tests/test_grammar.py`.
`tests/test_body.py` checks that the `tracker-body-template.md` files of the sibling import skills carry exactly the rendered headings.
