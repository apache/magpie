<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The conditional checks: 9, 10, 12, 13, 14, 15, 16 and 17

Eight of the checks, and check 8's whole-user branch, only apply when the install has the feature they
cover. `SKILL.md` carries the condition and reports **n/a** without
reading this file; read the section for a check whose condition holds.

## Check 8 — whole-user scope detection

   **Scope detection (per-project vs whole-user).** The install
   skill offers two scopes. Detect which one is in effect:

   ```bash
   git config --global --get core.hooksPath
   ```

   If the output equals `$HOME/.claude/git-hooks` (or its tilde-
   resolved form), the operator is in **whole-user** scope.
   Install Step P.0b offers two flavours of it, and the shape of
   `~/.claude/git-hooks/` tells them apart:

   - **Simple flavour** — `post-checkout` is a regular file, a copy
     of `tools/agent-isolation/git-global-post-checkout.sh`.
   - **Dispatcher flavour** — `post-checkout` (and every other hook
     name) is a symlink to `git-hook-dispatcher.sh` in the same
     directory, a copy of `tools/agent-isolation/git-hook-dispatcher.sh`.
     The dispatcher supersedes the standalone post-checkout script,
     so do **not** compare `post-checkout` against
     `git-global-post-checkout.sh` here; read the hook-name symlinks
     as the installed shape, not as drift.

   Resolve `post-checkout` (`readlink -f`) and check the script it
   lands on:

   - ✓ if it exists, is executable, and matches its own framework
     source (`git-global-post-checkout.sh` for the simple flavour,
     `git-hook-dispatcher.sh` for the dispatcher flavour).
   - ⚠ if the hook is missing or non-executable — the `core.hooksPath`
     pointer is set but the hook content is gone. Remediation:
     re-run `setup-isolated-setup-install` Step P.3-whole-user
     (simple) or Step P.3b-whole-user (dispatcher),
     or `setup-isolated-setup-update` to refresh the script copy.
   - ⚠ if the script drifted from its framework source-of-truth —
     surface the diff, propose `setup-isolated-setup-update`.
   - ✗ if the hook dir is not readable **from a sandboxed Bash**:
     `git hook run --ignore-missing post-checkout` succeeds either
     way, so probe with `test -r ~/.claude/git-hooks/post-checkout`
     and `test -r "$(readlink -f ~/.claude/git-hooks/post-checkout)"`
     run inside the sandbox. Unreadable means every git command the
     agent runs skips every hook silently — `pre-commit` and `prek`
     included. Remediation: the user-scope `allowRead` grant in
     [`docs/setup/sandbox-troubleshooting.md` → Git hooks silently skipped for commits made inside the sandbox](../../../../docs/setup/sandbox-troubleshooting.md#git-hooks-silently-skipped-for-commits-made-inside-the-sandbox),
     applied by the user.
   - **Loud reminder** (every run, not a ✗), by flavour:
     - *Simple:* surface a one-line note that per-repo
       `.git/hooks/*` are inert across the host (per [`docs/setup/secure-agent-setup.md` → *Per-project vs whole-user scope*](../../../../docs/setup/secure-agent-setup.md#per-project-vs-whole-user-scope)).
       This is informational, not a failure — the operator chose it
       deliberately during install. Surface so a future self
       debugging "why didn't my pre-commit fire" recognises the
       cause.
     - *Dispatcher:* surface instead that per-repo `.git/hooks/*`
       still fire, because the dispatcher chains to each repo's own
       hook (per [`docs/setup/secure-agent-setup.md` → *Whole-user with the per-repo dispatcher*](../../../../docs/setup/secure-agent-setup.md#whole-user-with-the-per-repo-dispatcher)).
       Do not report them as inert; that is the simple flavour's
       cost, which this flavour exists to remove.

   - ⚠ for each repository that sets its own `core.hooksPath`
     (`git config --local --get core.hooksPath`, often left by a
     `prek install`): it overrides the global one, so git never runs the
     dispatcher there, and neither its post-checkout allowlist sync nor its
     prek-home switch happens. magpie-setup's session-start hook removes
     a value pointing at the repository's own `.git/hooks` by itself; for
     any other, the remediation is `git config --local --unset
     core.hooksPath` in that repository, run by the operator; the
     dispatcher still chains to the repository's own `.git/hooks/`.

   If `core.hooksPath` is unset (or points elsewhere), the
   operator is in **per-project** scope (the default). No further
   sub-check needed — the per-project mode is fully covered by
   the static + live-probe checks above.

## Check 9 — the vetted-ops split and exclusion

9. **The vetted-ops split and exclusion.** Only meaningful when the
   adopter routes forge operations through the `vetted-ops`
   dispatcher; if the repo has no
   `.apache-magpie-overrides/tools/vetted-ops/config.toml`, no personal-layer
   `tools/vetted-ops/config.toml` and no `vetted-op` rule, report **n/a** and move on. With the sandbox not
   enabled, report **n/a** too: install Step V skips the bypass
   without it. A `vetted-op-read` allow rule or exclusion present
   while the sandbox is off is ✗ — the bypass without its confinement.

   **9a — which dispatcher is allowlisted.** This is the check that
   matters. `permissions.allow` may contain `vetted-op-read` and
   must **not** contain `vetted-op`. Finding the write dispatcher in
   `allow` is ✗ and worth stopping the report to say so plainly: it
   grants every operation in the catalogue, including `issue-close`
   and every `pr-review-*`, with no confirmation. It looks safe
   because the policy declares a read-only caller — but `--caller`
   is an argv string chosen by whoever runs the command, so the
   caller name in an example constrains nothing. Verify by
   inspection, not by trusting a comment next to the rule.

   `vetted-op` in `ask` (or absent) is correct.

   `vetted-op-tracker` belongs in `ask` and in
   `sandbox.excludedCommands`, never in `allow` — it writes. Its
   exclusion is correct: it refuses every operation except the
   tracker rollup / body-field procedures before reading the policy,
   and their runner refuses any `gh` call outside `repos/<tracker>/`.
   `vetted-op` itself in `sandbox.excludedCommands` is ✗ — it would
   run the whole write catalogue unsandboxed.

   A `vetted-op` rule, in `allow` or in `sandbox.excludedCommands`,
   that spells the versioned plugin-cache path with a `*`
   (`…/magpie-vetted-ops/*/tools/vetted-ops …`) is also ✗. The `*`
   matches spaces too, so it approves — and runs unsandboxed — a
   command with extra `uv` options spliced in where the version
   sits. The rule must name `~/.claude/magpie/vetted-ops`.

   **9b — the exclusion.** `permissions.deny` covers every surface,
   each with an `Edit` rule:

   - `~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/**` —
     the operation catalogue. The read dispatcher's `allow` rests on
     its shape, so an editable catalogue dissolves that `allow`.
   - `~/.claude/magpie/**` — the fixed path the rules name, which
     the plugin's `SessionStart` hook points at the catalogue.
   - `.apache-magpie-overrides/tools/vetted-ops/**` — the policy.
   - `//**/.git/**/apache-magpie/tools/vetted-ops/**`, `//**/.svn/apache-magpie/tools/vetted-ops/**`
     and `//**/.apache-magpie-local/tools/vetted-ops/**` — the policy in a
     maintainer's personal layer.

   Any one missing is ✗. One `Edit` rule per surface is the whole
   coverage — in `permissions`, `Edit(path)` binds every file-editing
   tool, and a `Write(path)` rule is not matched by the file
   permission check at all. A `Write(…)` line beside an `Edit(…)` is
   therefore a note, not a pass: it protects nothing and reads as a
   second layer that is not there.

   Report two things as **notes**, not failures. The policy's
   protection stops at the agent's editing tools — it sits in the
   sandbox-writable project root, so a Bash-level write is not
   covered; this is survivable only because the read dispatcher
   refuses writes without consulting policy. And per-caller scoping
   is least-privilege, not isolation: if the report describes it as
   a boundary, correct that, because it is the misreading that
   produces a `vetted-op` `allow` in the first place.

   The 9b rules are also required by check 16, the never-prompt
   imperative for `vetted-op-read`: they are what makes allowing
   that dispatcher without a prompt safe.

## Check 10 — hardware-key touch overlay and the signing key

10. **Hardware-key touch overlay and the signing key.** Only when
    commits are signed (`git config --get commit.gpgsign` is
    `true`) or a remote is reached over ssh through gpg-agent
    (`SSH_AUTH_SOCK` names its socket); otherwise report **n/a**.
    10c applies to any ssh-format signing key. 10a, 10b, 10d and 10e
    apply only to a hardware key and are **n/a** otherwise. A
    hardware key is an `sk-` public key (`sk-ssh-ed25519@openssh.com`,
    `sk-ecdsa-sha2-nistp256@openssh.com`), or a card that holds the
    signing key or the key a remote authenticates with, shown by any
    of: (a) `gpg.format=ssh`: the `ssh-add -L` line whose key equals
    `user.signingkey` has a `cardno:` comment; (b) OpenPGP format:
    `gpg --list-secret-keys --with-colons <key>`, where `<key>` is
    `user.signingkey` (unset: the committer email, as git picks it; do
    not list every secret key), shows a card serial in field 15 (not
    `+`, a software key, or `#`, an offline stub) on a record whose
    field 12 contains a lowercase `s` (the signing-capable key;
    uppercase letters on the primary are the whole key's capabilities;
    a card holding only the auth or encryption subkey does not count),
    or `gpg --card-status`'s signature key fingerprint matches; (c)
    the remote is reached over ssh through gpg-agent and the agent key
    offered has a `cardno:` comment (this is the key the remote
    authenticates with, not the signing key). A card holding only
    unrelated keys does not count. Ssh-format signing through
    gpg-agent uses the card's `aut` slot and shows a plain
    `ssh-ed25519` or `ssh-rsa` key. The user runs these from their own
    terminal when the sandbox cannot reach the agent or device. A
    plain software key, even beside a plugged-in card, needs no touch,
    so the overlay has nothing to show.
    Five sub-checks, plus a note for a hardware key: the key's own touch policies
    (`ykman openpgp info`, run by the user — the sandbox does not
    see the device) are what make the overlay matter; report them
    as seen, and suggest `cached` on the slot that signs where it is
    `Off` (`sig` for OpenPGP signing, `aut` with `gpg.format=ssh`) and,
    with OpenPGP signing, `off` on `aut` where it carries a policy —
    a transport touch is a prompt on every fetch and pull — per
    [`docs/setup/secure-agent-setup.md` → Hardware security keys](../../../../docs/setup/secure-agent-setup.md#hardware-security-keys--signing-and-authentication).

    **10a — wiring and scripts.** User-scope `~/.claude/settings.json`
    has a `PreToolUse` `Bash` hook running
    `gpg-touch-overlay.sh arm` and a `gpg-touch-overlay.sh disarm`
    `Bash` hook on each of `PostToolUse`, `PermissionDenied` and
    `PostToolUseFailure`. A missing `PostToolUse` disarm is ✗; a
    missing `PermissionDenied` or `PostToolUseFailure` disarm is ⚠
    with the reason — the overlay still works, but a rejected or
    failed command leaves its watcher armed until `MAX_WAIT`, and any
    unrelated signature in that window raises the window with nothing
    pending. The scripts must also be present and
    executable: `~/.claude/scripts/gpg-touch-overlay.sh`, plus
    `gpg-touch-overlay-window.py` (Linux) or
    `gpg-touch-overlay-window-macos.py` (macOS) beside it. Compare
    each against `tools/agent-isolation/` in the framework checkout:
    a copy that differs is ⚠ (stale — the watcher's behaviour has
    changed more than once, and a stale copy fails silently), a
    missing file or hook is ✗. With no framework checkout, report
    the comparison as unchecked, not ⚠. Install steps and rationale:
    [`docs/setup/secure-agent-setup.md` → Hardware-key touch overlay](../../../../docs/setup/secure-agent-setup.md#hardware-key-touch-overlay).

    **10b — the window can draw.** The window needs a toolkit —
    PyGObject or `zenity` on Linux, a python with Tk 8.6 or newer
    on macOS — and the script carries its own probe:
    `~/.claude/scripts/gpg-touch-overlay.sh _gui_available` (exit 0
    means a window can be shown). It must run **outside the
    sandbox**, where the hook itself runs: from inside the sandbox
    no display or window server is reachable, so an in-sandbox run
    says nothing. Do not reach for the bypass; surface the command
    for the user to run with the `!` prefix and read the exit code
    back. Non-zero is ✗, naming the platform's toolkit.

    **10c — the signing key is readable in the sandbox.** Only with
    `git config --get gpg.format` = `ssh`; otherwise n/a. The file
    `git config --get user.signingkey` names must open from a
    sandboxed Bash: `head -c 1 "$(git config --get user.signingkey)"
    >/dev/null`. `Operation not permitted` / `Permission denied` is
    ✗: the sandbox denies `~/.ssh/` wholesale and that one public
    key needs its own `sandbox.filesystem.allowRead` entry. Without
    it every commit fails before the key is asked for a touch, and
    the overlay — which shows once `ssh-keygen` has blocked on the
    key — has nothing to show. Remediation:
    [`docs/setup/sandbox-troubleshooting.md` → Signed commit fails before any touch when git signs with ssh](../../../../docs/setup/sandbox-troubleshooting.md#signed-commit-fails-before-any-touch-when-git-signs-with-ssh).

    **10d — git's own programs point at the wrapper.** The hook
    covers only git commands the agent runs; for the commits and
    pushes the user makes from a terminal, git itself has to be
    pointed at the script's `wrap` mode.
    `git config --global --get gpg.ssh.program` (or `gpg.program`,
    when `git config --get gpg.format` is not `ssh`) must name a
    `gpg-touch-wrap-<program>` symlink that resolves to
    `~/.claude/scripts/gpg-touch-overlay.sh`, and
    `git config --global --get core.sshCommand` must end in
    `gpg-touch-overlay.sh wrap ssh`. Either missing is ⚠, not ✗:
    the hook still covers the agent's own commands, and only the
    user's terminal commits and pushes go without a window. A value
    that names something else entirely (a company ssh wrapper, say)
    is ⚠ with the current value shown — the user decides. Rationale
    and the two lines to set:
    [`docs/setup/secure-agent-setup.md` → From your own terminal](../../../../docs/setup/secure-agent-setup.md#from-your-own-terminal--gits-program-config).

    When git *does* name the wrapper, both of its files must also
    open from a sandboxed Bash —
    `head -c 1 ~/.claude/scripts/gpg-touch-overlay.sh` and the same
    for the `gpg-touch-wrap-*` symlink git names. `Operation not
    permitted` is ✗, not ⚠: the git the agent runs reads the same
    global config, and every sandboxed signed commit then fails at
    once with `cannot exec`. The two files belong in
    `sandbox.filesystem.allowRead`, and nothing wider under
    `~/.claude/`:
    [`docs/setup/sandbox-troubleshooting.md` → Signed commit fails with "cannot exec" of the touch-overlay wrapper](../../../../docs/setup/sandbox-troubleshooting.md#signed-commit-fails-with-cannot-exec-of-the-touch-overlay-wrapper).

    **10e — the ssh shim directory, if the user wants one.** `ssh`,
    `scp`, `sftp` and `rsync` typed into a terminal have no program
    setting to point anywhere, so only a `PATH` shim puts the wrapper
    in front of them. Absent entirely is **n/a**, not a gap — it is
    opt-in. When `~/.claude/scripts/shims/` exists, every link in it
    must resolve to `~/.claude/scripts/gpg-touch-overlay.sh`
    (`readlink -f`) and be named for a command the script dispatches
    on — a link named anything else never wraps and is ⚠ with the
    name shown. The directory must also appear in `PATH` ahead of
    `/usr/bin`: compare `command -v ssh` against the shim path, and
    report ⚠ with both paths when the real binary wins, since the
    links are then inert. Rationale and the `PATH` line:
    [`docs/setup/secure-agent-setup.md` → Beyond git](../../../../docs/setup/secure-agent-setup.md#beyond-git--ssh-scp-sftp-and-rsync-you-type-yourself).

## Check 12 — container gateway wired

12. **Container gateway wired.** 12a–12d are only meaningful when
    `podman` or `docker` is on `PATH`; if neither is installed, report
    them **n/a**. 12e has its own condition, so with no container
    runtime check 12 reports 12e alone. Five sub-checks:

    - **12a — hooks wired.** User-scope `~/.claude/settings.json`
      or `~/.claude/settings.local.json` has a `SessionStart` hook
      running `container-gateway-hook.sh start` and a `SessionEnd`
      hook running `container-gateway-hook.sh stop`. Either missing is
      ✗, and so is a registered absolute path that does not exist on
      this machine (synced from another one, e.g. `/Users/...` on
      Linux): point at the setup guide's "Fixing your other machines".
      An absolute path in a `~/.claude/settings.json` that links into a
      synced config repo is ◐: it breaks on the next machine; a hook command naming the script through `~` or `$HOME`
      rather than its absolute path is ◐ (the launching shell expands
      it from `$HOME`, which the session environment can redirect),
      and so is one that runs it through `bash`/`sh` rather than
      directly (its `#!/bin/bash -p` shebang is what keeps `BASH_ENV`
      and exported functions out).
      A missing `PreToolUse` hook (matcher `Bash`) running
      `container-gateway-hook.sh ensure` is ◐, not ✗: the gateway
      still starts with each session, but once it exits mid-session
      (idle timeout, another session on the project ending, a crash)
      container commands fail until the next session. The same
      path, `~` and `bash`/`sh` rules apply to it.
    - **12b — hook script present.** `~/.claude/scripts/container-gateway-hook.sh`
      exists and is executable. Missing or non-executable is ✗.
    - **12c — project wiring.** The gitignored
      `.claude/settings.local.json` has `env.CONTAINER_HOST` and
      `env.DOCKER_HOST`, and both gateway sockets appear in
      `sandbox.network.allowUnixSockets`. On Linux, which ignores
      `allowUnixSockets`, the socket half is instead
      `sandbox.network.allowAllUnixSockets: true` in any scope;
      `allowUnixSockets` entries there are inert and neither satisfy
      nor fail it. Either half missing
      (the `env` pair or the socket half) is ✗; report
      which half. All four values must be **absolute** paths: the
      CLIs read a `unix://` URL's authority as a host component, so
      a project-relative `unix://./…` value dials a path that does
      not exist. A relative `env` value — including one left in the
      committed `.claude/settings.json` by an older install — is ✗,
      quoting it and pointing at
      [Container gateway](../../../../docs/setup/secure-agent-setup.md#container-gateway).
    - **12d — no raw daemon socket in any scope's `allowUnixSockets`.**
      Scan project, project-local, and user scope
      (`.claude/settings.json`, `.claude/settings.local.json`,
      `~/.claude/settings.json`) for an entry whose basename is
      `docker.sock`, `podman.sock`, or ends in `-api.sock`, unless
      its parent directory is the gateway's run directory —
      `<project>/.apache-magpie-local/run` or
      `<git-common-dir>/apache-magpie/run/<worktree-id>`. Any hit
      is ✗, quoting the offending entry, with this exact note —
      it is the same invariant `tools/sandbox-lint` enforces:

      > `sandbox.network.allowUnixSockets: <entry> names a
      > container daemon socket; route through the container
      > gateway (<project>/.apache-magpie-local/run/*.sock,
      > or <git-common-dir>/apache-magpie/run/<worktree-id>/*.sock when the
      > project has not adopted Magpie) instead`

    - **12e — Linux host sockets hidden.** Runs whenever any scope
      sets `sandbox.network.allowAllUnixSockets: true`, even when
      12a–12d are n/a (no container runtime: the flag may be there only
      for ssh-agent signing); with the flag absent or not on Linux it
      is n/a. The flag makes every Unix socket the sandbox can see
      connectable, so for each of `/run/docker.sock`,
      `/var/run/docker.sock`, `/run/docker-cli.sock`, `/run/podman`,
      `/run/user/<uid>` (`<uid>` from `id -u`), `/run/dbus`,
      `/tmp/.X11-unix`, `/run/WSL` and `/mnt/wslg` that exists on the
      host, some scope's `sandbox.filesystem.denyRead` must hold the
      path or a directory above it. Denying single sockets inside
      `/run/user/<uid>` (`bus`, `podman`) does not count: the systemd
      user manager also listens on `systemd/private`. Each one that
      exists and is not covered is ✗, naming the path; a path the host
      does not have needs no entry. Point at
      [Linux needs `allowAllUnixSockets`](../../../../docs/setup/secure-agent-setup.md#linux-needs-allowallunixsockets).

    Install detail:
    [`docs/setup/secure-agent-setup.md` → Container gateway](../../../../docs/setup/secure-agent-setup.md#container-gateway).
    On any ✗, point at
    [`docs/setup/sandbox-troubleshooting.md` → Docker / Podman command fails with a socket error](../../../../docs/setup/sandbox-troubleshooting.md#docker--podman-command-fails-with-a-socket-error)
    rather than re-explaining the fix.

## Check 13 — eval-harness exclusion, if installed

13. **Eval-harness exclusion, if installed.** Optional (step M of
    `setup-isolated-setup-install`): report **n/a** when
    `sandbox.excludedCommands` has no
    `~/.claude/scripts/magpie-run-evals.sh *` entry *and*
    `~/.claude/scripts/magpie-run-evals.sh` is absent. Not running
    eval suites is a normal posture, not a gap.

    When either is present, all of it must be:

    - **13a — both halves, or neither.** The exclusion entry and the
      installed wrapper must agree. An exclusion naming a script that
      is not there is dead config; an installed script with no
      exclusion silently runs sandboxed and reports `Not logged in`
      for every case. Either alone is ✗, naming which half is missing.
    - **13b — the package is beside the wrapper.**
      `~/.claude/scripts/skill-evals/src/skill_evals/` exists.
      Missing is ✗: the wrapper exits 2 without it, so no suite can
      run.
    - **13c — the copies match the repository.** Hash-compare
      `~/.claude/scripts/magpie-run-evals.sh` against
      `tools/skill-evals/magpie-run-evals.sh`, and every `*.py` under
      `~/.claude/scripts/skill-evals/src/skill_evals/` against
      `tools/skill-evals/src/skill_evals/` (ignore `__pycache__`).
      Any difference is ⚠, not ✗, and names the drifted files: the
      harness still runs, it just runs an older grader than the one
      in the tree. Remedy is re-running install step M.1. With no
      framework checkout, report 13c as unchecked, not ⚠.
    - **13d — the deny is present.** `permissions.deny` contains
      `Edit(~/.claude/scripts/**)`. Missing is ✗ — without it the
      agent can edit the very code the exclusion runs outside the
      sandbox, which is the whole bargain of the step.

    Report as a **note**, not a failure: the eval *fixtures* stay
    agent-writable in the repository by design. They are data the
    runner reads, never code it executes, so a fixture edit is a
    review problem visible in the diff rather than a sandbox escape.
    If a report describes the fixtures as protected, correct it.

    Rationale:
    [`tools/skill-evals/README.md` → Running from inside the sandbox](../../../../tools/skill-evals/README.md#running-from-inside-the-sandbox).

## Check 14 — adversarial-review exclusion, if installed

14. **Adversarial-review exclusion, if installed.** Optional (step R of
    `setup-isolated-setup-install`): report **n/a** when the
    `magpie-adversarial-review` plugin is not installed.

    When it is:

    - **14a — the exclusion.** `sandbox.excludedCommands` contains
      `uvx --from ~/.claude/magpie/adversarial-review adversarial-review *`.
      The older form with `magpie-adversarial-review/*/tools/adversarial-review`
      in place of that path is ✗: its `*` also matches options spliced in where
      the version sits, and those run outside the sandbox once approved.
      Missing is ⚠, not ✗: nothing unsafe happens, but every run stays
      sandboxed, where the reviewer CLIs cannot read their credentials,
      and every reviewer reports `unavailable`.
    - **14b — the plugin cache is not agent-writable.** `permissions.deny`
      contains `Edit(~/.claude/plugins/cache/apache-magpie/magpie-adversarial-review/**)`
      and `Edit(~/.claude/magpie/**)`, which covers the link the exclusion names.
      Missing is ✗: the exclusion runs that code outside the sandbox.
    - **14c — no `allow`.** No `permissions.allow` entry matches the tool's
      invocation. One is ✗: each run sends the change to other model
      providers and must keep its prompt.
    - **14d — the link resolves into the plugin.**
      `~/.claude/magpie/adversarial-review` is a symlink to
      `~/.claude/plugins/cache/apache-magpie/magpie-adversarial-review/<version>/tools/adversarial-review`,
      and that directory exists. A broken link is ⚠: the exclusion matches
      nothing that runs, so reviews stay sandboxed and every reviewer reports
      `unavailable`; a new session lets the plugin's `SessionStart` hook
      re-point it. A real file or directory at the path, or a link anywhere
      else, is ✗: the exclusion would run that code outside the sandbox, and
      the hook refuses to replace anything that is not a symlink.

## Check 15 — working directories under the read block

15. **Working directories under the read block.** Only when `permissions.blockReadsOutsideWorkingDirectories` is `true` in any scope (user, project, project-local or managed); otherwise **n/a**.
    Resolve `id -u`, then confirm the current worktree's project-local `.claude/settings.local.json` `permissions.additionalDirectories` contains `/tmp/claude-<uid>` as a literal absolute path.
    `$HOME/.claude/magpie` is deliberately not one of them; check 16f fails on it.
    A missing path is ⚠, not ✗: nothing is exposed, but every read under it prompts, and a bulk sync multiplies that by its gatherer agents.
    An entry with a glob (`/tmp/claude-*`) is listed as a working directory but never matched; report the path it was meant to cover as missing (⚠) and say plainly that the entry does nothing.
    The same path in the committed project `.claude/settings.json`, or in a user-scope `~/.claude/settings.json` synced across machines, is ⚠: it is per-host and belongs in `settings.local.json`.
    [Why this directory](../../../../docs/setup/secure-agent-setup.md#working-directories-under-the-read-outside-working-directories-block).
    Where check 16 applies, the read block being on at all is already ✗ there; these entries do not fix it.

## Check 16 — read-only vetted ops never prompt

16. **Read-only vetted ops never prompt.** An imperative, not a preference: the read dispatcher MUST NOT prompt in any form, because background gatherer agents cannot surface a prompt and each one becomes a silent denial.
    Same n/a condition as check 9.
    Resolve `$HOME`, read every scope (user, project, project-local, managed where readable), and report each sub-check ✓ or ✗; there is no ⚠ here.

    - **16a — both allow rules.** `permissions.allow` carries `Bash(<launcher> ~/.claude/magpie/vetted-ops vetted-op-read *)` for both launchers (`uvx --from`, `uv run --project`): two rules, in the project settings or in user scope.
      Name each missing one.
      A leftover rule spelled with the resolved `$HOME/.claude/magpie/vetted-ops` base is ✗ in the committed project settings (per-host path in a shared file) and otherwise only worth removing: the agent-guard `vetted-ops-spelling` guard refuses that spelling.
    - **16b — no ask rule.** No `permissions.ask` entry in any scope matches a `vetted-op-read` command in either launcher form; broad rules such as `Bash(uvx *)` count, so match each rule as a pattern rather than searching it for the dispatcher name.
      An ask rule prompts even when an allow rule matches.
      Name the file that carries it.
    - **16c — read block off.** `permissions.blockReadsOutsideWorkingDirectories` is `false` or absent in every scope.
      With it on, every call prompts: the check cannot resolve the literal `~` the commands spell, and no `allow` rule overrides it. Listing the checkout as a working directory is not a workaround: 16f fails on it.
    - **16d — tamper protection.** All three vetted-ops `Edit` deny rules from check 9 are present.
      This is what makes the unprompted read safe, so a missing one fails here as well as in check 9.
    - **16e — an exclusion for every allowed form.** `sandbox.excludedCommands` carries `<launcher> ~/.claude/magpie/vetted-ops vetted-op-read *` for both launchers of 16a.
      An allowed form without its exclusion is approved without a prompt but runs inside the sandbox, where its `gh` cannot verify TLS: a silent failure, as with a prompt.

    - **16f — the checkout is not a working directory.** No `permissions.additionalDirectories` entry in any scope overlaps `$HOME/.claude/magpie`: that path, its `~` spelling, anything inside it (such as `~/.claude/magpie/vetted-ops`, which the read-block prompt names), or a parent such as `$HOME/.claude` or `$HOME`.
      The sandbox makes every working directory writable to sandboxed Bash whatever `allowWrite` says, and the 16e exclusions run that checkout's code outside the sandbox, so a covering entry lets sandboxed code change what runs outside it.
      Older versions of `sandbox-add-project-root.sh` added the entry; re-running the updated script (`--all-worktrees`) removes `$HOME/.claude/magpie` and `~/.claude/magpie` from project-local files. A parent directory, or an entry in user or committed project scope, needs a hand edit; [install Step V.1](../isolated-setup-install/SKILL.md#step-v1--read-only-vetted-ops-must-never-prompt) item 7 proposes it.
    [The required shape and why](../../../../docs/setup/secure-agent-setup.md#read-only-vetted-ops-never-prompt).

## Check 17 — roborev exclusion, if installed

17. **roborev exclusion, if installed.** Optional (step B of
    `setup-isolated-setup-install`): report **n/a** when `command -v roborev`
    finds nothing.

    Seven sub-checks:
    - **17a — the exclusion.** `sandbox.excludedCommands` contains
      `roborev *` in the user scope (`~/.claude/settings.json`) or the
      project scope. Missing is ⚠, not ✗: nothing is exposed, but every
      sandboxed `roborev` call fails reading `~/.roborev/config.toml`.
    - **17b — nothing is allowed.** No `permissions.allow` entry in any
      scope matches a `roborev` command — not a catch-all, not one
      subcommand, not `version` or `status`. While 17e passes, such an entry
      is ⚠: the catch-all `ask` outranks it, so every call still prompts,
      but it is one deleted line away from running unprompted. With 17e
      failing it is ✗: outside the sandbox `review --local`, `fix`, `refine`
      and `run` run an agent, `--repo` reaches any checkout, `show --prompt`
      prints stored diffs from every repository roborev has reviewed, and
      even `status --server <host>` connects wherever it points — each with
      no confirmation.
    - **17c — `~/.roborev/` is never writable, and step B.2 is complete if
      taken.** In every case, an `allowWrite` entry in any scope covering
      `~/.roborev/` or an ancestor of it is ✗: it leaves the `Edit(~/.roborev/**)`
      deny (which merges into `denyWrite`) as the only thing keeping
      `config.toml` — which picks what the daemon runs outside the sandbox —
      out of reach of sandboxed commands, one deleted line from writable,
      and no roborev client needs write access. When an
      `allowRead` entry in any scope covers `~/.roborev/` or an ancestor of
      it, the review database is open to the sandbox as in step B.2: confirm `server_addr` in
      `~/.roborev/config.toml` is a `unix://` path and that the same path is
      in `sandbox.network.allowUnixSockets`. On Linux, where
      `allowUnixSockets` is ignored, the `allowRead` is ⚠ on its own: the
      database is exposed and the socket still cannot be reached. On macOS,
      a missing socket entry or a TCP `server_addr` is ⚠: the directory is open but sandboxed clients still
      cannot reach the daemon. Report the B.2 trade-off as a **note** either way — any
      sandboxed command can then drive roborev without step B's prompt (the
      `ask` matches only the literal `roborev …` spelling).
    - **17d — roborev's config is not agent-editable.** `permissions.deny`
      contains `Edit(**/.roborev.toml)` and `Edit(~/.roborev/**)`, step B.2
      or not. Missing is ✗: roborev takes its agent, endpoint
      and hooks from those files and then runs outside the sandbox.
    - **17e — the prompt is there.** `permissions.ask` in the user or
      project scope contains `Bash(roborev *)`. Missing is ✗: with no rule at all, auto mode
      hands a `roborev` command to the classifier instead of prompting.
    - **17f — no planted `.roborev.toml` under the hook.** Look for a
      `post-commit` that runs `roborev` both in the repository's own
      `$(git rev-parse --git-common-dir)/hooks/` and in the directory
      `git rev-parse --git-path hooks` resolves to. One in a shared,
      whole-user hooks directory (`core.hooksPath`, e.g.
      `~/.claude/git-hooks/`) is ✗: it reviews every commit in every
      repository on the host. When the repository's hook runs it, report whether
      `.roborev.toml` exists, whether it is tracked (`git ls-files`), its content, and its
      history with trailers (`git log -p --format='%h %an %s%n%b' --
      .roborev.toml`). Any such file is ⚠ unless the operator recognises
      every agent, model, endpoint and `[[hooks]]` entry in it — the author
      name proves nothing, since the agent commits under the operator's
      identity, and a committed file shows a clean status, and the operator's
      next commit queues a review that applies it, with no prompt.
    - **17g — no roborev hook or MCP server in the harness.** No `hooks`
      entry in any settings scope, and no MCP server registration, runs
      `roborev` (`agent-hook run`, `mcp serve`). MCP servers are not kept in
      `settings.json`: look in `~/.claude.json` (its top-level and
      per-project `mcpServers`), the project `.mcp.json`, and any managed MCP
      configuration. Those files carry servers' `env`, `headers`, `args` and
      `url`, which often hold tokens. Run only these projections and never
      fall back to reading either file whole. `~/.claude.json` is outside the
      sandbox's reads, so its command runs outside the sandbox, with that
      reason stated when proposing it; `.mcp.json` is in the working tree, and
      a missing one means no project MCP servers:

      ```bash
      jq '[.mcpServers // {}, (.projects // {} | .[].mcpServers // {})] | .[] | to_entries[] | {name: .key, command: .value.command, roborev: ([.key, .value.command // "", .value.url // ""] + (.value.args // []) | map(tostring | test("roborev|:7373|daemon\\.sock")) | any)}' ~/.claude.json
      test -e .mcp.json && jq '.mcpServers // {} | to_entries[] | {name: .key, command: .value.command, roborev: ([.key, .value.command // "", .value.url // ""] + (.value.args // []) | map(tostring | test("roborev|:7373|daemon\\.sock")) | any)}' .mcp.json
      ```

      Also report `roborev config get mcp.enabled --global` (a `roborev`
      command, so it prompts under step B's `ask`); `true` means roborev serves an
      HTTP MCP endpoint, and is ⚠ on its own, like a registered roborev
      server. The projection tests a URL without printing it. If the `~/.claude.json`
      projection cannot be run, report 17g as unchecked and leave the file
      for the operator to inspect. A roborev entry is ⚠: the harness starts it
      outside the sandbox and outside the Bash prompt; report it as the
      operator's accepted cost only if they say they chose it.
