#!/usr/bin/env bash
# Licensed to the Apache Software Foundation (ASF) under one
# or more contributor license agreements.  See the NOTICE file
# distributed with this work for additional information
# regarding copyright ownership.  The ASF licenses this file
# to you under the Apache License, Version 2.0 (the
# "License"); you may not use this file except in compliance
# with the License.  You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing,
# software distributed under the License is distributed on an
# "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied.  See the License for the
# specific language governing permissions and limitations
# under the License.
#
# Run a single static-check / test command across every workspace
# member declared in the root `pyproject.toml`'s
# `[tool.uv.workspace] members` list. Used by the four
# workspace-* hooks in `.pre-commit-config.yaml` so adding a new
# tool doesn't require editing the pre-commit config at all —
# just append the new member's path to `[tool.uv.workspace]`.
#
# Usage:
#   tools/dev/run-workspace-check.sh <check-key> <check-cmd> [args...]
#
# `check-key` selects which auto-discovery rule applies and which
# per-member opt-out entry to consult. Recognised keys:
#
#   ruff          → runs only on members with `[tool.ruff]`
#   ruff-format   → runs only on members with `[tool.ruff]`
#   ty            → runs on every member (opt out with the `skip` list below),
#                   with the shared rules of `tools/dev/shared/ty.toml` as flags
#   pytest        → runs only on members with `[tool.pytest.ini_options]`
#
# `check-cmd` is the actual command-line passed to `uv run`. It
# may be a multi-token string (e.g. "ruff check") quoted as a
# single argv item.
#
# For `pytest`, any further arguments are the changed files (the
# `workspace-pytest` hook passes them): only the members those files
# touch run, picked by `tools/dev/ci-pytest-batches.py`, the same
# selection a pull request's `tests` workflow makes. With no files
# every applicable member runs.
#
# Per-member opt-out: a workspace member can skip one or more
# checks by adding a `[tool.magpie.checks]` block:
#
#   [tool.magpie.checks]
#   skip = ["ty", "pytest"]
#
# Examples:
#   tools/dev/run-workspace-check.sh ruff        "ruff check"
#   tools/dev/run-workspace-check.sh ruff-format "ruff format --check"
#   tools/dev/run-workspace-check.sh ty          "ty check"
#   tools/dev/run-workspace-check.sh pytest      "pytest --color=yes -n auto"
#
# Exit code: 0 iff the check succeeded on every applicable
# member; 1 otherwise. The script does NOT short-circuit on the
# first failure — every member runs so the operator sees all
# failures in one pass.

set -uo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: $0 <check-key> <check-cmd> [args...]" >&2
  exit 64
fi

CHECK_KEY="$1"
CHECK_CMD="$2"
shift 2

# Scrub location-redirecting git env vars. When pre-commit runs this script
# as a git hook, git exports GIT_DIR / GIT_INDEX_FILE / GIT_WORK_TREE (etc.)
# pointing at *this* repository. Any member test that shells out to `git` in
# a throwaway repo (e.g. tools/agent-isolation, tools/vcs) would otherwise
# inherit those and operate on the wrong repository — passing standalone but
# failing under `git commit`. Unsetting them makes git resolve the repo from
# each test's own cwd. This script reads pyproject.toml via Python, not git,
# so it needs none of these itself.
unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_COMMON_DIR GIT_PREFIX

# Every check runs through `uv` against the member's own project — never a
# bare interpreter — so the tool version comes from that sub-project's
# pyproject.toml + dev group (see each member's `[dependency-groups] dev`).
# pytest is invoked as `python -m pytest` rather than via its
# console script: a console script bakes an absolute interpreter path into
# its shebang, which breaks when the shared workspace venv is reused across
# repos (a stale `#!/…/other-repo/.venv/bin/python3` fails to spawn). The
# `-m` form resolves the tool from the live interpreter and sidesteps that.

# Discover workspace members + per-check applicability. The Python
# helper walks the root `[tool.uv.workspace] members` list, opens
# each member's pyproject.toml, and emits one line per applicable
# member: "<check>\t<path>" — with the `<check>` filter already
# applied based on (a) the presence of the relevant `[tool.*]`
# section and (b) the member's `[tool.magpie.checks] skip` list.
applicable=$(python3 - "$CHECK_KEY" <<'PY'
import sys
import tomllib

check = sys.argv[1]

# Which `[tool.*]` section signals that this check is configured
# for a given member. ruff-check and ruff-format both look at
# `[tool.ruff]` because the same config drives both.
SECTION_FOR_CHECK = {
    "ruff": "ruff",
    "ruff-format": "ruff",
    # `ty` is opt-out: every member is type-checked unless it skips it, so a
    # new member cannot go unchecked by forgetting a config table.
    "ty": None,
    "pytest": "pytest",
}

if check not in SECTION_FOR_CHECK:
    sys.stderr.write(f"error: unknown check-key {check!r}\n")
    sys.exit(2)
section_key = SECTION_FOR_CHECK[check]


with open("pyproject.toml", "rb") as f:
    root = tomllib.load(f)

try:
    members = root["tool"]["uv"]["workspace"]["members"]
except KeyError:
    sys.stderr.write("error: [tool.uv.workspace] members not in root pyproject.toml\n")
    sys.exit(2)

for member in members:
    try:
        with open(f"{member}/pyproject.toml", "rb") as f:
            data = tomllib.load(f)
    except FileNotFoundError:
        sys.stderr.write(f"warning: workspace member missing pyproject.toml: {member}\n")
        continue

    tool = data.get("tool", {})

    # Opt-out check.
    skip = tool.get("magpie", {}).get("checks", {}).get("skip", [])
    if check in skip:
        continue

    if section_key is None:
        print(member)
        continue

    # Auto-discovery check — the [tool.<X>] block must exist.
    # `pytest` looks at the nested `[tool.pytest.ini_options]` table.
    if section_key == "pytest":
        if "ini_options" not in tool.get("pytest", {}):
            continue
    else:
        if section_key not in tool:
            continue

    print(member)
PY
)
status=$?
if [ "$status" -ne 0 ]; then
  exit "$status"
