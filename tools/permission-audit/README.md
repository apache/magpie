<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [permission-audit](#permission-audit)
  - [Prerequisites](#prerequisites)
  - [Why](#why)
  - [Install](#install)
  - [CLI](#cli)
    - [`audit`](#audit)
    - [`apply`](#apply)
    - [`list-known`](#list-known)
  - [Canonical lists](#canonical-lists)
  - [Tests](#tests)
  - [How `/magpie-setup verify` uses this](#how-magpie-setup-verify-uses-this)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# permission-audit

**Capability:** substrate:sandbox

**Harness:** Claude Code, OpenCode

Audit + atomically edit Claude Code's `permissions.allow[]` entries
in `<repo>/.claude/settings.json` and `<repo>/.claude/settings.local.json`.

Backs the `--apply-permission-audit` flag of
[`/magpie-setup verify`](../../skills/setup/verify.md#8d-permission-allow-list-hygiene)
(check 8d), and is also directly usable as a CLI.

**OpenCode.** The same over-permissioning check applies to the other
harness through `audit-opencode`, which reads an
[`opencode.json`](https://opencode.ai/docs/permissions/) `permission`
config instead of a Claude allow-list. OpenCode models permissions
differently — `permission` is a string or an object keyed by tool, and
`permission.bash` may map glob command patterns to `allow`/`ask`/`deny`
(last-matching-rule-wins, with a `"*"` default) — so this is a separate
classifier, but it enforces the same intent: **flag configuration that
auto-approves dangerous shell execution.** It reports, in JSON:

- `blanket-allow` — `permission` is the string `"allow"` (every tool
  auto-approved);
- `bash-allow-all` — the default `permission.bash` decision is `"allow"`;
- `dangerous-allow` — a specific rule auto-approves a dangerous command
  family (`git push`, `sudo`, `curl`/`wget`, `rm -rf`, cloud CLIs,
  `kubectl`, `docker run`, `ssh`, interpreters/`npx`/`uvx`, …) while the
  default is stricter.

```bash
uv run --project tools/permission-audit permission-audit audit-opencode opencode.json
```

The Claude-only `apply` subcommand (atomic allow-list edits) has no
OpenCode counterpart yet; `audit-opencode` is read-only.

## Prerequisites

- **Runtime:** Python 3.11+ run via `uv` (`uv sync` / `uv run`); the
  tool itself is stdlib-only.
- **CLIs:** None beyond the runtime.
- **Credentials / auth:** None.
- **Network:** None — operates entirely on local
  `.claude/settings.json` / `.claude/settings.local.json` files.
- **Optional:** dev group adds `pytest`, `ruff`, `mypy` for the test
  + lint suite.

## Why

Adopter permission allow-lists drift over time. Two failure modes
the framework's verify check 8d surfaces:

- **Forbidden wildcards accumulate** — patterns like
  `Bash(uv run *)`, `Bash(python3 *)`, `Bash(npm run *)`,
  `Bash(bash *)`, `Bash(gh api *)` are equivalent to allowing
  arbitrary code execution. Each is easy to add for a short-lived
  reason ("just for this session") and easy to forget.
- **Narrow read-only patterns the framework's skills invoke
  constantly are missing** — the `security` family's Gmail and
  PonyMail read MCPs, `Bash(vulnogram-api-record-fetch *)`,
  `Bash(lychee *)`. Pre-allowing them removes the per-call
  confirmation prompt without expanding the capability surface.

The audit phase is a pure classification — given the allow list +
the adopter's opt-in families, return `forbidden[]` (✗) and
`missing_recommended[]` (⚠). The apply phase is the only writer:
flock-guarded read → mutate → atomic rename.

## Install

```bash
uv sync --project tools/permission-audit
```

Stdlib-only runtime; the dev group adds `pytest`, `ruff`, `mypy`.

## CLI

```bash
permission-audit audit <settings-path> [--families security,issue]
permission-audit apply <settings-path> [--add <entry>]... [--remove <entry>]... [--create-if-missing]
permission-audit list-known
```

### `audit`

Reads the settings file, classifies its `permissions.allow[]`, and
prints JSON. Returns exit code `1` when any forbidden entry is
present (so a shell caller can gate a downstream action), `0`
otherwise. The empty-family bucket (`""`) is always included in
the recommended check — those entries (`Bash(lychee *)` today)
apply to every adopter.

```bash
$ permission-audit audit .claude/settings.local.json --families security
{
  "settings_path": "/repo/.claude/settings.local.json",
  "file_exists": true,
  "allow_count": 215,
  "families": ["security"],
  "forbidden": [
    {
      "severity": "forbidden",
      "pattern": "Bash(uv run *)",
      "json_pointer": ".permissions.allow[37]",
      "family": null
    }
  ],
  "missing_recommended": [
    {
      "severity": "missing-recommended",
      "pattern": "mcp__claude_ai_Gmail__list_labels",
      "json_pointer": null,
      "family": "security"
    }
  ]
}
```

### `apply`

Atomic add/remove. Concurrent writers (notably the sandbox-
allowlist helper writing `sandbox.filesystem.*`) serialize via
POSIX `fcntl.flock` on the target file. Unrelated keys
(`extraKnownMarketplaces`, `hooks`, `permissions.deny`, etc.) are
preserved verbatim.

```bash
permission-audit apply .claude/settings.local.json \
  --remove 'Bash(uv run *)' \
  --remove 'Bash(python3 *)' \
  --add 'Bash(lychee *)' \
  --add 'mcp__claude_ai_Gmail__get_thread'
```

Output: JSON describing what changed.

### `list-known`

Dumps the canonical forbidden + recommended-by-family lists for
diff-friendly inspection (used by the verify check 8d narrative
and by adopters wanting to vendor the same convention).

## Canonical lists

See [`src/permission_audit/audit.py`](src/permission_audit/audit.py).

Both lists are intentionally narrow:

- **Forbidden** — only the exact wildcard strings the verify check
  8d doc enumerates. Same-category extensions (a wildcard not on
  the list but with the same capability surface) are the caller's
  responsibility to flag — the framework cannot enumerate every
  variant.
- **Recommended** — every entry is verified against Claude Code's
  auto-allowed harness exclusions (`READONLY_COMMANDS`,
  `GIT_READ_ONLY_COMMANDS`, `GH_READ_ONLY_COMMANDS`, …) so the
  tool does not propose entries that the harness would never
  prompt on anyway.

## Tests

```bash
uv run --project tools/permission-audit pytest
```

Covers: classification, family-scoping, JSON-pointer numbering on
duplicates, atomic add/remove, no-op rewrite skip, malformed
JSON detection.

## How `/magpie-setup verify` uses this

The verify check 8d narrative describes the human-facing report;
this tool is the engine behind it. The skill calls

```bash
uv run --project <framework>/tools/permission-audit \
  permission-audit audit <repo>/.claude/settings.local.json \
  --families <comma-joined families from the lock>
```

for each of `.claude/settings.json` and `.claude/settings.local.json`,
folds the JSON output into the verify report, and — only on the
`--apply-permission-audit` flag and after the operator confirms
the exact list of changes — calls `permission-audit apply` for
each file.
