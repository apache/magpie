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
  **Notes**. Seven entries today: SSH agent / Yubikey, signed commit
  failing before any touch (`gpg.format=ssh` key unreadable), signed
  commit failing with `cannot exec` of the touch-overlay wrapper
  (`gpg.ssh.program` under the read-denied `~/.claude/scripts/`),
  localhost port bind, Docker / Podman socket, `/tmp` read-only, and
  `gh` inside the sandbox (TLS `OSStatus -26276` / `HTTP 401`).
- `tools/agent-isolation/sandbox-error-hint.sh` — a Claude Code
  `PostToolUse` hook on the `Bash` matcher. Scans the tool's stdout +
  stderr for the catalogued symptom strings and, on a match, prints
  one `[sandbox-hint] …` line to stderr naming the catalog anchor,
  exiting 1 so the line reaches the model and the user. Tests under
  `tools/agent-isolation/tests/test_sandbox_error_hint.py`.
- Skill `setup-isolated-setup-doctor` — live, read-only probes, one per
  catalog entry (`## The 6 probes`), each reporting ✓ / ✗ / ⊘ / ⚠ with
  the command and its output as evidence, and each mapping ✗ to the
  matching catalog anchor. The `gh` probe runs `gh` through `sh -c` so
  the `excludedCommands` exemption cannot apply to the probe itself,
  which shows what an un-excluded `gh` does on this machine, then
  checks that `"gh *"` is configured.
- Skill `setup-isolated-setup-verify` — static checks of the installed
  configuration (`## The 11 checks`): settings shape, hook wiring, hook
  scripts, wrapper, pinned versions, status line, denial canaries,
  project-root grant, the vetted-ops split, the touch overlay and
  signing key (check 10), and (check 11) the `gh` exclusion. Mirrors the "Via a Claude Code prompt" checklist in
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
  is drift.
- **Symptom strings are literal.** Entries quote the exact error text
  so a grep into the catalog finds them; the hook matches those same
  strings with anchored, specific regexes. False-positive hints are
  noise, so the pattern set errs on the side of missing a variant.
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
  `cd …` or `gh …`. A pipe, a `$(…)` substitution, a loop, or any file
  redirection (including `> /dev/null`) keeps the whole invocation in
  the sandbox, where `gh` fails with `x509: OSStatus -26276` on macOS
  because Go's TLS verification goes through Security.framework and
  Seatbelt blocks the trustd / keychain mach services. Nothing on the
  Go side works around that (no fallback roots in the Homebrew build,
  `SSL_CERT_FILE` ignored on darwin). The catalog entry carries the
  measured shape table, the `gh tofile` alias that moves a redirection
  inside `gh` (guarded to `$PWD` and the Claude scratch tree, because
  the alias runs unsandboxed), and the upstream report
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
- Non-Claude harnesses: the doctor and verify route Codex and Gemini to
  their adapters before the Claude-specific probes; the hook is a
  Claude Code `PostToolUse` contract.

## Acceptance criteria

1. Each catalog entry has the four sections, a literal symptom, and a
   matching `match … hint=` branch in the hook whose anchor resolves
   (lychee checks the docs; the hook's anchors are asserted by its
   tests).
2. The hook exits 1 with a `[sandbox-hint]` line for every catalogued
   signature, exits 0 with no output on benign output, on a non-Bash
   tool, and on invalid JSON.
3. The doctor has one probe per catalog entry and the verify skill has
   a check for every static setting an entry depends on; both are
   read-only and both link the catalog anchor on ✗.
4. The `gh` entry, probe and check agree on the invocation-shape rule
   and cite the upstream issue.

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

- The invocation-shape rule is measured on macOS / Claude Code 2.1.278
  and will change when anthropics/claude-code#95532 is fixed; the
  catalog entry, the probe text and the verify check all need the same
  edit on that day.
- Linux / bubblewrap is not measured for the `gh` entry: Go uses its
  own root store there, so the TLS half may not apply while the keyring
  half still can.
