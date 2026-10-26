---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: isolated-setup-install
family: setup
mode: Meta
description: >-
  Walk an adopter through the first-time install of the secure agent
  setup (sandbox, approval and clean-environment layers) for Claude
  Code, Codex or Antigravity. Interactive throughout; never runs sudo,
  edits a shell rc, or overwrites settings on its own.
when_to_use: >-
  When the user wants the secure setup installed for the first time, or
  is working in a fresh clone or on a new machine with no wiring yet.
  If it is already installed, use `setup-isolated-setup-verify` to check
  it or `setup-isolated-setup-update` to refresh it.
capability: capability:platform
surface_hash: sha256:d33e1ff373860d4b
license: Apache-2.0
measured_tokens: 8191
---

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → per file: the personal layer, else `.apache-magpie-overrides/`
     <tracker>        → value of `tracker_repo:` in <project-config>/project.md
     <upstream>       → value of `upstream_repo:` in <project-config>/project.md -->

# setup-isolated-setup-install

## Runtime routing (run before the Claude-specific procedure)

Use the operator's explicitly requested runtime when supplied; otherwise use the active session's runtime.
An installed executable or configuration directory alone does not select a runtime.
For the routing below, treat that selection as the active harness.

Determine the active harness from the session metadata and executable. When it
is Codex, follow the install lifecycle in
[docs/adapters/codex.md](../../../../docs/adapters/codex.md#install), including the
project profile merge, static lint, project trust, and `agent-iso codex`
steps. Do not write Claude settings or report a missing `.claude` file as a
Codex failure. After completing the Codex branch, stop; the remainder of this
skill is the Claude Code branch.

When the selected runtime is Antigravity, follow
[docs/adapters/antigravity.md](../../../../docs/adapters/antigravity.md#install): resolve the installed plugin, snapshot, or framework checkout; propose the merge of the user-scope profile into `~/.gemini/antigravity-cli/settings.json` and of the guard into `~/.gemini/config/hooks.json`; then guide the wrapper launch and verification.
The setup is per user: write nothing into the repository.
Do not require or write Claude configuration.
After completing the Antigravity branch, stop before the Claude-specific procedure below.

When the selected runtime is Copilot CLI, follow [docs/adapters/copilot.md](../../../../docs/adapters/copilot.md#install): register the guard hook, detect and declare mail sources from the MCP servers already present, and ask nothing beyond the single apply confirmation (PRINCIPLES.md §1, *Avoiding prompt fatigue*). Do not require or write Claude configuration.
After completing the Copilot branch, stop before the Claude-specific procedure below.

When the harness is Claude Code, continue below. If the harness cannot be
determined from the session or executable, stop and report that; never guess and never prompt.

This skill is the **on-ramp** for adopters who do not yet have the
secure setup running. It is a thin walkthrough wrapper around the
canonical install path documented in
[`docs/setup/secure-agent-setup.md`](../../../../docs/setup/secure-agent-setup.md). The
authoritative content lives there; this skill exists so an adopter
can say *"set up the secure agent setup"* in a fresh session and
land in the right step-by-step flow without first reading the
document.

## Adopter overrides

<!-- BEGIN MAGPIE BLOCK: adopter-overrides — generated from tools/dev/blocks/adopter-overrides.md -->

Before running its default behaviour, this skill consults
`setup-isolated-setup-install.md` in the personal layer
(`.apache-magpie-local/` when the project adopted Magpie, falling back to the main checkout's in a linked worktree,
or `<git-common-dir>/apache-magpie/` when Magpie is only installed; applied first, wins on conflict) and
[`.apache-magpie-overrides/setup-isolated-setup-install.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo, if present, and applies any agent-readable overrides it finds.
See [`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md) for the contract.

**Hard rule**: agents NEVER modify the snapshot under `<adopter-repo>/.apache-magpie/`.
Local modifications go in the override file; framework changes go via PR to `apache/magpie`.

<!-- END MAGPIE BLOCK: adopter-overrides -->

---

## Snapshot drift

Also at the top of every run, this skill compares the
gitignored `.apache-magpie.local.lock` (per-machine
fetch) against the committed `.apache-magpie.lock`
(the project pin). On mismatch the skill surfaces the
gap and proposes
[`setup upgrade`](../setup/upgrade.md).
The proposal is non-blocking — the user may defer if
they want to run with the local snapshot for now. See
[`docs/setup/install-recipes.md` § Subsequent runs and drift detection](../../../../docs/quick-start/other-install-methods.md#subsequent-runs-and-drift-detection)
for the full flow.

Drift severity:

- **method or URL differ** → ✗ full re-install needed.
- **ref differs** (project bumped tag, or `git-branch`
  local is behind upstream tip) → ⚠ sync needed.
- **`svn-zip` SHA-512 mismatches the committed
  anchor** → ✗ security-flagged; investigate before
  upgrading.

---
## Golden rules

- **Do not auto-run privilege-elevating commands.** Anything that
  needs `sudo` (apt / dnf installs, system-wide writes) is *printed*
  for the user to copy-paste into their own terminal. The skill
  never invokes `sudo` itself.
- **Do not edit shell rc files without approval.** `~/.bashrc` /
  `~/.zshrc` modifications (sourcing `agent-iso.sh`, the optional
  `alias claude='claude-iso'`) are surfaced as the exact line to
  add; the user pastes it themselves. The skill confirms the rc
  file path with the user first; it does not assume.
- **Do not overwrite an existing settings file silently.** If the
  user already has a project `.claude/settings.json` or a
  user-scope `~/.claude/settings.json`, the skill *diffs* the
  desired merge against the existing file and asks for explicit
  approval before writing. The merge carries the framework's
  `permissions.allow` set (the read-only reads: `gh` reads, the
  vetted-ops read dispatcher, archive / mailbox / roster MCP reads,
  registry `WebFetch` hosts) alongside `deny` and `ask` — leaving it
  out makes every skill read prompt. Only read-only entries belong in
  `allow`. Re-installs / partial-state recoveries
  are common — the skill must not blow away an unrelated
  pre-existing hook or `permissions.ask` rule. The desired merge
  **includes the agent-guard `hooks.PreToolUse` entry** (matcher
  `Bash`, command running the user-scope `~/.claude/scripts/agent-guard.py`)
  — the deterministic guard from
  [`tools/agent-guard`](../../../../tools/agent-guard/README.md). Install
  the script as `~/.claude/scripts/agent-guard.py` and populate
  `~/.claude/scripts/guards.d/` from both the engine's bundled
  `guards.d/*.py` and every skill-owned `skills/*/guards/*.py`
  (so skill-owned guards like `mention` / `mark-ready` are active),
  alongside the other user-scope scripts (Step P); wire the
  `PreToolUse` entry once, and preserve any pre-existing `hooks`
  entries.
- **Stop on the first failure.** If a step fails (manifest read
  fails, framework path wrong, an existing file conflicts in a way
  the user has not yet decided about), stop and report. Do not
  push past a failure to the next step.

## Up-front confirmations

Before walking any install step, confirm with the user:

1. **OS / distro.** macOS, Ubuntu / Debian (apt), Fedora / RHEL
   (dnf), or Arch / NixOS / other. macOS skips bubblewrap +
   socat (Seatbelt is built-in); Linux installs both per the
   distro shortcut.
2. **Framework checkout path.** The path to the user's local
   `magpie` clone. Required to read
   `tools/agent-isolation/pinned-versions.toml`,
   `.claude/settings.json`, and the
   `tools/agent-isolation/*.sh` scripts. If the user does not
   have a clone, walk them through `git clone` first.
3. **Fresh install or re-install.** For a re-install on a partial
   existing state, the skill must enumerate the existing wiring
   (project settings.json, user settings.json, hooks dir, the
   agent-guard `hooks.PreToolUse` entry + `~/.claude/scripts/agent-guard.py`,
   shell rc) before any merge so the user knows what is being
   preserved vs replaced.
4. **Sync repo (optional).** Whether the user maintains a
   private dotfile-style `~/.claude-config` repo per
   [Syncing user-scope config across machines](../../../../docs/setup/secure-agent-setup.md#syncing-user-scope-config-across-machines).
   If yes, the skill installs user-scope scripts as **symlinks**
   into `~/.claude-config/scripts/` rather than `cp`-ing into
   `~/.claude/scripts/` — the symlink approach is what makes
   sync push the upgrades to other machines automatically.

## Walk-through

Follow the canonical step list at
[docs/setup/secure-agent-setup.md → Adopter setup → Via a Claude Code prompt](../../../../docs/setup/secure-agent-setup.md#via-a-claude-code-prompt).
Each step in that list maps 1:1 to a step in this skill. Do not
re-write the list here — read the doc, follow it, and surface each
sub-step with the user. The doc names are the source of truth; the
skill is the runner.

For the verification step at the end, hand off to the
`setup-isolated-setup-verify` skill rather than re-walking the checklist
inline.

### Agent harness — install `@latest`, enforce the floor

`claude-code` is **not** pinned to an exact version. Install it with
`npm install -g --no-save @anthropic-ai/claude-code@latest` (the
command in the doc's install list) — latest always carries the newest
permission-rule / sandbox / prompt-injection fixes. The manifest's
`[tools.claude-code]` table in
[`pinned-versions.toml`](../../../../tools/agent-isolation/pinned-versions.toml)
declares a `min_version` **floor**, not a pin. Because this install is
driven from Claude Code, apply the same hard gate
`setup-isolated-setup-verify` check 5 applies: read the running
version (`command claude --version`, which skips an
`alias claude=claude-iso`) and, if it is **below** `min_version`,
**hard-fail** — stop the install, tell the operator to upgrade to
`@latest`, and have them re-run. The secure setup must not be stood up
on a below-floor runtime.

### Step P — Project-root coverage in the sandbox allowlists

The harness drops the literal `.` when it pre-resolves
`sandbox.filesystem.allowRead: ["."]`, so a session in a fresh clone can
write to the project root but not read from it. The fix is to add the root
as an absolute path to the project-local `settings.local.json`.

This step asks one question first — per-project or whole-user scope — and
the whole-user answer overrides git's hook lookup for every repository on
the machine, so it carries a disclosure the operator has to acknowledge.

**Full procedure, both scopes and both whole-user flavours:**
[`step-p-sandbox-allowlists.md`](step-p-sandbox-allowlists.md).

### Step V — The vetted-ops split and exclusion

Only applies when the adopter routes forge operations through the
`vetted-ops` dispatcher — i.e. the repo has
`.apache-magpie-overrides/tools/vetted-ops/config.toml`, the maintainer
keeps a personal one (`<personal layer>/tools/vetted-ops/config.toml`,
for a project that has not adopted Magpie), or the operator asks for the
dispatcher to be wired now. If neither is
true, skip this step, report it as **n/a**, and continue with the
next step: a missing policy is never a blocker for this install.
Do not create a policy the project has not asked for.

**Only with the sandbox on.** The allow rules and sandbox exclusions
below are a permission bypass: they let the dispatcher run without a
prompt, and outside the sandbox. They are safe only because the sandbox
confines everything else. If the sandbox is not enabled for this
session (Step P declined, or `sandbox.enabled` is not `true` in the
scope being wired), skip this step, say so, and leave every vetted
operation behind its normal prompt.

There are three console scripts over one catalogue, and which of them
gets the `allow` is the entire security question:

| Entry point | Can write? | Permission |
|---|---|---|
| `vetted-op-read` | never — refused before policy or `--caller` is consulted | `allow` |
| `vetted-op-tracker` | only the tracker rollup / body-field procedures — everything else refused before policy | `ask` |
| `vetted-op` | yes | `ask` |

**Never propose an `allow` on `vetted-op`.** It is tempting, because
the policy declares a read-only caller and the invocation names it.
That reasoning is wrong: `--caller` is an argv string chosen by
whoever runs the command, so an `allow` on the write dispatcher
grants every operation in the catalogue no matter which caller the
example names. The read dispatcher needs no such trust — it refuses
writes structurally.

```jsonc
"permissions": {
  "allow": [
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-read *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *)"
  ],
  "ask": [
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op *)",
    "Bash(uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker *)",
    "Bash(uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker *)"
  ],
  "deny": [
    // `Edit(path)` is the path rule for every file-writing tool — Write and
    // NotebookEdit included. A `Write(path)` rule is NOT matched by the file
    // permission check; do not add one alongside, it reads as a second layer
    // that is not there.
    //
    // the operation catalogue — the read `allow` rests on its shape
    "Edit(~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/**)",
    // the fixed path the rules name, which points into that catalogue
    "Edit(~/.claude/magpie/**)",
    // the policy naming which caller may run which operation
    "Edit(.apache-magpie-overrides/tools/vetted-ops/**)",
    "Edit(//**/.git/**/apache-magpie/tools/vetted-ops/**)",
    "Edit(//**/.svn/apache-magpie/tools/vetted-ops/**)",
    "Edit(//**/.apache-magpie-local/tools/vetted-ops/**)"
  ]
}
```

Allow **both** invocation forms, and add both to
`sandbox.excludedCommands` (`"uv run --project ~/.claude/magpie/vetted-ops vetted-op-read *"` and
`"uvx --from ~/.claude/magpie/vetted-ops vetted-op-read *"`). Skills document `uv run --project`; read-only
gatherer agents use `uvx --from`, because `uv run` in the plugin cache
needs to write a venv there. A rule for only one form leaves every call
in the other form prompting.

Add both forms of `vetted-op-tracker` to `sandbox.excludedCommands` too
(`"uv run --project ~/.claude/magpie/vetted-ops vetted-op-tracker *"` and
`"uvx --from ~/.claude/magpie/vetted-ops vetted-op-tracker *"`): the status-rollup
and body-field writes need a `gh` that can verify TLS, which a sandboxed one cannot.
Excluding it is acceptable where excluding `vetted-op` is not, because its catalogue
is closed to the tracker procedures — every other operation is refused before the
policy is read — and their runner refuses any `gh` call outside `repos/<tracker>/`.
It stays in `ask`, never `allow`, so each write keeps its confirmation.
**Never exclude `vetted-op` itself**: that would run the whole write catalogue unsandboxed.

The rules name the fixed path `~/.claude/magpie/vetted-ops`, never the
versioned plugin-cache directory. The plugin's `SessionStart` hook points
that path at the installed version every session, so an upgrade needs no
rule change. **Never write a rule with `*` in place of the plugin
version.** A `*` also matches spaces, so it approves — and, in
`excludedCommands`, runs unsandboxed — a command with extra `uv` options
spliced in at that position (`--with <any package>`, a second `--from`).
If an adopter's settings still carry the versioned `*` form, replace it
with the fixed path.

Tell the operator plainly what this buys and what it does not:

- The catalogue is protected twice — by these rules, and by the
  plugin cache sitting outside every `sandbox.filesystem.allowWrite`
  root, so sandboxed Bash cannot write there either.
- The policy TOML is protected **once**, and that is tolerable only
  because the read dispatcher ignores policy when it refuses a
  write. Editing the policy can widen which repo is *read*; it
  cannot turn a read into a write.
- Writes are not unattended. They keep the harness confirmation —
  the dispatcher bounds their *shape*, not the operator's decision
  to make them.

Do not describe per-caller scoping as isolation. It is
least-privilege hygiene for a cooperating skill, and it is worth
having for that, but it stops nothing that chooses to name a
different caller.

#### Step V.1 — Read-only vetted ops MUST never prompt

This is not optional. No `vetted-op-read` invocation may ever prompt, in
any form: bulk skills run it from background gatherer agents, which cannot
surface a prompt, so each prompt is a silent denial and the sync returns
partial results nobody can verify. Rationale and the full shape:
[`docs/setup/secure-agent-setup.md` → Read-only vetted ops never prompt](../../../../docs/setup/secure-agent-setup.md#read-only-vetted-ops-never-prompt).

Resolve `$HOME`, read every settings scope (user, project, project-local,
and managed where readable), and propose the exact edit for each gap. The
operator applies it; never write a settings file on your own.

1. **Allow both launchers.** `Bash(<launcher> ~/.claude/magpie/vetted-ops vetted-op-read *)`
   MUST be allowed for each launcher in {`uvx --from`, `uv run --project`}:
   two rules, in the committed project `.claude/settings.json` (as in the
   framework's own) or in user scope. The literal `~` is the only spelling:
   the agent-guard `vetted-ops-spelling` guard refuses an expanded home path,
   so no absolute-path rule is needed. If an earlier run left
   `<resolved $HOME>/.claude/magpie/vetted-ops` allow rules or exclusions,
   propose removing them.
2. **No ask rule.** Propose removing every `permissions.ask` rule, in any
   scope, that matches a `vetted-op-read` command in either launcher form —
   a broad rule such as `Bash(uvx *)` counts. An ask rule prompts even when
   an allow rule matches.
3. **Read block off.** If `permissions.blockReadsOutsideWorkingDirectories`
   is `true` in any scope, propose removing it (or setting it `false`). With
   it on, every call prompts, because the check cannot resolve the literal
   `~` the commands spell, and no `allow` rule overrides it. Never offer an
   `additionalDirectories` entry or `/add-dir` for the checkout instead (see
   item 7). Say plainly that Bash stays
   sandboxed and the credential `Read` denies still apply. If managed
   settings force it on, the imperative cannot be met on this machine:
   tell the operator, and that bulk skills must not run their gatherer
   agents there.
4. **Tamper protection.** The three `Edit` deny rules above MUST be present,
   in the project settings or in user scope; propose any that is missing.
   They are what makes the unprompted read safe.
5. **Exclusions for both launchers.** `sandbox.excludedCommands` keeps
   the `vetted-op-read` and `vetted-op-tracker` entries in both `~`
   launcher forms. Without them an allowed call runs inside the sandbox,
   where its `gh` cannot verify TLS: a silent failure again.
6. **The spelling guard.** The agent-guard plugin MUST be installed, so its
   `vetted-ops-spelling` guard turns an expanded spelling into a refusal that
   names the `~` command, instead of a sandboxed call that fails silently.
7. **The checkout is not a working directory.** No
   `permissions.additionalDirectories` entry in any scope may cover
   `$HOME/.claude/magpie` (that path, its `~` spelling, anything inside it
   such as `~/.claude/magpie/vetted-ops`, or a parent such as
   `$HOME/.claude` or `$HOME`). A working directory is writable to sandboxed
   Bash, and item 5's exclusions run that checkout outside the sandbox.
   `sandbox-add-project-root.sh` removes the `~/.claude/magpie` entry it once
   added from each worktree's `settings.local.json`; propose the hand edit for
   any other covering entry, naming the file.

This covers the read dispatcher only. `vetted-op-tracker` and `vetted-op`
stay in `ask`, never in `allow`, and `vetted-op` is never excluded.

### Step R — The adversarial-review exclusion

Only applies when the `magpie-adversarial-review` plugin is installed. If it
is not, skip this step and say so.

The reviewer CLIs it runs (`codex`, `copilot`, `agy`, `grok`, `claude`)
need network access and read their own credentials (`~/.codex`,
`~/.copilot`, `~/.gemini/antigravity-cli`, `~/.grok`, `~/.claude`), which this sandbox denies. The tool therefore
runs outside it, through one exclusion. It names `~/.claude/magpie/adversarial-review`,
a link the plugin's `SessionStart` hook points at the installed version every
session, never a `*` where the version sits: that would also match `uv`
options spliced in at that position, and run them outside the sandbox.

```jsonc
"sandbox": {
  "excludedCommands": [
    "uvx --from ~/.claude/magpie/adversarial-review adversarial-review *"
  ]
},
"permissions": {
  "deny": [
    // the tool runs unsandboxed, so the code it runs must not be editable
    // by the agent that calls it
    "Edit(~/.claude/plugins/cache/apache-magpie/magpie-adversarial-review/**)",
    "Edit(~/.claude/magpie/**)"
  ]
}
```

**Do not add an `allow` for it.** Every run sends the change to other
model providers and costs money; the harness prompt is the gate, by design.

Tell the operator what the exclusion covers and what it does not:

- It matches only the single-line form, spelled with a literal `~` and an
  unquoted path. A pipe, `$(…)`, `&&`, a redirection, quotes, or an
  expanded home directory put the command back in the sandbox, where the
  reviewer CLIs fail to read their credentials and report `unavailable`.
- The `*` in the pattern can match more than a version directory — a path
  with `..` segments would still match. The prompt that every run keeps is
  the gate against that; read the path in it before approving.
- The tool refuses a `--body-file` or `diff:` file outside the repository
  or a temporary directory, so an approved run cannot be pointed at
  `~/.ssh` or a private checkout to send it to a model.
- Outside the sandbox the tool only runs each reviewer CLI in its own
  read-only mode, and writes nothing to the repository. `codex`'s
  read-only mode still reads files anywhere on the machine; see the tool's
  README for what that means for a machine that also holds a private
  checkout.

### Step W — Working directories for the read block

Where the vetted-ops dispatcher is used, Step V.1 already requires
`permissions.blockReadsOutsideWorkingDirectories` to be off, and these
entries cannot stand in for that: they do not stop the `vetted-op-read`
prompt. They remain useful for the agent's own reads of the scratch root
where the block is on for other reasons.

Nothing extra to write: the `sandbox-add-project-root.sh` run in Step P also
adds `/tmp/claude-<uid>`, resolved, to `permissions.additionalDirectories` of
each worktree's project-local `settings.local.json`. Under
`permissions.blockReadsOutsideWorkingDirectories` the skills read it on every
run; without the entry each read prompts, and a bulk sync multiplies that by
its gatherer agents. The script also removes `$HOME/.claude/magpie` where an
earlier version added it.

After Step P, show the operator the resulting `additionalDirectories` list and
check three things:

- **Never `~/.claude/magpie`.** If any scope lists `$HOME/.claude/magpie` or a
  parent of it, propose removing it. A working directory is writable to
  sandboxed Bash, and the vetted-ops commands run from that checkout outside
  the sandbox. `/add-dir` has the same effect for a session.

- **No glob and no `~`.** If the operator already has an entry such as
  `/tmp/claude-*` in any scope, say it does nothing: the setting matches
  literal paths only, so the glob is listed but never matched.
- **Nothing per-host in a synced or committed file.** If the operator put the
  paths in a user-scope `~/.claude/settings.json` that is synced across
  machines, or in the committed project settings, suggest moving them: they
  name this host's uid.

Rationale and the rules in full:
[`docs/setup/secure-agent-setup.md` → Working directories under the read-outside-working-directories block](../../../../docs/setup/secure-agent-setup.md#working-directories-under-the-read-outside-working-directories-block).

### Step U — Host-only uv state

The excluded `uvx` / `uv run` commands, MCP servers launched with `uv`, hooks
that call `python3` and the operator's own terminal all run uv-managed code
outside the sandbox. None of it may come from a directory a sandboxed command
can write:

- **`~/.local/share/uv` is read-only to the sandbox.** No scope may list it,
  or a parent of it, in `allowWrite` or `additionalDirectories`. The Step P
  helper removes the write an earlier version added; propose removing any other
  by hand.
- **The host gets its own uv cache.** Read `~/.config/uv/uv.toml`. Unless it
  sets a `cache-dir` that is absolute and, symlinks resolved, outside every
  directory a sandboxed command can write (every `allowWrite` and `additionalDirectories` entry in any scope, every project root, and the roots the sandbox writes without a grant (`/tmp`, `/private/tmp`, `/var/folders`, `/private/var/folders`, `$TMPDIR`)),
  stage it with `cache-dir = "<resolved $HOME>/.local/share/uv-host/cache"`
  added, keeping every other setting, and give the operator the copy command:
  `Edit(~/.config/uv/**)` keeps the agent from writing it. Never `~` (uv does
  not expand it there) and never a relative path.
- **The sandbox cannot read that file.** `permissions.deny` carries
  `Read(~/.config/uv/uv.toml)` and `Edit(~/.config/uv/**)` (both in the
  framework's `.claude/settings.json`, so Step 2's copy brings them). Sandboxed
  uv then keeps its default, writable cache.

- **Sandboxed prek gets its own home.** The `env` entry is needed only where a
  repository uses prek (a `prek.toml`, `.pre-commit-config.yaml` or
  `.pre-commit-config.yml`, or a hook that runs it:
  [detection](../../../../tools/hook-manager/README.md#detection)); the deny
  is always kept, since the default home is per-user. The settings carry
  `"env": {"PREK_HOME": "~/.cache/prek-sandbox"}` and `permissions.deny`
  carries `Edit(~/.cache/prek/**)` (both in the framework's
  `.claude/settings.json`): a terminal's git hooks run prek outside the
  sandbox from `~/.cache/prek`. The whole-user dispatcher (Step P) gives hooks
  that Claude Code runs outside the sandbox a host-only home and cache root
  too; if a repository sets its own `core.hooksPath`, propose unsetting it so
  the dispatcher runs there.

Then hand the operator the reinstall commands from the doc to run in a
terminal: interpreters and tools the sandbox could write before may already
have been changed. Rationale and commands:
[`docs/setup/secure-agent-setup.md` → Host-only uv state](../../../../docs/setup/secure-agent-setup.md#host-only-uv-state).

### Step T — Local agent settings

The committed `.claude/settings.json` is only the shared floor; the rest
of a working setup is personal and goes in `.claude/settings.local.json`.
Build and hand over that file exactly as
[`setup upgrade` → Reconcile the local agent settings](../setup/upgrade.md#reconcile-the-local-agent-settings)
does: the MCP tools for families installed here but not adopted by the
project and, **only when this project is the Magpie framework checkout**,
its template (`tools/agent-isolation/claude-settings.local.template.json`).
Never stage that template into another project: it would widen that
project's sandbox beyond what its maintainers configured. An agent
cannot write that file, so stage it and give the user the copy command.

### Steps K, L, M and B — optional extras

None of these is needed for a working install. Walk the one the operator
asks for: a hardware security key (K), the container gateway (L), the
eval-harness exclusion (M), or the exclusion for the third-party
[roborev](../../../../docs/setup/companion-skills.md#roborev) CLI (B) — offer B
unprompted when `command -v roborev` finds it.

**Procedures:** [`optional-steps.md`](optional-steps.md).

## After the install lands

**Tell the operator what to look for in the footer**, and what each
state means. This is the one piece of the install they will see on
every render afterwards, so a wrong reading here persists:

| Tag | Means |
|---|---|
| `[sandbox]` green | sandboxed, and still prompting per command |
| `[sandbox-auto]` yellow | sandboxed, **not** prompting per command — auto-allow; wider blast radius, which is why it is not green |
| `[NO SANDBOX]` bold red | not sandboxed; the state this install exists to make impossible to miss |

Captures of each are in
[*What a session looks like*](../../../../docs/setup/secure-agent-setup.md#what-a-session-looks-like);
point the operator there rather than describing the colours twice.

Two things to say explicitly, because both are counter-intuitive:

- **The tag reads the settings files, not the running process.** A
  CLI flag that disables sandboxing mid-session is not visible here.
  Pair it with the bypass-warn hook, which fires per call.
- **Yellow is not a warning that something is broken.** Auto-allow is
  a deliberate, common choice; the colour distinguishes two postures
  rather than flagging a fault.

Suggest two follow-up routines the user can wire later:

- `setup-isolated-setup-verify` — re-run after every Claude Code upgrade
  or settings-file edit, to confirm denials still fire as
  expected. The "did a denial silently turn into an allow?"
  signal is exactly what this skill exists for.
- `setup-isolated-setup-update` — periodic check for framework
  updates, pinned-tool upgrade candidates, and drift between the
  installed user-scope copies and the framework's
  source-of-truth. The pre-flight of every skill proposes it for them
  once the install is recorded (below): after an upgrade that changes
  the secure-setup files, and weekly otherwise.

**Record the install** so that pre-flight knows the isolated setup is
used on this machine and what it was installed against:

```bash
PYTHONPATH=".apache-magpie-local:$(git rev-parse --git-common-dir 2>/dev/null || echo .git)/../.apache-magpie-local:$(git rev-parse --git-common-dir 2>/dev/null || echo .git)/apache-magpie:.svn/apache-magpie" \
  python3 -m setup_preflight.isolated record-update
```

It writes the `isolated_setup` block of the personal layer's
`reconciled.json` (`<git-common-dir>/apache-magpie/` when the project has
not adopted Magpie, `.apache-magpie-local/` when it has) and nothing
else. Skip it when the command cannot find `setup_preflight` — say that
`/magpie-setup:setup config` installs the checker, and that the reminders start
once it is there.

**Check that the vetted-ops plugin is installed.** `magpie-vetted-ops`
is part of the baseline: the family skills run their forge operations
through its dispatcher, and Step V's permission rules point at it.
If the harness's plugin listing lacks it, propose
`claude plugin install magpie-vetted-ops@apache-magpie`
(`codex plugin add magpie-vetted-ops@apache-magpie` on Codex) and run it once the operator confirms.
Where the harness has no plugin CLI, print the command instead of running it.

**Always propose shared-config sync once the install lands.**
Regardless of whether the operator already maintains the
`~/.claude-config` sync repo, proactively offer to run
`setup-shared-config-sync` as a follow-up:

- If the `~/.claude-config` sync repo is already in place, the
  skill commits + pushes the local modifications (the user-scope
  scripts, hooks, and settings this install just wired up) so the
  other machines pick them up.
- If the operator does **not** yet have `~/.claude-config`, the
  `setup-shared-config-sync` skill bootstraps it (clones the
  default private remote if it exists, or creates a fresh private
  remote and scaffolds the layout). Mention this so a first-time
  operator knows the follow-up will set sync up from scratch — the
  point of proposing it is precisely so the just-installed config
  does not stay machine-local.

Surface it as an offer for the operator to accept, not an
auto-run — the sync skill has its own confirmation gates before it
commits or pushes anything.
