<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Agent isolation / layered sandbox
status: stable
kind: feature
mode: infra
source: >
  MISSION.md § Privacy, security and supply-chain integrity ("Clean-
  environment wrapper", "Layered sandbox by default", "Pinned, reviewed,
  signed dependencies"). Implemented in tools/agent-isolation/,
  tools/agent-guard/, tools/permission-audit/, tools/egress-gateway/,
  the setup-isolated-setup-* skills, and .claude/settings.json.
acceptance:
  - The reference setup uses an OS-level sandbox with default-deny
    filesystem reads and network egress; runtime-specific exceptions
    are documented in the adapter and this spec.
  - Credential-shaped env vars are stripped before the agent execs.
  - State-mutating shell calls (git push, every gh write subcommand,
    each listed explicitly, and every write-shaped `gh api` call) require
    a confirmation prompt; read-only gh subcommands and plain `gh api`
    GETs do not; secrets/cred files are deny-read.
  - The reference `permissions.allow` set of read-only entries ships to
    adopters with `deny` and `ask`, and drift in it is reported like any
    other settings drift.
---

# Agent isolation / layered sandbox

## What it does

Runs reference agent invocations inside a layered sandbox so that even a
successful prompt injection cannot read credentials or reach a
non-allowed host. The fallback when prompt engineering fails is the OS
saying "no".

Gemini CLI uses tool sandboxing rather than whole-process isolation.
Its native file tools restrict reads to allowed directories, but the tested
Linux backend exposes host files broadly read-only to approved shell commands.
Native credential-path policy denies do not block equivalent shell reads.
Tool network restrictions do not cover the CLI, hooks, or MCP servers;
existing sandbox grants can widen the baseline. See `docs/adapters/gemini.md`.

## Where it lives

- `tools/agent-isolation/` — the harness (clean-env wrapper +
  sandbox profiles).
- `tools/agent-isolation/gpg-touch-overlay.sh` (+ the two window
  scripts) — the hardware-key touch overlay: a window on screen while a
  signing key or ssh authentication key with a touch policy blocks
  waiting for a touch. Two entry points: `arm` /
  `disarm` as a `PreToolUse` / `PostToolUse` `Bash` hook around the
  agent's git commands — with `disarm` also on `PermissionDenied` and
  `PostToolUseFailure`, because `PreToolUse` fires before the
  permission prompt and a command that never runs would otherwise
  leave its watcher armed until `MAX_WAIT`, raising the window for an
  unrelated signature — and `wrap` as git's own signing program and ssh
  command (`gpg.ssh.program` / `gpg.program` through an argument-free
  `gpg-touch-wrap-<program>` symlink, `core.sshCommand … wrap ssh`) for
  the commits and pushes the operator makes by hand — no git hook type
  sits at the right moment for those. The hook arms on any command that
  can reach the key, which is broader than signing: every git
  subcommand that signs or opens an ssh remote, and the key consumers
  git never sees — `ssh`, `scp`, `sftp`, `rsync`, `gpg` and the ssh
  signer invoked directly. Arming is deliberately over-broad because
  the *window* is what a false positive would cost, and the watcher
  shows none until something has actually blocked on the key for
  longer than the grace. `wrap` reaches those same non-git consumers
  through an optional shim directory on `PATH`: the script dispatches
  on its own basename for a key command's name, not only for
  `gpg-touch-wrap-<program>`, and resolves the real program by walking
  every `PATH` match and skipping the one that resolves back to
  itself. That self-skip is load-bearing twice over — it is why a
  wrapped git does not chain into a shim, and why the lookup must fail
  with 127 rather than fall back to the bare name, which on a `PATH`
  holding the shim re-execs the script indefinitely. Each is a signing
  context that
  owns its own watcher, registered under `owners/` and keyed by the
  harness session id the hooks carry or by the wrapper's pid, so a
  context can only ever tear down the watcher it started; a context
  whose owner process is gone is swept by the next `arm`. Never two
  windows for one signature: inside an agent session (`CLAUDECODE=1`)
  the wrapper only runs the program and the hook's watcher shows the
  window, and across contexts the window is leased by atomic directory
  create, so only one watcher draws it and a lease left by a watcher
  that died is reclaimed. The window names the blocked command and the
  directory it runs in, so a touch is never given to the wrong one of
  two waiting contexts: `arm` records them from the hook payload and
  `wrap` from its own `$PWD` and argv, into a per-owner file under
  `context/` keyed like the registration. The watcher holds the path
  and re-reads it each time it raises the window, which is what lets a
  second command arming into an already-watched session replace the
  text without a second watcher. A password in a URL is masked before
  it is written; nothing else is, and the window is full-screen. That
  registry, the context files, the lease, and the watcher's
  pid and log files live in `$XDG_RUNTIME_DIR/magpie-gpg-touch`, else
  `${XDG_CACHE_HOME:-$HOME/.cache}/magpie-gpg-touch` on a platform that
  sets no `XDG_RUNTIME_DIR`. The fallback has to be per-user rather than
  `/tmp`, which is world-writable and outside the reference
  `allowWrite` — a sandboxed signed commit died there at
  `watcher.pid: Operation not permitted` before any watcher started —
  and it has to be stable across contexts rather than `$TMPDIR`, which
  differs between the agent's hooks and a terminal `git` and would give
  two contexts two registries that cannot see each other.
  The hook-side owner is the harness process, not the hook's parent:
  Claude Code on Linux runs a hook through `sh -c`, which exits the
  moment the hook returns, so `arm` walks up past intermediate shells
  to the first non-shell ancestor and records that — otherwise the
  watcher's parent-liveness check ended the watch before the key ever
  blocked (#1365).
  On macOS the window closes when its application loses activation
  (`<Deactivate>`, bound after a short grace because activation itself
  churns focus) rather than re-grabbing the keyboard: the overlay
  never traps the screen, since the key still has to be touched for
  the command to go through (#1325). The macOS window takes
  `SIGTERM` / `SIGINT` / `SIGHUP` back from Aqua Tk right after the root
  window exists, so the watcher's close signal only sets the flag
  `watch_for_stop` polls; Tk's own handler called `Tcl_Exit` inside the
  signal and could deadlock the window mid-redraw until force-quit, and a
  regression test pins the ordering (#1376). Visibility never depends on
  activation, which macOS 14 made cooperative: a watcher started in the
  background can be refused it, so every window is ordered front with
  `orderFrontRegardless` at a level above other windows and joins all Spaces
  (including a full-screen terminal's), and activation is only asked for
  with `activate`, falling back to the deprecated
  `activateIgnoringOtherApps:`; a refusal costs the keyboard, not the
  window (#1697).
  A key that never waits for a touch draws no window at all: before
  anything signs, `arm` and `wrap` read the signature and authentication
  slots' touch policies from the `uif:` record of
  `gpg --card-status --with-colons` (never `ykman`, which needs PC/SC,
  denied in the sandbox, and contends with scdaemon for the card), and
  start no watcher when both are `off` (#1715).
  `cached`, any other value, and an unknown policy (no card, no gpg, no
  `uif:` record) keep the window.
  A definite answer is cached in the runtime directory for ten minutes,
  but an `off` only for one, so a policy turned on since is honoured on
  the next burst of commands (#1723). The
  git the agent runs reads the same global config, so the wrapper's
  two files are a `sandbox.filesystem.allowRead` grant of their own
  (nothing wider under `~/.claude/`), or every sandboxed signed commit
  fails with `cannot exec`. Installed by `setup-isolated-setup-install` Step K,
  checked by `setup-isolated-setup-verify` check 10. Capability:
  `substrate:sandbox`.
- **Hardware-key touch policy** (the recommendation Step K proposes and
  check 10 reports against). The touch goes on the slot that **signs**,
  never on the ssh transport alone: a touch on every fetch and pull is
  a prompt on a read, and a push is already gated by the `git push`
  ask rule and carries only commits signed with a touch. Which slot
  signs follows `gpg.format`: with OpenPGP signing (unset or
  `openpgp`) it is `sig`, recommended `cached`, and `aut` is
  recommended `off`; with `gpg.format=ssh` the signature is made by the
  key `ssh-add -L` lists, so `aut` is the signing slot and must stay
  `cached` — the skill never proposes turning it off there, and states
  once that the transport then pays the touch too (OpenPGP signing or
  an https remote avoids it) — while `sig` signs nothing and is left
  alone. `cached` (a touch honoured for 15 seconds) rather than `on`,
  and never `fixed` / `cached-fixed`, which cannot be undone without
  deleting the private key (#1367).
- `tools/agent-guard/` — deterministic pre-execution guard dispatcher
  (`stdlib`-only). Wired as a `PreToolUse` hook (Claude Code) or a
  `tool.execute.before` plugin (OpenCode), with a `--gemini` adapter for
  Gemini CLI's `BeforeTool` event (wired in the repository's
  `.gemini/settings.json`; registration for snapshot adopters), a `--grok`
  adapter for Grok Build's `PreToolUse` event, and a `--copilot` adapter
  for Copilot CLI's `preToolUse` event (wired in `.github/hooks/magpie.json`,
  #1560), which also allows one simple read-only command (`gh` reads,
  `git status/diff/log`, GET-only `gh api`, `vetted-op-read`) so reads never
  prompt and leaves anything else to Copilot's own permission flow, and a
  `--junie` adapter for JetBrains Junie's Early Access `PreToolUse` hook
  (`~/.junie/config.json`, #1666; guide in `docs/adapters/junie.md`), which blocks with exit `2` and a
  `decision` JSON, the one signal Junie honours, because Junie ignores the
  Claude-shaped `hookSpecificOutput` deny; inspects every shell command
  before it runs and denies the ones that break a hard framework rule,
  independent of model memory. The guard decisions live in a single
  harness-agnostic `dispatch()` core so every wired harness enforces
  an identical rule set. Git guards resolve the subcommand by walking
  past git's global options (`git -C <dir> commit`, `git -c k=v commit`,
  `git --no-pager commit`), never by a fixed argv slice, and
  `GuardContext.git_subcommand()` gives contributed guards the same
  resolution `gh_subcommand()` gives for `gh` (#1330).
  Every guard first unwraps the prefix wrappers that run their argument,
  `env` (its GNU / BSD options, clustered short flags and `NAME=value`
  assignments, which still count as inline overrides) and `command -p`,
  until none is left, so `env git commit …` reaches the same guards as
  `git commit …`; `command -v` is a lookup and is left alone. A segment
  nested past a generous depth limit, carrying an undocumented `env`
  option or another `command` flag, is marked unparsed and refused, and
  `env -S` is refused outright, because GNU env splits its string with
  escapes `shlex` does not reproduce (#1691, #1694).
  Beyond the bundled `guards.d`, skill-owned guards are discovered in
  place, with no collection step: every `$MAGPIE_GUARD_DIRS` entry, then
  every `plugins/*/skills/*/guards` and `skills/*/guards` of the framework
  tree the engine runs from (#1757), or, on a marketplace install, where
  each plugin is cached on its own as `<marketplace>/<plugin>/<version>/`
  and there is no framework tree, the `skills/*/guards` of the family
  plugins cached beside `magpie-agent-guard`, each at the engine's own
  version, else its most recently installed one (#1762).
  Hooks invoke the engine as a bare `python3`; when that resolves to a
  pre-3.11 interpreter, the engine re-runs itself under the newest
  `python3.N` (3.11+) on `PATH`, and exits 1 with an actionable message
  when none exists.
  The `commit-trailer` guard follows the project's commit-attribution
  convention (#1385): it denies a `Co-Authored-By:` trailer unless the
  convention resolved for the repository being committed to (following
  `git -C`) is `co-authored-by`, failing closed to `generated-by` on an
  unreadable file or unknown value, with `MAGPIE_ALLOW_COAUTHOR=1` as the
  per-command override. It scans the message file a `-F` / `--file`
  names, resolved against the `-C`-adjusted directory as git does,
  alongside the command line and any `--trailer` (#1386); stdin and a file
  that does not exist when the command starts are skipped, so a file
  written earlier in the same command line is a known limit.
  Resolution rules: `docs/setup/commit-attribution.md`.
  Capability: `substrate:action-guard`.
- `tools/permission-audit/` — audits and atomically edits Claude Code's
  `permissions.allow[]` entries in `.claude/settings.json` and
  `.claude/settings.local.json`. Backs the `--apply-permission-audit`
  flag of `/magpie-setup:setup verify` (check 8d). Also handles OpenCode
  `permission` config via `audit-opencode`. Capability: `substrate:sandbox`.
- `tools/agent-isolation/sandbox-add-project-root.sh` — writes the
  worktree's absolute path, and the absolute dev-tool paths `prek` and
  `uv` need (`~/.gitconfig`, `~/.config/git`, `~/.cache`,
  `~/.local/share/uv`, `~/.local/bin`; only the cache also writable,
  and it removes a `~/.local/share/uv` write an earlier version added,
  because uv's interpreters and tool venvs there run outside the
  sandbox; sandbox-lint rejects any write grant over that directory,
  #1785), into each worktree's gitignored
  `.claude/settings.local.json`, through a temporary copy and a final
  rename. A rename the sandbox denies — the dispatcher runs the helper
  sandboxed on every post-checkout — removes the copy, warns and leaves
  the file untouched rather than aborting the remaining worktrees
  (#1812). The harness drops the committed
  project-scope `sandbox.filesystem` allow entries (issue #197), so the
  local file is where they take effect. It never adds the credential
  paths the committed list also names; `--no-tool-paths` limits it to
  the project root. Checked by `setup-isolated-setup-verify` check 8.
  It also adds the scratch root `/tmp/claude-<uid>`, which the skills
  read on every run, to `permissions.additionalDirectories` of the same
  file, resolved to a literal absolute path, because with
  `permissions.blockReadsOutsideWorkingDirectories` on every read outside
  a working directory asks and a glob such as `/tmp/claude-*` is listed
  but never matched (#1418). It names one host's uid, so it stays per
  host in the gitignored local file rather than in a synced user-scope
  settings file; `--no-working-dirs` skips it. Install proposes it
  (Step W), verify check 15 and doctor probe 9 report it, and update
  treats its absence as drift.
  `$HOME/.claude/magpie` (the fixed vetted-ops path) is deliberately not
  a working directory, and the helper removes it where an earlier version
  added it: the sandbox makes every working directory writable to
  sandboxed Bash, and the vetted-ops exclusions run that checkout's code
  outside the sandbox. sandbox-lint counts working directories as
  writable and fails on one covering the checkout; verify check 16f,
  doctor probe 9 (✗) and update report it. Reads of the checkout keep
  prompting under the read block, which the vetted-ops commands need off
  anyway: they spell `~` literally, which the read block cannot check, so
  install Step V.1 requires it off where vetted-ops is used (#1640; see
  [`vetted-command-surface.md`](vetted-command-surface.md)).
  Capability: `substrate:sandbox`.
- Whole-user git hooks — the install skill's Step P.3 alternative to
  per-project scope: global `core.hooksPath` pointing at
  `~/.claude/git-hooks/`, in a *simple* flavour (a standalone
  `post-checkout`) or a *dispatcher* flavour (every hook name symlinked
  to `git-hook-dispatcher.sh`, which chains to per-repo `.git/hooks/*`).
  That directory sits under the read-denied home, and git treats a hook
  directory it cannot see as "no hooks", so without a read-only
  user-scope `sandbox.filesystem.allowRead` grant for it (plus
  `~/.claude-config/git-hooks/` when the hooks are symlinks into the
  sync repo, since the sandbox checks the resolved path) every
  sandboxed commit silently skips `pre-commit`, `commit-msg` and the
  rest. Install proposes the grant at Step P.3-whole-user; verify
  check 8 probes the directory from inside the sandbox (#1364). Both
  the update skill's drift check and verify check 8 recognise the
  dispatcher flavour's symlinks as its installed shape, not as drift
  or as inert per-repo hooks (#1322, #1358).
- `tools/hook-manager/` — the contract for git-hook managers (prek
  today) under the secure setup, `contract:hook-manager`: a manager's
  install puts its hook in the repository's own
  `$(git rev-parse --git-common-dir)/hooks`, where the dispatcher
  chains, and its home is split — `env.<HOME>` gives sandboxed runs a
  home of their own, `Edit(<default home>/**)` is denied, and the
  dispatcher gives hooks run outside the sandbox a host-only home under
  `~/.local/share`. `registry.json` holds the adapters;
  `tools/dev/sync-hook-managers.py` writes it into
  `tools/agent-isolation/hook-manager-shim.sh` (installed as
  `~/.claude/bin/<tool>`, keyed by that name), the dispatcher and
  `sandbox-lint`, and checks the committed settings against it.
  The settings template likewise denies `Edit(~/.cache/ponymail-attachments/**)`
  (#1828): the PonyMail MCP saves report attachments there from outside the
  sandbox, and a sandboxed command that could rename directories under that
  root mid-save could race the server's path checks.
  For prek the split is concrete (#1792): the settings `env` sets
  `PREK_HOME=~/.cache/prek-sandbox` for sandboxed runs,
  `Edit(~/.cache/prek/**)` keeps sandboxed commands out of the default
  home a terminal commit runs hooks from, and the dispatcher, when
  `SANDBOX_RUNTIME` is absent (a terminal commit or a bypassed one),
  points `PREK_HOME` at `~/.local/share/prek-host` and `XDG_CACHE_HOME`
  at `~/.local/share/prek-host/cache`, keeping an operator's own value
  outside `~/.cache`.
  Detection (a root config file, a tracked nested config, or an
  installed hook that runs the manager) decides only what a repository
  is configured with — the sandbox home its settings must carry, the
  shim, verify check 19d; the default-home deny and the dispatcher's host
  home stay on for every registered manager, because both homes are per
  user (#1819).
- `plugins/magpie-setup/hooks/check-upgrade.sh` — magpie-setup's
  `SessionStart` hook.
  It runs outside the sandbox over a sandbox-writable tree, so it trusts
  nothing the session environment supplies: `/bin/bash -p`, a fixed `PATH`,
  and Python only from a vetted root-owned interpreter under `env -i` with
  `-I -S` (#1769, #1791, #1794).
  It also removes the stale `~/.local/share/uv` write grant (#1788) and a
  repository-level `core.hooksPath` that would skip the whole-user
  dispatcher (#1792).
  The full contract, including the isolation warning, is specified in
  [`adoption-and-setup.md`](adoption-and-setup.md).
- `tools/egress-gateway/` — local HTTP(S) forward proxy for egress
  control. Framework tools point `HTTPS_PROXY`/`HTTP_PROXY` at it; the
  gateway rejects any connection to a host not on its allowlist before a
  socket is opened. Defence-in-depth per RFC-AI-0003: even a
  prompt-injection reaching for an arbitrary endpoint is blocked at the
  network layer. The `egress-gateway` console script takes `--host`
  (default `127.0.0.1`), `--port` (default `8899`) and `--log-level`,
  passes any other argument through to proxy.py unfiltered (a trusted
  operator's choice, outside the allowlist guarantee), and starts the
  proxy with those arguments explicitly, as `proxy.Proxy(input_args=…)`
  plus `sleep_loop()`, rather than letting proxy.py parse the process
  argv (#1774). Capability: `substrate:sandbox`.
- `.claude/settings.json` — the committed floor: the `sandbox` block
  (filesystem allow/deny, the core network `allowedDomains`, the vetted-ops
  `excludedCommands`) and `permissions` (every `deny` / `ask`, the
  `vetted-op-read` pair and the adopted families' MCP tools).
- `tools/agent-isolation/claude-settings.local.template.json` — the rest of
  the framework checkout's settings (the `gh` read allows, the remaining
  exclusions, family-specific domains, personal tool paths), reconciled into
  each contributor's `.claude/settings.local.json`. `sandbox-lint` lints the
  two merged and keeps every `deny` / `ask` in the floor. Its workflow also
  runs when `.claude/settings.local.json` changes and fails while that file
  is tracked, since a committed copy would load for everyone and its
  scalars override the floor's (#1692). sandbox-lint refuses
  `~/.config/apache-magpie` in `allowRead`: the Gmail OAuth token there is
  read only by the drafting MCP server outside the sandbox, and the
  template no longer grants it or the Google API hosts (#1681).
  Because that server runs outside the sandbox, it accepts a
  caller-supplied `credentials_path` only as a `.json` file directly in
  `~/.config/apache-magpie/` or in the directory of
  `$GMAIL_OAUTH_CREDENTIALS`, reached without a symlink, so a tool call
  can neither write the refresh token where sandboxed code reads it nor
  load a planted file (#1795).
- `.gemini/settings.json` and `.gemini/policies/magpie.toml` — Magpie's Gemini profile: tool-sandboxing and an explicitly loaded User-tier approval policy.
  Scoped shell reads are allowed; other shell calls, native edits, and MCP calls ask; listed commands and credential paths deny.
  Credential-path denies name the canonical `grep_search`; the native probe verifies its `search_file_content` alias, canonical policy names, and search/multi-file/web/resource argument schemas against the loaded runtime.
  `google_web_search`, `web_fetch`, and `read_mcp_resource` require approval for each call in every mode, including auto-edit and Plan Mode; headless calls are refused.
  Web search and URL fetching run outside shell network isolation; native MCP resource reads need an explicit rule because the MCP server-tool wildcard does not match them.
  `list_mcp_resources` retains the built-in allow for cached resource discovery.
  The native probe executes resource listing against a synthetic cache, asserts that metadata reaches the model, and rejects access to an MCP client.
  Plan Mode permits the scoped reads and approved web/resource reads, and denies other shell calls, file edits, and MCP server tools; YOLO and remembered tool approvals are disabled.
  `sandbox-lint --gemini .gemini` checks the static profile, with opt-in pytest integration tests against native 0.59.0 APIs for settings, policies, headless refusal, and Linux enforcement.
  Every Gemini upgrade requires revalidating the native probe against that version; static CI checks alone do not establish effective policy precedence.
- Skills: `setup-isolated-setup-install`, `-update`, `-verify`,
  `-doctor`. The update skill establishes the agent-guard wiring before
  diffing anything: with the `magpie-agent-guard` plugin enabled, the
  plugin's `hooks/hooks.json` registers the hook and resolves the engine
  under `${GROK_PLUGIN_ROOT:-${CLAUDE_PLUGIN_ROOT}}` (#1516), so an absent `~/.claude/scripts/agent-guard.py`
  is the expected shape rather than drift, and on either wiring a
  `git commit` carrying a `Co-Authored-By:` trailer must be denied as a
  behavioural canary (#1323). The diagnostic side — the failure catalog in
  `docs/setup/sandbox-troubleshooting.md`, the `sandbox-error-hint.sh`
  hook, the doctor's live probes and the verify checks — is specified
  in [`sandbox-diagnostics.md`](sandbox-diagnostics.md).
- `docs/setup/secure-agent-internals.md` — the three-layer model.

## Behaviour & contract

The reference model is four layers, layered:

1. **Clean environment** — a wrapper strips the process env to a
   project-declared whitelist before exec (no `$GH_TOKEN`, `$AWS_*`,
   `$ANTHROPIC_API_KEY` leakage).
   `AGENT_ISO_ALLOW` explicitly names additional variables required by runtime authentication or tooling.
   It replaces `CLAUDE_ISO_ALLOW` when set, including an empty value; the legacy name remains supported otherwise.
   Unlisted variables stay stripped and values are never printed by the wrapper.
   The sourced-mode flag that makes `claude-iso` and friends launch a
   child rather than `exec` is a `local` inside each sourced entry point,
   not a global: Claude Code's Bash tool replays a snapshot of functions
   and aliases that drops plain variables, so under the documented
   `alias claude=claude-iso` an agent's `claude --version` used to take
   the `exec` path and replace its own shell (#1383). The verify and
   install skills read the runtime version with `command claude --version`
   for the same reason (#1384).
2. **Filesystem + network sandbox** — Linux `bubblewrap` + `socat` SNI
   proxy; macOS `sandbox-exec`. Default-deny reads outside the tree and
   egress to non-allowed hosts. `sandbox.excludedCommands` carves out
   commands that need host auth the sandbox blocks:
   - `gh` (OS keyring and, on macOS, Security.framework TLS
     verification); the blast radius is held by layers 3 (`gh auth
     token` / `gh auth refresh` denied) and 4 (`gh` writes gated by
     `ask`).
   - the vetted-ops **read** dispatcher, which spawns `gh` and so
     inherits the same need; only the read dispatcher, never
     `vetted-op` itself, because `--caller` is argv. Both invocation
     forms are excluded and allowed — `uv run --project … vetted-op-read`
     and the `uvx --from … vetted-op-read` form the read-only gatherer
     agents use (#1393) — and both name the fixed path
     `~/.claude/magpie/vetted-ops` rather than a versioned plugin-cache
     glob (#1406; see [`vetted-command-surface.md`](vetted-command-surface.md)).
   - the vetted-ops **tracker** dispatcher, `vetted-op-tracker`, in both
     forms (#1448).
     The status-rollup and body-field writes need a `gh` that can verify
     TLS, and `tools/github-rollup` / `tools/github-body-field` call `gh`
     from a `uv run` subprocess, so every skill using them failed in the
     sandbox.
     Excluding this entry point is acceptable where excluding `vetted-op`
     is not: it refuses every operation except the tracker procedures
     before reading the policy, and their runner refuses any `gh` call
     outside `repos/<tracker>/`.
     It is on `ask` and never `allow`, so each write keeps its
     confirmation.
     `vetted-op` itself is never excluded, because that would run the
     whole write catalogue unsandboxed.
     sandbox-lint's `expected.json` carries both forms in
     `excludedCommands` and `ask`, and its tests assert the tracker
     dispatcher is excluded and asked but not allowed, and that
     `vetted-op` is never excluded.
   - the adversarial-review tool, in its single-line form
     (`uvx --from ~/.claude/magpie/adversarial-review adversarial-review *`),
     because the reviewer CLIs need network and their own credentials
     (#1371). The path is the fixed link its plugin's `SessionStart` hook
     maintains, never a `*` where the version sits, which would also match
     `uv` options spliced in there; sandbox-lint rejects a `*` before the end
     of any excluded command. The plugin cache and the link are `Edit`-denied, and there is
     deliberately no `allow` rule, so every run keeps its prompt.
     Install Step R wires it; verify check 14 checks the exclusion, the
     deny and the absence of an allow.
   - `roborev *` (optional, third-party): the
     [roborev](../../../docs/setup/companion-skills.md#roborev) CLI reads
     its config, review database and daemon state under `~/.roborev/`.
     It is not in the reference settings. Install Step B adds it with a
     catch-all `Bash(roborev *)` ask and no `allow`, since outside the
     sandbox `review --local` runs an agent, `--repo` reaches any checkout
     and even `status --server` dials out, and `Edit`-denies
     `.roborev.toml` and `~/.roborev/**`, which pick the agent, endpoint and
     hooks the daemon runs. Optional Step B.2 moves the daemon to a fixed
     unix socket and makes `~/.roborev/` readable (never writable) from the
     sandbox so the post-commit hook reviews the agent's own commits, at the
     cost of letting any sandboxed command drive the daemon without the
     prompt. Verify check 17 covers both.
   - `~/.claude/scripts/magpie-run-evals.sh` (optional), so a suite
     can be graded by `claude -p` from inside the sandbox.

   That list is closed: sandbox-lint accepts an exclusion only when it is
   one of these entries or a narrowing of one (`EXCLUDED_COMMAND_ALLOWLIST`),
   because no check can recognise every command that runs its arguments.
   An adopter adds its own in
   `.apache-magpie-overrides/sandbox-lint/excluded-commands.txt`, and those
   still have to pass the runs-anything check.

   An exclusion runs whatever the command executes **outside** the
   sandbox, so the executed code must not be writable by the thing
   being sandboxed. The non-`gh` entries above therefore address code
   outside the repository — the plugin cache, `~/.claude/magpie/` and
   `~/.claude/scripts/`, none inside any `allowWrite` root or working
   directory (`permissions.additionalDirectories`, which the sandbox
   also makes writable) — with
   `permissions.deny` `Edit(…)` rules over the same paths. An in-repo path cannot carry
   that guarantee: without a deny the agent rewrites what runs
   unsandboxed, and a deny only stops the agent's editing tools while
   the file stays in a tree the agent can otherwise reach. The
   mechanical cost is separate and already solved — an `Edit(path)`
   deny merges into `sandbox.filesystem.denyWrite`, so an in-repo
   denied path must also join the `sandbox_write_denied` anchor in
   `.pre-commit-config.yaml` or the three whitespace hooks abort the
   run (#1309).

   A second, independent deny protects the vetted-ops **policy** — the
   file the dispatcher consults to decide which caller may run which
   operation — on both surfaces it can resolve to: the
   `magpie-vetted-ops` plugin-cache install and the committed
   `.apache-magpie-overrides/tools/vetted-ops/**` override. An agent
   able to rewrite the policy grants itself the whole write catalogue
   regardless of which dispatcher binary handles the call, so this
   deny applies even though the write dispatcher (`vetted-op`) is
   never excluded from the sandbox. The override is the in-repo case
   described above, `sandbox_write_denied` entry included (#1308,
   #1309). The framework's own dispatcher source at
   `tools/vetted-ops/` is deliberately left un-denied — it is PR-gated
   code, and a write-deny there would make the whole tree read-only to
   every sandboxed subprocess, `prek`'s fixers included.

   The `gh` exemption applies only to invocations made of `cd …` /
   `gh …` parts; the same whole-command shape rule governs the other
   entries. The rule and its failure signature are in
   [`sandbox-diagnostics.md`](sandbox-diagnostics.md).

   `sandbox.filesystem.allowRead` grants Docker Desktop's CLI
   directories `~/.docker/bin/` and `~/.docker/cli-plugins/` as exact
   paths by default, so `docker`, `docker compose` and `docker buildx`
   start inside the sandbox; the rest of `~/.docker` stays denied, and
   `Read(~/.docker/**)` still denies it to the file tools (#1404; see
   [`container-gateway.md`](container-gateway.md)).

   `sandbox.network.allowedDomains` stays deliberately narrow: beyond the
   service hosts the skills call, it carries only the build-time download
   hosts prek needs — `*.crates.io` and `static.rust-lang.org` for the
   `lychee` toolchain, and `registry.npmjs.org`, `nodejs.org` and
   `releases.astral.sh` for the node and python hook environments
   (#1565). sandbox-lint's `expected.json` carries all five, and the
   update skill reports any of them missing as drift.
3. **Tool permissions** — the host's `permissions.deny` blocks denied
   paths/binaries (`Read(~/.ssh/**)`, `Bash(curl *)`, …).
4. **Forced confirmation** — `permissions.ask` on `git push` and,
   on every `gh` **write** subcommand, listed one by one (`gh pr merge`,
   `gh issue close`, `gh release delete`, `gh api`, …). Not on a
   catch-all `Bash(gh *)`: Claude Code evaluates deny, then ask, then
   allow, and a matching ask rule prompts even when a more specific
   allow rule also matches, so a catch-all would silently defeat the
   read-only allows (`gh pr view`, `gh * list`, …) and prompt on every
   read. A subcommand in neither list falls through to the mode's
   default (prompt in default mode, classifier in auto).

   `gh api` asks only in its write shapes (#1432). It sends something
   other than a GET only when it names a method (`-X` / `--method`),
   sends request fields (`-f` / `-F` / `--field` / `--raw-field`, which
   switch the default to POST) or sends a body (`--input`), so the ask
   list matches each of those flags both right after `gh api` and later
   in the command, value attached or separate. It also asks on `-i`
   (`--include`), `gh api`'s only boolean short flag: a write flag can be
   bundled behind it (`-iXPOST`, `-iFquery=@q.graphql`), and such a
   cluster matches none of the per-flag rules. A plain GET (with `--jq`,
   `-H` or `--paginate`) does not prompt, and the specific `gh api` GET
   allow rules, which a blanket `Bash(gh api *)` ask had silently
   overridden, take effect. GraphQL still asks, since every call sends
   `-f query=…` and a pattern cannot tell a query from a mutation.
   sandbox-lint's `expected.json` mirrors the rules.

   The **allow** half ships too (#1393). `setup-isolated-setup-install`
   carries the reference `permissions.allow` set into an adopter's
   settings merge alongside `deny` and `ask` — `gh` reads, both
   vetted-ops read forms, the read-only archive / mailbox / roster MCP
   tools, and the registry `WebFetch` hosts (`cveawg.mitre.org`,
   `pypi.org`, `lists.apache.org`) — and `setup-isolated-setup-update`
   diffs it, because a missing read-only entry is a prompt on every skill
   run. Only read-only entries belong there; `vetted-op` (writes) stays
   on `ask`.
   Install Step V now describes three entry points over one catalogue and
   adds `vetted-op-tracker` to both `ask` and `sandbox.excludedCommands`.
   The update skill reports `vetted-op-tracker` in `allow`, or `vetted-op`
   in `excludedCommands`, as a must-fix, and a missing tracker exclusion
   or `ask` entry as drift; the verify skill fails the check when
   `vetted-op` is in `excludedCommands` (#1448).

Pinned system tools (`bubblewrap`, `socat`, agent CLI) are aged through a
cooldown window; bumps are PRs, not silent updates. The window is the
framework's 7-day default unless a tool's `[tools.<name>]` table in
`tools/agent-isolation/pinned-versions.toml` sets its own
`cooldown_days`; `bubblewrap` carries `cooldown_days = 1`, so a pin
carrying a sandbox-setup security fix can move a day after release
(#1360; pinned at 0.13.1 since #1721).

## Out of scope

- The human-in-the-loop *confirmation* itself (that is the modes' job);
  this area provides the OS-level enforcement underneath it.
- Editing `.claude/settings.json` (it is in the `deny` list).

## Acceptance criteria

1. Filesystem and network default-deny with explicit allow-lists in the
   reference setup; Gemini's different boundaries are documented above.
2. The clean-env wrapper strips credential-shaped vars before exec.
3. `git push` and every `gh` write subcommand are in `permissions.ask`,
   the read-only `gh` subcommands are in `allow`, and no catch-all
   `Bash(gh *)` sits in `ask`; secret/cred files are in `permissions.deny`.
4. `gh api` asks in each write shape (`-X`, `--method`, `-f`, `-F`,
   `--field`, `--raw-field`, `--input`, directly after `gh api` or later)
   and not on a plain GET; no blanket `Bash(gh api *)` sits in `ask`.
5. The adopter install merges `permissions.allow` with `deny` and `ask`,
   and the update skill diffs it.
6. The dogfooded `allowedDomains` includes `registry.npmjs.org`,
   `nodejs.org` and `releases.astral.sh`, so a sandboxed `prek run` builds
   its node and python hook environments; the update skill reports their
   absence as drift (#1565).

## Validation

```bash
uv run --project tools/agent-isolation --group dev pytest
uv run --directory tools/agent-guard --group dev pytest
uv run --project tools/permission-audit --group dev pytest
uv run --project tools/egress-gateway --group dev pytest
python3 -c "import json,sys; s=json.load(open('.claude/settings.json')); \
  ask=s['permissions']['ask']; \
  sys.exit(0 if any(a.startswith('Bash(git push') for a in ask) \
    and 'Bash(gh pr merge *)' in ask and 'Bash(gh *)' not in ask \
    and 'Bash(gh api -X*)' in ask and 'Bash(gh api *)' not in ask else 1)"
uv run --project tools/sandbox-lint --group dev pytest
python3 tools/dev/sync-hook-managers.py --check
uv run --project tools/setup-preflight --group dev pytest \
  tools/setup-preflight/tests/test_session_hook.py
```

## Known gaps

- `stable`; drift shows up when a new state-mutating command is added to a
  skill without a matching `ask` rule — the plan pass flags it.
- **`tools/agent-guard/` and `tools/egress-gateway/` are new additions**
  since the last pilot cycle; end-to-end integration with a real adopter
  session has not yet been exercised.

## Gemini setup lifecycle

The four `setup-isolated-setup-*` skills route Gemini requests to
`docs/adapters/gemini.md` and stop before the Claude-specific procedure.
The install route merges the workspace profile and a single guard registration
from the existing extension, snapshot, or framework checkout, preserving
unrelated settings and requiring review of conflicts.
Extension setup must not introduce a second snapshot installation.
Verification distinguishes static configuration from live enforcement;
update and doctor report drift or diagnoses without applying changes.
Generic setup reconciles installed profiles and removes their guard references
before uninstalling the source.
