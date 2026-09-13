<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Gemini CLI runtime](#gemini-cli-runtime)
  - [Runtime contract](#runtime-contract)
  - [Invoke a Magpie skill](#invoke-a-magpie-skill)
  - [Install](#install)
    - [Authentication with the clean-environment wrapper](#authentication-with-the-clean-environment-wrapper)
  - [Security model](#security-model)
    - [Tool-sandboxing boundaries](#tool-sandboxing-boundaries)
    - [What asks and what denies](#what-asks-and-what-denies)
    - [Policy loading and precedence](#policy-loading-and-precedence)
    - [Deterministic guard rules](#deterministic-guard-rules)
  - [Reuse framework MCP servers](#reuse-framework-mcp-servers)
  - [Spec-loop runner](#spec-loop-runner)
  - [Verify](#verify)
  - [setup-isolated lifecycle](#setup-isolated-lifecycle)
  - [Known limitations](#known-limitations)
  - [Developer checks](#developer-checks)
  - [Upstream references](#upstream-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Gemini CLI runtime

**Capability:** capability:platform

**Harness:** Gemini CLI

Gemini CLI runs Magpie's shared skills with repository instructions, an action guard, tool sandboxing, and per-action approval policies.
The adapter is **experimental**: its Linux sandbox does not provide the Claude Code reference setup's home-directory read isolation or domain allowlist.
The integration follows the runtime contract in [add-a-harness](add-a-harness.md)
and [RFC-AI-0004](../rfcs/RFC-AI-0004.md).

## Runtime contract

| Magpie requirement | Gemini CLI implementation |
|---|---|
| Skill discovery | Gemini reads the canonical `.agents/skills/magpie-*/SKILL.md` links. The existing `universal` row in `skills/setup/agents.md` covers this path. |
| Repository instructions | The framework's `GEMINI.md` imports its `AGENTS.md`. |
| Deterministic guard | Project `.gemini/settings.json` wires `agent_guard/__init__.py --gemini` to `BeforeTool` shell events, which call the harness-neutral `dispatch()` core. Snapshot adopters register the hook using the recipe below. |
| Spec-loop | The `gemini` profile forwards the prompt, model, and output format. |
| Credential isolation | `agent-iso gemini` launches the CLI through the generic clean-environment wrapper, which filters inherited environment variables. |
| Filesystem and network | `security.toolSandboxing: true` enables Gemini's tool sandboxing. The shipped profile adds no extra writable directories or network grant. See [Tool-sandboxing boundaries](#tool-sandboxing-boundaries) for the difference between native file tools and shell access. |
| Tool approval | Explicit `policyPaths` loads `policies/magpie.toml`: scoped reads are allowed, other shell calls and native edits require confirmation, and selected commands and credential paths are denied. MCP calls require confirmation. |
| MCP servers | Register the same server commands in Gemini's user settings; see [Reuse framework MCP servers](#reuse-framework-mcp-servers). No servers or credentials are installed by this profile. |

## Invoke a Magpie skill

After [setup](../../skills/setup/SKILL.md) creates the canonical `.agents/skills/` links, Gemini discovers the same skill sources used by the other runtimes.
The [extension installation recipe](../quick-start.md#google-gemini-cli) provides another distribution path.
The framework's [`GEMINI.md`](../../GEMINI.md) imports `AGENTS.md`; adopters retain their own project instructions alongside that context.

From the adopter repository root:

1. Complete [installation](#install) and launch Gemini through the clean-environment wrapper.
2. Use `/memory show` to inspect repository instructions and `/skills list` to check discovery.
3. Ask `Use the magpie-list-skills skill.` and review the activation request.
4. Approve the skill's catalogue script when prompted; interpreter commands require tool approval even for a read-only workflow.

Skill activation consent and tool approval are separate decisions.
Skills use the existing `tools/*` adapters, whose READMEs declare their prerequisites.

## Install

Use Gemini CLI **0.59.0 or later**.
The validation baseline is 0.59.0 on Linux; later versions require [verification](#verify) before use.
The tested Linux backend requires `bwrap` (bubblewrap), usable user namespaces, and ordinary shell utilities.
Use the framework's [sandbox primitive versions](../../tools/agent-isolation/pinned-versions.toml) when installing bubblewrap.
Python 3 is also required for the existing action guard.

In this framework checkout, [`.gemini/settings.json`](../../.gemini/settings.json) already enables the profile.
From the checkout root, source the updated wrapper:

```bash
source tools/agent-isolation/agent-iso.sh
```

Then use the [authentication recipe](#authentication-with-the-clean-environment-wrapper) for your selected method to launch Gemini.

For a snapshot adopter, configure the adopter workspace as follows.
Extension installation supplies skills and context; the workspace profile and action guard still need to be configured separately.
The hook recipe below assumes a framework snapshot at `.apache-magpie/`; provision that snapshot through [setup](../../skills/setup/SKILL.md) if you only installed the extension.
Run these steps in a normal terminal or editor:

1. Copy [the policy file](../../.gemini/policies/magpie.toml) into the adopter's `.gemini/policies/magpie.toml`.
2. Merge `policyPaths`, `general`, `security`, and `tools` from the framework's settings into the adopter's `.gemini/settings.json`.
   Retain unrelated settings and existing policy paths; review conflicting security values instead of overwriting the whole file.
3. Register the action guard using the [snapshot hook recipe](../../tools/agent-guard/README.md#gemini-cli), which points at `.apache-magpie/tools/agent-guard/`.
   The framework checkout's hook path does not work unchanged inside a snapshot adopter.
4. Run `sandbox-lint --gemini .gemini` from the adopter root using the framework's tool environment, then launch through `agent-iso gemini` and [verify](#verify) the live behavior.

For a snapshot at `.apache-magpie/`, source its wrapper and validate from the adopter root:

```bash
source .apache-magpie/tools/agent-isolation/agent-iso.sh
uv run --project .apache-magpie/tools/sandbox-lint sandbox-lint --gemini .gemini
```

The [committed settings](../../.gemini/settings.json) are the profile's source of truth; avoid maintaining a second copy of the settings recipe.
Start each session from the directory containing `.gemini/`, because the policy path is relative to the launch directory.
Review Gemini's [workspace trust request](https://geminicli.com/docs/cli/trusted-folders/) if shown; project settings and hooks depend on that decision.
Restart Gemini after changing settings or policies.

### Authentication with the clean-environment wrapper

The [clean-environment wrapper](../../tools/agent-isolation/README.md#explicit-environment-opt-in) strips inherited credentials and non-essential configuration variables.
Use `AGENT_ISO_ALLOW` to pass only the variables needed by your selected [authentication method](https://geminicli.com/docs/get-started/authentication/):

| Method | Variables to pass through |
|---|---|
| Gemini API key from Google AI Studio | `GEMINI_API_KEY` |
| Vertex AI with Application Default Credentials (ADC) | `GOOGLE_CLOUD_PROJECT GOOGLE_CLOUD_LOCATION`; add `GOOGLE_APPLICATION_CREDENTIALS` for a custom credential-file path. |
| Vertex AI with a Google Cloud API key | `GOOGLE_API_KEY GOOGLE_CLOUD_PROJECT GOOGLE_CLOUD_LOCATION` |
| Sign in with Google | Usually none; pass `GOOGLE_CLOUD_PROJECT` if the account requires it. |

Configure authentication in a normal terminal first, then select the matching method in Gemini.
For an AI Studio key already set in your shell:

```bash
AGENT_ISO_ALLOW=GEMINI_API_KEY agent-iso gemini --approval-mode default
```

For Vertex with ADC and project/location already set:

```bash
AGENT_ISO_ALLOW="GOOGLE_CLOUD_PROJECT GOOGLE_CLOUD_LOCATION" \
  agent-iso gemini --approval-mode default
```

For Google sign-in without additional variables, use `agent-iso gemini --approval-mode default`.
Naming a variable does not obtain credentials; a later wrapped session must pass the required variables again.
Keep persistent credentials in the runtime's home-directory storage or your secret manager, never in a project `.env` file.
Explicitly passed credentials are available to the CLI; environment redaction for tools is a separate runtime control.

## Security model

### Tool-sandboxing boundaries

`security.toolSandboxing: true` enables Gemini's tool sandboxing.
On Linux, bubblewrap permits writes in the workspace and temporary areas; Magpie's profile starts without tool network access or additional allowed paths.
Gemini's `--sandbox` flag selects a separate full-process sandbox and is not needed for this profile.
See the upstream [sandbox guide](https://geminicli.com/docs/cli/sandbox/).

**Native file tools and shell commands have different read boundaries.**
Native file tools check paths against allowed workspace directories.
The Linux backend mounts host files broadly read-only, so an approved shell command can read files outside the workspace that the backend has not masked.
Magpie's credential-path policies deny matching native file-tool arguments; they do not prevent an approved shell from reading the same files.
The upstream [bubblewrap argument builder](https://github.com/google-gemini/gemini-cli/blob/v0.59.0/packages/core/src/sandbox/linux/bwrapArgsBuilder.ts) defines these mounts.

Tool approval authorizes an operation.
**Sandbox expansion** separately grants network access or additional filesystem access when needed.
Review the paths and duration of each grant: filesystem expansion can cover entire directories, and network expansion grants general network access rather than a domain allowlist.
Existing session grants and `~/.gemini/policies/sandbox.toml` can widen the baseline; disabling remembered tool approvals does not remove saved sandbox grants.

### What asks and what denies

The shipped policy applies these decisions to model-requested tool calls in Default Mode:

| Requested action | Result |
|---|---|
| Ordinary native workspace read | Allow under Gemini's built-in read policy. |
| Listed inspection commands, such as `git status --short`, `git diff --stat`, or `gh pr view` | Allow; network access may still require sandbox expansion. |
| Other shell commands, including tests, interpreters, `git push`, PR creation, and raw `gh api` calls | Ask before execution. |
| Native file edits and MCP calls | Ask for each call, including read-only MCP operations. |
| Listed credential/export commands, such as `gh auth token`, `curl`, or cloud CLIs | Deny. |
| Matching credential paths or `.env` files through native file/search tools | Deny. |
| Native edits to `.gemini/`, `.geminiignore`, `GEMINI.md`, or `AGENTS.md` | Deny. |

The [policy file](../../.gemini/policies/magpie.toml) defines the complete command and path lists.
Read allowances match complete command arguments; unlisted Git flags, shell operators, substitutions, and complex quoting fall back to approval.
This follows the shared intent of the Claude Code and Codex profiles: routine inspection proceeds, mutations require confirmation, and credential disclosure is denied.
Each runtime implements its own rule precedence.

Plan Mode retains scoped reads and denies other shell, edit, and MCP calls.
YOLO and remembered tool approvals are disabled, and automatic edit mode does not override the shipped ask/deny rules.
These settings preserve [per-proposal confirmation](../rfcs/RFC-AI-0004.md#principle-1--human-in-the-loop-on-every-state-change).
Commands typed directly through Gemini's shell interface have different confirmation semantics from model-requested calls.

### Policy loading and precedence

Gemini 0.59.0 requires explicit `policyPaths` to load the workspace policy at **User** tier.
The profile also retains `~/.gemini/policies`, because specifying paths replaces the default user-policy search path.
See the upstream [policy reference](https://geminicli.com/docs/reference/policy-engine/).

Within Magpie's policy, scoped read allows outrank fallback asks, while credential and configuration denies outrank both.
Plan Mode rules preserve read-only behavior despite the higher tier of the workspace policy.
Other user policies, administrative policies, command-line overrides, and sandbox grants can change the effective behavior.
The static linter checks the project profile; [live verification](#verify) checks that it is active in your installation.

### Deterministic guard rules

The project `BeforeTool` hook passes shell commands to Magpie's shared [action guard](../../tools/agent-guard/README.md#gemini-cli).
The guard enforces framework rules independently of model memory and returns Gemini's blocking exit code when a rule denies the command.
It retains the shared guard's fail-open behavior for malformed events and covers shell calls; native file and MCP calls use the policy engine.

The framework checkout registers the hook in `.gemini/settings.json` using `GEMINI_PROJECT_DIR`.
Snapshot adopters must register it in their own workspace settings using the linked recipe; `/magpie-setup` does not yet install Gemini hooks.

## Reuse framework MCP servers

Register the servers selected by the adopter's tool configuration in Gemini's user-scoped [`mcpServers` settings](https://geminicli.com/docs/tools/mcp-server/).
Reuse each adapter's server command, prerequisites, and home-directory credential storage; registrations in another runtime are not imported automatically.
For example, the [Apache Projects](../../tools/apache-projects/tool.md#1-install-the-mcp-server) and [PonyMail](../../tools/ponymail/tool.md#1-install-the-mcp-server) adapters provide compatible server commands.
Set `trust: false` and register only the servers the workflow needs.

Restart Gemini and use `/mcp` to inspect connections and discovered operations.
Tool names can differ from the Claude-oriented examples; select the equivalent server operation.
Magpie's policy asks for every MCP call and denies them in Plan Mode.
Tool sandboxing does not confine MCP server processes or their network connections.
Live MCP connections and authenticated archive access have not been verified for this profile.

## Spec-loop runner

The existing `gemini` profile in
[`tools/spec-loop/lib.sh`](../../tools/spec-loop/lib.sh) invokes the CLI with
`--approval-mode default`, `--prompt`, and `--output-format`.
It forwards `--model` when one is supplied.
Gemini has no per-invocation effort flag in the inspected CLI, so the runner
omits that option.

**Upgrade behavior:** the earlier Gemini launcher used `--yolo`; it now preserves this profile's approval boundary with `--approval-mode default`.
In headless mode, an action that needs confirmation is refused because there is no interactive approver.
Native reads and the scoped shell reads can run, but a build iteration needing edits or other approval-required calls cannot complete unattended under this profile.
Use an interactive session for those operations; the runner does not silently bypass the policy.
See the [spec-loop guide](../../tools/spec-loop/README.md) for its operating
environment and invocation options.

## Verify

From the framework checkout root, check the installed version and static profile:

```bash
gemini --version
bwrap --version
uv run --project tools/sandbox-lint sandbox-lint --gemini .gemini
```

Snapshot adopters use the command in [Install](#install).
The linter must report `OK`; it does not certify a running session.

Launch through the wrapper and check `/settings` with **Workspace Settings** selected: **Tool Sandboxing** must be enabled.
Check `/skills list` and confirm `magpie-agent-guard` is enabled in `/hooks panel`.
Then make these requests to the model, rather than using Gemini's `!` shell interface:

| Request | Expected result |
|---|---|
| Read `README.md` with `read_file`. | Read succeeds. |
| Run exactly `git status --short`. | Runs without tool approval. |
| Run exactly `python3 -c "print('magpie-probe')"`. | Asks on every invocation; decline once and retry to check this. |
| Run `gh auth token --help`. | Policy denial; the help flag keeps a failed check harmless. |
| Read the nonexistent path `.aws/magpie-policy-probe`. | Policy denial, rather than a file-not-found error. |
| Create or edit an ordinary scratch file with native tools. | Asks before each edit. |
| Run `git commit --dry-run --no-verify -m hook-probe`. | `agent-guard[no-verify]` denial; the dry run prevents a commit if the hook is missing. |

Inspect actual tool results; a verbal refusal by the model does not establish enforcement.
Repeat the read and edit checks in a new session launched with `--approval-mode plan`: scoped reads should work, while edits and unlisted shell commands are denied.
For a filesystem check, create a harmless file outside the workspace in a normal terminal, then compare a native read with an approved shell `cat` of that path.
On the tested Linux backend, the native read is refused while the shell can return the file's contents without expansion.
Decline expansion requests during this comparison and remove the scratch files afterward.

## setup-isolated lifecycle

For Gemini, follow the lifecycle steps below.
The `setup-isolated-*` skills do not yet route to this adapter.

- **Install:** follow [Install](#install) to merge the workspace settings and policy, register the guard, and launch with `agent-iso gemini`.
- **Verify:** follow [Verify](#verify) to check the configuration, live approvals, filesystem behavior, skill discovery, and guard registration.
- **Update:** compare your wrapper, workspace settings, policy, and hook with the current framework.
  Merge changes while retaining unrelated configuration, restart Gemini, and repeat verification after runtime upgrades.
- **Doctor:** inspect `/settings`, `/hooks panel`, and the actual tool denial.
  Use the checks above to distinguish a policy denial, a file-tool path rejection, and a sandbox expansion request.

Installing the extension provides skills and context; the workspace profile supplies tool sandboxing and approval policies.
The Claude-specific lifecycle probes do not verify Gemini's configuration.

## Known limitations

- **Host reads:** the [Linux read boundary](#tool-sandboxing-boundaries) differs from the Claude Code reference setup.
  Workflows requiring credentials to remain unreadable after shell approval need a separately provisioned environment containing only the required files and credentials.
- **Execution scope:** model requests, built-in web tools, hooks, and MCP servers use separate execution paths.
  Tool network restrictions are not a firewall for the whole runtime.
- **Policy coverage:** argument patterns do not resolve every symlink or encoded path.
  An approved shell can modify policy or hook files in the writable workspace; native editing-tool denies do not make them immutable.
- **Platform and version:** runtime validation covers Gemini 0.59.0 on Linux.
  macOS and Windows backends have not been verified, and the clean-environment wrapper requires a POSIX shell.
  Repeat verification after upgrades.

## Developer checks

Run the affected package suites from the framework checkout:

```bash
uv run --directory tools/sandbox-lint --group dev pytest
uv run --directory tools/agent-isolation --group dev pytest tests/test_generic_iso.py
uv run --directory tools/agent-guard --group dev pytest
bash tools/spec-loop/tests/test_runner_fixtures.sh
```

The sandbox-lint suite checks profile regressions without Gemini or Node.
The optional [runtime integration tests](../../tools/sandbox-lint/tests/integration/README.md) additionally exercise Gemini's own policy engine and Linux sandbox using synthetic files, without a model or authentication.
Use them when changing policy semantics or validating a runtime upgrade; normal CI runs the static checks only.
Complete the shared [harness validation](add-a-harness.md#step-5--validate-the-full-wiring) before submitting adapter changes.

## Upstream references

- [Gemini skills](https://geminicli.com/docs/cli/using-agent-skills/)
- [Gemini configuration](https://geminicli.com/docs/reference/configuration/)
- [Gemini authentication](https://geminicli.com/docs/get-started/authentication/)
- [Gemini tool sandboxing and sandbox expansion](https://geminicli.com/docs/cli/sandbox/#tool-sandboxing)
- [Gemini policy engine](https://geminicli.com/docs/reference/policy-engine/)
- [Gemini CLI source](https://github.com/google-gemini/gemini-cli)
