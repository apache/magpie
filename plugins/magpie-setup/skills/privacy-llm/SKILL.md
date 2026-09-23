---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: privacy-llm
family: setup
mode: Meta
description: >-
  Decide which LLMs this project's skills may send private foundation
  content to, then prove it. Detects the stack in use, writes
  <project-config>/privacy-llm.md, and runs the approved-model gate and
  the PII redactor end to end so the result is demonstrated rather than
  declared.
when_to_use: >-
  Before any skill reads a private mailing list or a pre-disclosure
  report, and whenever a pre-flight says privacy-llm.md does not
  resolve. Also when the LLM stack changes, or after a framework
  upgrade, which can narrow what counts as approved by default.
capability:
  - capability:platform
surface_hash: sha256:49a65c36a0dc49ab
license: Apache-2.0
---

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- Placeholder convention (see ../../AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config>  → resolved per file: `.apache-magpie-local/` (gitignored,
                         personal) first, then `.apache-magpie-overrides/` (committed)
     <framework>       → the framework checkout or plugin root
     <private-list>    → the project's private PMC list
     <security-list>   → the project's security-report list -->

# setup-privacy-llm

Decide **which LLMs this project's skills may send private
foundation content to**, record that decision where the skills
look for it, and prove it holds.

Two mechanisms, and this skill configures one of them:

1. **The approved-LLM gate** — applies to `<private-list>` mail
   and any other private foundation list. A skill refuses to
   fetch unless *every* LLM in the active stack is approved. This
   is what the skill configures, by picking a variant.
2. **PII redaction** — applies to `<security-list>` mail. Third
   parties the reporter names are replaced with hash-prefixed
   identifiers before any LLM sees them. It runs under **every**
   variant and needs no per-variant configuration; this skill
   only verifies it works.

The recipes are [`docs/setup/privacy-llm.md`](../../../../docs/setup/privacy-llm.md);
the contract behind them is
[`tools/privacy-llm/tool.md`](../../../../tools/privacy-llm/tool.md).
This skill walks the recipe rather than restating it — read the
variant you land on before writing anything.

> [!IMPORTANT]
> **This is a project decision, not a personal preference.** What
> goes in the committed copy says what *the project* permits for
> everyone's sessions. Configure locally for yourself freely; see
> Step 5 before promoting anything to the committed half.

---

## Step 1 — Does it already resolve?

Resolve `privacy-llm.md` through the lookup chain, per file,
local first:

1. `.apache-magpie-local/privacy-llm.md` — gitignored, yours;
2. `.apache-magpie-overrides/privacy-llm.md` — committed, the
   project's.

**Both present** → say so and name which one wins here (the local
one does), because a local file silently shadowing the project's
answer is exactly the case an operator needs told. Offer to show
the difference, then go to Step 4 and verify rather than rewrite.

**Only one present** → read it, report the stack it declares, and
go to Step 4. Do not rewrite a working configuration because this
skill happened to be invoked.

**Neither** → continue to Step 2. This is the first run.

## Step 2 — Detect the stack, do not ask for it

Ask the user nothing you can determine. Establish what is
actually in the stack:

- **The agent itself** — which harness is running this skill
  (Claude Code, Codex, Gemini CLI, …). Always in the stack.
- **Local inference** — is an Ollama, llama.cpp or vLLM endpoint
  reachable and configured for this project? Check the adapter
  configuration and the environment, not a guess.
- **Third-party endpoints** — anything in the project's existing
  configuration naming a model endpoint the framework does not
  ship.
- **Whether this project has private lists at all.** A project
  with no `<private-list>` still wants the file, because the
  redactor and the gate both read it — but the variant is the
  simple one and the interview is one question shorter.

Report what you found as a list before proposing anything. A
detection the user can see is a detection they can correct.

## Step 3 — Pick the variant and write it

Map what Step 2 found onto a variant in
[`docs/setup/privacy-llm.md`](../../../../docs/setup/privacy-llm.md):

| What the stack is | Variant |
|---|---|
| The agent and nothing else | 1 — agent only (the default) |
| A local Ollama model beside it | 2 — local inference (Ollama) |
| A local vLLM endpoint beside it | 3 — local inference (vLLM) |
| An Apache-hosted endpoint | 4 — Apache-hosted endpoint |
| AWS Bedrock | 5 — Bedrock |
| The Anthropic API directly | 6 — direct API (opt-in) |

Propose the variant your detection implies, say what it means in
one sentence — *this permits the private list to be read by X and
nothing else* — and let the user correct it.

Then write `.apache-magpie-local/privacy-llm.md` from that
variant's block, substituting the project's real list addresses.
**Local, always, on this step.** Writing the gitignored copy
needs nobody's permission, is invisible to every other clone, and
is undone by deleting a directory.

Two things this step may not do: **invent an endpoint** — if the
detection is ambiguous, ask rather than assume — and **widen the
stack to make the gate pass**. The gate failing is information.

## Step 4 — Prove it, do not declare it

Run all three. A privacy configuration nobody has exercised is a
comment.

```bash
# 1. The gate: is every LLM in the active stack approved?
uv run --project <framework>/tools/privacy-llm/checker \
  privacy-llm-check --reads-private-list

# 2. The redactor, end to end. "Other Researcher" is a third party
#    the reporter named — never the reporter themselves.
echo "I worked with Other Researcher (other@example.com) on this" | \
  uv run --project <framework>/tools/privacy-llm/redactor \
  pii-redact --field name:"Other Researcher" \
             --field email:"other@example.com"

# 3. The resulting local map.
uv run --project <framework>/tools/privacy-llm/redactor pii-list
```

Expected: exit `0` from the gate; the two values in step 2 replaced
by `N-…` and `E-…` identifiers; step 3 listing them.

**A non-zero gate is the finding, not a failure of this skill.**
Report which member of the stack is unapproved and what the
options are — drop it from the stack, or take the opt-in recipe
for it — and stop. Do not edit the file until the user picks.

## Step 5 — Say that adopting exists, then stop

Everything so far is local and yours. If the project should
*commit* this answer so every contributor's session is bound by
it, that is [`adopt`](../setup/adopt.md), which promotes
`.apache-magpie-local/` into the committed
`.apache-magpie-overrides/` and stages it for review.

Say that in **one line** and name the command. Do not run it, do
not offer to run it, and do not repeat it on later invocations.
Deciding what the project permits its agents to do with private
foundation mail is a maintainer decision taken with the other
maintainers — and unlike the rest of this skill, it is the one
part that is not undone by deleting a directory.

## Step 6 — Re-run after an upgrade

What counts as default-approved can narrow between framework
versions. After `/magpie-setup upgrade`, re-run Step 4: if an
entry that used to pass is now opt-in, the gate surfaces it and
the user takes the matching variant's opt-in recipe.

Say this once, at the end of a first run. It is the reason this
skill is worth invoking a second time.

---

## Status — provisional pending ASF Legal

The registry this skill checks against is **provisional**: it
reflects the framework maintainers' working position in the
absence of a ratified ASF Legal Affairs policy for AI-assisted
handling of foundation private data. Say so when a user asks
whether a variant is "allowed" — the honest answer is that the
framework enforces a list nobody has yet ratified, and
[`docs/setup/privacy-llm.md`](../../../../docs/setup/privacy-llm.md)
carries the full caveat.
