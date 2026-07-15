<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Privacy-LLM setup](#privacy-llm-setup)
  - [The two mechanisms recap](#the-two-mechanisms-recap)
  - [Claude Code trust boundary](#claude-code-trust-boundary)
  - [Variant 1 — Claude Code only (default)](#variant-1--claude-code-only-default)
  - [Variant 2 — Local inference (Ollama)](#variant-2--local-inference-ollama)
  - [Variant 3 — Local inference (vLLM)](#variant-3--local-inference-vllm)
  - [Variant 4 — Apache-hosted endpoint](#variant-4--apache-hosted-endpoint)
  - [Variant 5 — AWS Bedrock](#variant-5--aws-bedrock)
  - [Variant 6 — Direct Anthropic API (opt-in)](#variant-6--direct-anthropic-api-opt-in)
  - [Verifying the setup](#verifying-the-setup)
  - [Updating after a framework version bump](#updating-after-a-framework-version-bump)
  - [Status — provisional pending ASF Legal](#status--provisional-pending-asf-legal)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/legal/release-policy.html -->

# Privacy-LLM setup

How to configure the framework's privacy-aware LLM routing for
your adopting project. Pick a variant below; copy the matching
`<project-config>/privacy-llm.md` block into your project; verify
with `/magpie-setup-isolated-setup-verify` (or the privacy-llm-specific
check once PR-3 lands the gate-call wiring).

The contract behind these recipes lives in
[`tools/privacy-llm/tool.md`](../../tools/privacy-llm/tool.md),
[`tools/privacy-llm/pii.md`](../../tools/privacy-llm/pii.md), and
[`tools/privacy-llm/models.md`](../../tools/privacy-llm/models.md).
This file is **how-to**; those are the **what** and **why**.

## The two mechanisms recap

The framework treats two distinct privacy concerns separately:

1. **PII redaction** — applies to `<security-list>` content (the
   reporter mail). The body is OK to flow through any approved
   LLM. The reporter's own identity (name, email, etc.) flows
   as-is — they sent the mail and are operationally known to the
   security team. **What gets redacted** is PII the reporter
   discloses about *other people* (third-party researchers,
   victims, named individuals other than the reporter), replaced
   with hash-prefixed identifiers (`N-a3f9d2`, …) before any LLM
   step — *unless* the named individual is already a collaborator
   on the `<tracker>` repo (their identity is already public/known
   via collaborator status, no privacy gain from redacting). The
   mapping is local to the user's machine. This applies under
   **every** variant below — even Variant 1 (Claude-only).
2. **Approved-LLM gate** — applies to `<private-list>` content
   (PMC private mail) and any other private foundation lists.
   The skill refuses to fetch unless every LLM in the active
   stack is in the approved-model registry.

Picking a variant below configures the **gate** (the LLM stack).
The redactor (mechanism 1) runs regardless and needs no
per-variant config beyond the home-dir storage path.

## Claude Code trust boundary

The framework treats the Claude Code instance running the skills
as **default-approved**: a working position the maintainer chose
on 2026-05-04 in the absence of a ratified ASF Legal Affairs
list. This means:

- A pure Claude-only deployment (Variant 1) needs no per-LLM
  approval workflow — the gate is satisfied by construction.
- Adding **any** other LLM to the stack (a summarizer, a
  delegated-analysis hop, an outbound classifier) requires
  matching it against the registry per
  [`tools/privacy-llm/models.md`](../../tools/privacy-llm/models.md).
- If ASF Legal subsequently rules that Anthropic-hosted endpoints
  require a data-processing agreement for foundation private
  data, the framework will narrow this default and bump the
  registry version. Adopters using Variant 1 at that point will
  need to re-evaluate.

## Variant 1 — Claude Code only (default)

The simplest variant. Claude Code is the only LLM in the stack;
no external endpoints; the gate is auto-satisfied.

**`<project-config>/privacy-llm.md`** content (copy verbatim,
substitute `<private-list>` for your project's actual list):

```markdown
## Currently configured LLM stack

- Claude Code (the agent running framework skills)

## Approved third-party endpoints (opt-in)

(none — Claude Code is the only LLM)

## Private mailing lists for this project

- private@<project>.apache.org
```

**Setup steps:**

1. Place the file at `<project-config>/privacy-llm.md` in your
   adopter repo (alongside `project.md`).
2. Commit it. The file is project-config — it travels with the
   repo, not per-machine.
3. Run `/magpie-setup-isolated-setup-verify` to confirm the existing
   secure-agent setup is in place — no new secure-setup steps
   are needed for Variant 1.

That is the entire variant. Every framework skill that consults
`<project-config>/privacy-llm.md` will see "Claude-only" and pass
the gate.

## Variant 2 — Local inference (Ollama)

Use when the project wants a second LLM in the stack — typically
for delegated summarisation of long mail threads — without
sending data to any external service.

**Prerequisites:**

- [Ollama](https://ollama.ai) installed locally (`brew install
  ollama` on macOS; per-distribution package on Linux).
- A model pulled (`ollama pull llama3.1:8b` or similar — the
  framework does not prescribe which model).
- Ollama bound to `127.0.0.1` only (the default; do not expose to
  external interfaces).

**`<project-config>/privacy-llm.md`** content:

```markdown
## Currently configured LLM stack

- Claude Code (the agent running framework skills)
- Local Ollama at http://127.0.0.1:11434/  (model: llama3.1:8b)

## Approved third-party endpoints (opt-in)

(none — local Ollama is local-only inference, default-approved)

## Private mailing lists for this project

- private@<project>.apache.org
```

**Setup steps:**

1. Confirm Ollama is reachable: `curl
   http://127.0.0.1:11434/api/tags` returns the model list.
2. Confirm Ollama is **not** reachable from outside the host:
   `curl http://<your-LAN-IP>:11434/api/tags` should fail.
3. Place the file at `<project-config>/privacy-llm.md`. Commit.
4. The framework helper detects `127.0.0.1` (and `localhost`,
   `::1`) hostnames as default-approved local inference; no
   third-party-endpoint declaration is needed.

## Variant 3 — Local inference (vLLM)

Same shape as Ollama but targeting vLLM for projects that need a
larger model than Ollama hosts comfortably or need OpenAI-API
compatibility for downstream tooling.

**`<project-config>/privacy-llm.md`** content:

```markdown
## Currently configured LLM stack

- Claude Code (the agent running framework skills)
- Local vLLM at http://127.0.0.1:8000/v1/  (model: meta-llama/Llama-3.1-70B-Instruct)

## Approved third-party endpoints (opt-in)

(none — local vLLM is local-only inference, default-approved)

## Private mailing lists for this project

- private@<project>.apache.org
```

Same `127.0.0.1`-or-`localhost` test as Ollama applies.

## Variant 4 — Apache-hosted endpoint

Use when the ASF (or your project's PMC) hosts an inference
endpoint at an `*.apache.org` domain. These are
**default-approved** — anything served from an `*.apache.org`
hostname runs on infra under ASF governance.

**`<project-config>/privacy-llm.md`** content (substitute the
actual endpoint):

```markdown
## Currently configured LLM stack

- Claude Code (the agent running framework skills)
- ASF inference at https://inference.apache.org/v1/  (model: llama3.1-asf)

## Approved third-party endpoints (opt-in)

(none — *.apache.org endpoints are default-approved)

## Private mailing lists for this project

- private@<project>.apache.org
```

**Setup steps:**

1. Confirm the endpoint resolves under `*.apache.org`. The
   framework helper greps the URL host suffix; `apache.org` is
   the trigger.
2. Confirm authentication if the endpoint requires it. ASF
   endpoints typically authenticate via the user's ASF identity
   (LDAP / OAuth); credentials live at
   `~/.config/apache-magpie/<endpoint>-token.json` or similar
   — never in the project tree
   (see [`AGENTS.md` — Local setup](../../AGENTS.md#local-setup)).
3. Place the file at `<project-config>/privacy-llm.md`. Commit.

## Variant 5 — AWS Bedrock

**Opt-in.** AWS Bedrock with a region-bounded endpoint is a
common choice for projects whose contributors are split across
organisations and need a managed-inference fallback. The opt-in
mechanism reflects that the data-residency contract is
Bedrock-specific (region pinning, no-training, IAM-bounded
access) and the adopter's security team is responsible for
verifying it matches ASF expectations for foundation private
data.

**Prerequisites:**

- An AWS account the adopter's security team controls.
- Bedrock **enabled in a region you've verified for data
  residency** (typically a region inside the EU or a region with
  a Bedrock data-processing addendum that covers foundation
  private data).
- The model the project uses **enabled in that region** (Bedrock
  requires per-region model enablement).
- An IAM identity for the framework with
  `bedrock:InvokeModel` (and nothing else) on the specific
  model ARN.
- The IAM credentials at `~/.aws/credentials` (default AWS SDK
  path; never in the project tree).

**`<project-config>/privacy-llm.md`** content:

```markdown
## Currently configured LLM stack

- Claude Code (the agent running framework skills)
- AWS Bedrock at https://bedrock-runtime.eu-central-1.amazonaws.com
  (model: anthropic.claude-3-5-sonnet-20241022-v2:0)

## Approved third-party endpoints (opt-in)

- AWS Bedrock — eu-central-1
  - Data-residency contract: AWS DPA + Bedrock no-training default
    (https://aws.amazon.com/service-terms/, section 50.4 last
    reviewed YYYY-MM-DD)
  - IAM principal: arn:aws:iam::<account>:role/<project>-bedrock-readonly
  - Approved-by: <PMC-member-initials> <YYYY-MM-DD>

## Private mailing lists for this project

- private@<project>.apache.org
```

**Setup steps:**

1. Verify the region's data-residency contract matches your
   project's expectations for foundation private data. Document
   the link in the *Data-residency contract* line above.
2. Verify Bedrock has *Model invocation logging* **disabled** (or
   that any logging destination is inside the same compliance
   boundary). The default is disabled.
3. Provision the IAM role; place credentials at
   `~/.aws/credentials`.
4. Place the file at `<project-config>/privacy-llm.md` with the
   *Approved-by* line filled in by a PMC member of the security
   team. Commit.

## Variant 6 — Direct Anthropic API (opt-in)

**Opt-in.** Direct calls to the Anthropic API outside of Claude
Code (e.g. for a delegated-summarisation hop) require a contract
covering data-processing for ASF private data — typically a
zero-data-retention agreement plus a no-training clause.

**Prerequisites:**

- An Anthropic account with a zero-data-retention agreement
  applied to the API key.
- The API key at `~/.config/apache-magpie/anthropic-api.json`
  or via `$ANTHROPIC_API_KEY` set from a home-dir-sourced
  shell-rc — never in the project tree.

**`<project-config>/privacy-llm.md`** content:

```markdown
## Currently configured LLM stack

- Claude Code (the agent running framework skills)
- Direct Anthropic API at https://api.anthropic.com/v1/
  (model: claude-3-5-sonnet-20241022)

## Approved third-party endpoints (opt-in)

- Anthropic API direct
  - Data-residency contract: ZDR + no-training agreement applied
    to API key xxxxxx-…  (Anthropic console → Privacy → ZDR
    confirmed YYYY-MM-DD)
  - Approved-by: <PMC-member-initials> <YYYY-MM-DD>

## Private mailing lists for this project

- private@<project>.apache.org
```

The *Approved-by* line is required because Direct-Anthropic is
opt-in. A `<project-config>/privacy-llm.md` that lists this
endpoint without the *Approved-by* line will be flagged by the
gate as incomplete.

## Verifying the setup

Once `<project-config>/privacy-llm.md` is in place:

1. Run `/magpie-setup-isolated-setup-verify` to confirm the underlying
   secure-agent setup is unchanged.
2. (PR-3) Run the privacy-llm-specific check:

   ```bash
   uv run --project <framework>/tools/privacy-llm/checker \
     privacy-llm-check --reads-private-list
   ```

   Returns exit code 0 if the active stack is fully approved.
3. Sanity-check the redactor end-to-end. The third party in this
   example is `Other Researcher` (someone the reporter mentions
   in their report; the reporter's own name would NOT be passed
   to `--field`):

   ```bash
   echo "I worked with Other Researcher (other@example.com) on this finding" | \
     uv run --project <framework>/tools/privacy-llm/redactor \
     pii-redact \
     --field name:"Other Researcher" \
     --field email:"other@example.com"
   ```

   Output should replace the two values with `N-…` and `E-…`
   identifiers.
4. List the resulting map:

   ```bash
   uv run --project <framework>/tools/privacy-llm/redactor pii-list
   ```

## Updating after a framework version bump

The registry of default-approved entries can change between
framework versions (e.g. ASF Legal ratifies a list, or a previously-
default-approved class is narrowed). After running
`/magpie-setup upgrade`, re-run the verification checks above. If
an entry that was previously default-approved is now opt-in, the
gate will surface the gap and the adopter follows the recipe for
the matching variant above.

## Status — provisional pending ASF Legal

This document and the registry it points at are **provisional**:
they reflect the framework maintainer's current working position
in the absence of a ratified ASF Legal Affairs / Privacy policy
for AI-assisted handling of foundation private data. When such a
policy lands, the registry will be updated to point at it as
source-of-truth, and the variants above will be re-checked
against it.

If you are a PMC member or ASF Legal Affairs reviewer reading
this and want to formalise the list: open an issue on
[`apache/magpie`](https://github.com/apache/magpie)
referencing this file. The framework will track ratification as
a project memory and bump the registry version once the ratified
list lands.
