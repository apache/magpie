<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Codex first-class harness](#codex-first-class-harness)
  - [Harness contract](#harness-contract)
  - [Invoke a Magpie skill](#invoke-a-magpie-skill)
  - [Install](#install)
  - [Security model](#security-model)
    - [Sandbox and network](#sandbox-and-network)
    - [Exec-policy rules and approval policy](#exec-policy-rules-and-approval-policy)
    - [Deterministic guard rules](#deterministic-guard-rules)
    - [Vetted operations](#vetted-operations)
    - [Trust boundary](#trust-boundary)
  - [Verify](#verify)
  - [setup-isolated lifecycle](#setup-isolated-lifecycle)
  - [Known limitations](#known-limitations)
  - [Comparison with the Claude setup](#comparison-with-the-claude-setup)
  - [Upstream references](#upstream-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Codex first-class harness

**Capability:** capability:platform

**Harness:** OpenAI Codex CLI, IDE, and desktop local runtime

This adapter makes Codex a native Apache Magpie skill runtime. It is not the
Claude Code codex delegation plugin: a maintainer with Codex and no Claude Code
can discover, invoke, and run Magpie skills end to end.

The implementation follows
[RFC-AI-0004](../rfcs/RFC-AI-0004.md): shared skill sources, a native sandbox,
and per-action human confirmation through Codex's own approval and exec-policy
layers.

## Harness contract

| Magpie requirement | Codex implementation |
|---|---|
| Skill discovery | Codex reads the existing canonical `.agents/skills/magpie-*/SKILL.md` symlinks directly. No SKILL.md-to-AGENTS.md translation or duplicate source tree is needed. |
| Repository instructions | Codex reads the repository `AGENTS.md` hierarchy natively. |
| Tool bridges | Skills invoke the same language-neutral `tools/` CLI adapters. Network is disabled inside `workspace-write`; approved network actions cross the sandbox through Codex rules and approval policy. |
| Filesystem sandbox | Project `.codex/config.toml` selects `workspace-write`. |
| Human in the loop | `approval_policy = "on-request"` and `.codex/rules/magpie.rules` allow scoped reads, prompt mutations, and forbid credential disclosure. |
| Deterministic guard | Native `PreToolUse` invokes the shared `tools/agent-guard` dispatcher; guard denials use Codex’s hook-specific JSON response. |
| Vetted operations | Fixed installed dispatcher prefixes allow reads and prompt both write entry points through native exec-policy. |
| Credential isolation | `tools/agent-isolation/agent-iso.sh` launches `agent-iso codex` through the shared clean-environment wrapper. |

The committed profile lives in:

~~~text
.codex/
|-- config.toml
`-- rules/
    `-- magpie.rules
~~~

Both files are policy and are reviewed in Git.

## Invoke a Magpie skill

Codex scans `.agents/skills` from the current directory to the repository root,
follows symlinked skill directories, and reads `SKILL.md` when a skill is
chosen. After `magpie-setup` has adopted the repository:

1. Start Codex at the adopter repository root, preferably with
   `agent-iso codex`.
2. Use `/skills` to confirm that `magpie-*` skills are visible.
3. Invoke a skill explicitly by mentioning it with `$`, for example
   `$magpie-security-issue-triage`, or describe a task that matches its
   frontmatter description.
4. The selected skill resolves `tools/*` commands and project placeholders in
   exactly the same way as every other runtime.

An end-to-end triage therefore starts with:

~~~text
$magpie-security-issue-triage
~~~

There is no generated AGENTS.md per skill. `AGENTS.md` carries persistent
repository instructions; `SKILL.md` remains the workflow source.

## Install

Prefer the installed `magpie-agent-guard` plugin for routine adopter sessions: its engine lives outside workspace-writable roots.
The project registration below supports framework development and snapshot installations, but its in-repository engine is writable by the agent; hook-definition trust does not protect that file’s contents.
Report this tamper-protection gap explicitly during verification.

Run `$magpie-setup` from Codex and select adopt or upgrade. The setup
lifecycle:

1. Creates the canonical `.agents/skills` links and harness relay links.
2. Merges the reviewed Codex posture into `.codex/` without deleting unrelated
   project settings. Conflicting sandbox or approval values are surfaced to the
   maintainer; they are never silently weakened.
3. Registers the synchronous Bash `PreToolUse` guard from `.codex/config.toml`.
   The stock command resolves the git root, selects `.apache-magpie/tools/agent-guard/src/agent_guard/__init__.py` when present, and otherwise uses the framework’s `tools/agent-guard/src/agent_guard/__init__.py`.
   Both paths invoke `--codex`, so the same registration works in source checkouts and snapshot adopters without rewriting.
   Resolve the git root at invocation time so launching from a subdirectory works.
   For marketplace installs, enable `magpie-agent-guard` instead: its existing Claude-compatible plugin hook uses the same native event and denial schema in Codex.
   Keep one guard registration; do not add a repository hook alongside the plugin hook.
4. Runs `sandbox-lint --codex .codex` on the project profile.
   Static lint checks that the registered engine exists in the source checkout or snapshot.
   A marketplace adopter that keeps a project profile uses `sandbox-lint --codex .codex --guard-from-plugin` instead.
   This mode checks sandbox and exec-policy invariants while explicitly reporting that plugin registration and trust still need separate verification.
   Do not copy the project guard hook when using that plugin mode.
5. Asks the operator to trust the project and review the guard in Codex’s `/hooks` browser.
   Project trust and hook-definition trust are separate decisions.
   Repository content cannot grant either trust.
6. When vetted operations are enabled, follows [Vetted operations](#vetted-operations) to render and review the per-machine rules.

When `.codex/` already exists, setup preserves unrelated keys. `magpie.rules`
is Magpie-owned; hand edits are shown before replacement.

For the clean-environment layer on Linux or macOS:

~~~bash
source <framework>/tools/agent-isolation/agent-iso.sh
agent-iso codex
~~~

On Windows, run the POSIX isolation layer through WSL when that layer is
required. Codex's native Windows sandbox and the project policy still apply to
a native Windows session.

## Security model

### Sandbox and network

The profile requires:

~~~toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[sandbox_workspace_write]
network_access = false
~~~

Networked bridges such as `gh`, `jira`, Gmail, PonyMail, and CVE tooling
therefore cannot silently use network access from the workspace sandbox. The
exec-policy file allows narrowly scoped read-only commands, prompts known
mutations, and forbids `gh auth token` and credential refresh operations.
Commands not matched by an allow rule still follow the native on-request
approval path.

### Exec-policy rules and approval policy

Per-action confirmation belongs to Codex's native rules and approval system:
`.codex/rules/magpie.rules` classifies known commands as `allow`, `prompt`,
or `forbidden` before they cross the sandbox boundary, and
`approval_policy = "on-request"` routes everything else to the operator. This
is the Codex mapping of RFC-AI-0004 Principle 1 (human-in-the-loop).

### Deterministic guard rules

Codex supports a synchronous native `PreToolUse` hook for shell commands, including unified exec.
The canonical hook event names these calls `Bash` and supplies `tool_input.command` and `cwd`.
The `--codex` adapter in [`tools/agent-guard`](../../tools/agent-guard/README.md#codex) passes them to the same `dispatch()` core as Claude Code.
A guard hit emits `hookSpecificOutput.permissionDecision: "deny"`; ordinary commands emit no approval and remain subject to sandbox and native approval policy.
The marketplace plugin’s existing Claude-compatible registration also accepts Codex’s canonical event.

Hooks require review in `/hooks`, including after a hook definition changes.
A configured but untrusted hook is skipped; static lint cannot certify that a running session has trusted it.
Malformed events follow the shared guard’s fail-open behavior.
Codex also treats hook execution errors and timeouts as non-blocking, so these hooks complement the sandbox rather than replacing it.
Interactive shell input through `write_stdin` does not trigger another `PreToolUse` check.
These are native hook limits, documented in [OpenAI’s hooks reference](https://learn.chatgpt.com/docs/hooks).

### Vetted operations

Install the `magpie-vetted-ops` substrate plugin alongside the skill families that need it.
Its Claude-compatible `SessionStart` hook maintains the shared stable path `~/.claude/magpie/vetted-ops` in Codex too; this directory name does not require Claude Code to be installed.
Review that hook in `/hooks` and confirm that the symlink points to the installed plugin, outside every sandbox-writable root.
Do not allowlist a dispatcher from a checkout the agent can edit.

The tool’s `vetted-ops-codex-rules` command prints native rules with the current user’s absolute stable path:

~~~bash
uv run --project ~/.claude/magpie/vetted-ops vetted-ops-codex-rules
~~~

Review the output and install it as `~/.codex/rules/magpie-vetted-ops.rules`.
This is per-machine user configuration; never commit the expanded home path into a project.
The renderer writes nothing itself and accepts `--tool-root` for a different trusted installed location.
It deliberately preserves a stable symlink path instead of resolving a versioned plugin-cache target.
The rules name only the absolute path, never `~`. Codex's plain-command parser rejects any word containing `~`, so a skill's `uv run --project ~/.claude/magpie/vetted-ops …` matches no rule as written; and a `~` rule would be unsafe, because the shell resolves `~` from `HOME`, which an earlier command can reassign, and `uv` treats a literal `~` as a relative directory the agent can create.

To keep the `~` spelling skills use from prompting on every read, install the Codex-only rewrite hook the same tool prints:

~~~bash
uv run --project ~/.claude/magpie/vetted-ops vetted-ops-codex-rules --hook
~~~

Review the output, add it to your user `~/.codex/config.toml`, and trust it in `/hooks`.
Before the rules run, the hook rewrites a command only when the whole command is one read call in that spelling — `uv run --project ~/.claude/magpie/vetted-ops vetted-op-read …` or the `uvx --from` form, with plain or simply quoted arguments — replacing the path with the absolute stable path fixed at render time from `--tool-root`, the same path the rules name.
Anything chained, redirected, substituted or spanning lines is left alone, and so are `vetted-op` and `vetted-op-tracker`, which must always prompt.
It grants nothing: the rewritten command is checked by the rules above like any other, and even if a hook's `allow` were read as an approval, it could only approve that lone read, which the rules already allow.
Never register this hook for Claude Code: Codex needs `permissionDecision: "allow"` to carry the rewrite, while Claude Code reads that field as a permission grant. As a backstop the hook stays silent unless the event carries the `turn_id` and `model` fields only Codex sends.

Both `uv run --project <installed-path> vetted-op-read` and `uvx --from <installed-path> vetted-op-read` are `allow`.
Both launchers with `vetted-op` or `vetted-op-tracker` are `prompt`.
There is no general `uv` or `uvx` allow rule and no catalogue-wide write exemption.
When the sandbox blocks network or credential access, invoke the approved fixed read prefix through Codex’s escalation path; do not enable sandbox-wide network access.
Codex rules replace Claude’s `sandbox.excludedCommands` for this purpose.

The policy remains `.apache-magpie-overrides/tools/vetted-ops/config.toml`, and caller grants and parameter validation are unchanged.
Verify `--describe`, then a permitted read such as `viewer`, with the selected skill’s actual caller.
Test a prohibited write against `vetted-op-read` using `--dry-run`; it must refuse before issuing any forge request.
Use `codex execpolicy check` with the generated rules to verify both launchers classify reads as `allow` and writes as `prompt`, without executing writes.

Code in the home-directory plugin store is outside sandbox-writable roots.
The in-repository policy is still shell-writable, just as in Claude’s setup; a native prefix rule is not a file-write restriction.
Do not claim Claude’s `Edit` deny rules have been ported by the exec-policy file.
For stronger policy isolation keep policy outside writable roots and explicitly select it with `--config`.

### Trust boundary

Project `.codex` configuration and rules load only for a trusted project. The
operator reviews that trust decision. The framework does not modify user trust
state.

Policy changes remain normal reviewed repository changes: an approved elevated
action can still modify `.codex/`, so the profile complements — never
replaces — code review.

## Verify

Run the static validator from the framework or snapshot:

~~~bash
uv run --project tools/sandbox-lint --group dev sandbox-lint --codex .codex
~~~

For a marketplace-owned guard, append `--guard-from-plugin` to that command and verify the installed plugin in `/hooks`.
The option never certifies plugin presence or trust by itself.

Then test native rule classification:

~~~bash
codex execpolicy check --pretty \
  --rules .codex/rules/magpie.rules \
  -- gh pr view 313

codex execpolicy check --pretty \
  --rules .codex/rules/magpie.rules \
  -- gh pr create --title test --body test

codex execpolicy check --pretty \
  --rules .codex/rules/magpie.rules \
  -- gh auth token
~~~

The expected strictest decisions are `allow`, `prompt`, and `forbidden`,
respectively.

Also verify:

- `/skills` lists `magpie-setup` and a representative workflow skill.
- `/hooks` lists the guard and shows the current definition as trusted; hooks are enabled.
- Identify the engine location: prefer installed plugin or user-scope code outside writable roots.
  Report a source or snapshot engine under the writable workspace as a tamper-protection gap; static lint and hook trust do not close it.
- Feed synthetic native `PreToolUse` events for `git status` (silent success) and `git commit --no-verify -m test` (JSON deny) to the registered command.
  These are input to the hook, never commands to execute.
- For vetted operations, verify stable-path provenance, all six generated native decisions, an authenticated permitted read, and the read dispatcher’s write refusal.
- Each `tools/*` bridge used by the selected skill is present and
  authenticated; tool-specific preflight remains owned by that skill.

## setup-isolated lifecycle

The four setup-isolated skills route Codex to this adapter:

- `setup-isolated-setup-install` installs or merges the project profile and
  explains `agent-iso codex`.
- `setup-isolated-setup-verify` runs the static validator, rule-classification
  probes, `/skills` checks, and tool preflights.
- `setup-isolated-setup-update` compares the installed profile with the
  current framework snapshot. It reports drift and never weakens policy
  automatically.
- `setup-isolated-setup-doctor` runs the shared live environment probes inside
  the active Codex sandbox and reports native approval or network failures
  separately.

The Claude-specific setup remains available for Claude Code. Runtime routing
must happen before a setup-isolated skill follows Claude-only settings paths.

## Known limitations

- Codex exec-policy rules are an evolving runtime interface. Pin a minimum
  tested Codex version before calling the adapter stable, and rerun the
  classification probes on upgrades.
- Native hooks must be trusted separately, and hook errors can fail open;
  see [Deterministic guard rules](#deterministic-guard-rules).
- Native project policy requires explicit project trust.
- The clean-environment wrapper is POSIX shell. Native Windows sessions rely
  on the Codex Windows sandbox unless launched through WSL.
- MCP and account-backed integrations still require user-scoped registration
  and authentication. Repository policy never copies credentials into the
  project.

## Comparison with the Claude setup

This compares the framework’s reference profiles, not a certification of a particular running session.
The Claude checklist is [the verification skill](../../plugins/magpie-setup/skills/isolated-setup-verify/SKILL.md).

| Claude check | Codex equivalent or remaining gap |
|---|---|
| Sandbox profile and network | `workspace-write`, network disabled, native approval policy and rules; static lint covers these. Claude’s domain allowlist has no equivalent in this profile. |
| Credential file read restrictions | **Gap:** the Codex profile restricts writes but supplies no equivalent to Claude’s home-directory `denyRead` allowlist. The clean-env wrapper strips inherited secrets but does not block file reads. |
| User hook registration and scripts | Native plugin or project guard registration; verify `/hooks` trust separately. Claude’s bypass-warning and error-hint scripts are not installed for Codex. |
| Isolation launcher | Shared `agent-iso codex` exists; its launch and stripped environment still need a live check. |
| Runtime version floor | **Gap:** no minimum tested Codex version is declared in `pinned-versions.toml`. Hook support was checked with CLI 0.163.0; this is not a compatibility floor. |
| Sandbox visibility | Native Codex approvals and sandbox UI; no Magpie status-line equivalent in this profile. |
| Live denials | Native rule-classification tests are offline evidence. Actual file-read and network denials require separate live probes; a rule result does not prove OS enforcement. |
| Project root and worktrees | Codex uses its own workspace roots. Claude’s absolute-path helper and global hook dispatcher are not Codex requirements; test each worktree’s effective roots. |
| Vetted reads and writes | Fixed installed paths and generated native rules replace Claude allow/ask/exclusion entries; verify authentication, read refusal of writes, and hook trust. |
| Guard engine tamper protection | **Gap for project hooks:** source and snapshot engines are workspace-writable; changing their code does not renew hook trust. Prefer the plugin-owned or user-scope engine outside writable roots. |
| Vetted tamper protection | Installed plugin code is outside writable roots. **Gap:** no equivalent to Claude’s tool-level `Edit` denies for the repository policy. Both profiles leave shell writes to in-repo policy possible. |
| Hardware signing and touch overlay | Shared git/gpg configuration may work, but the Codex branch does not verify the signing key, socket or overlay. |
| GitHub outside sandbox | Native read-prefix approval plus escalation; verified with `gh auth status` and a read request. Claude’s exclusion syntax does not apply. |
| Container gateway | **Gap:** the Codex profile does not register Claude’s container-gateway pre-tool hook. |
| Eval and adversarial-review exclusions | **Gap:** no fixed installed-prefix Codex rules supplied for these optional tools. Do not allowlist general `uv` to compensate. |
| Read-only operations never prompt | Generated `vetted-op-read` rules provide the native allow decision. Verify active user rules and that no stricter native rule still prompts or forbids the command. |
| Read-outside-working-directory prompts | Claude-specific switch; Codex’s write sandbox is not a replacement for credential read isolation. |

Setup verification must report these gaps or untested live properties explicitly rather than declaring full Claude parity from a successful static lint.

## Upstream references

- [Codex skills](https://developers.openai.com/codex/skills)
- [Codex configuration](https://developers.openai.com/codex/config-reference)
- [Codex rules](https://developers.openai.com/codex/rules)
- [Codex native hooks](https://learn.chatgpt.com/docs/hooks)
- [Codex CLI source](https://github.com/openai/codex)
- [Agent Skills specification](https://agentskills.io/specification)
