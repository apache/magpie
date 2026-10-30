<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Pi harness](#pi-harness)
  - [Harness contract](#harness-contract)
  - [Install](#install)
  - [Security model](#security-model)
    - [What asks and what denies](#what-asks-and-what-denies)
    - [Sandbox boundaries](#sandbox-boundaries)
    - [Limits](#limits)
  - [Spec-loop runner](#spec-loop-runner)
  - [Verify](#verify)
  - [Update](#update)
  - [Doctor](#doctor)
  - [setup-isolated lifecycle](#setup-isolated-lifecycle)
  - [Upstream references](#upstream-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Pi harness

**Capability:** capability:platform

**Harness:** Pi

[Pi](https://pi.dev/) (CLI `pi`, npm `@earendil-works/pi-coding-agent`) is a minimal terminal coding agent.
Out of the box it runs every tool call without asking and has no sandbox, so Magpie ships the secure setup as a Pi extension: an action guard, permission rules, and an OS sandbox for bash.
The setup is **per user, never per repository**: one `pi install` adds the skills and the extension to the user's `~/.pi/agent/settings.json`, and the extension reads no project configuration, so a repository cannot weaken it.
The adapter is **experimental**: it was validated with Pi 1.4.0 on macOS; Linux and Windows have not been verified.
The integration follows the harness contract in [add-a-harness](add-a-harness.md) and [RFC-AI-0004](../rfcs/RFC-AI-0004.md).

## Harness contract

| Magpie requirement | Pi implementation |
|---|---|
| Skill discovery | Pi reads `.agents/skills/` from the working directory up to the repository root, the canonical `universal` row in `skills/setup/agents.md`. The Pi package adds the framework's `skills/`. Each skill is also a `/skill:<name>` command. |
| Repository instructions | Pi loads `AGENTS.md` (and `CLAUDE.md`) natively, before project trust. |
| Tool bridges | Skills invoke the existing `tools/*` CLI adapters through the `bash` tool, subject to the extension's rules and sandbox. |
| Deterministic guard | The extension sends every bash command to `agent_guard/__init__.py --pi` before it runs; a deny blocks the call. See [agent-guard](../../tools/agent-guard/README.md#pi). |
| Permission rules | The extension derives them from the Claude Code baseline ([`expected.json`](../../tools/sandbox-lint/expected.json)): denied commands are blocked, asked ones need confirmation, and native reads and writes of credential paths, `.env` files, agent settings and Pi's own configuration are refused. |
| Filesystem and network | Bash runs in [`@anthropic-ai/sandbox-runtime`](https://github.com/anthropics/sandbox-runtime), the engine of Claude Code's sandbox, with the baseline's `denyRead` / `allowRead` / `allowWrite` and domain allowlist. |
| Credential isolation | The sandbox strips the baseline's credential variables (`GH_TOKEN`, cloud keys, …) from bash; `agent-iso pi` launches Pi through the generic clean-environment wrapper. |
| Spec-loop | The `pi` profile runs `pi -p` headless; see [Spec-loop runner](#spec-loop-runner). |
| MCP servers | Pi has no built-in MCP; Magpie's skills use the `tools/*` CLI adapters instead. |

The extension is [`tools/agent-isolation/pi/magpie.ts`](../../tools/agent-isolation/pi/magpie.ts); its decisions live in [`policy.ts`](../../tools/agent-isolation/pi/policy.ts), which reads the same baseline the Claude Code profile is linted against, so the two profiles cannot drift apart.
The repository's root [`package.json`](../../package.json) makes the repository a Pi package that carries both the skills and the extension.

## Install

Use Pi **1.4.0 or later** and Python 3.11+ (for the guard).
On Linux the sandbox also needs `bubblewrap`, `socat` and `ripgrep`; use the framework's [sandbox primitive versions](../../tools/agent-isolation/pinned-versions.toml).

```bash
pi install git:github.com/apache/magpie
```

That one command is the whole install, for every repository: Pi clones the framework, installs the pinned sandbox dependency, and records the package in `~/.pi/agent/settings.json`.
Pi runs `npm install --omit=dev --legacy-peer-deps` in its clone, which honours the committed [`package-lock.json`](../../package-lock.json): every package in the sandbox runtime's tree is pinned to an exact version and integrity hash, and none has an install script.
To refresh the lockfile, resolve with the same flags and the repository's 7-day cooldown, without installing or running anything:

```bash
npm install --package-lock-only --ignore-scripts --omit=dev --legacy-peer-deps \
  --before="$(python3 -c 'import datetime; print(datetime.date.today() - datetime.timedelta(days=7))')"
```

Dependabot proposes the same updates weekly, with the same cooldown.
Never install it per project with `pi install -l`; the secure setup belongs to the user.
For guided setup, ask Pi: `/skill:isolated-setup-install`.

Then start every session through the clean-environment wrapper:

```bash
source "<framework>/tools/agent-isolation/agent-iso.sh"
agent-iso pi
```

Pi keeps provider credentials in `~/.pi/agent/auth.json` after `/login`; pass an API-key variable explicitly with `AGENT_ISO_ALLOW=<NAME> agent-iso pi` when you use one instead.

## Security model

### What asks and what denies

| Requested action | Result |
|---|---|
| A bash command that matches no rule | Runs in the OS sandbox without a prompt. |
| A read-only `gh` command from the baseline's allow list, as plain words | Runs outside the sandbox, with `gh`'s own credentials. |
| `git push`, mutating `gh` commands, `gh api` with a method or field flag | Asks; refused in a non-interactive run. |
| Any other `gh` command outside the sandbox | Asks. |
| Credential and export commands, such as `curl`, `gh auth token`, cloud CLIs | Denied. |
| A command agent-guard denies (a `Co-Authored-By` trailer, `--no-verify`, …) | Denied, with the guard's reason. |
| Native `read` / `grep` / `find` / `ls` of credential paths or `.env` files, or rooted above them | Denied, symlinks resolved. |
| Native `write` / `edit` of agent settings, `~/.pi/agent/` or `.pi/` | Denied. |
| Native `write` / `edit` outside the working folder, symlinks resolved | Asks; refused in a non-interactive run. |

Deny outranks ask, which outranks allow, as in Claude Code.
A command leaves the sandbox only when it is plain words: quotes, escapes, expansions, redirections and operators keep it inside.

### Sandbox boundaries

A probe with Pi 1.4.0 on macOS observed:

| Probe | Result |
|---|---|
| `cat ~/.ssh/known_hosts` | Blocked. |
| `test -r ~/.gitconfig` | Readable (in the baseline's `allowRead`). |
| `touch ~/probe` | Blocked. |
| A request to `example.com` | Blocked by the domain allowlist. |
| A request to `api.github.com` | Allowed. |
| A write in the workspace | Allowed. |
| `echo $GH_TOKEN` | Empty. |

If the sandbox cannot start, the extension refuses bash rather than running it unsandboxed.
`pi --magpie-no-sandbox` runs one session without it; the guard and rules still apply.

### Limits

- Native file tools and extension tools run in the Pi process, outside the sandbox; the rules above gate the built-in ones, not tools other extensions add.
- A rule for a file name anywhere (`**/.env`) cannot stop a directory search from reading such a file; Pi's `grep` and `find` follow `.gitignore`, which usually lists them.
  Neither follows symlinks, so a search cannot walk through a link into a denied directory, and file tools are handed the checked path with links already resolved.
- The extension's command rules are a friction layer; the guard and the sandbox are the enforcement.
- `@anthropic-ai/sandbox-runtime` 0.0.80 pulls `node-forge` and `zod` versions with open advisories in its TLS-interception and validation paths, which this extension does not drive with untrusted input.

## Spec-loop runner

The `pi` profile in [`tools/spec-loop/lib.sh`](../../tools/spec-loop/lib.sh) runs `pi -p`, forwarding `--model` and `--thinking` when supplied.
A non-interactive run has no UI, so every command that would ask is refused: a build iteration needing a push or a mutating `gh` call cannot complete unattended.
See the [spec-loop guide](../../tools/spec-loop/README.md).

## Verify

Ask `/skill:isolated-setup-verify`, or check by hand:

```bash
pi --version
pi list
```

`pi list` must show `git:github.com/apache/magpie`, and the startup header of an interactive session must list the `magpie.ts` extension.
Then make these requests to the model rather than typing the commands yourself:

| Request | Expected result |
|---|---|
| Run exactly `git status --short`. | Runs. |
| Run exactly `cat ~/.ssh/known_hosts`. | Fails inside the sandbox. |
| Run exactly `gh auth token --help`. | Denied by the rules. |
| Run exactly `git commit --dry-run --no-verify -m hook-probe`. | `agent-guard[no-verify]` denial. |
| Run exactly `git push --dry-run`. | Asks before running. |
| Read `~/.ssh/config` with the read tool. | Denied. |

Inspect the actual tool results; a verbal refusal by the model does not establish enforcement.

## Update

`pi update --extensions` pulls the framework package to its pinned ref and reinstalls its dependencies.
Ask `/skill:isolated-setup-update` for a read-only drift report first.

## Doctor

| Symptom | Check and next step |
|---|---|
| Bash refused: "the OS sandbox could not start" | On Linux install `bubblewrap`, `socat` and `ripgrep`; check that `pi update --extensions` installed the package's dependencies. |
| Guard never denies | Check `python3 --version` (3.11+) and that `pi list` shows the framework package. |
| A command fails only inside the sandbox | Network and most of the home directory are unavailable there. Report what it needs; do not widen the baseline without the operator's decision. |
| A command keeps asking in a headless run | Asked commands need an interactive session. |

## setup-isolated lifecycle

The four `setup-isolated-setup-*` skills route Pi sessions to [Install](#install), [Verify](#verify), [Update](#update), and [Doctor](#doctor).
Uninstall is `pi remove git:github.com/apache/magpie`, which removes the skills, the guard and the sandbox together.

## Upstream references

- [Pi packages](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/packages.md)
- [Skills](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/skills.md)
- [Extensions](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md)
- [Security](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/security.md)
- [Containerization](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/containerization.md)
- [CLI](https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/cli.md)
