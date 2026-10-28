<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

---
title: Sandbox diagnostics — catalog, hint hook, doctor, verify
status: stable
kind: feature
mode: infra
source: >
  MISSION.md § Privacy, security and supply-chain integrity ("Layered
  sandbox by default") and docs/setup/secure-agent-setup.md § Sandbox-
  error hint hook. Implemented in docs/setup/sandbox-troubleshooting.md,
  tools/agent-isolation/sandbox-error-hint.sh, and the
  setup-isolated-setup-doctor / setup-isolated-setup-verify skills.
acceptance:
  - Every sandbox-shaped failure the framework knows about has exactly
    one catalog entry, in the symptom / root cause / fix / notes shape,
    and the catalog is the single source of truth for the remediation.
  - The hint hook recognises every catalogued symptom string and points
    at that entry; it never changes the tool call's outcome and never
    fires on benign output.
  - The doctor probes every catalogued failure mode live and read-only;
    the verify skill checks the static configuration each entry relies
    on; neither edits settings.
  - A gh call that ran inside the sandbox is recognised as such, with
    the invocation-shape rule that decides whether the exclusion
    applied.
---

# Sandbox diagnostics — catalog, hint hook, doctor, verify

## What it does

Makes an over-restrictive sandbox self-explaining. A correct sandbox
denies credentials and unknown hosts; the same denials also break
legitimate workflows in ways that look like unrelated bugs — an SSH
agent that "refuses", a Docker daemon that is "not running", a `gh`
that "cannot verify" a valid certificate. This area turns each of
those into a catalogued failure mode with three discovery surfaces:
the catalog entry itself, a just-in-time hint printed next to the
error, and two skills that probe or verify the setup on demand.

## Where it lives

- `docs/setup/sandbox-troubleshooting.md` — the catalog. One entry per
  failure mode, each with **Symptom** (the literal error text),
  **Root cause** (which sandbox layer blocks it and why), **Fix** (a
  settings widening with per-entry rationale, or — for the `gh` entry —
  an invocation-shape rule, because there is nothing to widen), and
  **Notes**. Fourteen entries today: SSH agent / Yubikey, signed commit
  failing before any touch (`gpg.format=ssh` key unreadable), signed
  commit failing with `cannot exec` of the touch-overlay wrapper
  (`gpg.ssh.program` under the read-denied `~/.claude/scripts/`),
  signed commit failing with the agent refusing and the overlay never
  appearing (the touch overlay's runtime-state directory denied —
  `/tmp` on a platform with no `$XDG_RUNTIME_DIR`, before the
  per-user cache-dir fallback), localhost port bind, Docker / Podman
  socket, `/tmp` read-only, `gh` inside the sandbox (TLS
  `OSStatus -26276` / `HTTP 401`), `prek` or `uv` not found or unable
  to write its cache (the home-directory dev-tool paths not granted in
  the worktree's `settings.local.json`, #1359), `uv python install` or
  `uv tool install` failing under `~/.local/share/uv/` (deliberately
  read-only to the sandbox, since hooks and excluded commands run the
  interpreters there outside it; the fix is to run the install from a
  terminal, #1785), git hooks silently
  skipped for sandboxed commits (whole-user `core.hooksPath` under the
  read-denied home, #1364), and reads of `/tmp/claude-<uid>` asking for
  approval every time (`permissions.blockReadsOutsideWorkingDirectories`
  on and the directory not a working directory, #1418), every Bash call
  failing with `bwrap: Can't create file … Read-only file system` (an
  `allowRead` parent of an `allowWrite` path makes bubblewrap mount it
  read-only, #1809), and `git status` listing files nobody created
  (`.mcp.json`, `.bash_profile`: the character-device placeholders
  bubblewrap mounts over denied paths, #1809).
  The Docker / Podman entry also covers the container gateway's policy
  refusals (BuildKit, a socket bind-mount, an untyped `docker inspect`):
  a tool that drives the docker CLI may hide the 403 body or report only
  `unable to upgrade to h2c, received 403`, and the expected behaviour is
  to report the refusal, never to route around the gateway (#1810).
- `tools/agent-isolation/sandbox-error-hint.sh` — a Claude Code
  `PostToolUse` hook on the `Bash` matcher. Scans the tool's stdout +
  stderr for the catalogued symptom strings and, on a match, prints
  one `[sandbox-hint] …` line to stderr naming the catalog anchor,
  exiting 1 so the line reaches the model and the user. Tests under
  `tools/agent-isolation/tests/test_sandbox_error_hint.py`.
- Skill `setup-isolated-setup-doctor` — live, read-only probes
  (nine, `### Probe 1` to `### Probe 9`, under `## The probes`), each reporting ✓ / ✗ / ⊘ / ⚠ with the command
  and its output as evidence, and each mapping ✗ to the matching
  catalog anchor. Each probe is a deterministic, side-effect-free
  script, `scripts/probe-<n>-<slug>.sh`, printing one
  `PROBE: <slug> → ✓|✗|⊘|⚠ (<evidence>)` line the skill's
  interpretation tables match on; the commands stay out of the
  skill body, so they cost no context and can be run and tested on
  their own (#1336). A probe holds a command's output in a variable,
  never a file: `/tmp` is read-only inside the sandbox, and a failed
  redirection skips the command and exits 1, which probe 1 once read as
  "agent reachable, no identities" for every agent (#1770). Probes 1, 3
  and 5 have tests under the skill's `tests/` that run each script
  against fake binaries (#1770, #1776). Probe 3 trusts a gateway socket
  only on the gateway's own read-only `status` report, taken from the
  pinned snapshot, the framework tree, or else the operator install at
  `~/.claude/scripts/container-gateway/src` (a marketplace install); with
  no report it fails as "gateway status unavailable" rather than "not
  running", and a `status` that exits 2 without a report as "refused the
  run directory" (#1815). Probe 7 checks that `prek` and `uv` run inside
  the sandbox and can write `~/.cache`, telling a missing grant (⚠)
  from a tool that is not installed (⊘) by reading the worktree's
  `settings.local.json`, since a read-denied `~/.local/bin` looks the
  same as an absent one (#1362). Probe 8 looks at the global
  `core.hooksPath` directory from inside the sandbox: skip when none
  is set, fail when the directory or a hook's symlink target is
  unreadable, warn when it holds none of the common hooks (#1364). Probe 9, only
  when `permissions.blockReadsOutsideWorkingDirectories` is on, checks
  that `/tmp/claude-<uid>` is a working directory as a resolved path, and
  fails (✗, read block or not) when `$HOME/.claude/magpie` is one, since
  that makes the vetted-ops checkout sandbox-writable: ⚠ for a missing path or for a glob entry
  such as `/tmp/claude-*`, which is listed but never matched, and ⊘ when
  the block is off, `HOME` is unset, or the entries are absent from the
  readable project files while user-scope settings are unreadable from
  the sandbox (#1418). The `gh` probe runs `gh` through `sh -c` so
  the `excludedCommands` exemption cannot apply to the probe itself,
  which shows what an un-excluded `gh` does on this machine, then
  checks that `"gh *"` is configured.
- Skill `setup-isolated-setup-verify` — static checks of the installed
  configuration (numbered 1–17 under `## The checks`; 13, 14 and 17
  optional): settings shape, hook wiring, hook scripts, wrapper,
  pinned versions, status line, denial canaries, project-root grant
  (check 8 — also the dev-tool paths, whose absence is ⚠ not ✗, and in
  whole-user scope the shared hook directory probed from inside the
  sandbox, whose unreadability is ✗), the vetted-ops split, the touch
  overlay and signing key (check 10), the `gh` exclusion (check 11),
  the container gateway (check 12; 12a accepts the hooks in
  `~/.claude/settings.json` or `~/.claude/settings.local.json`, fails a
  registered absolute path that does not exist on this machine, and marks
  one in a `settings.json` linked into a synced config repo as ◐, #1797),
  the eval-harness exclusion
  (check 13, if installed), the adversarial-review exclusion (check 14,
  if the `magpie-adversarial-review` plugin is installed: the
  `excludedCommands` entry on the fixed `~/.claude/magpie/adversarial-review`
  path, ⚠ when missing and ✗ in the older versioned-glob form; the
  plugin-cache and `~/.claude/magpie/**` `Edit` denies, ✗ when missing;
  no `allow` rule, ✗ when one matches, #1371; and 14d, the link resolving
  into the installed plugin, ⚠ when broken and ✗ when it is a real file
  or directory or points anywhere else, #1578),
  and the working directories under the read block (check 15: the two
  resolved paths in the worktree's `settings.local.json`, ⚠ when missing
  or glob-only, ⚠ when they sit in committed or synced user-scope
  settings instead, #1418), and the never-prompt shape for read-only
  vetted ops (check 16: every `vetted-op-read` allow form including the
  absolute-`$HOME` base, each with its exclusion, no ask rule matching a
  `vetted-op-read` command, the read block off,
  the three vetted-ops `Edit` denies; each ✗ when it fails), and the roborev exclusion (check 17, if
  `roborev` is on `PATH`: the `roborev *` exclusion, ⚠ when missing; no
  `allow` for any roborev command, ✗ unless the catch-all `ask` covers it;
  the `Bash(roborev *)` ask, ✗ when missing; `Edit` denies on
  `.roborev.toml` and `~/.roborev/**`, ✗ when missing; an `allowWrite`
  covering `~/.roborev/`, ✗ in every case; step B.2's `unix://` socket and
  `allowUnixSockets` entry when `~/.roborev/` is opened, ⚠ when
  incomplete; a roborev `post-commit` hook in a shared
  whole-user hooks directory, ✗, and an operator-unconfirmed
  `.roborev.toml` under the hook, ⚠; roborev agent hooks or MCP servers
  in the harness, ⚠). Check 9 also fails a vetted-ops rule that
  spells the versioned plugin-cache path with a `*`, since the rule must
  name `~/.claude/magpie/vetted-ops` (#1406).
  Checks are written to catch false passes (#1808): check 1 evaluates the
  merged project, project-local and user settings, requires the home
  `denyRead` entry, and names the file each key came from; check 7a probes
  credential paths with `test -r` / `stat`, never `cat`, and check 7b lists
  variable names only and warns on an IDE-launched session that never went
  through `claude-iso`; checks 5, 10a and 13c report unchecked when the
  pre-flight finds no framework checkout; check 10's overlay sub-checks
  apply only to a hardware key (a card `gpg --card-status` finds, whatever
  `gpg.format` is); and check 12e fails `allowAllUnixSockets` on Linux
  without the host-socket `denyRead` cover, whether or not a container
  runtime is present (#1809).
  Verify and doctor both say how to recognise the sandbox's `/dev/null`
  placeholders and to take host state from git or the user.
  The conditional checks —
  9, 10, 12, 13, 14, 17 and check 8's whole-user branch — live in
  `conditional-checks.md`; the
  body keeps each one's condition and its **n/a** answer, so a run
  that meets none of the conditions reads none of them (#1334).
  Mirrors the "Via a Claude Code prompt" checklist in
  `docs/setup/secure-agent-setup.md`, which is the canonical list.
- `docs/setup/secure-agent-setup.md` § Sandbox-error hint hook — the
  signature → anchor table, install recipe, and trade-offs.

## Behaviour & contract

- **The catalog is the source of truth.** The hook, the doctor and the
  verify skill are discoverability layers over it. A new failure mode
  lands as a catalog entry first; the same change adds a `match … hint=`
  branch to the hook, a probe to the doctor, and — where the entry
  relies on a static setting — a check to the verify skill. A catalog
  entry with no hook branch, or a hook branch with no catalog anchor,
  is drift. The one sanctioned exception is a failure that prints
  nothing: git skips a hook directory it cannot see without a word, so
  the git-hooks entry has no symptom string to match and is reached
  through the doctor's probe 8 and verify check 8 instead, and says so
  in its **Notes**. The working-directories entry is the second: its
  approval prompt comes before any command runs, so the hook never sees
  it, and it is reached through doctor probe 9 and verify check 15.
- **Symptom strings are literal.** Entries quote the exact error text
  so a grep into the catalog finds them; the hook matches those same
  strings with anchored, specific regexes. False-positive hints are
  noise, so the pattern set errs on the side of missing a variant.
  Branch order matters when two entries' error text overlaps: the
  touch-overlay runtime-state branch is checked before the SSH-agent
  branch because both end in `agent refused operation`, and the more
  specific pattern has to win or the reader is sent to the entry about
  an unreachable key when the key was never the problem.
- **The hook never changes the outcome.** It exits 0 silently on no
  match, on a non-`Bash` tool, on unparsable JSON, or on any unexpected
  envelope shape (fail-open), and exits 1 — never 2 — on a match, so
  the tool call that already ran is not retroactively blocked.
- **Doctor and verify are read-only.** They report and link; the
  settings edit is the operator's, made outside the skill. A probe that
  cannot run because a prerequisite is absent (no `docker` on `PATH`,
  no `SSH_AUTH_SOCK`, no `gh`) reports ⊘, not ✗.
- **Every probe runs even after an early failure**, so one report lists
  every restriction rather than one per re-run.
- **The `gh` exclusion rule.** `sandbox.excludedCommands: ["gh *"]`
  exempts a `gh` call only when every part of the Bash invocation is
  `cd …` or `gh …`. A pipe, a `$(…)` substitution, a loop, any file
  redirection (including `> /dev/null`), or a backtick anywhere in the
  command string, even escaped or single-quoted (#1384), keeps the whole
  invocation in the sandbox, where `gh` fails with `x509: OSStatus -26276` on macOS
  because Go's TLS verification goes through Security.framework and
  Seatbelt blocks the trustd / keychain mach services. Nothing on the
  Go side works around that (no fallback roots in the Homebrew build,
  `SSL_CERT_FILE` ignored on darwin). The catalog entry carries the
  measured shape table, the `gh tofile` alias that moves a redirection
  inside `gh` (guarded to `$PWD` and the Claude scratch tree, because
  the alias runs unsandboxed), the rule to pass Markdown titles and
  bodies from a file (`--body-file`, or `--input` for `gh api`) because
  an inline Markdown body carries backticks, and the upstream report
  anthropics/claude-code#95532 for the redirection regression.
- **The `gh` ask-rule rule.** `permissions.ask` names gh write
  subcommands one by one and never a catch-all `Bash(gh *)`: Claude
  Code evaluates deny, then ask, then allow, and a matching ask rule
  prompts even when a more specific allow rule also matches, so the
  catch-all would turn every read-only gh call into a prompt. The verify
  skill fails on a catch-all in any scope; the doctor's gh probe warns
  on it.
- **User-scope install.** The hook is meant for `~/.claude/settings.json`
  so it fires in every project on the host; the framework's own
  `.claude/settings.json` does not wire it.

## Out of scope

- The sandbox itself — profiles, allowlists, the clean-env wrapper, the
  action guard — is `agent-isolation-sandbox.md`.
- Installing or updating the secure setup (`setup-isolated-setup-install`
  / `-update`); this area only diagnoses what is installed.
- Applying a settings widening from a skill. Every fix is the
  operator's edit, and the doctor says so explicitly.
- Non-Claude harnesses: the doctor and verify route Codex and Antigravity to
  their adapters before the Claude-specific probes; the hook is a
  Claude Code `PostToolUse` contract.

## Acceptance criteria

1. Each catalog entry has the four sections, a literal symptom, and a
   matching `match … hint=` branch in the hook whose anchor resolves
   (lychee checks the docs; the hook's anchors are asserted by its
   tests), except the two entries that print nothing the hook could
   see (git hooks skipped, working-directory prompts), which name their
   probe and check in **Notes** instead.
2. The hook exits 1 with a `[sandbox-hint]` line for every catalogued
   signature, exits 0 with no output on benign output, on a non-Bash
   tool, and on invalid JSON.
3. The doctor has one probe per catalog entry and the verify skill has
   a check for every static setting an entry depends on; both are
   read-only and both link the catalog anchor on ✗.
4. The `gh` entry, probe and check agree on the invocation-shape rule
   and cite the upstream issue.
5. Verify check 14 fails the versioned-glob adversarial-review exclusion,
   requires the `Edit(~/.claude/magpie/**)` deny, and reports a broken
   `~/.claude/magpie/adversarial-review` link as ⚠ and a non-symlink or a
   link outside the installed plugin as ✗ (#1578).

## Validation

```bash
uv run --project tools/agent-isolation --group dev python -m pytest \
  tools/agent-isolation/tests/test_sandbox_error_hint.py
bash -n tools/agent-isolation/sandbox-error-hint.sh
prek run lychee --files docs/setup/sandbox-troubleshooting.md docs/setup/secure-agent-setup.md
# every hook anchor must exist as a heading in the catalog
python3 - <<'PY'
import re, sys
doc = open("docs/setup/sandbox-troubleshooting.md").read()
hook = open("tools/agent-isolation/sandbox-error-hint.sh").read()
anchors = set(re.findall(r"\$\{doc_path\}#([a-z0-9-]+)", hook))
toc = set(re.findall(r"\]\(#([a-z0-9-]+)\)", doc))
missing = anchors - toc
print("hook anchors missing from catalog:", sorted(missing) or "none")
sys.exit(1 if missing else 0)
PY
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
  tools/skill-evals/evals/setup-isolated-setup-doctor/
PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner \
  tools/skill-evals/evals/setup-isolated-setup-verify/
```

## Known gaps

- The doctor runs 9 probes over the catalog's 12 entries: the two
  touch-overlay entries (`cannot exec` of the wrapper, and the
  runtime-state directory) have no live probe. Verify check 10 covers
  the wrapper's `allowRead` grant statically; the runtime-state entry
  is reached only through the hint hook.
- The `uv python install` / `uv tool install` entry (#1785) has neither a
  hint-hook branch nor a doctor probe, and has no **Notes** section at all
  (acceptance 1's four sections), so it breaks the "catalog entry first,
  hook branch beside it" rule; the session-start hook's grant cleanup and `isolated-setup-update`'s
  must-fix report are its only other surfaces.
- Probes 2, 4 and 6–9 still have no script tests.
- A command that spells a working directory with a literal `~` still
  prompts under the read block even when the directory is listed. For
  the vetted-ops commands the setup closes this by requiring the read
  block off (verify check 16); for any other such command it stays open.

- The invocation-shape rule is measured on macOS / Claude Code 2.1.278
  and will change when anthropics/claude-code#95532 is fixed; the
  catalog entry, the probe text and the verify check all need the same
  edit on that day.
- Linux / bubblewrap is not measured for the `gh` entry: Go uses its
  own root store there, so the TLS half may not apply while the keyring
  half still can.
