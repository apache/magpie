<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# What to diff against what

The user-scope copies checked by *What to check* item 3, each against
its source of truth in the framework checkout. Read this while doing
that item; the rule itself — diff, report as a unified diff, never
re-`cp` — is in the body.

## Plain content diffs

| user-scope copy | framework source |
|---|---|
| `~/.claude/scripts/sandbox-bypass-warn.sh` | `tools/agent-isolation/` |
| `~/.claude/scripts/sandbox-status-line.sh`, or whatever the user's `statusLine` command actually resolves to | `tools/agent-isolation/` |
| `~/.claude/agent-isolation/agent-iso.sh` (global wrapper install) | `tools/agent-isolation/` |
| `~/.claude/scripts/sandbox-add-project-root.sh` (the issue-#197 project-root helper) | `tools/agent-isolation/` |
| `~/.claude/scripts/gpg-touch-overlay.sh`, with `gpg-touch-overlay-window.py` and `gpg-touch-overlay-window-macos.py` | `tools/agent-isolation/` |
| `~/.claude/scripts/container-gateway-hook.sh` | `tools/agent-isolation/container-gateway-hook.sh` |

## The four that are not a plain content diff

**Symlinks are compared by target, not contents.** The
`gpg-touch-wrap-*` entry beside the overlay scripts is a symlink to the
script, so there is nothing to diff — but report it **missing** when
git's `gpg.ssh.program`, `gpg.program` or `core.sshCommand` names it and
it is gone. The same holds for anything under
`~/.claude/scripts/shims/`.

**Two Python packages are diffed file-by-file**, because a stale copy
here is silent behaviour drift rather than the no-op a missing copy
would be:

- `~/.claude/scripts/container-gateway/src/container_gateway/` against
  `tools/container-gateway/src/container_gateway/`.
- `~/.claude/scripts/skill-evals/src/skill_evals/` against
  `tools/skill-evals/src/skill_evals/`, ignoring `__pycache__`, along
  with `~/.claude/scripts/magpie-run-evals.sh` against
  `tools/skill-evals/magpie-run-evals.sh`.

For the eval harness, **absent on both sides is not drift** — it is the
default posture, since the exclusion is optional. A *stale* copy is the
worst case, because the suites keep passing while grading against an
older runner than the tree's.

**`~/.claude/git-hooks/` only when whole-user scope is in effect**,
detected by `git config --global --get core.hooksPath` resolving to it.
Its shape depends on the flavour Step P.3 installed: the **simple**
flavour puts a copy of `git-global-post-checkout.sh` at `post-checkout`;
the **dispatcher** flavour installs `git-hook-dispatcher.sh` there and
symlinks every hook name to it, superseding the standalone
post-checkout script. Diff whichever script is present against its own
source, and read the hook-name symlinks as the installed shape rather
than as drift.

**`~/.claude/scripts/guards.d/`**, when the agent-guard plugin is not
enabled, against the union of the engine's bundled
`tools/agent-guard/src/agent_guard/guards.d/` **and** every skill-owned
`skills/*/guards/*.py`. Locally added `*.py` are expected; flag only
missing framework or skill guards, and stale copies. A new skill guard
present in the framework but absent here is the most common drift on
that wiring, and re-syncing `guards.d` activates it with **no
`settings.json` change**. The engine itself is
`~/.claude/scripts/agent-guard.py` against
`tools/agent-guard/src/agent_guard/__init__.py`.

## Rename migration: `claude-iso.sh` to `agent-iso.sh`

The clean-env launcher was renamed; it now isolates **OpenCode** as well
as Claude Code, exposing `claude-iso` and `opencode-iso` entry points
from one file.

When a pre-rename copy exists at
`~/.claude/agent-isolation/claude-iso.sh` — or wherever the adopter
installed the wrapper — surface it as a migration candidate: install the
new `agent-iso.sh` by the Step P re-install path, remove the stale
`claude-iso.sh`, and update any `source …/claude-iso.sh` line in the
shell rc. The `claude-iso` shell function keeps its name, so
`alias claude=claude-iso` still works once the `source` path is fixed.

Consistent with this skill's read-only posture, **do not delete the old
file**. List it as a candidate and show the two commands the user would
run:

```bash
cp tools/agent-isolation/agent-iso.sh ~/.claude/agent-isolation/agent-iso.sh
rm ~/.claude/agent-isolation/claude-iso.sh
```
