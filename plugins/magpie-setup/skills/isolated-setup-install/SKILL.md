---
# SPDX-License-Identifier: Apache-2.0
# https://www.apache.org/licenses/LICENSE-2.0
name: magpie-setup-isolated-setup-install
family: setup
mode: Meta
description: >-
  Walk an adopter through the first-time install of the secure agent
  setup (sandbox, approval and clean-environment layers) for Claude
  Code, Codex or Gemini CLI. Interactive throughout; never runs sudo,
  edits a shell rc, or overwrites settings on its own.
when_to_use: >-
  When the user wants the secure setup installed for the first time, or
  is working in a fresh clone or on a new machine with no wiring yet.
  If it is already installed, use `setup-isolated-setup-verify` to check
  it or `setup-isolated-setup-update` to refresh it.
capability: capability:platform
surface_hash: sha256:e78e03834f4fdec8
license: Apache-2.0
---

<!-- Placeholder convention (see AGENTS.md#placeholder-convention-used-in-skill-files):
     <project-config> → adopting project's `.apache-magpie/` directory
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

When the selected runtime is Gemini CLI, follow
[docs/adapters/gemini.md](../../../../docs/adapters/gemini.md#install): resolve the existing extension, snapshot, or framework checkout; propose the workspace profile and guard merge; then guide the wrapper launch and verification.
Do not require or write Claude configuration.
After completing the Gemini branch, stop before the Claude-specific procedure below.

When the harness is Claude Code, continue below. If the harness cannot be
determined, ask once rather than applying one runtime's policy to another.

This skill is the **on-ramp** for adopters who do not yet have the
secure setup running. It is a thin walkthrough wrapper around the
canonical install path documented in
[`docs/setup/secure-agent-setup.md`](../../../../docs/setup/secure-agent-setup.md). The
authoritative content lives there; this skill exists so an adopter
can say *"set up the secure agent setup"* in a fresh session and
land in the right step-by-step flow without first reading the
document.

## Adopter overrides

Before running the default behaviour documented
below, this skill consults
[`.apache-magpie-local/setup-isolated-setup-install.md`](../../../../docs/setup/agentic-overrides.md) (personal, gitignored) and [`.apache-magpie-overrides/setup-isolated-setup-install.md`](../../../../docs/setup/agentic-overrides.md) (committed, project-wide)
in the adopter repo if it exists, and applies any
agent-readable overrides it finds. See
[`docs/setup/agentic-overrides.md`](../../../../docs/setup/agentic-overrides.md)
for the contract — what overrides may contain, hard
rules, the reconciliation flow on framework upgrade,
upstreaming guidance.

**Hard rule**: agents NEVER modify the snapshot under
`<adopter-repo>/.apache-magpie/`. Local modifications
go in the override file. Framework changes go via PR
to `apache/magpie`.

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
  approval before writing. Re-installs / partial-state recoveries
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
version (`claude --version`) and, if it is **below** `min_version`,
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
`.apache-magpie-overrides/tools/vetted-ops/config.toml`, or the
operator asks for the dispatcher to be wired now. If neither is
true, skip this step and say so; do not create a policy the project
has not asked for.

There are two console scripts over one catalogue, and which of them
gets the `allow` is the entire security question:

| Entry point | Can write? | Permission |
|---|---|---|
| `vetted-op-read` | never — refused before policy or `--caller` is consulted | `allow` |
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
    "Bash(uv run --project ~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/*/tools/vetted-ops vetted-op-read *)"
  ],
  "ask": [
    "Bash(uv run --project ~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/*/tools/vetted-ops vetted-op *)"
  ],
  "deny": [
    // `Edit(path)` is the path rule for every file-writing tool — Write and
    // NotebookEdit included. A `Write(path)` rule is NOT matched by the file
    // permission check; do not add one alongside, it reads as a second layer
    // that is not there.
    //
    // the operation catalogue — the read `allow` rests on its shape
    "Edit(~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/**)",
    // the policy naming which caller may run which operation
    "Edit(.apache-magpie-overrides/tools/vetted-ops/**)"
  ]
}
```

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

### Steps K, L and M — optional extras

None of these is needed for a working install. Walk the one the operator
asks for: a hardware security key (K), the container gateway (L), or the
eval-harness exclusion (M).

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
  source-of-truth. Recommend a per-Claude-Code-upgrade or
  monthly cadence, whichever comes first.

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
