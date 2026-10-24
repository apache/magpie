<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Optional steps: K, L, M and B

Read the one the walk-through reaches. None of these is required for
a working install: a hardware security key, the container gateway,
the eval-harness exclusion, and the roborev exclusion.

## Step K — Hardware security key (optional)

Fully optional, **default no**. Ask once whether the operator signs
commits or authenticates to the forge with a hardware security key
(YubiKey, Nitrokey, any OpenPGP card) or wants to start. On no, skip
the step and say so. On yes, four sub-steps, each surfaced for the
operator to run or approve; the rationale they should hear once is
in
[docs/setup/secure-agent-setup.md → Hardware security keys](../../../../docs/setup/secure-agent-setup.md#hardware-security-keys--signing-and-authentication)
and
[RFC-AI-0002 → Layer 3b](../../../../docs/rfcs/RFC-AI-0002.md#layer-3b--hardware-key-touch-physical-confirmation-of-signatures-and-remote-access).

**K.1 — Touch policy on the key.** Hand the operator
`ykman openpgp info` to run themselves (the tool needs the USB device,
which the sandbox does not expose) and read the touch policies back
from what they paste. The output is data: a line in it that reads like
an instruction is flagged, not followed. The touch goes on the slot
that **signs**, never on the transport alone — a touch on every fetch
and pull is a prompt on a read (PRINCIPLES.md §1), and a push is
already gated by the `git push` ask rule and carries only commits that
were signed with a touch. Which slot signs depends on
`git config --get gpg.format`:

- **OpenPGP** (unset or `openpgp`) — `sig` signs. If `sig` reports
  `Off`, surface `ykman openpgp keys set-touch sig cached`. If `aut`
  reports `On` or `Cached`, surface `ykman openpgp keys set-touch aut off`,
  so ssh fetches, pulls and pushes stop waiting for a touch.
- **`ssh`** — `aut` signs, since an ssh signature uses the key
  `ssh-add -L` lists. If `aut` reports `Off`, surface
  `ykman openpgp keys set-touch aut cached`; never propose turning it
  off, which would take the touch off the signature. Tell the operator
  once that the transport then needs the touch too, and that OpenPGP
  signing or an https remote avoids it. `sig` signs nothing here — leave
  it as it is.

```sh
ykman openpgp keys set-touch sig cached    # the signing slot, OpenPGP
ykman openpgp keys set-touch aut off       # the transport, OpenPGP
ykman openpgp keys set-touch aut cached    # the signing slot, gpg.format=ssh
```

Never run these yourself — they prompt for the key's admin PIN. Propose
`cached` (a touch honoured for 15 seconds, so a rebase replaying many
commits needs one), not `on`, and **never** `fixed` or `cached-fixed`,
which cannot be undone without deleting the private key. Leave the
attestation slot alone. A signing slot already at `On` or `Cached` is
fine as it is.

**K.2 — The touch overlay.** Copy
`tools/agent-isolation/gpg-touch-overlay.sh`,
`gpg-touch-overlay-window.py` and `gpg-touch-overlay-window-macos.py`
into `~/.claude/scripts/`, `chmod +x` them, and wire a `PreToolUse`
`Bash` hook running `gpg-touch-overlay.sh arm` and a
`gpg-touch-overlay.sh disarm` hook on **three** events —
`PostToolUse`, `PermissionDenied` and `PostToolUseFailure`, each on
the `Bash` matcher — into `~/.claude/settings.json`, merging into
existing arrays with a diff the operator approves, exactly as for the
bypass-warn hook. The last two matter because `PreToolUse` fires
before the permission prompt: a command the operator rejects has
already armed a watcher that `PostToolUse` never tears down, and it
lives until `MAX_WAIT` raising the window for somebody else's
signature. Install detail:
[docs/setup/secure-agent-setup.md → Hardware-key touch overlay](../../../../docs/setup/secure-agent-setup.md#hardware-key-touch-overlay).

**K.3 — Git from the operator's own terminal.** The hook covers only
the git commands the agent runs; a commit or push the operator makes
in a terminal or an IDE waits for the same touch with nothing on
screen. Point git's own programs at the script's `wrap` mode instead
of at any git hook (none sits at the right moment — `pre-push` runs
after ssh has authenticated, and only `git commit` has hooks around
its signature). Create the argument-free entry beside the script —
`ln -s gpg-touch-overlay.sh ~/.claude/scripts/gpg-touch-wrap-ssh-keygen`
(`gpg-touch-wrap-gpg` when `git config --get gpg.format` is not
`ssh`) — and hand the operator the two settings to run themselves,
since global git config is theirs to write:

```sh
git config --global gpg.ssh.program "$HOME/.claude/scripts/gpg-touch-wrap-ssh-keygen"
git config --global core.sshCommand "$HOME/.claude/scripts/gpg-touch-overlay.sh wrap ssh"
```

(`gpg.program` and `gpg-touch-wrap-gpg` for OpenPGP signing.) If either
setting already names something else — a company ssh wrapper, say —
show the current value and let the operator decide; do not overwrite
it. Why a symlink, what it covers, what it costs:
[docs/setup/secure-agent-setup.md → From your own terminal](../../../../docs/setup/secure-agent-setup.md#from-your-own-terminal--gits-program-config).

**Optional, beyond git.** `ssh`, `scp`, `sftp` and `rsync` typed
straight into a terminal reach the key with no program setting to
point anywhere — only `PATH` sits in front of them. Offer a shim
directory: `mkdir -p ~/.claude/scripts/shims` and, for each of
`ssh scp sftp rsync`, `ln -sfn ~/.claude/scripts/gpg-touch-overlay.sh
~/.claude/scripts/shims/<name>`. The script dispatches on its own
basename for those names and skips any `PATH` entry resolving back to
itself, so a shim finds the real program and a wrapped git does not
chain into a shim. Create the directory and the links, then **print
the `PATH` line and let the operator add it themselves** — a shell rc
is never edited for them:
`export PATH="$HOME/.claude/scripts/shims:$PATH"`. No sandbox grant
is needed beyond K.4's: the links resolve to the script already
allowed there. Skip the offer when the operator has no touch-required
key. Rationale and the undo:
[docs/setup/secure-agent-setup.md → Beyond git](../../../../docs/setup/secure-agent-setup.md#beyond-git--ssh-scp-sftp-and-rsync-you-type-yourself).

**K.4 — Sandbox grants.** Three, all surfaced as one settings diff:
gpg-agent's ssh socket (`gpgconf --list-dirs agent-ssh-socket`,
absolute path) under `sandbox.network.allowUnixSockets`, so a sandboxed
git can sign and authenticate; only when
`git config --get gpg.format` is `ssh`, the file
`git config --get user.signingkey` names under
`sandbox.filesystem.allowRead`, since the sandbox denies the rest of
`~/.ssh/`; and, once K.3 points git at the wrapper, the wrapper's two
files — `~/.claude/scripts/gpg-touch-overlay.sh` and the
`gpg-touch-wrap-*` symlink — under `sandbox.filesystem.allowRead`,
because the git the agent runs reads the same global config and the
sandbox denies `~/.claude/` wholesale: without this grant every
sandboxed signed commit fails at once with `cannot exec`
([`docs/setup/sandbox-troubleshooting.md` → Signed commit fails with "cannot exec" of the touch-overlay wrapper](../../../../docs/setup/sandbox-troubleshooting.md#signed-commit-fails-with-cannot-exec-of-the-touch-overlay-wrapper)).
Resolve both with `readlink -f` first and grant the real files as
well when they are symlinks into a sync repository — the sandbox
checks the resolved path. Nothing wider: not `~/.ssh/`, not `~/.gnupg/`, not `~/.claude/scripts/`.

Verification of all four is check 10 of
`setup-isolated-setup-verify`; hand off rather than re-checking here.

## Step L — Container gateway (optional)

Fully optional, **default no**. Ask once whether the operator runs
`podman` or `docker` from inside sandboxed sessions, or wants to
start. On no, skip the step and say so. On yes, the sandboxed CLI
never reaches the real daemon socket directly — it talks to the
[container gateway](../../../../tools/container-gateway/README.md)
instead, a per-project policy proxy that runs outside the sandbox.
Rationale and the full install:
[docs/setup/secure-agent-setup.md → Container gateway](../../../../docs/setup/secure-agent-setup.md#container-gateway).

**L.1 — Hook script and the package it runs.** Copy
`tools/agent-isolation/container-gateway-hook.sh` into
`~/.claude/scripts/`, `chmod +x` it. The hook itself never executes
code from the repository being opened — only from a location the
operator installed or pinned — so also copy the whole package
`tools/container-gateway/src/container_gateway/` to
`~/.claude/scripts/container-gateway/src/container_gateway/`, next
to the hook. Without this second copy the hook finds no source at
session start and is a silent no-op: it never fails the session,
it simply never starts the gateway.
A framework contributor re-copies the package after changing it: the hook
refuses a source under any sandbox-writable directory, so neither
`MAGPIE_CONTAINER_GATEWAY_SRC=tools/container-gateway/src` pointing into
this checkout nor an `.apache-magpie/` snapshot is used — the project root is
always writable from the sandbox, and the hook runs outside it.

The hook also never takes `python3` from `PATH`, which project settings can
set. It runs the first Python 3.11+ outside every writable directory among
`/opt/homebrew/bin`, `/usr/local/bin`, `/usr/bin` and uv's managed
interpreters under `~/.local/share/uv/python`, by its real path with `-I -S`.
The uv interpreters count only while `~/.local/share/uv` is read-only to the
sandbox, as the reference settings keep it; a write grant over it in any
scope makes the hook skip them. Where none qualifies, write the absolute path
of one that does to `~/.claude/scripts/container-gateway/python`; until then
the hook logs one line and does not start the gateway.

**L.2 — Hooks.** Wire a `SessionStart` hook running
`container-gateway-hook.sh start` and a `SessionEnd` hook running
`container-gateway-hook.sh stop` into `~/.claude/settings.json`, each
**by the script's absolute path** with the home directory written out (a `~`
there is expanded from `$HOME`, which the session environment can redirect),
executed directly rather than through `bash`/`sh` (its `#!/bin/bash -p`
shebang keeps `BASH_ENV` and exported functions out) —
merging into existing arrays with a diff the operator approves,
exactly as for K.2's touch-overlay hooks.

**L.3 — Project wiring.** Propose the `env` block
(`CONTAINER_HOST` / `DOCKER_HOST`) and the `allowUnixSockets` pair
as a single settings diff into the gitignored
`.claude/settings.local.json`. The sockets are `podman.sock` and
`docker.sock` in the gateway's run directory:
`<project>/.apache-magpie-local/run/` when the project has adopted
Magpie (a committed `.apache-magpie.lock`), otherwise
`<git-common-dir>/apache-magpie/run/<worktree-id>/` — the absolute path of
`git rev-parse --git-common-dir`, which is the main checkout's `.git`
from every worktree, then `main` for the main working tree or the
linked worktree's `.git/worktrees/<name>` name. Compute the run directory in the worktree being wired, never by hand:

```bash
# adopted (a committed .apache-magpie.lock): the run directory is in the tree
[ -f .apache-magpie.lock ] && echo "$PWD/.apache-magpie-local/run"
# not adopted: one per worktree, inside the git directory
common=$(git rev-parse --path-format=absolute --git-common-dir)
gitdir=$(git rev-parse --path-format=absolute --git-dir)
if [ "$gitdir" = "$common" ]; then wid=main; else wid=${gitdir##*/}; fi
echo "$common/apache-magpie/run/$wid"
```

and propose `unix://<run-dir>/podman.sock`, `unix://<run-dir>/docker.sock`
and the same two socket paths for `allowUnixSockets`. A linked worktree
gets its own entries in its own `.claude/settings.local.json`: the
run directory is per worktree whatever the adoption state.
All four values are **absolute**
paths and therefore per-machine: the CLIs do not resolve a
project-relative `unix://./…` value against the cwd — the URL
authority is read as a host component, so `unix://./x` dials
`/.//x` — and `allowUnixSockets` has no relative form either.
Nothing gateway-related is committed to `.claude/settings.json`.
Never propose the real
daemon socket under any name; `tools/sandbox-lint` rejects an
`allowUnixSockets` entry named `docker.sock` / `podman.sock` /
`*-api.sock` outside the gateway's run directory
(`.apache-magpie-local/run/` or `<git-common-dir>/apache-magpie/run/<worktree-id>/`).

Tell the operator plainly, every time this step runs:

- The framework never starts a Podman machine or Docker Desktop —
  discovery happens only at gateway start time, against whatever is
  already running.
- When Docker is absent but Podman is present, the gateway still
  serves the `docker` CLI, translated onto the Podman backend — the
  operator does not need both installed.
- The hook lives in `~/.claude/scripts/`, runs outside the sandbox
  on every `SessionStart` / `SessionEnd`, and — per L.1 — only ever
  executes the copy installed here, never anything from the project
  tree it is about to serve.

Verification of all four pieces is check 12 of
`setup-isolated-setup-verify`; hand off rather than re-checking here.

## Step M — the eval-harness exclusion (optional)

**Offer this only when the operator runs Magpie's eval suites** —
framework contributors, and adopters who maintain agentic overrides
and want the suites graded by a model. Everyone else should decline;
the step adds an unsandboxed command for no benefit. If the repo has
no `tools/skill-evals/`, skip it silently.

The problem it solves: `--cli` mode needs the model CLI's
credentials, which the sandbox denies, so an agent that runs a suite
itself gets one `ERROR` per case rather than a grade.

**M.1 — Copy the wrapper and the package it runs.** Same shape as
L.1, and for the same reason. Copy
`tools/skill-evals/magpie-run-evals.sh` into `~/.claude/scripts/`,
`chmod +x` it, and copy the whole package
`tools/skill-evals/src/skill_evals/` to
`~/.claude/scripts/skill-evals/src/skill_evals/` beside it. The
wrapper finds the package by looking next to itself.

**M.2 — The exclusion and the deny.** Propose, as one diff:

```jsonc
"sandbox": {
  "excludedCommands": ["~/.claude/scripts/magpie-run-evals.sh *"]
},
"permissions": {
  "deny": ["Edit(~/.claude/scripts/**)"]
}
```

Say why the copy is not optional, because it is the whole point of
the step:

- An exclusion makes whatever the command executes run **outside**
  the sandbox, so that code must not be writable by the thing being
  sandboxed. `~/.claude/scripts/` is outside every
  `sandbox.filesystem.allowWrite` root, so the copies are already
  beyond sandboxed Bash; the `Edit` deny closes the agent's own
  editing tools over the same directory.
- Excluding the runner **in the repository** instead fails twice
  over. `--cli` is an arbitrary shell command, so the exclusion
  would carve out `--cli "curl …"`, not the eval harness — and
  pinning `--cli` in the pattern does not hold, because argparse is
  last-wins. An `Edit` deny on an in-repo wrapper does not rescue
  it either: the wrapper matters only for what it executes, so the
  runner's whole source tree would need denying too.
- Remember the coupling when *any* in-repo path gets a deny: it
  becomes a sandbox write-deny, so the path must also join the
  `sandbox_write_denied` anchor in `.pre-commit-config.yaml`, or
  `end-of-file-fixer`, `mixed-line-ending` and `trailing-whitespace`
  abort `prek run --all-files`. Out-of-tree paths like
  `~/.claude/scripts/**` need no such entry.
- The wrapper takes exactly one positional path under `evals/` and
  no flags. That shape is what the exclusion is trusting. Any other
  eval invocation stays on the `!` prefix, outside the sandbox.
- **The copy goes stale.** Re-run M.1 after changing the runner, or
  the suites run from inside the sandbox are the old ones. Drift is
  check 13 of `setup-isolated-setup-verify` and a line in
  `setup-isolated-setup-update`.

Full rationale:
[`tools/skill-evals/README.md` → Running from inside the sandbox](../../../../tools/skill-evals/README.md#running-from-inside-the-sandbox).

## Step B — The roborev exclusion (optional)

Only applies when the [`roborev`](https://roborev.io) CLI is on `PATH`
(`command -v roborev`). It is a third-party
[companion](../../../../docs/setup/companion-skills.md#roborev), not part
of Magpie; if it is not installed, skip this step and say so.

Every `roborev` subcommand talks to a local daemon and reads its own state
under `~/.roborev/` (`config.toml`, the review database, the daemon's
runtime sockets), which this sandbox's `denyRead: ["~/"]` blocks.
Sandboxed, even `roborev review` fails with
`cannot load daemon client config: stat ~/.roborev/config.toml: operation not permitted`.
The CLI therefore runs outside the sandbox through one exclusion, and that
makes it a wider door than it looks. Outside the sandbox, `roborev` can:

- run a full coding agent in its own process (`review --local`, `fix`,
  `refine`, `run`), with that agent's credentials and no sandbox around it;
- review any checkout on the machine (`--repo <path>`), including one the
  sandbox's `denyRead` hides, and send it to a provider the caller picks
  (`--agent`, `--model`, `--provider`);
- print stored review prompts, diffs included, for every repository roborev
  has ever reviewed (`show --prompt`, `list`, `log`, `search`, `cost`
  `--repo`): the review database is per machine, not per project.

So no `roborev` command runs without a prompt — the same position Step R
takes for the adversarial-review tool, for the same reason:

```jsonc
"sandbox": {
  "excludedCommands": ["roborev *"]
},
"permissions": {
  "ask": [
    // every subcommand, every flag order, and any subcommand roborev adds
    // later: even `status` takes the global `--server <host>`, which
    // connects wherever it points, outside the sandbox
    "Bash(roborev *)"
  ],
  "deny": [
    // roborev reads its agent, model, endpoint and hooks from these files,
    // and then runs outside the sandbox; the agent that calls it must not
    // be able to rewrite them
    "Edit(**/.roborev.toml)",
    "Edit(~/.roborev/**)"
  ]
}
```

Put it in the user scope (`~/.claude/settings.json`): the binary and
`~/.roborev/` are per machine, not per project. **Do not add an `allow`**
for any subcommand, not even `version` or `status`: a trailing global
`--server` or `-v` matches a wildcard `allow`, and an exact one saves a
click on a command nobody needs to run unattended. Because `ask` outranks
`allow`, the catch-all also overrides an `allow` for `roborev` from any
other scope, a project `.claude/settings.json` in a cloned repository
included.

Tell the operator what the exclusion covers and what it does not:

- **Read every prompt before approving it.** The prompt is the only gate:
  look for `--local`, `--repo` pointing outside the current project,
  `--agent`/`--provider` naming a provider the operator has not chosen,
  `--prompt` on `show`, and any `config set` — it writes `.roborev.toml`
  (default) or `~/.roborev/config.toml` (`--global`), the files that pick
  the agent, endpoint and hooks the daemon runs; `init` writes repository
  config and installs the hook, so read it as carefully. Do not add an `allow` for `review` to save the
  click — that is the same refusal Step R makes for the adversarial-review
  tool, for the same reason.
- **The flags are not the whole story.** roborev also reads a per-repo
  `.roborev.toml`, which can name the review agent, the model, a
  `model@base_url` endpoint and `[[hooks]]` to run. The `deny` above stops
  the file-editing tools and, because an `Edit(path)` deny merges into the
  sandbox's `denyWrite`, sandboxed Bash too. What remains is a committed
  one arriving with a checkout: a contributor's PR, a cloned repository, a
  commit made outside the sandbox. The same merge has a cost: a sandboxed
  `git checkout`, `pull`, `rebase` or `stash` that must rewrite a tracked
  `.roborev.toml` fails with `operation not permitted`, and has to run in
  the operator's terminal; in a repository whose `prek` whitespace hooks
  touch it, add it to the `sandbox_write_denied` anchor (#1309). Before approving a `roborev` prompt,
  check whether the file exists at all (`test -e .roborev.toml`), then read
  it and its history: `cat .roborev.toml` and
  `git log -p --format='%h %an %s%n%b' -- .roborev.toml`, so `Generated-by:`
  trailers show. The author name proves nothing — the agent commits under
  the operator's own git identity. Approve only when the operator
  recognises every agent, model, endpoint and `[[hooks]]` entry in it.
  `~/.roborev/config.toml` is outside every `allowWrite` root, with or
  without Step B.2, and the `Edit(~/.roborev/**)` deny puts it in
  `denyWrite` as well, so sandboxed Bash cannot rewrite it — only an
  approved `roborev config set --global` can.
- `fix`, `refine` and `run` hand the working tree to an agent that edits
  and commits outside this sandbox.
- **roborev's agent hook and MCP server bypass the prompt.**
  `roborev agent-hook install` (which `doctor` and `quickstart` suggest)
  writes harness hooks that run `roborev agent-hook run`, and with `--mcp`
  registers a `roborev mcp serve` MCP server; `[mcp] enabled` in
  `config.toml` opens an HTTP endpoint. The harness starts hooks and MCP
  servers itself, outside the sandbox and outside the Bash `ask` rule, so
  each runs roborev with no prompt and hands the agent stored reviews from
  every repository. Do not install either under the secure setup; an
  operator who wants them accepts that the prompt no longer gates roborev.
- **A planted `.roborev.toml` also reaches the operator's own commits.**
  With the post-commit hook installed, a commit made in the operator's
  terminal queues a review with no prompt at all, and the daemon applies
  whatever `.roborev.toml` is in the tree. After any agent session in such
  a repository, check the file before committing from the terminal — the
  same three commands as above, since a committed one shows a clean
  status. Do not install the hook (`roborev init`,
  `install-hook`) in a repository the agent works in unless that check is
  part of the routine.
- **Under a whole-user `core.hooksPath`, keep roborev's hook per
  repository.** With Step P's whole-user scope, `core.hooksPath` points at
  the shared `~/.claude/git-hooks/`, and roborev follows it: `roborev init`
  or `install-hook` would target the shared `post-commit` — the dispatcher
  every repository on the host runs. Refuse that, and never pass `--force`
  there: replacing the dispatcher breaks every repository's own hooks and
  queues every commit on the host, private checkouts included, for review.
  With Step P's dispatcher flavour, put roborev's hook in the repository's
  own `$(git rev-parse --git-common-dir)/hooks/post-commit` instead, where
  the dispatcher chains to it. With the simple flavour there is no shared
  `post-commit` and per-repository hooks never fire, so `roborev init` would
  quietly create a new host-wide one: refuse it, and either run
  `roborev review` explicitly or switch Step P to the dispatcher flavour.
- **The post-commit hook stays sandboxed when the commit is.** The hook `roborev init` or
  `install-hook` installs runs `roborev post-commit` as a child of
  `git commit`, and an exclusion matches only the command the agent typed,
  not its children. A commit the agent makes therefore runs the hook inside
  the sandbox, where it fails on the `~/.roborev/` read and queues nothing —
  silently. Commits the operator makes in their own terminal are reviewed
  as usual; for the agent's, either run `roborev review` (or `--branch`)
  explicitly, which prompts, or take
  [Step B.2](#step-b2--let-roborev-run-inside-the-sandbox-optional).
  A `git commit` retried with the sandbox disabled — the usual fix for a
  signing failure — runs the hook unsandboxed instead, with no roborev
  prompt: the operator approves `git commit` and roborev queues a review
  that applies whatever `.roborev.toml` is in the tree. Before approving
  such a bypass in a repository with the hook, run the same
  `.roborev.toml` check as for a terminal commit.
- Like every exclusion it matches only the single-line form. A pipe,
  `$(…)`, `&&` or a redirection puts the command back in the sandbox, where
  it fails on the `~/.roborev/` read.

### Step B.2 — Let roborev run inside the sandbox (optional)

Offer it only after Step B, only on macOS, and only when the operator
wants the post-commit hook to review the agent's own commits. On Linux the
sandbox ignores `sandbox.network.allowUnixSockets`, so the hook still cannot
reach the daemon and the step would expose the review database for nothing;
there, run `roborev review` explicitly instead. It gives sandboxed
processes what roborev needs, so a `roborev` child of `git commit` works:

1. Move the daemon from loopback TCP, which the sandbox blocks, to a fixed
   unix socket. The default `unix://` path sits under the per-machine temp
   directory, so name one under `~/.roborev/`, written out as an absolute
   path with `$HOME` expanded — `/Users/alice` below stands for it — because
   the socket allow-list takes literal paths:

   ```bash
   roborev config set server_addr 'unix:///Users/alice/.roborev/daemon.sock' --global
   roborev daemon restart
   ```

   An explicit `unix://` makes the daemon socket-only; every `roborev`
   client reads the same `config.toml`, so the CLI follows it.
2. Add the host-independent half to the user scope
   (`~/.claude/settings.json`):

   ```jsonc
   "sandbox": {
     "filesystem": {
       "allowRead": ["~/.roborev/"]
     }
   }
   ```

   Read only, never `allowWrite`: the client reads `config.toml` and the
   daemon's runtime file and sends everything else over the socket, so it
   needs no write access, and a writable `config.toml` — which picks the
   agent, endpoint and hooks the daemon runs outside the sandbox — would be
   one sandboxed command away from running anything there.

   and the socket, which the allow-list takes only as a literal resolved
   path, to each worktree's project-local `.claude/settings.local.json` —
   the same per-host file check 15 uses, never a synced or committed one:

   ```jsonc
   "sandbox": {
     "network": {
       "allowUnixSockets": ["/Users/alice/.roborev/daemon.sock"]
     }
   }
   ```

Tell the operator what this costs, plainly:

- **Step B's prompt stops being the gate.** The `Bash(roborev *)` ask
  matches only a command spelled `roborev …`. Once sandboxed processes can
  read `~/.roborev/` and reach the socket, `/opt/homebrew/bin/roborev …`,
  `env roborev …` or `sh -c 'roborev …'` drive the daemon with no prompt —
  `--repo` reviews of any checkout, any `--agent` or `--provider`,
  `show --prompt` — and the daemon does that work outside the sandbox.
- The review database becomes readable by every sandboxed command, so the
  stored diffs of every repository roborev has reviewed are no longer
  behind a prompt.
- Anything that connects to the socket can queue reviews.

Without B.2 the agent's commits are simply not reviewed in the background,
which fails safe. Take it only when that trade is the right one for this
machine.