fi

if [ "$CHECK_KEY" = "pytest" ] && [ "$#" -gt 0 ]; then
  # The list goes through stdin, not a temp file: a sandboxed agent may
  # not be able to write the system temp directory.
  applicable=$(printf '%s\n' "$@" | python3 tools/dev/ci-pytest-batches.py --changed-file - --paths | tr -d '\r')
  status=$?
  if [ "$status" -ne 0 ]; then
    exit "$status"
  fi
  set --
fi

if [ -z "$applicable" ]; then
  echo "→ ${CHECK_KEY}: no applicable workspace members (nothing to run)"
  exit 0
fi

# ty: the workspace-wide settings in `tools/dev/shared/ty.toml`, turned into
# flags. `ty check --config-file` would replace each member's own `[tool.ty]`
# instead of merging with it; command-line rule flags merge. Read once, before
# the loop, and appended after any arguments the caller passed.
TY_FLAGS=()
if [ "$CHECK_KEY" = "ty" ]; then
  flags=$(python3 - tools/dev/shared/ty.toml <<'PY'
import sys
import tomllib

with open(sys.argv[1], "rb") as f:
    shared = tomllib.load(f)
unknown = set(shared) - {"rules", "analysis", "terminal"}
if unknown:
    sys.exit(f"error: {sys.argv[1]}: only [rules], [analysis] and [terminal] are read, not {sorted(unknown)}")
for rule, level in shared.get("rules", {}).items():
    if level not in ("error", "warn", "ignore"):
        sys.exit(f"error: {sys.argv[1]}: rule {rule!r} has level {level!r}")
    print(f"--{level}")
    print(rule)
for key, value in shared.get("analysis", {}).items():
    if not isinstance(value, bool):
        sys.exit(f"error: {sys.argv[1]}: [analysis] {key} must be true or false")
    print("--config")
    print(f"analysis.{key}={str(value).lower()}")
terminal = shared.get("terminal", {})
if set(terminal) - {"error-on-warning"}:
    sys.exit(f"error: {sys.argv[1]}: only [terminal] error-on-warning is read")
if terminal.get("error-on-warning"):
    print("--error-on-warning")
PY
)
  status=$?
  if [ "$status" -ne 0 ]; then
    exit "$status"
  fi
  while IFS= read -r flag; do
    TY_FLAGS+=("$flag")
  done <<< "$flags"
fi

count=$(echo "$applicable" | wc -l | tr -d ' ')
echo "→ workspace-check: ${CHECK_KEY} (${CHECK_CMD} $*) across ${count} members"

# Run one member's check via uv, against the member's own project:
#   --directory "$member"  → cwd is the member, so ruff / ty / pytest
#                            configs resolve paths relative to the member root
#   --project .            → the environment is that member's project (its
#                            pyproject.toml + dev group), resolved after the
#                            --directory chdir
# pytest goes through `python -m` to bypass console-script shebangs; ruff
# and ty are native binaries with no interpreter shebang, so they run directly.
run_member() {
  local member=$1
  shift
  # shellcheck disable=SC2086 # CHECK_CMD may legitimately be multi-token
  if [[ "$CHECK_KEY" == "pytest" ]]; then
    uv run --directory "$member" --project . python -m $CHECK_CMD "$@"
  else
    # `${a[@]+…}`: an empty array is "unbound" under `set -u` in bash 3.2
    # (macOS), so expand it only when it has elements.
    uv run --directory "$member" --project . $CHECK_CMD "$@" ${TY_FLAGS[@]+"${TY_FLAGS[@]}"}
  fi
}

failed=()
for member in $applicable; do
  name=$(basename "$member")
  status=0
  run_member "$member" "$@" || status=$?
  # A status above 128 is a process killed by a signal — a crash, not a
  # finding. ruff has segfaulted on CI runners on members whose code did
  # not change, failing unrelated PRs, so a crash gets one retry. A real
  # finding exits 1 and is never retried; a second crash still fails.
  if [ "$status" -gt 128 ]; then
    echo "↻ ${CHECK_KEY}: ${name} crashed (signal $((status - 128))); retrying once" >&2
    status=0
    run_member "$member" "$@" || status=$?
  fi
  if [ "$status" -ne 0 ]; then
    failed+=("$name")
  fi
done

if [ "${#failed[@]}" -gt 0 ]; then
  echo "✗ ${CHECK_KEY} failed for: ${failed[*]}" >&2
  exit 1
fi
echo "✓ ${CHECK_KEY} passed for all ${count} applicable members"
