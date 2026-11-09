<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Aider agent harness](#aider-agent-harness)
  - [Harness contract](#harness-contract)
  - [Invoke a Magpie skill](#invoke-a-magpie-skill)
    - [Interactive terminal session](#interactive-terminal-session)
    - [Progressive skill disclosure](#progressive-skill-disclosure)
    - [Headless or automated execution](#headless-or-automated-execution)
  - [Configuration and repository instructions](#configuration-and-repository-instructions)
    - [Repository configuration (`.aider.conf.yml`)](#repository-configuration-aiderconfyml)
    - [Protecting private and local state (`.aiderignore`)](#protecting-private-and-local-state-aiderignore)
  - [Tool bridges and subshell execution](#tool-bridges-and-subshell-execution)
  - [Human-in-the-loop and git confirmation](#human-in-the-loop-and-git-confirmation)
  - [Multi-model routing and model floors](#multi-model-routing-and-model-floors)
    - [Architect and editor model split](#architect-and-editor-model-split)
    - [Local LLM connectivity (Ollama / vLLM)](#local-llm-connectivity-ollama--vllm)
  - [Clean-environment wrapper and isolation](#clean-environment-wrapper-and-isolation)
  - [Upgrade Magpie](#upgrade-magpie)
  - [Verify](#verify)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Aider agent harness

**Capability:** capability:platform

**Harness:** Aider (aider.chat)

[Aider](https://aider.chat/) is an open-source (Apache 2.0 licensed), model-agnostic terminal pair programming agent harness.
This guide documents how Aider operates as an agent harness for Apache Magpie for [#317](https://github.com/apache/magpie/issues/317).
Grounding is established by [RFC-AI-0004 Principle 3 (Vendor Neutrality)](../rfcs/RFC-AI-0004.md), which guarantees that Magpie adopters can drive all framework workflows using fully open-source, non-proprietary agent harnesses.

Aider provides an open-source execution stack with:
1. **Model independence:** Native connectivity to Anthropic Claude, OpenAI GPT, DeepSeek, Google Gemini, OpenRouter, and local open-weight inference runners (Ollama, llama.cpp, vLLM).
2. **Git-native pairing:** Tight integration with git working trees and incremental file editing.
3. **Multi-model tiering:** Built-in `--architect` mode splitting reasoning and code-editing responsibilities across specialized model tiers.

## Harness contract

| Magpie requirement | Aider implementation |
|---|---|
| Skill discovery | Aider ingests canonical `.agents/skills/magpie-*/SKILL.md` workflows on demand via `/read-only` or `--read` (Progressive Disclosure). |
| Repository instructions | Aider ingests repository instructions from `.aider.conf.yml` or `CONVENTIONS.md` (referencing `AGENTS.md` and adopter instructions from `<project-config>/`). |
| Tool execution | Aider executes Magpie's language-agnostic `tools/*` CLI bridges via in-session `/run <cmd>` or subshell execution with operator confirmation. |
| Model Context Protocol (MCP) | Aider does not include a Model Context Protocol (MCP) client; deterministic operations execute through local CLI scripts under `tools/`. |
| Human-in-the-loop (HITL) | Prescribed `--no-auto-commits` and `--no-dirty-commits` enforces strict proposal-then-confirm discipline before mutating git state. |
| Credential & environment isolation | `agent-iso aider` launches the agent through the clean-environment wrapper (Layer 0 isolation, stripping ambient tokens while passing `SSH_AUTH_SOCK`). |

## Invoke a Magpie skill

After running `/magpie-setup` to adopt the repository, the canonical `.agents/skills/` links are active in your working tree.
Aider does not discover skills on its own; load the one you need with `/read-only` or `--read` (see below).

### Interactive terminal session

Start an interactive session within the adopted repository:

```bash
# Launch Aider with filtered environment variables and disabled auto-commits
source <framework>/tools/agent-isolation/agent-iso.sh
agent-iso aider --model <model> --no-auto-commits --no-dirty-commits
```

### Progressive skill disclosure

To prevent context-window exhaustion across Magpie's 70+ workflows, load only the specific skill required for the current task:

```text
/read-only .agents/skills/magpie-security-issue-triage/SKILL.md
```

Inside the session, prompt Aider to execute the workflow:

```text
Follow the procedure in the loaded SKILL.md to triage inbound report #<issue-number>.
Adhere strictly to proposal-then-confirm discipline before applying any tracker mutations.
```

Aider reads the loaded `SKILL.md`, checks prerequisites, and presents proposed diagnostic steps before taking action.

### Headless or automated execution

For non-interactive triage passes, automated sweeps, or headless scripting:

```bash
# Headless run using an explicit instruction text (-m) and target skill file
aider --model <model> \
  --read .agents/skills/magpie-list-skills/SKILL.md \
  --message "Execute the loaded list-skills procedure and summarize available workflows." \
  --no-auto-commits
```

## Configuration and repository instructions

### Repository configuration (`.aider.conf.yml`)

Configure repository defaults in `.aider.conf.yml` at the repository root to ensure all team members operate under Magpie's safety baseline:

```yaml
# .aider.conf.yml
# 1. Enforce Human-in-the-loop confirmation
auto-commits: false
dirty-commits: false

# 2. Ingest repository safety instructions
read:
  - AGENTS.md

# 3. Model parameters (optional adopter defaults)
# model: <model>
# edit-format: diff
```

### Protecting private and local state (`.aiderignore`)

Aider automatically constructs a repository map (repomap) to track codebase structure.
To prevent Aider from reading private adopter tokens, test fixtures, or local overrides into the prompt context, configure `.aiderignore` at the repository root:

```text
# .aiderignore
.env*
*.key
*.pem
*.token
```

## Tool bridges and subshell execution

Magpie skills execute deterministic operations via language-agnostic scripts under `tools/` (e.g. `tools/cve-tool-vulnogram/`, `tools/github/`, `tools/privacy-llm/`).

When a skill requires running a tool command:
- The operator or model proposes the subshell command (e.g. `gh issue view <issue-number> --repo <tracker>`).
- In an interactive session, execute the command directly via `/run <cmd>` or `!<cmd>`.
- Actions execute in the local project environment following standard subshell semantics.

## Human-in-the-loop and git confirmation

Magpie enforces strict [Human-in-the-Loop principles](../rfcs/RFC-AI-0004.md): no destructive action or git state mutation occurs without explicit human approval.

> [!IMPORTANT]
> **Aider auto-commit policy:** By default, Aider automatically commits every code modification to git.
>
> In Magpie adopted repositories, adopters **must disable auto-commits** either via CLI flags:
> ```bash
> aider --no-auto-commits --no-dirty-commits
> ```
> or via `.aider.conf.yml`:
> ```yaml
> auto-commits: false
> dirty-commits: false
> ```

When operating with auto-commits disabled:
- **Diff review:** Review proposed file changes using `git diff` or in-session `/diff` before staging.
- **Explicit commit gating:** Use `/commit` only after confirming the change satisfies review criteria.
- **Write-access discipline:** Outbound communications, issue state changes (`gh issue close`), and remote pushes (`git push`) must always remain gated on explicit human confirmation.

## Multi-model routing and model floors

Aider supports multi-provider model routing, allowing adopters to calibrate model power against task complexity per [docs/mode-economics.md](../mode-economics.md).

### Architect and editor model split

For complex triage and vulnerability assessment, use Aider's `--architect` mode to separate high-level reasoning from code editing:

```bash
# Reasoning model handles analysis; fast editor applies diffs
aider --architect \
  --model <reasoning-model> \
  --editor-model <editor-model> \
  --no-auto-commits
```

### Local LLM connectivity (Ollama / vLLM)

For sovereign or air-gapped deployments where data cannot leave the local host (see [docs/adapters/local-llm.md](local-llm.md)):

```bash
# Connect Aider to a local Ollama instance
export OLLAMA_API_BASE=http://127.0.0.1:11434
aider --model ollama_chat/<model> \
  --no-auto-commits
```

## Clean-environment wrapper and isolation

To run Aider under Magpie's standard credential isolation policy:

```bash
source <framework>/tools/agent-isolation/agent-iso.sh
agent-iso aider --model <model> --no-auto-commits
```

The `agent-iso` launcher scrubs ambient cloud tokens while preserving local developer tooling (`git`, `uv`, `gh`, `aider`).

> [!WARNING]
> **Layer 0 Isolation Caveat:** As documented in [`tools/agent-isolation/README.md`](../../tools/agent-isolation/README.md), generic harness invocations (`agent-iso <cli>`) provide **Layer 0 environment stripping only — no push gate**. Aider receives the live `SSH_AUTH_SOCK` with nothing gating a `git push` at the wrapper boundary. Gating remote pushes relies on operating with `--no-auto-commits` and operator diligence.

## Upgrade Magpie

After a new Magpie version, load the upgrade skill and ask Aider to follow it: `/read-only .agents/skills/magpie-setup-upgrade/SKILL.md`, then *"upgrade magpie"*.
On the pinned snapshot it runs `setup update` first, then checks and fixes this machine and project.
Every skill stops on a snapshot behind the committed lock and proposes it.
Every harness: [Upgrading Magpie](../setup/marketplace.md#upgrading-magpie).

## Verify

Verify that the Aider harness wiring conforms to framework standards:

```bash
# 1. Verify skill discovery topology
PYTHONUTF8=1 uv run --project tools/symlink-lint symlink-lint

# 2. Validate skill and tool metadata
PYTHONUTF8=1 uv run --project tools/skill-and-tool-validator --group dev skill-and-tool-validate

# 3. Check vendor neutrality score
PYTHONUTF8=1 uv run --project tools/vendor-neutrality-score vendor-neutrality-score

# 4. Check documentation table of contents and formatting
uv run prek run doctoc --all-files
```

## See also

- [`docs/rfcs/RFC-AI-0004.md`](../rfcs/RFC-AI-0004.md) — normative principles for vendor neutrality and open-source harnesses.
- [`docs/vendor-neutrality.md`](../vendor-neutrality.md) — framework vendor neutrality index across agent harnesses.
- [`docs/adapters/local-llm.md`](local-llm.md) — running open-weight models via local inference engines.
- [`docs/adapters/goose.md`](goose.md) — Block's Goose agent harness guide.
- [`docs/adapters/add-a-harness.md`](add-a-harness.md) — step-by-step guide for integrating agent harnesses.
- [`tools/agent-isolation/README.md`](../../tools/agent-isolation/README.md) — clean-environment launcher.
- [Aider documentation](https://aider.chat/) — official Aider installation and usage guides.
