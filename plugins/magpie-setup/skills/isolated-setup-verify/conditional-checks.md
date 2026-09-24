<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The conditional checks: 9, 10, 12 and 13

Four of the checks only apply when the install has the feature they
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

   If `core.hooksPath` is unset (or points elsewhere), the
   operator is in **per-project** scope (the default). No further
   sub-check needed — the per-project mode is fully covered by
   the static + live-probe checks above.

## Check 9 — the vetted-ops split and exclusion

9. **The vetted-ops split and exclusion.** Only meaningful when the
   adopter routes forge operations through the `vetted-ops`
   dispatcher; if the repo has no
   `.apache-magpie-overrides/tools/vetted-ops/config.toml` and no
   `vetted-op` rule, report **n/a** and move on.

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

   **9b — the exclusion.** `permissions.deny` covers both surfaces,
   each with an `Edit` rule:

   - `~/.claude/plugins/cache/apache-magpie/magpie-vetted-ops/**` —
     the operation catalogue. The read dispatcher's `allow` rests on
     its shape, so an editable catalogue dissolves that `allow`.
   - `.apache-magpie-overrides/tools/vetted-ops/**` — the policy.

   Either one missing is ✗. One `Edit` rule per surface is the whole
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

## Check 10 — hardware-key touch overlay and the signing key

10. **Hardware-key touch overlay and the signing key.** Only when
    commits are signed (`git config --get commit.gpgsign` is
    `true`) or a remote is reached over ssh through gpg-agent
    (`SSH_AUTH_SOCK` names its socket); otherwise report **n/a**.
    Four sub-checks, plus a note: the key's own touch policies
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
    missing file or hook is ✗. Install steps and rationale:
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

12. **Container gateway wired.** Only meaningful when `podman` or
    `docker` is on `PATH`; if neither is installed, report **n/a**
    for the whole check. Four sub-checks:

    - **12a — hooks wired.** User-scope `~/.claude/settings.json`
      has a `SessionStart` hook running
      `container-gateway-hook.sh start` and a `SessionEnd` hook
      running `container-gateway-hook.sh stop`. Either missing is
      ✗.
    - **12b — hook script present.** `~/.claude/scripts/container-gateway-hook.sh`
      exists and is executable. Missing or non-executable is ✗.
    - **12c — project wiring.** The gitignored
      `.claude/settings.local.json` has `env.CONTAINER_HOST` and
      `env.DOCKER_HOST`, and both gateway sockets appear in
      `sandbox.network.allowUnixSockets`. Either half missing
      (the `env` pair or the socket allow-list pair) is ✗; report
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
      its parent directory is `.apache-magpie-local/run`. Any hit
      is ✗, quoting the offending entry, with this exact note —
      it is the same invariant `tools/sandbox-lint` enforces:

      > `sandbox.network.allowUnixSockets: <entry> names a
      > container daemon socket; route through the container
      > gateway (<project>/.apache-magpie-local/run/*.sock)
      > instead`

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
      in the tree. Remedy is re-running install step M.1.
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
      `uvx --from ~/.claude/plugins/cache/apache-magpie/magpie-adversarial-review/*/tools/adversarial-review adversarial-review *`.
      Missing is ⚠, not ✗: nothing unsafe happens, but every run stays
      sandboxed, where the reviewer CLIs cannot read their credentials,
      and every reviewer reports `unavailable`.
    - **14b — the plugin cache is not agent-writable.** `permissions.deny`
      contains `Edit(~/.claude/plugins/cache/apache-magpie/magpie-adversarial-review/**)`.
      Missing is ✗: the exclusion runs that code outside the sandbox.
    - **14c — no `allow`.** No `permissions.allow` entry matches the tool's
      invocation. One is ✗: each run sends the change to other model
      providers and must keep its prompt.
