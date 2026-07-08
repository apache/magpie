<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Secure agent setup](#secure-agent-setup)
  - [Quick start](#quick-start)
    - [Agent-guided (recommended)](#agent-guided-recommended)
    - [Manual (if you do not want the agent-guided path)](#manual-if-you-do-not-want-the-agent-guided-path)
  - [Required tools (pinned versions)](#required-tools-pinned-versions)
    - [Install commands](#install-commands)
    - [Distro-specific shortcut — Linux Mint 22.x / Ubuntu 24.04 Noble](#distro-specific-shortcut--linux-mint-22x--ubuntu-2404-noble)
    - [Bumping a pinned version](#bumping-a-pinned-version)
    - [Wiring the check script into a weekly routine](#wiring-the-check-script-into-a-weekly-routine)
  - [The framework's own `.claude/settings.json`](#the-frameworks-own-claudesettingsjson)
  - [Project-root coverage in the sandbox allowlists](#project-root-coverage-in-the-sandbox-allowlists)
    - [Why project-local, not user-scope and not committed-project](#why-project-local-not-user-scope-and-not-committed-project)
    - [Security rationale — why project-local is safe to write to](#security-rationale--why-project-local-is-safe-to-write-to)
    - [`sandbox-add-project-root.sh`](#sandbox-add-project-rootsh)
    - [When the helper runs](#when-the-helper-runs)
    - [Per-project vs whole-user scope](#per-project-vs-whole-user-scope)
  - [The clean-env wrapper](#the-clean-env-wrapper)
    - [Automatic sandbox allow-paths](#automatic-sandbox-allow-paths)
  - [Sandbox-bypass visibility hook](#sandbox-bypass-visibility-hook)
    - [Why install it user-scope, not project-scope](#why-install-it-user-scope-not-project-scope)
    - [Install (user-scope)](#install-user-scope)
    - [Verify](#verify)
    - [Trade-offs](#trade-offs)
  - [Agent-guard deterministic guard hook](#agent-guard-deterministic-guard-hook)
    - [Extensible — any skill can contribute a guard](#extensible--any-skill-can-contribute-a-guard)
    - [Install (user-scope)](#install-user-scope-1)
    - [Verify](#verify-1)
  - [Sandbox-error hint hook](#sandbox-error-hint-hook)
    - [Why install it](#why-install-it)
    - [Why install it user-scope, not project-scope](#why-install-it-user-scope-not-project-scope-1)
    - [Install (user-scope)](#install-user-scope-2)
    - [Verify](#verify-2)
    - [Trade-offs](#trade-offs-1)
  - [Sandbox-state status line](#sandbox-state-status-line)
  - [Waiting-for-input terminal tint](#waiting-for-input-terminal-tint)
  - [Syncing user-scope config across machines](#syncing-user-scope-config-across-machines)
    - [What to track, what not to track](#what-to-track-what-not-to-track)
    - [Layout](#layout)
    - [Setting up a fresh host](#setting-up-a-fresh-host)
    - [A minimal `sync.sh`](#a-minimal-syncsh)
    - [Extending `sync.sh`: share project memory across machines](#extending-syncsh-share-project-memory-across-machines)
    - [Extending `sync.sh`: expose tracked scripts on `$PATH`](#extending-syncsh-expose-tracked-scripts-on-path)
    - [Why a *private* repo](#why-a-private-repo)
  - [Adopter setup](#adopter-setup)
    - [Direct manual install](#direct-manual-install)
    - [Via a Claude Code prompt](#via-a-claude-code-prompt)
  - [Verification](#verification)
    - [Direct Bash verification](#direct-bash-verification)
    - [Via a Claude Code prompt](#via-a-claude-code-prompt-1)
  - [Keeping the setup updated](#keeping-the-setup-updated)
    - [Direct steps](#direct-steps)
    - [Via a Claude Code prompt](#via-a-claude-code-prompt-2)
  - [What a session looks like](#what-a-session-looks-like)
  - [See also](#see-also)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Secure agent setup

**Audience: adopters.** This document walks through every install
step for the secure agent setup — pinned tool versions, the
framework's `.claude/settings.json`, the `claude-iso` clean-env
wrapper, the sandbox-bypass-warn hook, the sandbox-state status
line, multi-host syncing, the agent-guided install / verify /
keep-updated prompts, and the five session screenshots that show
what a working setup looks like in action. Read this end-to-end
and you will have the secure setup running.

**Why** this setup is shaped the way it is — the threat model it
addresses, how the three layers fit together, what bubblewrap /
Seatbelt actually do at the OS layer, where the residual blind
spots are — lives in the companion document
[`secure-agent-internals.md`](secure-agent-internals.md). It is
optional reading for adopters; required reading for anyone
modifying the setup or debugging an unexpected denial.

The framework's tracker repo and `<security-list>` thread content are
**pre-disclosure CVE material**. A default agent session with
unfettered access to `~/`, all environment variables, and a
permissive network egress can — by accident or via a prompt-injection
attack hidden in an inbound report — exfiltrate cloud credentials,
SSH keys, GitHub tokens, the Gmail OAuth refresh token, and similar
host-level secrets. This setup does not eliminate that risk; it
reduces it to the project tree.

## Quick start

If you just want the secure setup running, follow this short
path. The rest of the document below expands every bullet here
with the *why* and the trade-offs; you can return to it whenever
you want the full picture. For the rationale and mechanism behind
each layer, see
[`secure-agent-internals.md`](secure-agent-internals.md).

### Agent-guided (recommended)

If you have Claude Code installed and a clone of `magpie`
on the host, the framework ships six skills that walk every
step interactively. Each surfaces sudo / shell-rc / settings-file
changes for explicit approval before applying — nothing
privilege-elevating runs without you saying so.

```text
1. Open Claude Code in your tracker repo (or any directory).
2. If you consume the framework as a gitignored snapshot managed
   by `setup` (the canonical adopter pattern), run
   `/magpie-setup verify` to confirm the snapshot at
   `.apache-magpie/`, the committed `.apache-magpie.lock`, and
   the project-config files are wired correctly. Read-only —
   surfaces gaps, never auto-fixes.
3. Run /magpie-setup-isolated-setup-install — guided first-time install of
   the secure-agent setup (sandbox, hooks, status line,
   clean-env wrapper).
4. Run /magpie-setup-isolated-setup-verify — confirms ✓/✗/⚠ for every piece
   of the secure-agent setup.
5. When you want to be on the framework's latest, run
   `/magpie-setup upgrade` — pulls your local magpie
   checkout to origin/main with --ff-only, refuses to touch a
   dirty working tree, surfaces what arrived. Then run
   /magpie-setup-isolated-setup-update to surface user-side drift the
   upgrade introduced (new permissions.deny entries,
   user-scope script copies older than the framework, pinned
   tool bumps that warrant a host install).
6. Optional: if you maintain a private dotfile-style sync repo
   per
   [Syncing user-scope config across machines](#syncing-user-scope-config-across-machines),
   run /magpie-setup-shared-config-sync to push local edits to the remote
   so other machines pick them up.
```

The skills are at
[`.claude/skills/magpie-setup/verify.md`](../../skills/setup/verify.md),
[`.claude/skills/setup-isolated-setup-install/`](../../skills/setup-isolated-setup-install/SKILL.md),
[`.claude/skills/setup-isolated-setup-verify/`](../../skills/setup-isolated-setup-verify/SKILL.md),
[`.claude/skills/magpie-setup/upgrade.md`](../../skills/setup/upgrade.md),
[`.claude/skills/setup-isolated-setup-update/`](../../skills/setup-isolated-setup-update/SKILL.md),
[`.claude/skills/setup-shared-config-sync/`](../../skills/setup-shared-config-sync/SKILL.md).
Each skill references back into the canonical sections of this
document rather than duplicating them, so anything the skill walks
you through has a longer-form section here you can read for
context.

### Manual (if you do not want the agent-guided path)

The same flow, condensed to commands you run yourself:

```bash
# 1. Pinned system tools (Linux only — macOS uses built-in
#    Seatbelt). Exact distro commands and version pins are in
#    `tools/agent-isolation/pinned-versions.toml`; canonical
#    section: "Required tools (pinned versions)" below.
sudo apt-get install --no-install-recommends \
    bubblewrap=0.11.2-* socat=1.8.1.3-*
npm install -g --no-save @anthropic-ai/claude-code@2.1.202

# 2. Project-scope `.claude/settings.json`. Copy the framework's
#    sandbox / permissions.deny / permissions.ask / allowedDomains
#    blocks into your tracker repo's `.claude/settings.json`.
#    Section: "The framework's own .claude/settings.json" below.

# 3. The clean-env wrapper. Source `agent-iso.sh` from your rc
#    file, optionally alias `claude=claude-iso`. Section: "The
#    clean-env wrapper" below.

# 4. User-scope hooks. Copy `sandbox-bypass-warn.sh`,
#    `sandbox-error-hint.sh`, and `sandbox-status-line.sh` into
#    `~/.claude/scripts/`, wire them into `~/.claude/settings.json`
#    under `PreToolUse`, `PostToolUse`, and `statusLine`.
#    Sections: "Sandbox-bypass visibility hook",
#    "Sandbox-error hint hook", and "Sandbox-state status line"
#    below.

# 5. Verify the install actually denies what it claims to —
#    section "Verification" below has both a three-line Bash
#    check and the agent-guided form.
```

Both paths converge on the same end state: a sandboxed Claude Code
session that cannot read `~/.aws/`, cannot exfiltrate via `curl`,
runs Bash subprocesses inside bubblewrap (Linux) or Seatbelt
(macOS), and visibly flags `sandbox` / `NO SANDBOX` / bypass
attempts in the terminal so an unprotected session cannot drift
unnoticed.

The rest of this document is the long-form reference behind each
of those steps. If you used the agent-guided path, you can read
sections on demand when a skill points you at one for more
detail.

## Required tools (pinned versions)

Every system-level tool the secure setup depends on is pinned with a
**per-tool cooldown** before the framework adopts a new upstream
release — same convention as the `[tool.uv] exclude-newer = "7 days"`
setting in [`pyproject.toml`](../../pyproject.toml) and the weekly Dependabot
updates in [`.github/dependabot.yml`](../../.github/dependabot.yml).
Default cooldown is 7 days; individual tools can override via
`cooldown_days = N` in the manifest when their release stream
warrants it. `claude-code` is the canonical override at 1 day —
its release cadence is high enough that a longer floor would
strand the framework many versions behind upstream, and any
regression that affects the secure setup's permission-rule
semantics or sandbox flags is caught broadly within hours of
release.

The current pins live in machine-readable form in
[`tools/agent-isolation/pinned-versions.toml`](../../tools/agent-isolation/pinned-versions.toml):

| Tool | Pinned version | Released | Cooldown | Purpose |
|---|---|---|---|---|
| `bubblewrap` | 0.11.2 | 2026-04-23 | 7d (default) | Linux user-namespace sandbox (filesystem layer). Required on Linux; macOS uses Seatbelt instead. |
| `socat` | 1.8.1.3 | 2026-06-26 | 7d (default) | TCP relay for the sandbox network allowlist. Linux only. |
| `claude-code` | 2.1.202 | 2026-07-06 | 1d (override) | Agent runtime. Pin separately from any system claude install so behavioural changes don't drift the framework's effective security posture without review. |

The pin date floor (`pinned_at` in the manifest) is the day the
manifest was last touched; it is the framework's promise that every
version above had at least its tool's cooldown to settle before
being adopted.

### Install commands

The exact commands are also in `pinned-versions.toml` under each
tool's `install.<distro>` field; below is the one-line view per
distro. Choose whichever applies to your host.

**Debian / Ubuntu (apt)**:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends \
    bubblewrap=0.11.2-* \
    socat=1.8.1.3-*
```

> **Debian stable (bookworm) caveat.** The pinned `bubblewrap 0.11.2`
> is not available on Debian bookworm — bookworm ships an older
> `bubblewrap`, and an adopter reported the `0.11.x` line not working
> there. `0.11.x` ships in **Debian trixie**, so the supported path is
> to run the secure setup on **trixie** (or newer). If you must stay on
> bookworm, install the older distro `bubblewrap` and accept the same
> LTS trade-off documented in the Ubuntu Noble shortcut below — the
> sandbox flags don't depend on a specific bubblewrap version (the
> `denyRead`/`allowRead` API has been stable since `0.6.x`).

**Fedora / RHEL (dnf)**:

```bash
sudo dnf install \
    bubblewrap-0.11.2 \
    socat-1.8.1.3
```

**macOS**: bubblewrap is not needed (Seatbelt is built in); socat is
optional. If you want socat, `brew install socat` (current Homebrew
version, no pin enforced — Homebrew rolls forward, so the
"7-day cooldown" promise is best-effort here).

**Claude Code**:

```bash
# npm distribution (the only stable channel today)
npm install -g --no-save @anthropic-ai/claude-code@2.1.202
```

### Distro-specific shortcut — Linux Mint 22.x / Ubuntu 24.04 Noble

The pinned versions above (bubblewrap `0.11.2`, socat `1.8.1.3`) are
the *upstream* releases that have aged past the framework's 7-day
cooldown. **They are not in Ubuntu Noble's main repos** — Noble
ships `bubblewrap 0.9.0` (`0.9.0-1ubuntu0.1`) and
`socat 1.8.0.0` (`1.8.0.0-4build3`).

Both Noble-shipped versions pre-date the framework's pins by months
and are well past the 7-day cooldown, so they're a legitimate
adopter choice on Mint 22.x / Ubuntu 24.04. The trade-off is the
usual LTS one: older feature set, but no source build required,
and security backports flow through Ubuntu's standard update
channel.

If you accept the trade-off, install via apt:

```bash
sudo apt-get update
sudo apt-get install --no-install-recommends \
    bubblewrap=0.9.0-1ubuntu0.1 \
    socat=1.8.0.0-4build3
```

The framework's `.claude/settings.json` works unchanged — the
sandbox flags don't depend on a specific bubblewrap version (the
`denyRead`/`allowRead` API has been stable since `0.6.x`).

The framework's `tools/agent-isolation/check-tool-updates.sh` will
still report upstream `0.11.2` / `1.8.1.3` as the pinned versions —
that's the manifest's view of what's *upstream-current*, not what
your distro shipped. If you want to silence the drift, override the
manifest locally with a `pinned-versions.local.toml` (gitignored)
declaring the Noble versions; the script's manifest-precedence
follows the same `*.local` convention as Claude Code's
`settings.local.json`.

> **Why this is documented as a separate "shortcut" rather than
> the canonical path.** The framework's default pin tracks the
> upstream release stream, not any specific distro. Adopters on
> distros that ship recent versions (Arch, Fedora rolling, NixOS
> on `nixos-unstable`) can install the upstream-pinned versions
> directly from their package manager. Adopters on LTS distros
> like Mint / Ubuntu Noble use this shortcut. The two paths
> converge — once Noble's next LTS adopts a newer bubblewrap, this
> section retires.

### Bumping a pinned version

When an upstream release has aged past the tool's cooldown (7-day
default, 1-day for `claude-code` per its manifest override) and
you want to adopt it:

1. Run `tools/agent-isolation/check-tool-updates.sh`. It compares the
   pinned versions to upstream and prints an "upgrade candidate" line
   for any tool whose latest aged-past-cooldown release is newer than
   the pin.
2. Read the upstream release-notes / CHANGELOG for the tool. Don't
   bump on a "performance improvements" entry — wait for a feature
   you actually want or a security fix.
3. Edit `tools/agent-isolation/pinned-versions.toml`: update the
   tool's `version` and `released` fields, then update the top-level
   `pinned_at` field to today's date.
4. Update the install commands in this document if the distro
   package version string has shifted.
5. Open the bump as its own PR with a one-paragraph rationale.

The check script is idempotent and side-effect-free — it never edits
the manifest, never installs anything, never opens a PR.

### Wiring the check script into a weekly routine

The framework's `/schedule` slash-command lets you wire the check
script into a recurring agent without leaving Claude Code:

```text
/schedule weekly run tools/agent-isolation/check-tool-updates.sh
                  and surface upgrade candidates
```

The scheduled agent runs in the same secure setup the rest of the
framework uses, so it has no special access to install the upgrade
itself — the surfaced candidates are a *proposal*, and the framework
maintainer's deliberate confirmation (per step 5 above) is what
actually lands the bump.

## The framework's own `.claude/settings.json`

The framework dogfoods the secure config in
[`.claude/settings.json`](../../.claude/settings.json). The full block is
below, annotated.

```jsonc
{
  "sandbox": {
    "enabled": true,
    // `excludedCommands` runs the listed commands OUTSIDE the sandbox.
    // `gh` authenticates via the OS keyring (and `~/.config/gh`), which the
    // sandbox blocks — so a sandboxed `gh` fails with a keyring / "not
    // logged in" error. Excluding it lets `gh` use the real host auth. Its
    // write / destructive subcommands are still gated by the
    // `permissions.ask` rules below, and `gh auth token` / `gh auth refresh`
    // stay in `permissions.deny` so the token can never be dumped. This is
    // what makes the "`gh` is sandbox-bypassed" note under `credentials`
    // below actually hold.
    "excludedCommands": ["gh *"],
    // The `lychee` link-check hook runs in OFFLINE mode (`offline =
    // true` in `.lychee.toml`): it validates only local cross-file and
    // anchor references and never fetches remote URLs, so it makes no
    // network calls and needs no in-sandbox TLS at runtime. This
    // sidesteps a macOS-26 issue where the sandbox's CONNECT proxy is
    // incompatible with SecureTransport (the `native-tls` stack the
    // cargo/brew lychee links): online link checks fail every external
    // URL with `OSStatus -26276` even though the certs are valid and
    // `enableWeakerNetworkIsolation` is set. Building lychee still
    // needs the rust toolchain (see the `~/.rustup`/`~/.cargo` +
    // `*.crates.io`/`static.rust-lang.org` entries below); only its
    // *runtime* network use is eliminated.
    "filesystem": {
      "denyRead": ["~/"],          // default-deny the entire home dir for Bash subprocesses
      "allowRead": [
        ".",                          // the project tree (cwd)
        "~/.gitconfig",               // git's user.name / user.email
        "~/.config/git/",             // git's per-host config
        "~/.config/gh/",              // gh CLI auth (token in hosts.yml)
        "~/.cache/",                  // dev tool caches (uv HTTP cache, prek logs, ruff/mypy caches)
        "~/.local/share/uv/",         // uv's tool venvs (prek, etc.)
        "~/.rustup/",                 // rustup toolchains (the `lychee` rust hook builds against them)
        "~/.cargo/",                  // cargo registry + the lychee binary the rust hook installs
        "~/.local/bin/",              // uv-installed tool entry points
        "~/.config/apache-magpie/",  // Gmail OAuth refresh token (oauth-draft tool)
        "~/.gnupg/",                  // gpg keys (commit signing)
        "/run/user/*/gnupg/"          // gpg-agent socket dir (ssh-via-gpg-agent commit signing)
      ],
      "allowWrite": [
        "~/.cache/",                  // uv lock files, prek log + state, ruff/mypy caches
        "~/.local/share/uv/",         // uv's tool venvs (prek installs new hook envs here)
        "~/.rustup/",                 // rustup writes settings.toml + downloaded toolchains (first run of the `lychee` rust hook)
        "~/.cargo/"                   // cargo registry cache + the compiled lychee binary
      ]
    },
    "network": {
      "allowedDomains": [          // every host the framework legitimately reaches
        "github.com", "api.github.com", "raw.githubusercontent.com",
        "objects.githubusercontent.com", "codeload.github.com", "uploads.github.com",
        "pypi.org", "files.pythonhosted.org",
        "lists.apache.org", "dist.apache.org", "downloads.apache.org", "archive.apache.org",
        "cveprocess.apache.org", "cve.org", "www.cve.org", "cveawg.mitre.org",
        "oauth2.googleapis.com", "gmail.googleapis.com",
        // `*.crates.io` + `static.rust-lang.org` let the `lychee` rust
        // hook bootstrap a rustup toolchain and `cargo install` lychee
        // on first run (rustup downloads the toolchain from
        // static.rust-lang.org; crate deps come from crates.io). These
        // are the ONLY hosts lychee needs: it runs offline (see
        // `.lychee.toml`), so it never fetches the external URLs the
        // docs link to — the wildcard link-target hosts that used to
        // live here (`*.apache.org`, `*.nist.gov`, `lychee.cli.rs`, …)
        // were removed when the hook went offline.
        "*.crates.io", "static.rust-lang.org"
      ],
      // Lets native-TLS CLI tools (lychee — and, per the schema, gh /
      // gcloud / terraform) verify TLS through the sandbox's
      // TLS-terminating proxy; without it lychee fails every external
      // link with `failed to verify TLS certificate`. Documented
      // trade-off: "reduces security — opens a potential
      // data-exfiltration vector through the trustd service." No-op
      // outside the sandbox (e.g. CI). macOS-only.
      "enableWeakerNetworkIsolation": true
    },
    // `sandbox.credentials` (claude-code 2.1.187+) is the only layer
    // that protects secret ENVIRONMENT VARIABLES — `denyRead` and the
    // `permissions.deny[Read(...)]` rules are filesystem-only and do
    // NOT stop a sandboxed command from reading `$ANTHROPIC_API_KEY`
    // or dumping `env`. `mode: "deny"` unsets the var for sandboxed
    // commands only; the unsandboxed agent process keeps its own auth,
    // and sandbox-bypassed commands (e.g. `gh`, which reads
    // ~/.config/gh) are unaffected. Credential FILES are already
    // covered by `denyRead: ["~/"]`, so only `envVars` is listed here.
    // (`mode: "mask"` + `injectHosts` is the alternative: keep the var
    // usable only for connections to named hosts — not needed here.)
    "credentials": {
      "envVars": [
        { "name": "ANTHROPIC_API_KEY", "mode": "deny" },
        { "name": "ANTHROPIC_AUTH_TOKEN", "mode": "deny" },
        { "name": "CLAUDE_CODE_OAUTH_TOKEN", "mode": "deny" },
        { "name": "GH_TOKEN", "mode": "deny" },
        { "name": "GITHUB_TOKEN", "mode": "deny" },
        { "name": "AWS_ACCESS_KEY_ID", "mode": "deny" },
        { "name": "AWS_SECRET_ACCESS_KEY", "mode": "deny" },
        { "name": "AWS_SESSION_TOKEN", "mode": "deny" },
        { "name": "NPM_TOKEN", "mode": "deny" },
        { "name": "TWINE_PASSWORD", "mode": "deny" }
      ]
    }
  },
  "permissions": {
    "allow": [
      "Bash(gh api graphql *)",                 // read-only GraphQL fetches (PR-triage paginated loop). MORE SPECIFIC than the `gh *` ask below, so it — and the read-only rules that follow — run WITHOUT a prompt. GraphQL mutations slip through; accepted, since the skills route mutations through REST, not graphql.
      // Read-only gh, allow-listed so they don't trip the `gh *` ask below.
      // Anything NOT listed here — every write/destructive gh, and REST `gh
      // api` (GET included) — falls through to `gh *` and prompts.
      "Bash(gh pr view *)", "Bash(gh pr list *)", "Bash(gh pr diff *)", "Bash(gh pr checks *)",
      "Bash(gh issue view *)", "Bash(gh issue list *)",
      "Bash(gh repo view *)", "Bash(gh repo list *)",
      "Bash(gh run view *)", "Bash(gh run list *)", "Bash(gh run watch *)",
      "Bash(gh workflow view *)", "Bash(gh workflow list *)",
      "Bash(gh release view *)", "Bash(gh release list *)",
      "Bash(gh label list *)", "Bash(gh cache list *)",
      "Bash(gh search *)", "Bash(gh browse *)", "Bash(gh auth status*)"
    ],
    "deny": [
      "Read(~/.aws/**)", "Read(~/.ssh/**)", "Read(~/.netrc)",
      "Read(~/.docker/**)", "Read(~/.kube/**)",
      "Read(~/.config/gh/**)",                  // bash can read it (sandbox.allowRead); the AGENT can't
      "Read(~/.config/apache-magpie/**)",      // same — Bash via oauth-draft tool, not the agent directly
      "Read(~/.config/gcloud/**)", "Read(~/.azure/**)",
      "Read(//**/.env)", "Read(//**/.env.local)", "Read(//**/.env.*.local)",
      "Bash(curl *)", "Bash(wget *)",           // network egress via Bash bypasses the sandbox proxy
      "Bash(aws *)", "Bash(gcloud *)", "Bash(az *)", "Bash(kubectl *)",
      "Bash(docker login *)", "Bash(npm publish *)",
      "Bash(pip install --upgrade *)", "Bash(uv self update *)",
      "Bash(gh auth token*)", "Bash(gh auth refresh*)"  // gh runs unsandboxed (excludedCommands), so deny the two subcommands that would print/rotate the token
    ],
    "ask": [
      "Bash(git push *)",                        // including --force / --force-with-lease variants
      "Bash(gh *)"                               // safe-by-default: EVERY gh command prompts unless it matches a more-specific read-only allow rule above. Guarantees every destructive / unknown gh subcommand (gh pr close, gh run delete, gh label delete, gh repo archive, gh variable set, gh project item-delete, …) is confirmed. `gh auth token`/`refresh` are denied above (deny > ask).
    ]
  }
}
```

The deny / allow split for `~/.config/gh/` and
`~/.config/apache-magpie/` is deliberate: bash subprocesses (the `gh`
CLI, `oauth-draft-create`) need to *use* the credential, but the
agent should never *see* it. `sandbox.filesystem.allowRead` permits
the bash subprocess to read the file; `permissions.deny[Read(...)]`
blocks the agent's Read tool from reading the same path.

**OpenCode parity.** OpenCode has no per-command sandbox exclusion — its
isolation is the OS-level sandbox of the [clean-env wrapper](#the-clean-env-wrapper),
which already runs `gh` with the host keyring, so there is no `excludedCommands`
equivalent to add. The "always confirm" half carries over via OpenCode's own
policy: `sandbox-lint --opencode` requires `permission.bash` to default to
`ask`/`deny` (never a blanket `allow`), so `gh` write subcommands prompt there
by default. No `opencode.json` change is needed to match the Claude config.

## Project-root coverage in the sandbox allowlists

The `.` entry in `sandbox.filesystem.allowRead` is **intended** to
mean "the session's current working directory, resolved at
access-time" — exactly the same semantics `allowWrite: ["."]` has.
In practice the two sides diverge in the harness: `allowWrite`
keeps `.` literal (resolved per access), while `allowRead`
pre-resolves the path list at session start to absolute paths *and
silently drops the literal `.`*. The consequence is that a session
in a freshly-cloned adopter repo can **write** to CWD but cannot
**read** from it under the sandbox — `git rev-parse --git-dir`
fails with `Operation not permitted`, and `Read`-tool reads of
files like `.apache-magpie.lock` fail too. The full reproducer
and harness-side analysis is in
[issue #197](https://github.com/apache/magpie/issues/197).

The framework's defensive fix is to add the project root as an
**explicit absolute path** to both `sandbox.filesystem.allowRead`
and `sandbox.filesystem.allowWrite` in the adopter's **project-local**
settings file — `<repo>/.claude/settings.local.json`. The `.`
entry stays in the committed project-scope `settings.json` — the
explicit absolute path in `settings.local.json` is belt-and-braces:

- If the harness ever stops resolving `.` consistently, the
  explicit absolute path still covers the project.
- If `.` works correctly, the explicit entry is redundant but
  harmless.

### Why project-local, not user-scope and not committed-project

Three scopes the harness merges, top to bottom:

| Scope | File | Shared by | Suitable for the fix? |
|---|---|---|---|
| User | `~/.claude/settings.json` | every session on the host (every adopter project, every tool) | **No** — pollutes user-scope with every adopter project's abs path. |
| Project (committed) | `<repo>/.claude/settings.json` | every contributor on the project | **No** — machine-specific abs paths would leak into the repo. |
| Project (local, gitignored) | `<repo>/.claude/settings.local.json` | this machine, this checkout only | **Yes** — per-machine, per-project, never committed. |

Worktrees handle themselves: each worktree has its own working
tree (and so its own `.claude/` directory and its own
`.claude/settings.local.json`). The helper writes each worktree's
absolute path into **that worktree's own** settings.local.json,
not into a shared file. When a session starts in worktree A, the
harness reads worktree A's settings.local.json and sees the
explicit allow for worktree A's root — nothing more.

The committed project-scope `settings.json` is **never** modified
by the helper; the user-scope `settings.json` and
`settings.local.json` are likewise never touched.

### Security rationale — why project-local is safe to write to

A reasonable question: *"the helper writes a config file that
governs the sandbox itself. If the sandbox grants write access to
the project tree, can a compromised agent rewrite that file and
broaden the sandbox for the next session?"* The answer is no, but
only because the protection comes from **Claude Code's built-in
sandbox denylist**, not from anything the framework can configure.
Walking the threat model:

**1. Bash writes from inside the sandbox: blocked by the harness.**
Claude Code's sandbox resolves the user's
`sandbox.filesystem.allowWrite` against a hardcoded
`denyWithinAllow` set that always includes
`<repo>/.claude/settings.json`,
`<repo>/.claude/settings.local.json`,
`<repo>/.claude/skills/`, and the user-scope settings files. This
is enforced at the bubblewrap (Linux) / Seatbelt (macOS) syscall
level — the write fails with `Operation not permitted` regardless
of what `allowWrite` says. Verify empirically with a single line:

```bash
echo "test" >> .claude/settings.local.json
# zsh: operation not permitted: .claude/settings.local.json
```

There is no settings.json field that overrides this protection
(no `denyWrite` user-config exists at the time of writing); the
harness owns it. So a sandboxed Bash invocation, even one running
attacker-chosen code, cannot mutate `.claude/settings.local.json`
to broaden the next session's sandbox.

**2. Edit / Write / MultiEdit agent tools bypass the sandbox.**
These tools call into the harness directly, not through a Bash
subprocess, so the sandbox's `denyWithinAllow` does not apply. The
framework closes the bypass by adding the per-tool denies in the
committed `.claude/settings.json`:

```jsonc
"deny": [
  "Edit(.claude/settings.json)",
  "Edit(.claude/settings.local.json)",
  "Write(.claude/settings.json)",
  "Write(.claude/settings.local.json)",
  "MultiEdit(.claude/settings.json)",
  "MultiEdit(.claude/settings.local.json)"
]
```

A compromised agent that tries `Edit('.claude/settings.local.json', ...)`
hits the deny rule and the call fails. The denies are committed at
project scope, so every contributor inherits them; an adopter who
follows the framework's settings template gets them automatically.

**3. The framework's own helper also gets blocked from inside the sandbox.**
The same `denyWithinAllow` that defends against attack also blocks
[`sandbox-add-project-root.sh`](../../tools/agent-isolation/sandbox-add-project-root.sh)
when it is invoked through the agent's `Bash` tool from inside a
sandboxed session. Three legitimate-write paths remain, all
auditable:

- **User-terminal post-checkout hook.** `git worktree add` /
  `git checkout` fired from the operator's shell triggers
  `post-checkout`, which runs the helper in the *shell's* context —
  outside the agent sandbox. Writes succeed normally.
- **First-time install.** `setup-isolated-setup-install` is
  typically run with the operator's awareness; its Step P
  invocation of the helper happens in a context where the operator
  is already approving setup actions.
- **`dangerouslyDisableSandbox: true` from agent sessions.**
  `/magpie-setup adopt`, `upgrade`, and `worktree-init` invoke the
  helper with explicit sandbox bypass. Every bypass triggers
  [`sandbox-bypass-warn.sh`](../../tools/agent-isolation/sandbox-bypass-warn.sh)'s
  bold-red banner naming the command, the reason, and the file
  being touched; the operator approves per call. No silent writes.

**4. No vector via commits.**
`<repo>/.claude/settings.local.json` is gitignored — the adopt
flow adds the line to `.gitignore`, and
[`/magpie-setup verify`](../../skills/setup/verify.md)
Check 4 surfaces ✗ if it is missing. The helper itself runs
`git check-ignore` against the target file before writing and
*refuses* to write when the file is not ignored (defense in depth
against a stale `.gitignore`). A malicious contributor cannot ship
sandbox-allowlist content via a PR.

**5. No vector via the helper's inputs.**
The helper takes paths exclusively from
`git rev-parse --show-toplevel` and
`git worktree list --porcelain` — both walk the operator's own
local git state. The only paths added are working directories the
operator has already created themselves with `git clone` /
`git worktree add`. No command-line path argument; no
environment-variable injection.

**6. Cross-project isolation, as a bonus.**
A session in project A reads
`<A>/.claude/settings.local.json` and gets read+write access only
to A. A session that `cd`s into project B mid-session keeps A's
settings (loaded at session start), so it sees A's grants — never
B's. The same fix at user-scope (`~/.claude/settings.json`) would
have given every Claude Code session on the host read+write access
to every adopter project the operator has ever set up; project-local
scope confines the grant.

**Net:** every write path to the file is either physically blocked
or requires explicit per-call user approval. The harness's built-in
sandbox protection is what makes this true — the framework cannot
configure it, but it can verify and document it.

### `sandbox-add-project-root.sh`

The framework ships
[`tools/agent-isolation/sandbox-add-project-root.sh`](../../tools/agent-isolation/sandbox-add-project-root.sh)
to perform this addition idempotently. Installed during
[`setup-isolated-setup-install`](../../skills/setup-isolated-setup-install/SKILL.md)
into `~/.claude/scripts/sandbox-add-project-root.sh` (the
*script file* lives user-scope so a single install covers every
adopter project on the host; what it *writes* is project-local).
The helper:

- Resolves `git rev-parse --show-toplevel` in the current working
  directory.
- With `--all-worktrees`, also enumerates
  `git worktree list --porcelain` and writes a separate entry
  into **each worktree's** own `.claude/settings.local.json`.
- Without the flag, writes only the current worktree's path
  into the current worktree's `.claude/settings.local.json`.
- Creates `.claude/settings.local.json` from scratch if missing
  (with only the `sandbox.filesystem` block — nothing else is
  touched).
- Updates the file in place, atomically (`jq` → tmp → `mv`).
- Skips any path already present in either array (idempotent).
- Tolerant of missing prerequisites (no `jq`, not in a git repo,
  invalid existing JSON) — warns on stderr and exits 0 so the
  calling hook is never derailed by a half-installed setup.

### When the helper runs

The helper is invoked from four points in the framework's lifecycle:

1. **At install** — `setup-isolated-setup-install` runs the
   helper with `--all-worktrees` against the adopter repo the
   operator is sitting in.
2. **During adoption** — `/magpie-setup adopt` Step 12 runs the
   helper with `--all-worktrees` so a fresh adopter repo with
   pre-existing worktrees has every working-tree path covered
   without an extra round-trip through
   `setup-isolated-setup-install`.
3. **During upgrade** — `/magpie-setup upgrade` Step 6c, after
   the per-worktree `worktree-init` chain, runs the helper with
   `--all-worktrees` so any worktree added since adopt has its
   path written into its own settings.local.json.
4. **Per worktree, on creation** — the `post-checkout` git hook
   installed by `/magpie-setup adopt` runs the helper *without*
   `--all-worktrees`, picking up only the new worktree's path.
   `git worktree add` fires `post-checkout` in the new working
   tree, so every worktree added after adoption inherits sandbox
   access automatically — landing its abs path in its own
   `.claude/settings.local.json`.

The verification surface:

- [`setup-isolated-setup-verify`](../../skills/setup-isolated-setup-verify/SKILL.md)
  Check 8 — live sandboxed read+write probe of the project root,
  plus the static cross-check that the abs path is in the current
  worktree's `.claude/settings.local.json`.
- [`/magpie-setup verify`](../../skills/setup/verify.md)
  Check 8b — static cross-check that the current worktree's
  abs path is in its own `.claude/settings.local.json`.

### Per-project vs whole-user scope

[`setup-isolated-setup-install`](../../skills/setup-isolated-setup-install/SKILL.md)
offers two scopes for the project-root sandbox-allowlist setup.
The operator picks one during install; both are reversible.

| Scope | What it covers | Mechanism | Reversal |
|---|---|---|---|
| **Per-project** (default) | The single adopter repo the operator is sitting in when running the install skill. Each subsequent adopter project needs the install skill re-run there. | The helper runs once with `--all-worktrees` against the current repo; nothing global is touched. The per-repo `post-checkout` hook (installed by `/magpie-setup adopt` in Magpie-adopted repos) chains into the helper on future `git checkout` operations within that repo. | None needed — per-project scope is inert outside the configured repos. |
| **Whole-user** | Every git repo on the operator's host, existing and future. Includes non-Magpie Claude-Code-aware projects (any project with a `.claude/` directory). | Walks the operator's existing checkouts under prompted root dirs and writes each one's `settings.local.json`; sets `git config --global core.hooksPath ~/.claude/git-hooks/` and installs the universal [`git-global-post-checkout.sh`](../../tools/agent-isolation/git-global-post-checkout.sh) there. | `git config --global --unset core.hooksPath` restores per-repo hook lookup. The populated `settings.local.json` files stay (they are harmless if the operator no longer wants them, and gitignored so they cause no commit noise). |

#### Important trade-off — `core.hooksPath` shadows per-repo hooks

When `core.hooksPath` is set globally, git looks up hooks **only**
in that directory for every repo on the host. Every per-repo
`<repo>/.git/hooks/*` becomes inert across the host. If the
operator has hooks they care about (pre-commit formatters,
commit-msg linters, pre-push gates, project-specific
post-checkout actions), those will no longer fire after whole-user
scope is set, unless the operator migrates them into
`~/.claude/git-hooks/`.

The framework installs **only** the `post-checkout` hook in the
shared dir. Pre-commit / commit-msg / pre-push / other hook types
need their own files in the shared dir if the operator wants
them to fire. This is a deliberate trade-off: a single mechanism
for whole-user coverage at the cost of needing to migrate
per-repo hooks.

The install skill surfaces this trade-off loudly before setting
`core.hooksPath` and requires explicit operator acknowledgement.
See
[`setup-isolated-setup-install` Step P.0a](../../skills/setup-isolated-setup-install/SKILL.md#step-p0a--loud-disclosure-before-setting-whole-user-scope).

#### When to pick which scope

- **Pick per-project** when:
  - You adopt one or two projects on this host and prefer not to
    touch global git config.
  - You have per-repo hooks (pre-commit, commit-msg, etc.) you
    rely on and do not want shadowed.
  - You are evaluating Magpie and have not yet decided
    whether to commit to the framework.

- **Pick whole-user** when:
  - You adopt many Claude-Code-aware projects and do not want to
    re-run the install skill in each.
  - You add worktrees frequently and want each one's
    `settings.local.json` auto-populated without per-worktree
    action.
  - You do not rely on per-repo hooks (or are prepared to migrate
    them into the shared dir).
  - You sync `~/.claude/` across machines via the private dotfile
    repo (the global config + hook propagates with the sync).

Switching scopes later is non-destructive: the install skill is
idempotent. Re-running it with a different scope is the supported
upgrade path. The walking pass under whole-user scope is also a
one-time bulk operation — once existing checkouts are populated,
the global `post-checkout` keeps everything aligned going forward.

## The clean-env wrapper

Layer 0 — strip credential-shaped env vars from the parent shell
before invoking `claude` — is implemented by
[`tools/agent-isolation/agent-iso.sh`](../../tools/agent-isolation/agent-iso.sh).

There are two valid ways to make `claude-iso` available on your
shell. Pick whichever matches how you use Claude Code; the wrapper
behaviour is identical either way.

**Per-repo install** — source the script directly from the
framework checkout. Simplest, always tracks the wrapper version in
the repo (so a `git pull` of the framework updates the wrapper),
but only works on hosts where the framework path resolves.

```bash
# ~/.bashrc or ~/.zshrc
source /path/to/magpie/tools/agent-isolation/agent-iso.sh
```

**Global (user-scope) install** — copy the script into
`~/.claude/agent-isolation/` and source from there. Survives
branch / worktree / repo-path changes, travels with the rest of
`~/.claude/` when you sync dotfiles between machines, and works
regardless of whether the framework repo happens to be checked
out on a given host.

```bash
# one-time install (re-run to pick up an upstream wrapper change)
mkdir -p ~/.claude/agent-isolation
cp /path/to/magpie/tools/agent-isolation/agent-iso.sh \
    ~/.claude/agent-isolation/agent-iso.sh

# ~/.bashrc or ~/.zshrc — guarded so it's a no-op until the file exists
[ -f "$HOME/.claude/agent-isolation/agent-iso.sh" ] \
    && . "$HOME/.claude/agent-isolation/agent-iso.sh"
```

Trade-off: the global install decouples the wrapper from the
repo's pinned copy. If a future framework release changes the
wrapper (new passthrough vars, security fix), you need to
re-`cp` it into `~/.claude/agent-isolation/` by hand. Diff the
two paths periodically — or schedule it via `/schedule` — to
surface drift.

Then use `claude-iso` instead of `claude` whenever you start a
session in the tracker repo:

```bash
cd ~/code/<tracker>
claude-iso
```

The wrapper hard-allows only a tiny passthrough list (`HOME`, `PATH`,
`SHELL`, `TERM`, `LANG`, `XDG_*`, `DISPLAY`, `SSH_AUTH_SOCK`,
`USER`, `LOGNAME`, `PWD`); everything else from the parent shell is
dropped via `env -i`.

**Optional — make the isolated wrapper your default `claude`.** Once
the wrapper is sourced, you can alias `claude` to it so every plain
`claude` invocation goes through the clean-env path:

```bash
# in your ~/.bashrc or ~/.zshrc, *after* the source line above
alias claude='claude-iso'
```

The wrapper resolves the underlying binary via shell-aware path lookup
(`type -P` in bash, `whence -p` in zsh) rather than `command -v`, so
the alias does not loop back into itself. Each launch prints a dim
one-line banner on stderr (`[claude-iso] running in isolated env (…)`)
so it is obvious which mode the agent is starting in. To bypass the
alias for a single invocation, use `command claude …` or `\claude …`.

The trade-off is the same one as any "shadow the binary with a safer
wrapper" pattern: a session you forgot to start in a tracker checkout
also runs with a stripped env, which surprises tools that rely on a
parent-shell credential. If that bites, drop the alias and call
`claude-iso` explicitly when you actually want the isolation.

To inject one credential explicitly for one session:

```bash
# git push session — bring in the gh token for one run
CLAUDE_ISO_ALLOW="GH_TOKEN" GH_TOKEN="$(gh auth token)" claude-iso

# 1Password integration:
CLAUDE_ISO_ALLOW="GH_TOKEN" GH_TOKEN="$(op read 'op://Personal/GitHub/token')" claude-iso
```

The `CLAUDE_ISO_ALLOW` mechanism is opt-in per invocation — no
implicit propagation, no persistent allowlist.

### Automatic sandbox allow-paths

Beyond the env-stripping role, `claude-iso` also injects up to two
absolute paths into the session's `sandbox.filesystem.allowRead`
via a one-shot `claude --settings <json>` flag prepended to the
argv. The injection merges with the loaded settings stack at
startup, *before* sandbox initialisation, so the paths take
effect for that session immediately — no on-disk
`settings.local.json` edit, no per-checkout bootstrap, nothing
to clean up afterwards. A stderr banner reports what was added.

**Current-repo auto-allow (always on).** Whenever `claude-iso` is
launched from inside a git working tree, the working-tree root
(resolved via `git rev-parse --show-toplevel`) is added to
`allowRead`. This closes the visibility gap described in
[Project-root coverage in the sandbox allowlists](#project-root-coverage-in-the-sandbox-allowlists)
for the wrapper-launch path: when launched through `claude-iso`,
you do not also need the project root hand-listed in
`<repo>/.claude/settings.local.json` for the agent to be able to
read the source tree. (The settings.local.json fix remains the
right answer for plain `claude` launches — the harness can't
see the wrapper's argv.) Outside a git repo, this is a silent
no-op.

**Worktree mode (`claude-iso -w` / `claude-iso --worktree`).**
Additive on top of the current-repo auto-allow. When `-w` is on
the argv and `$PWD` is a worktree, the *main* repo (resolved via
`git rev-parse --git-common-dir`) is also added — that path is
otherwise unreachable from a worktree session, because the
sandbox's relative `.` rule covers only the worktree itself.
Run inside the main repo, `-w` is effectively a no-op: the
working-tree root and the main repo resolve to the same path
and dedupe into a single `allowRead` entry. Both paths ride
into the session via a single `--settings` injection.

## Sandbox-bypass visibility hook

The Bash tool accepts a `dangerouslyDisableSandbox: true` flag that
lets the model run a single command outside the sandbox — necessary
for the (rare) cases where a legitimate task needs to read or write
a path that the sandbox denies. Claude Code prompts the user before
honouring the bypass, but in a long session the prompt is easy to
skim past, especially when several appear in quick succession.

The framework ships a `PreToolUse` hook in
[`tools/agent-isolation/sandbox-bypass-warn.sh`](../../tools/agent-isolation/sandbox-bypass-warn.sh)
that makes every bypass attempt visually impossible to miss: a bold
red banner with the command and the model's stated reason printed
to stderr, before the permission prompt appears.

The hook is **complementary** to the rest of the secure setup, not a
replacement: it does not prevent a bypass, it just makes the bypass
visible. The user still has to approve the call at the permission
prompt — the banner gives them a fair chance to read what they are
about to approve.

### Why install it user-scope, not project-scope

Unlike the framework's
[`.claude/settings.json`](../../.claude/settings.json) (which is
repo-scoped — only sessions started inside the tracker repo see
it), this hook is most useful in
**`~/.claude/settings.json`** — the user-scope config that applies
to *every* Claude Code session on the host, tracker or otherwise.
A sandbox-bypass attempt is just as worth noticing in an unrelated
project as in the tracker.

Per-project-scope installation is also valid (drop the same hook
entry into a tracker's `.claude/settings.json`) — the trade-off is
narrower coverage in exchange for one fewer file to manage at the
user level.

### Install (user-scope)

```bash
# Copy the hook script into ~/.claude/scripts/ (or symlink it from
# the framework checkout — see "Syncing user-scope config across
# machines" below for the multi-host pattern).
mkdir -p ~/.claude/scripts
cp /path/to/magpie/tools/agent-isolation/sandbox-bypass-warn.sh \
    ~/.claude/scripts/sandbox-bypass-warn.sh
chmod +x ~/.claude/scripts/sandbox-bypass-warn.sh
```

Then wire the hook into `~/.claude/settings.json` under the
`PreToolUse` block, matched on the `Bash` tool. If a `Bash` matcher
already exists (e.g. for an unrelated hook), append to its `hooks`
array rather than creating a second matcher block:

```jsonc
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/scripts/sandbox-bypass-warn.sh"
          }
        ]
      }
    ]
  }
}
```

### Verify

The hook is exit-code-driven — exit 1 with stderr output means
"show stderr to the user, tool proceeds". To test without a real
bypass:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"ls ~/.aws","description":"check aws creds","dangerouslyDisableSandbox":true}}' \
    | ~/.claude/scripts/sandbox-bypass-warn.sh; echo "exit=$?"
```

Expected: a four-line red banner on stderr, then `exit=1`. A second
call with `dangerouslyDisableSandbox` set to `false` (or absent
entirely) should produce no output and `exit=0`.

### Trade-offs

- **No block, only visibility.** The hook deliberately exits 1, not
  2 — exit 2 would block the call outright, and that defeats the
  model's ability to do legitimate work the user has just asked for
  (e.g. installing packages outside the project tree). If a stricter
  posture is wanted, change the script's `exit 1` to `exit 2`; the
  consequence is that *every* sandbox-bypass attempt then has to be
  unblocked by editing the hook out, which in practice trains the
  user to skip the safety entirely. Visibility-with-prompt is the
  better steady state.
- **Schema robustness.** The hook greps the JSON payload for
  `"dangerouslyDisableSandbox": true` rather than reading a fixed
  JSON path via `jq`, so it keeps working if Claude Code reshuffles
  where in the payload the flag lives. Cost: a future Claude Code
  release that renames the flag will silently stop firing the hook
  until the regex is updated. Re-run the verification snippet after
  every Claude Code upgrade — same cadence as the
  [Verification](#verification) section below.

## Agent-guard deterministic guard hook

A `PreToolUse` hook that, unlike the bypass-visibility hook above,
**blocks** (not just annotates) a small set of `gh`/`git` commands
that would violate a hard framework rule — protections that must not
depend on the model remembering a `SKILL.md` instruction. The engine
lives in [`tools/agent-guard`](../../tools/agent-guard/README.md) and
ships two **bundled** (universal `git` hygiene) guards:

- **commit-trailer** — never let a `git commit` carry a
  `Co-Authored-By:` trailer (use `Generated-by:`).
- **empty-rebase** — never force-push a branch with no commits over
  its base (an empty push to a PR head auto-closes it and revokes
  write).

The domain-specific guards are **owned by the skills that need them**
and discovered the same way (below) — `skills/pr-management-triage/guards/`
ships **mention** (never `@`-ping a non-author in an author-directed
`gh pr comment`/`gh issue comment`; never `@`-mention anyone in a
`gh pr edit --body` fold) and **mark-ready** (never add `ready for
maintainer review` while CI awaits approval); `skills/security-issue-fix/guards/`
ships **security-language** (no CVE / security-fix wording in a public
`gh pr create|edit` title/body).

Each guard is overridable per command by a visible inline env
assignment (`MAGPIE_ALLOW_MENTIONS=1 gh pr comment …`, etc.) or
disabled wholesale with `MAGPIE_GUARD_OFF=1` — the deny message
names the override. The dispatcher is stdlib-only and invoked as
`python3 …/agent-guard.py`, fast-pathing everything that is not a
`gh` / `git` command.

### Extensible — any skill can contribute a guard

The hook is **wired once**. Additional guards are discovered at
runtime from the `guards.d` directory next to the script (plus any
dir in `$MAGPIE_GUARD_DIRS`). A skill contributes a guard by
shipping one import-free `*.py` file that defines `guard(ctx)` (and
an optional `TRIGGERS` list) — **no `settings.json` change**. The
setup skills sync `guards.d` from the snapshot, so a new bundled or
skill-contributed guard activates on the next `/magpie-setup` /
`setup-isolated-setup-update`. See the
[tool README](../../tools/agent-guard/README.md) for the contract and
`guards.d/no_verify_commit.py` for the template.

### Install (user-scope)

```bash
mkdir -p ~/.claude/scripts/guards.d
cp /path/to/magpie/tools/agent-guard/src/agent_guard/__init__.py \
    ~/.claude/scripts/agent-guard.py
# Bundled (universal) guards…
cp /path/to/magpie/tools/agent-guard/src/agent_guard/guards.d/*.py \
    ~/.claude/scripts/guards.d/
# …plus every skill-owned guard (mention, mark-ready, security-language, …)
cp /path/to/magpie/skills/*/guards/*.py ~/.claude/scripts/guards.d/ 2>/dev/null || true
chmod +x ~/.claude/scripts/agent-guard.py
```

Then wire it into `~/.claude/settings.json` (project-scope
`.claude/settings.json` works too) under `PreToolUse`, matched on
`Bash` — append to an existing `Bash` matcher's `hooks` array if one
is already present (e.g. the bypass-visibility hook):

```jsonc
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "python3 \"$HOME/.claude/scripts/agent-guard.py\"",
            "timeout": 30
          }
        ]
      }
    ]
  }
}
```

### Verify

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"gh pr edit 5 --body \"@alice hi\""}}' \
    | python3 ~/.claude/scripts/agent-guard.py
```

Expected: a JSON object with `permissionDecision: "deny"` and a
reason mentioning the `mention` guard. A plain command
(`{"tool_input":{"command":"ls"}}`) produces no output and `exit=0`.

## Sandbox-error hint hook

Companion to the *Sandbox-bypass visibility hook* above — a
`PostToolUse` hook that fires **after** every Bash tool call and
scans the result for the known sandbox-shaped error signatures
catalogued in
[`sandbox-troubleshooting.md`](sandbox-troubleshooting.md).
On a match, prints a `[sandbox-hint] …` line to stderr pointing
at the matching catalog entry. The tool's actual outcome is
unchanged — the hook is purely an annotation layer that surfaces
the catalog reference at the moment of failure, so the agent (or
the user) does not have to remember the catalog exists.

### Why install it

The catalog (PR #291) and the diagnostic skill
[`setup-isolated-setup-doctor`](../../skills/setup-isolated-setup-doctor/SKILL.md)
(PR #292) cover the same ground but require explicit
recall — *"my SSH push failed; let me check the catalog"* or
*"let me run the doctor"*. The hint hook closes the loop by
making the catalog reference appear next to the error
automatically. Three classes of failure are recognised today:

| Error signature | Catalog anchor |
|---|---|
| `Could not open a connection to your authentication agent` / `agent refused operation` / `ssh-add: error fetching identities` / `Permission denied (publickey)` | [SSH agent / Yubikey unreachable](sandbox-troubleshooting.md#ssh-agent--yubikey-appears-unreachable-from-inside-the-sandbox) |
| `Cannot connect to the Docker daemon` / `open /var/run/docker.sock: operation not permitted` / `Cannot connect to Podman` / podman `connect: permission denied` | [Docker / Podman socket denied](sandbox-troubleshooting.md#docker--podman-command-fails-with-a-socket-error) |
| `127.0.0.1 … Permission denied` / `Operation not permitted … bind` / `Errno 49 … assign requested address` / `Connection refused … 127.0.0.1` | [Localhost port-bind blocked](sandbox-troubleshooting.md#test-cannot-bind-to-a-localhost-port) |

The hint also tells the user to run
`/magpie-setup-isolated-setup-doctor` for a structured probe of all
three failure modes, so a single mid-flow failure can lead to a
broader sandbox health-check.

### Why install it user-scope, not project-scope

Same reasoning as the bypass-warn hook: the failure signatures
the hook detects are not framework-specific — they show up in any
sandboxed Bash session against any project. Putting the hook in
`~/.claude/settings.json` makes the hint fire across every
project on the host, including adopters that have not (yet)
adopted the framework. Project-scope wiring would leave
unrelated sessions silent.

### Install (user-scope)

```bash
mkdir -p ~/.claude/scripts
cp /path/to/magpie/tools/agent-isolation/sandbox-error-hint.sh \
    ~/.claude/scripts/sandbox-error-hint.sh
chmod +x ~/.claude/scripts/sandbox-error-hint.sh
```

Then wire under `PostToolUse` with a `Bash` matcher. If a
`PostToolUse` `Bash` matcher already exists for another hook,
append to its `hooks` array rather than creating a second
matcher block:

```jsonc
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "~/.claude/scripts/sandbox-error-hint.sh"
          }
        ]
      }
    ]
  }
}
```

### Verify

The hook is exit-code-driven — exit 1 with stderr output means
"surface stderr to the user as a tool-result hint". To test
without a real failure:

```bash
echo '{"tool_name":"Bash","tool_response":{"stdout":"","stderr":"Could not open a connection to your authentication agent."}}' \
    | ~/.claude/scripts/sandbox-error-hint.sh; echo "exit=$?"
```

Expected: a yellow `[sandbox-hint] SSH agent / Yubikey appears
unreachable …` line on stderr, then `exit=1`. A second call with
benign tool output (e.g. `"stdout":"hello world","stderr":""`)
should produce no output and `exit=0`.

### Trade-offs

- **Pattern-matched, not semantic.** The hook recognises literal
  error strings; it does not know *why* a tool call failed. A
  failure mode dressed up in a userland framework's generic error
  ("test failed", "build error") slips past silently. The
  doctor skill is the catch-all when the hint does not fire and
  the user suspects a sandbox issue.
- **Pattern set must stay in lock-step with the catalog.** When a
  new entry lands in [`sandbox-troubleshooting.md`](sandbox-troubleshooting.md),
  add a matching `match … hint=…` branch to the script. The
  catalog is the source of truth; the hook is the discoverability
  layer.
- **Fail-open by design.** Any unexpected JSON shape, missing
  `tool_response`, missing `jq`, or other parse failure exits 0
  silently. A broken hint must never break a legitimate tool
  call. Cost: a future Claude Code hook-schema change can silently
  stop the hook from firing; re-run the verification snippet
  above after every Claude Code upgrade.
- **Non-blocking.** The hook exits 1, not 2 — the tool call
  result is unchanged. The hint is informational; the user
  decides whether to apply the catalog's remediation.

## Sandbox-state status line

The Claude Code terminal footer (`statusLine`) is the
always-visible bottom-of-window line that renders the model name,
context usage, and any custom information you wire in. It is the
right place to surface whether the sandbox is currently active for
this session — a session that is inadvertently running with
`sandbox.enabled` unset (or globally bypassed) cannot then drift
unnoticed for hours.

The framework ships
[`tools/agent-isolation/sandbox-status-line.sh`](../../tools/agent-isolation/sandbox-status-line.sh)
to render exactly that:

- `<model> [sandbox]` in green when the active settings set
  `"sandbox": { "enabled": true }`, OR
- `<model> [NO SANDBOX]` in bold red when they do not.

The script walks the same precedence Claude Code itself uses for
`sandbox.enabled` — project `settings.local.json` first, then
project `settings.json`, then `~/.claude/settings.local.json`,
then `~/.claude/settings.json` — and stops at the first file
that sets the key (to `true` *or* `false`). The `/sandbox`
slash-command toggle persists to project `settings.local.json`,
so flipping it mid-session is reflected in the prefix on the
next render.

Like the [Sandbox-bypass visibility hook](#sandbox-bypass-visibility-hook),
this is **complementary**, not authoritative — see Trade-offs
below.

**Why user-scope.** Same reasoning as the bypass-warn hook: a
session that runs without the sandbox is just as worth flagging
in an unrelated project as in a tracker. Install in
`~/.claude/settings.json` so the indicator shows in every session
on the host, not only sessions inside a tracker repo whose
project-level `.claude/settings.json` would otherwise have to wire
it itself.

**Install (user-scope).**

```bash
mkdir -p ~/.claude/scripts
cp /path/to/magpie/tools/agent-isolation/sandbox-status-line.sh \
    ~/.claude/scripts/sandbox-status-line.sh
chmod +x ~/.claude/scripts/sandbox-status-line.sh
```

Wire it into `~/.claude/settings.json` under the `statusLine` key:

```jsonc
{
  "statusLine": {
    "type": "command",
    "command": "~/.claude/scripts/sandbox-status-line.sh"
  }
}
```

If you already maintain a richer custom statusLine, the helper is
intentionally one-line — call it as one segment of your own
renderer rather than replacing it.

For adopters who want a richer variant out of the box, the framework
also ships
[`tools/agent-isolation/sandbox-status-line-rich.sh`](../../tools/agent-isolation/sandbox-status-line-rich.sh).
Same sandbox-state detection, plus folder name (hash-coloured for a
stable per-repo identity), git branch + dirty marker + ahead/behind,
per-branch PR title (cached for 5 min, silent when `gh` is missing or
unauthenticated), and a yellow `[sandbox-auto]` tag for the
`autoAllowBashIfSandboxed` setting. Install steps are identical —
copy the `-rich` file in place of the minimal one and point
`statusLine.command` at it. The minimal variant remains the
documented default; the rich one is opt-in.

**Verify.**

```bash
echo '{"model":{"display_name":"Sonnet 4.6"},"workspace":{"current_dir":"'"$PWD"'"}}' \
    | ~/.claude/scripts/sandbox-status-line.sh
```

Expected output, *inside* this repo (its
[`.claude/settings.json`](../../.claude/settings.json) sets
`sandbox.enabled: true`, and assuming `.claude/settings.local.json`
either does not exist or does not override the key):
`Sonnet 4.6 [sandbox]` with `[sandbox]` rendered in green. From a
directory whose project and user settings files do **not** enable
the sandbox (or do not exist), the output is `[NO SANDBOX]` in
bold red.

**Trade-offs.**

- **Settings-level truth, not session-level truth.** The script
  reads `sandbox.enabled` from the file system. It cannot see CLI
  flags (`--bypass-permissions`, equivalent runtime overrides) —
  those still display as `[sandbox]` even though the running
  session is unprotected. The `/sandbox` slash-command toggle
  *is* reflected, because it persists to project
  `settings.local.json`, which the script reads. Pair the
  indicator with the
  [Sandbox-bypass visibility hook](#sandbox-bypass-visibility-hook)
  so per-call bypass attempts also surface in real time.
- **Schema robustness.** The Claude Code statusLine input JSON
  does not currently expose sandbox state — we read the settings
  files ourselves. If a future Claude Code release adds a sandbox
  field to the statusLine input, the script can be simplified to
  read that field directly. Until then the file-read approach is
  the only option, with the trade-off above.

## Waiting-for-input terminal tint

> **Quality-of-life helper, not a security control.** Unlike the
> rest of this document, this piece protects nothing — it just
> makes the "Claude is blocked on me" state impossible to miss. It
> rides the same user-scope-hook install machinery as the helpers
> above, which is why it lives here, but it is entirely optional
> and off by default.

When you run several agents across tabs, it is easy to leave one
sitting at a permission prompt or a finished turn while you work
elsewhere. The framework ships
[`tools/agent-isolation/claude-term-bg.sh`](../../tools/agent-isolation/claude-term-bg.sh)
to make a **calm baseline the normal state and tint the background
only when Claude genuinely wants you to act** — never while it is
working, and never when it merely *finished* a turn and is idle
until you start the next thing. Those last two look identical at the
`Stop` event, so the model leans on three "Claude is asking you for
something" signals (two exact, one heuristic), wired across six
hooks:

| Moment | Hook → action | Background |
|---|---|---|
| Turn ended on a genuine question/request | `Stop` → `stop` | tinted (muted indigo `#2a1a3a`) |
| Turn ended on a completion ("Done.") | `Stop` → `stop` | calm |
| Structured question posed | `PreToolUse` (matcher `AskUserQuestion`) → `wait` | tinted |
| Blocked on a permission prompt | `Notification` → `notify` | tinted |
| Actively working / you just acted | `PostToolUse` (matcher `*`) → `reset` | calm |
| Plain 60-second idle ping | `Notification` → `notify` (no-op) | unchanged |
| Fresh session, or you submit a reply | `SessionStart` / `UserPromptSubmit` → `reset` | calm |

Four details make the model behave:

- **`Stop` → `stop`** is the only non-exact signal. It reads the
  last assistant text message from the session transcript (the path
  arrives on stdin in the `Stop` payload) and tints only when that
  message ends as a question (`…?`) or with a strong trailing
  request ("want me to", "would you like", "should I", "OK to",
  "your call", …); a statement-shaped completion stays calm. Needs
  `python3`/`python` on `PATH`; if absent, `stop` defaults to calm
  and only the two exact signals tint.
- **`PostToolUse` → `reset`** (not `PreToolUse`) clears the "you
  just acted" tint. `PreToolUse` fires *before* the permission
  prompt is shown, so it cannot clear a tint the prompt itself
  sets; `PostToolUse` fires *after* the tool completes — the moment
  your approval lets work resume — so it is what returns the screen
  to calm. `PreToolUse` is reserved for the `AskUserQuestion` →
  `wait` tint.
- **`SessionStart` → `reset`** clears any tint a *previous* session
  left behind (OSC background changes persist in the terminal
  across processes, so a session closed mid-wait would otherwise
  hand its tint to the next one — making a "fresh" session look
  like it is waiting on you).
- **`Notification` → `notify`** is selective: the same hook fires
  both for permission prompts *and* the plain 60-second idle ping,
  so the script reads the notification payload on stdin and tints
  only for a permission/attention prompt. The idle ping is a
  deliberate **no-op** (not a reset) — otherwise a turn that ended
  on a genuine question, tinted by `stop`, would silently go calm
  after a minute.

**Two mechanics make this work** (both are easy to get wrong):

1. **Hooks have no controlling terminal.** Claude Code spawns hook
   commands detached from the tty, so `/dev/tty` does not resolve
   to your window — a naive `printf '\033]11;…' > /dev/tty` writes
   nowhere. The script walks up the process tree from `$PPID` to
   find the Claude process's pty (e.g. `/dev/ttys003`) and writes
   the escape straight to that device.
2. **Set and reset are not symmetric.** iTerm2 honours OSC 11 (set
   background) but does **not** reliably honour OSC 111
   (reset-to-default) through Claude's fullscreen TUI, so a naive
   reset leaves the tint stuck on. The script resets
   belt-and-braces: it emits both OSC 111 *and* iTerm2's
   proprietary `SetColors=bg=default`. For a guaranteed reset on
   any terminal, set `CLAUDE_RESET_BG` to your normal background
   colour and the script re-applies it via OSC 11 (the path that
   is known to work since the tint itself does).

**Why user-scope.** Same reasoning as the helpers above: you want
the signal in every session on the host, not only tracker
sessions. Install in `~/.claude/settings.json`.

**Install (user-scope).**

```bash
mkdir -p ~/.claude/scripts
cp /path/to/magpie/tools/agent-isolation/claude-term-bg.sh \
    ~/.claude/scripts/claude-term-bg.sh
chmod +x ~/.claude/scripts/claude-term-bg.sh
```

Wire it into `~/.claude/settings.json` under six hook events. If
you already have hooks on any of these events, add the command as
an extra entry rather than replacing the existing array. The
`PreToolUse` entry uses the `AskUserQuestion` matcher (not `*`), so
it tints only on a structured question; `PostToolUse` carries the
general `reset`. The `CLAUDE_RESET_BG=#000000` prefix makes the
calm state a deterministic black (recommended — it sidesteps the
OSC-111 reset gap described above); drop it to fall back to
profile-default reset.

```jsonc
{
  "hooks": {
    "Stop": [
      { "hooks": [ { "type": "command", "command": "CLAUDE_RESET_BG=#000000 ~/.claude/scripts/claude-term-bg.sh stop" } ] }
    ],
    "PreToolUse": [
      { "matcher": "AskUserQuestion", "hooks": [ { "type": "command", "command": "~/.claude/scripts/claude-term-bg.sh wait" } ] }
    ],
    "PostToolUse": [
      { "matcher": "*", "hooks": [ { "type": "command", "command": "CLAUDE_RESET_BG=#000000 ~/.claude/scripts/claude-term-bg.sh reset" } ] }
    ],
    "UserPromptSubmit": [
      { "hooks": [ { "type": "command", "command": "CLAUDE_RESET_BG=#000000 ~/.claude/scripts/claude-term-bg.sh reset" } ] }
    ],
    "SessionStart": [
      { "hooks": [ { "type": "command", "command": "CLAUDE_RESET_BG=#000000 ~/.claude/scripts/claude-term-bg.sh reset" } ] }
    ],
    "Notification": [
      { "hooks": [ { "type": "command", "command": "CLAUDE_RESET_BG=#000000 ~/.claude/scripts/claude-term-bg.sh notify" } ] }
    ]
  }
}
```

Override the colours via the environment: `CLAUDE_WAIT_BG`
(default `#2a1a3a`) and `CLAUDE_RESET_BG` (default unset → reset to
the profile default; set to a colour like `#000000` for a
deterministic calm background).

**Verify.** The hooks fire on real events, so the quickest check
is live: start a session, let a turn finish, and confirm the
background tints; then send a reply and confirm it resets. To
sanity-check the script in isolation, run it against your own
terminal device:

```bash
~/.claude/scripts/claude-term-bg.sh wait   # background tints
~/.claude/scripts/claude-term-bg.sh reset  # background restored
```

(Run directly from an interactive shell, the script finds the
shell's pty via `$PPID` and writes there.)

**Trade-offs.**

- **iTerm2-tested, fail-soft elsewhere.** The set path uses OSC 11,
  which most modern terminal emulators support; terminals that
  ignore it simply show no change. The reset path is hardened for
  iTerm2's OSC-111 gap specifically. On a terminal where reset
  misbehaves, set `CLAUDE_RESET_BG` for a deterministic restore.
- **Cosmetic only.** It conveys no sandbox or permission state —
  pair it with the [Sandbox-state status line](#sandbox-state-status-line)
  and [Sandbox-bypass visibility hook](#sandbox-bypass-visibility-hook)
  for the security-relevant signals.

## Syncing user-scope config across machines

The user-scope pieces of the secure setup —
`~/.claude/scripts/sandbox-bypass-warn.sh`, an optional global copy
of `agent-iso.sh` (per the
[Global (user-scope) install](#the-clean-env-wrapper) trade-off),
your personal `~/.claude/CLAUDE.md`, plus any other custom hooks —
only protect a host once they are installed there. Working on more
than one machine means keeping all of them in lockstep, by hand,
forever. That is exactly the workflow a small dotfile-style sync
repo solves.

The recommended pattern is a **private** git repository (private,
not public, because `~/.claude/CLAUDE.md` typically carries personal
collaboration preferences and the scripts may reference internal
paths). Track the artifacts you want shared, symlink them into
`~/.claude/`, and run a small sync script that pulls/commits/pushes.

### What to track, what not to track

| Track in the synced repo | Keep per-machine |
|---|---|
| `CLAUDE.md` (personal collaboration prefs) | `~/.claude/.credentials.json` — ⚠ secret, never commit |
| `scripts/sandbox-bypass-warn.sh`, `scripts/sandbox-error-hint.sh`, `scripts/sandbox-status-line.sh`, and any other hooks | `~/.claude/sessions/`, `~/.claude/history.jsonl` — session state |
| `agent-isolation/agent-iso.sh` (if you globally installed it per the wrapper section) | `~/.claude/projects/<key>/` — per-project session state and tasks (the `memory/` subdir is optionally sharable, see [Extending `sync.sh`: share project memory across machines](#extending-syncsh-share-project-memory-across-machines)) |
| Custom slash commands (`commands/<name>.md`) | `~/.claude/settings.json` — typically differs per host (plugins, statusLine paths, voice) |
| MCP servers you've audited and want everywhere (`.mcp.json` shape, by hand) | `~/.claude/settings.local.json` — by design machine-specific |

The settings.json line is worth highlighting: it is tempting to
sync it, and it does work, but in practice the machines drift
(different plugin sets, different terminal capabilities) and the
last-writer-wins behaviour of a naive sync script overwrites the
divergent settings every push. Keep it per-machine and document
the **wiring** instead — i.e. ship the `scripts/` directory in the
synced repo, then on each new host edit `~/.claude/settings.json`
once to point at the synced scripts. The "Install" snippets above
already follow this pattern.

### Layout

A minimal repo layout:

```text
~/.claude-config/                       # the synced repo's checkout
├── CLAUDE.md                           # symlinked → ~/.claude/CLAUDE.md
├── scripts/
│   ├── sandbox-bypass-warn.sh          # symlinked → ~/.claude/scripts/sandbox-bypass-warn.sh
│   └── sandbox-status-line.sh          # symlinked → ~/.claude/scripts/sandbox-status-line.sh
├── agent-isolation/
│   └── agent-iso.sh                   # symlinked → ~/.claude/agent-isolation/agent-iso.sh
├── README.md                           # what's in the repo, install steps per machine
└── sync.sh                             # the pull/commit/push helper
```

Each tracked artifact lives in the repo; the path under `~/.claude/`
is a symlink pointing at the repo. Editing either side updates both.

### Setting up a fresh host

```sh
git clone git@github.com:<you>/claude-config.git ~/.claude-config

# CLAUDE.md
mkdir -p ~/.claude
[ -f ~/.claude/CLAUDE.md ] && [ ! -L ~/.claude/CLAUDE.md ] && \
    mv ~/.claude/CLAUDE.md ~/.claude/CLAUDE.md.bak
ln -sf ~/.claude-config/CLAUDE.md ~/.claude/CLAUDE.md

# Sandbox-bypass warning hook + sandbox-state status line
mkdir -p ~/.claude/scripts
ln -sfn ~/.claude-config/scripts/sandbox-bypass-warn.sh \
    ~/.claude/scripts/sandbox-bypass-warn.sh
ln -sfn ~/.claude-config/scripts/sandbox-status-line.sh \
    ~/.claude/scripts/sandbox-status-line.sh

# (Optional) global claude-iso wrapper — see the wrapper section
mkdir -p ~/.claude/agent-isolation
ln -sfn ~/.claude-config/agent-isolation/agent-iso.sh \
    ~/.claude/agent-isolation/agent-iso.sh
```

Then wire the per-machine bits one time, per the install snippets
in the relevant sections (the hook entry in
`~/.claude/settings.json`, the `source …/agent-iso.sh` line in
`~/.bashrc` / `~/.zshrc`, etc.).

### A minimal `sync.sh`

The script is intentionally tiny — pull, commit anything dirty,
push. Run it manually, on a cron, on a systemd timer, or wherever
fits your workflow:

```bash
#!/usr/bin/env bash
# Pull-commit-push the personal claude-config repo. Safe to run on
# a timer: flock prevents concurrent runs, --rebase --autostash
# carries any local edits through cleanly.
set -u
REPO="$HOME/.claude-config"
LOCK="$REPO/.sync.lock"
exec 9>"$LOCK"; flock -n 9 || exit 0
cd "$REPO" || exit 1
git pull --rebase --autostash
git add -A
git diff --cached --quiet || \
    git commit -m "auto-sync from $(hostname) at $(date -Iseconds)"
git log @{u}.. --oneline | grep -q . && git push
```

### Extending `sync.sh`: share project memory across machines

Claude Code persists durable per-project memory under
`~/.claude/projects/<key>/memory/`, where `<key>` is the project's
absolute working directory with `/` and `.` replaced by `-`. The same
project takes a different key on each host
(`-home-you-code-foo` on Linux vs `-Users-you-code-foo` on macOS), so
a naive copy-the-tree-into-the-repo sync either misses the cross-host
mapping or stomps over it.

The pattern that works: store memories in the repo under a
`$HOME`-relative subdir, and have `sync.sh` re-establish a per-host
symlink after every pull. The function below is idempotent — it
ingests any non-symlink memory dir found on the host that is not yet
in the repo, then re-points the runtime symlinks at the repo paths.
New project on a new host? Open it once; the next sync pass picks up
the memory dir, ingests it, and the symlink appears on every other
host on their next pull.

```bash
MEM_REPO="$HOME/.claude-config/memory"
PROJECTS="$HOME/.claude/projects"

# Encode an absolute path the way Claude Code keys project dirs: every
# / and . becomes -. So /home/you/.claude-config -> -home-you--claude-config.
encode_path() {
  local p="$1"
  p="${p//\//-}"
  p="${p//./-}"
  printf '%s' "$p"
}

ensure_memory_links() {
  mkdir -p "$MEM_REPO"
  local home_key
  home_key="$(encode_path "$HOME")"

  # Step 1 — ingest any non-symlink memory dir not yet in the repo.
  for project_dir in "$PROJECTS"/*/; do
    runtime_mem="${project_dir}memory"
    [[ -d "$runtime_mem" && ! -L "$runtime_mem" ]] || continue
    [[ -n "$(ls -A "$runtime_mem" 2>/dev/null)" ]] || continue

    key="$(basename "${project_dir%/}")"
    if [[ "$key" == "$home_key" ]]; then
      norm="_root_"
    elif [[ "$key" == "$home_key-"* ]]; then
      norm="${key#$home_key-}"
    else
      # Project lives outside $HOME — preserve full key under ABS-.
      norm="ABS$key"
    fi

    repo_mem="$MEM_REPO/$norm"
    [[ -e "$repo_mem" ]] && continue
    mv "$runtime_mem" "$repo_mem"
  done

  # Step 2 — re-establish per-host symlinks for every tracked memory dir.
  for repo_mem in "$MEM_REPO"/*/; do
    [[ -d "$repo_mem" ]] || continue
    norm="$(basename "${repo_mem%/}")"
    if [[ "$norm" == "_root_" ]]; then
      key="$home_key"
    elif [[ "$norm" == ABS-* ]]; then
      key="${norm#ABS}"
    else
      key="$home_key-$norm"
    fi
    target="$PROJECTS/$key/memory"
    mkdir -p "$(dirname "$target")"
    if [[ -L "$target" ]]; then
      [[ "$(readlink "$target")" == "${repo_mem%/}" ]] && continue
      rm "$target"
    elif [[ -d "$target" ]]; then
      continue   # real dir not yet ingested — leave alone
    fi
    ln -s "${repo_mem%/}" "$target"
  done
}
```

Call `ensure_memory_links` from `sync.sh` *after* `git pull` (untracked
files are not autostashed, so ingesting before pull risks colliding with
a remote add of the same path).

### Extending `sync.sh`: expose tracked scripts on `$PATH`

A second helper, dropped into the same `sync.sh`, symlinks every
tracked executable into `~/.local/bin/` so the scripts are invocable
by name from any shell. Platform-suffixed binaries (`foo-linux`,
`foo-macos`) link as the bare `foo` on the matching host only — so the
same repo can carry both builds and each host picks up the right one.

```bash
LOCAL_BIN="$HOME/.local/bin"
REPO="$HOME/.claude-config"

ensure_bin_links() {
  mkdir -p "$LOCAL_BIN"
  local platform=""
  case "$(uname -s)" in
    Linux) platform=linux ;;
    Darwin) platform=macos ;;
  esac

  link_one() {
    local src="$1" name="$2" dst="$LOCAL_BIN/$2"
    if [[ -L "$dst" ]]; then
      [[ "$(readlink "$dst")" == "$src" ]] && return
      rm "$dst"
    elif [[ -e "$dst" ]]; then
      return   # something non-symlink is in the way — leave alone
    fi
    ln -s "$src" "$dst"
  }

  for f in "$REPO"/bin/* "$REPO"/scripts/*.sh; do
    [[ -f "$f" && -x "$f" ]] || continue
    name="$(basename "$f")"
    case "$name" in
      *-linux) [[ "$platform" == "linux" ]] && link_one "$f" "${name%-linux}" ;;
      *-macos) [[ "$platform" == "macos" ]] && link_one "$f" "${name%-macos}" ;;
      *)       link_one "$f" "$name" ;;
    esac
  done
}
```

With this in place, no one-shot symlink step is needed when wiring a
fresh host for scripts in `bin/` or `scripts/` — the next sync pass
takes care of it. The hooks referenced by absolute path from
`settings.json` (e.g. `~/.claude/scripts/sandbox-bypass-warn.sh`) still
need their one-time symlink as in
[Setting up a fresh host](#setting-up-a-fresh-host) — these run from
the harness, not the user shell.

### Why a *private* repo

Three reasons make this non-negotiable:

1. **`CLAUDE.md` carries personal preferences.** Tone overrides
   for specific people, opinions about review style, names of
   internal projects — content you do not want indexed by GitHub
   search.
2. **Hooks may embed internal paths.** A custom statusline script
   that pokes at `~/work/<employer>/` is not something to publish.
3. **Audit surface for prompt-injection.** If the synced repo is
   public and writable by anyone with a PR, an attacker can land
   a malicious script that every host pulling the repo will then
   execute on the next sync. A private repo with branch protection
   (or a single-author push policy) closes that vector.

Public dotfile repos are fine for shell aliases and editor configs;
they are the wrong shape for agent-runtime files.

## Adopter setup

If you are adopting the framework into your own tracker repo, copy
the secure setup into your tracker's working tree. Two paths —
the manual recipe is below, the agent-guided form is in the
sub-section that follows.

### Direct manual install

1. Install the pinned tools per [Install commands](#install-commands)
   above.
2. Copy
   [`.claude/settings.json`](../../.claude/settings.json) from the framework
   snapshot at `<your-tracker>/.apache-magpie/.claude/settings.json`
   into `<your-tracker>/.claude/settings.json`. Adjust:
   - The `sandbox.network.allowedDomains` list — drop the framework
     domains you don't actually use, add any project-specific hosts.
   - The `sandbox.filesystem.allowRead` list — same: drop the
     dotfiles your project doesn't need, add any project-specific
     paths the host requires. If you use Claude Code's `--worktree`
     agent isolation, sibling agent worktrees live next to the active
     one (e.g. `~/code/<project>/.claude/worktrees/agent-*/`), and
     `git` operations on a worktree follow its `.git` file up to the
     main repo's `.git/` directory. Both require read access to the
     parent path that contains all worktrees and the main repo —
     adopters who keep their checkout at, say, `~/code/<project>/`
     should add that directory to `allowRead`.
   - The `permissions.ask` list — add any project-specific
     write-side commands you want to confirm explicitly (e.g. a
     custom release-publishing CLI).
3. Make `claude-iso` available on your shell — either per-repo
   (sourcing the script from the framework snapshot) or globally
   (copying the script to `~/.claude/agent-isolation/` and
   sourcing from there). Both options are documented in
   [The clean-env wrapper](#the-clean-env-wrapper). When the
   framework is consumed via the standard snapshot path, the
   per-repo source path is
   `<your-tracker>/.apache-magpie/tools/agent-isolation/agent-iso.sh`.
4. Decide whether to gitignore `.claude/settings.local.json` in your
   tracker repo — Claude Code does this by default; verify with
   `git check-ignore .claude/settings.local.json`.
5. **Recommended (user-scope, not repo-scope):** install the
   sandbox-bypass warning hook per
   [Sandbox-bypass visibility hook](#sandbox-bypass-visibility-hook)
   *and* the sandbox-state status line per
   [Sandbox-state status line](#sandbox-state-status-line). Both
   apply to every Claude Code session on the host (not only
   tracker sessions), so they belong in your user-scope
   `~/.claude/settings.json` — not in the tracker's
   `.claude/settings.json`.
6. **Optional (multi-machine workflow):** keep the user-scope
   pieces (the hook scripts, the status-line script, your personal
   `CLAUDE.md`, an optional global `agent-iso.sh`) in a private
   dotfile-style repo per
   [Syncing user-scope config across machines](#syncing-user-scope-config-across-machines).

### Via a Claude Code prompt

Paste the following into Claude Code at the start of a fresh
session in your tracker repo. Claude walks every install step,
surfacing each command for you to approve or run yourself —
nothing privilege-elevating, nothing that touches your shell rc
or overwrites an existing settings file is applied without your
explicit OK:

```text
Set up the secure-agent setup for me from scratch in this tracker
repo. Walk me through every step before doing it; do not auto-run
anything that needs sudo, would overwrite an existing file, or
would write to my shell rc — print the command and ask me to run
it / approve it.

Before starting, confirm:

- The OS (Linux distro / macOS).
- The path to my magpie framework checkout (you'll need
  to read its `.claude/settings.json`,
  `tools/agent-isolation/*`, and
  `tools/agent-isolation/pinned-versions.toml`).
- Whether this is a fresh install (no prior secure setup) or a
  re-install on top of a partial state — for a re-install,
  surface any existing user-scope `~/.claude/settings.json` hooks
  and statusLine before merging.

Then walk through:

1. **Pinned tools.** Read
   `<magpie>/tools/agent-isolation/pinned-versions.toml`
   and surface the install command for `bubblewrap` and `socat`
   at the pinned versions for my distro (skip both on macOS —
   Seatbelt is built-in). Then surface the npm command for
   `claude-code` at the pinned version. Print these for me to
   run; do not invoke sudo or npm yourself.

2. **Project `.claude/settings.json`.** Read
   `<magpie>/.claude/settings.json` and copy its
   `sandbox`, `permissions.deny`, and `permissions.ask` blocks
   into this repo's `.claude/settings.json`. If a project
   settings.json already exists, surface a diff of the merged
   result first and ask me to approve before writing.

3. **Clean-env wrapper.** Surface the line to add to my
   `~/.bashrc` or `~/.zshrc` to source
   `<magpie>/tools/agent-isolation/agent-iso.sh`. Ask
   whether I want it as the default `claude` (alias) or
   on-demand only. Print the line; do not edit my shell rc
   yourself.

4. **User-scope hook scripts.** `mkdir -p ~/.claude/scripts`,
   then copy
   `<magpie>/tools/agent-isolation/sandbox-bypass-warn.sh`
   and
   `<magpie>/tools/agent-isolation/sandbox-status-line.sh`
   into `~/.claude/scripts/` and `chmod +x` them.

5. **User-scope `~/.claude/settings.json` wiring.** Read the
   file if it exists. Add the `PreToolUse` `Bash` matcher wired
   to `sandbox-bypass-warn.sh` and the `statusLine` command set
   to `sandbox-status-line.sh`. If either key exists already
   (e.g. I have other PreToolUse hooks for unrelated work),
   surface the merge diff and ask me to approve before writing.

6. **(Optional) Waiting-for-input terminal tint.** Ask me whether
   I want the terminal background to tint while Claude is waiting
   on me (a pure quality-of-life signal, no security effect).
   **Default no.** Only if I say yes: copy
   `<magpie>/tools/agent-isolation/claude-term-bg.sh`
   into `~/.claude/scripts/` and `chmod +x` it, then add six
   hooks to `~/.claude/settings.json`, merging into any existing
   arrays on those events — `Stop` → `claude-term-bg.sh stop`
   (heuristic tint on a question/request, calm on a completion);
   `PreToolUse` (matcher `AskUserQuestion`) → `claude-term-bg.sh
   wait`; `UserPromptSubmit`, `SessionStart`, and `PostToolUse`
   (matcher `*`) → `claude-term-bg.sh reset`; and `Notification` →
   `claude-term-bg.sh notify`. Ask whether I want the calm state
   to be a deterministic black (prefix the reset/notify commands
   with `CLAUDE_RESET_BG=#000000`) or the terminal's profile
   default. See
   [Waiting-for-input terminal tint](#waiting-for-input-terminal-tint).

7. **Verify.** After everything is in place, walk through the
   Verification checks from the next section of this document
   ("Verification — Via a Claude Code prompt") and report
   ✓ done / ✗ missing / ⚠ partial for each piece.

If any step fails, stop and report the failure — do not work
around it silently.
```

When the prompt finishes, the [Verification](#verification)
section is the natural next step (Claude can run the verification
prompt in the same session — it has all the context already), and
[Keeping the setup updated](#keeping-the-setup-updated) is the
section to revisit after every Claude Code upgrade.

## Verification

After installing and configuring, verify the setup actually denies
what it claims to. Two paths — pick whichever is easier; the
Claude-prompt path is more thorough, the direct-Bash path is
faster.

### Direct Bash verification

Inside a `claude-iso` session, run these from the agent's Bash
tool. Each should fail or be denied:

```bash
cat ~/.aws/credentials      # → permission denied (sandbox)
echo $AWS_ACCESS_KEY_ID     # → empty (env stripped by claude-iso)
curl https://example.com    # → blocked by permissions.deny
```

Each command should produce a denial — not a leaked credential.

### Via a Claude Code prompt

Paste the following into Claude Code at the start of a fresh
session in the tracker repo. Claude walks every install step and
reports what is wired vs missing, without trying to fix anything
on its own:

```text
Verify my secure-agent-setup install is complete. Check each item
below and report ✓ done / ✗ missing / ⚠ partial, with the evidence
(file path, line, command output). Do not attempt to fix anything
— surface the gaps and stop:

1. Project `.claude/settings.json` exists and has
   `sandbox.enabled: true`, the `permissions.deny` block, the
   `permissions.ask` block, the
   `sandbox.network.allowedDomains` block, and the
   `sandbox.filesystem` allowlist (`allowRead`/`allowWrite`).
2. User-scope `~/.claude/settings.json` has the `PreToolUse`
   `Bash` matcher wired to a `sandbox-bypass-warn.sh` command
   and the `statusLine` command set to `sandbox-status-line.sh`.
3. Both hook scripts exist and are executable
   (`~/.claude/scripts/sandbox-bypass-warn.sh`,
   `~/.claude/scripts/sandbox-status-line.sh`).
4. The `claude-iso` shell function is sourced in `~/.bashrc` or
   `~/.zshrc`. Note whether `alias claude='claude-iso'` is set.
5. The pinned tool versions from
   `tools/agent-isolation/pinned-versions.toml` are installed at
   the pinned versions: `bubblewrap` (Linux only), `socat`
   (Linux only), `claude-code`.
6. The status-line prefix in this session shows `[sandbox]` (not
   `[NO SANDBOX]`).
7. Run `cat ~/.aws/credentials`, `echo $AWS_ACCESS_KEY_ID`, and
   `curl https://example.com` and confirm each is denied.
8. If a `ponymail` and/or `apache-projects` MCP server is
   registered in `~/.claude/settings.json` or
   `.claude/settings.json`, resolve its `apache/comdev` checkout
   from the `args` path and confirm it is on `main`
   (`git -C <root> rev-parse --abbrev-ref HEAD`) and not behind
   the last-fetched `origin/main`
   (`git -C <root> rev-list --count HEAD..origin/main`). These
   MCP servers track `main` by design — see
   `tools/ponymail/tool.md` → "Keeping the checkout current".
   Report only; do not fetch or pull.
```

Re-run either form after every Claude Code upgrade — the sandbox
semantics occasionally evolve and the framework maintainer wants
to know the day a denial silently turns into an allow.

## Keeping the setup updated

The secure setup has three independent moving parts that drift on
different schedules: the framework checkout (`.claude/settings.json`,
the wrapper / hook / status-line scripts under
`tools/agent-isolation/`, the pinned-versions manifest), the
pinned upstream tools (`bubblewrap`, `socat`, `claude-code`), and
any user-scope copies of helper scripts you installed under
`~/.claude/scripts/` or `~/.claude/agent-isolation/`. Keeping them
synchronised is a periodic operation, not a one-time install.

### Direct steps

1. **Framework checkout.** From your `magpie` clone,
   pull the latest:

   ```bash
   cd /path/to/magpie
   git pull --ff-only
   ```

   That carries forward updates to `.claude/settings.json` (new
   `denyRead` paths, `allowedDomains` entries, `ask`-list
   additions), the wrapper / hook / status-line scripts under
   `tools/agent-isolation/`, and the pinned-versions manifest.

2. **Pinned upstream tools.** Run the framework's check script,
   which compares your pins to upstream releases that have aged
   past the 7-day cooldown:

   ```bash
   tools/agent-isolation/check-tool-updates.sh
   ```

   For any candidate worth adopting, follow
   [Bumping a pinned version](#bumping-a-pinned-version) — the
   check script is side-effect-free and never edits the manifest
   itself.

3. **User-scope script copies.** If you installed any helpers
   user-scope (per
   [Syncing user-scope config across machines](#syncing-user-scope-config-across-machines)),
   diff each installed copy against the framework's
   source-of-truth and re-`cp` if it has drifted:

   ```bash
   diff ~/.claude/scripts/sandbox-bypass-warn.sh \
       /path/to/magpie/tools/agent-isolation/sandbox-bypass-warn.sh
   diff ~/.claude/scripts/sandbox-status-line.sh \
       /path/to/magpie/tools/agent-isolation/sandbox-status-line.sh
   diff ~/.claude/agent-isolation/agent-iso.sh \
       /path/to/magpie/tools/agent-isolation/agent-iso.sh
   ```

4. **comdev MCP checkouts.** If you registered the `ponymail`
   and/or `apache-projects` MCP servers, refresh their local
   `apache/comdev` checkout — these track `main`, not a pinned
   tag (comdev ships them as in-repo source with no releases):

   ```bash
   git -C /path/to/comdev fetch origin main
   git -C /path/to/comdev rev-list --count HEAD..origin/main   # behind?
   git -C /path/to/comdev pull --ff-only                       # if behind
   ( cd /path/to/comdev/mcp/ponymail-mcp && npm install )
   ( cd /path/to/comdev/mcp/apache-projects-mcp && npm install )
   ```

   See [`tools/ponymail/tool.md` → Keeping the checkout current](../../tools/ponymail/tool.md#keeping-the-checkout-current).

5. **Re-verify.** Re-run [Verification](#verification) above
   (either form) to confirm the denials still fire after the
   update.

### Via a Claude Code prompt

Paste the following into Claude Code at the start of a fresh
session in the tracker repo. Claude reports drift and upgrade
candidates, without modifying anything — you decide what to
apply:

```text
Update my secure-agent-setup install to the framework's latest.
Surface the diffs and the upgrade candidates; do not modify
anything — I will decide what to apply:

1. `cd` into my `magpie` clone and `git pull --ff-only`.
   Report what changed under `tools/agent-isolation/`,
   `.claude/settings.json`, and `secure-agent-setup.md`.
2. Run `tools/agent-isolation/check-tool-updates.sh` and surface
   any upgrade candidates for `bubblewrap`, `socat`, or
   `claude-code`, with the upstream changelog link for each. Do
   not bump the manifest.
3. Diff every user-scope copy under `~/.claude/scripts/` and (if
   present) `~/.claude/agent-isolation/` against the framework
   checkout. Report any drift, file by file.
4. For any `ponymail` / `apache-projects` MCP server registered in
   my settings, resolve its `apache/comdev` checkout from the
   `args` path, `git -C <root> fetch origin main`, and report the
   behind-count. When behind, print (do not run)
   `git -C <root> pull --ff-only` + `npm install` in the affected
   `mcp/<server>/` dir, plus the
   `github.com/apache/comdev/compare/<sha>...main` link. These
   servers track `main` by design — no manifest bump, no cooldown.
5. Re-run `cat ~/.aws/credentials`, `echo $AWS_ACCESS_KEY_ID`,
   `curl https://example.com` and confirm each is still denied.
   Note any newly-allowed call as a regression to investigate.
```

A good cadence for this prompt is once per Claude Code upgrade
or once a month, whichever comes first — and immediately after
adopting a pinned-version bump elsewhere in your fleet (so the
machines do not silently drift apart). Wire it into a recurring
agent via the framework's `/schedule` slash-command if you want
it to run unattended; the surfaced drift and upgrade candidates
land as a report you skim, not as auto-applied changes.

## What a session looks like

The four screenshots below cover the visible states an adopter
actually meets. Each is reproducible from this repo with the
setup steps written into the screenshot's caption.

**1. Sandboxed session — the steady state.**

![Sandboxed session: status-line prefix `[sandbox]` rendered green](../../assets/session-sandboxed.png)

The terminal footer renders `<model> [sandbox]` in green when
the active settings (project `settings.local.json` →
project `settings.json` → user-scope) set
`sandbox.enabled: true`. Bash subprocesses run inside
bubblewrap (Linux) or Seatbelt (macOS) and only see paths
listed in `sandbox.filesystem.allowRead`.

**2. Unsandboxed session — the failure mode this setup exists
to make obvious.**

![Unsandboxed session: status-line prefix `[NO SANDBOX]` rendered bold red](../../assets/session-no-sandbox.png)

`[NO SANDBOX]` in bold red means the active settings do not
enable the sandbox. The agent's Bash subprocesses run with full
access to the host filesystem. The
[Sandbox-state status line](#sandbox-state-status-line)
exists specifically so a session in this state cannot drift
unnoticed for hours.

**3. Sandbox-bypass attempt — the per-call signal.**

![Bold red SANDBOX BYPASS banner immediately above the Claude Code permission prompt](../../assets/sandbox-bypass-banner.png)

When the model invokes the Bash tool with
`dangerouslyDisableSandbox: true`, the
[Sandbox-bypass visibility hook](#sandbox-bypass-visibility-hook)
prints a bold red banner to stderr **before** the Claude Code
permission prompt renders. Approving the prompt at that point is
a deliberate act, not a skim-past click.

The hook fires on bypass *attempts*, not on sandbox denials — a
Bash call that simply hits the sandbox and fails (screenshot 4
below) will not trigger the banner, because the model never
requested bypass. To reproduce this state in a fresh session, ask
the model explicitly: *"use the Bash tool with
`dangerouslyDisableSandbox: true` to run `ls ~/.aws/`"*. The
explicit flag-name makes the next call a deterministic bypass
request — the banner renders, the prompt appears, and you can
deny at the prompt (the visual is what matters).

**4. Sandbox actually denying a read — proof it is real.**

![Sandboxed Bash call to `ls ~/Downloads` blocked by the runtime; surfaced as "read ~/Downloads (outside allowed read paths)" with an offer to retry with the sandbox disabled](../../assets/sandbox-blocks-read.png)

In a sandboxed session **without** bypass, a Bash call that
tries to touch a path outside `allowRead` is intercepted by
Claude Code's tool runtime *before* the bubblewrap (Linux) /
Seatbelt (macOS) subprocess actually fires. The runtime
surfaces the rule that was violated by name (here,
`read ~/Downloads (outside allowed read paths)`) and offers to
retry with the sandbox disabled — which would, in turn, route
through the bypass-warn hook from screenshot 3. The call never
reaches the OS-level enforcement layer; the runtime catches it
at the tool boundary, which is the cleaner failure mode.

**5. bubblewrap / Seatbelt in action — the OS layer the runtime
falls back to.**

![Sandboxed Bash call running `python3 -c 'os.listdir(os.path.expanduser("~/.aws/"))'`; the inner syscall fails with PermissionError: [Errno 1] Operation not permitted: '/Users/jarekpotiuk/.aws/'](../../assets/sandbox-os-level-block.png)

When the eventual filesystem access is **opaque to lexical
analysis** — here, a path constructed inside a `python3 -c`
one-liner via `os.path.expanduser`, which the runtime cannot
parse without actually executing it — the runtime hands the
Bash subprocess off to bubblewrap (Linux) / Seatbelt (macOS).
The OS sandbox then catches the violation at the syscall
boundary. The visible result is the underlying OS error: on
macOS Seatbelt, `[Errno 1] Operation not permitted` (above);
on Linux bubblewrap, `[Errno 2] No such file or directory`,
because the path is not even mounted into the subprocess's
namespace.

Claude Code's runtime *also* recognises the denied path
post-hoc from the traceback and refuses to retry with bypass —
visible as the "I am **not** going to propose bypassing the
sandbox for this" narration below the python error. The two
layers are stacked deliberately: the runtime is the cheap,
predictable check (screenshot 4); bubblewrap/Seatbelt is the
unbypassable backstop for everything the runtime cannot
lexically pre-parse (this screenshot). Either layer alone has
gaps; together they are the actual sandbox.

## See also

- [`secure-agent-internals.md`](secure-agent-internals.md) — the
  design and mechanism behind the install steps in this document:
  threat model, the three-layer defence, what `sandbox.enabled`
  actually directs the Bash tool to do, how bubblewrap (Linux)
  and Seatbelt (macOS) enforce the policy at the OS layer, the
  SNI / DoH blind spot, the feedback-mechanism layering, and the
  residual risks the setup does not eliminate.
- [`sandbox-troubleshooting.md`](sandbox-troubleshooting.md) —
  catalog of known sandbox-shaped failure modes (SSH agent /
  Yubikey unreachable, test port-bind blocked, docker / podman
  socket denied) with symptom → root cause → settings.json fix
  for each. Grep here first when a normal-looking operation fails
  inside the sandbox.
- [`AGENTS.md`](../../AGENTS.md) — placeholder convention used in skill
  files (`<tracker>`, `<upstream>`, `<security-list>`, …).
- [`README.md`](../../README.md) — framework overview and how the
  secure setup fits the broader skill workflow.
