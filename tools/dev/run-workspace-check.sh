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
#   mypy          → runs only on members with `[tool.mypy]`
#   pytest        → runs only on members with `[tool.pytest.ini_options]`
#
# `check-cmd` is the actual command-line passed to `uv run`. It
# may be a multi-token string (e.g. "ruff check") quoted as a
# single argv item.
#
# Per-member opt-out: a workspace member can skip one or more
# checks by adding a `[tool.magpie.checks]` block:
#
#   [tool.magpie.checks]
#   skip = ["mypy", "pytest"]
#
# Examples:
#   tools/dev/run-workspace-check.sh ruff        "ruff check"
#   tools/dev/run-workspace-check.sh ruff-format "ruff format --check"
#   tools/dev/run-workspace-check.sh mypy        mypy
#   tools/dev/run-workspace-check.sh pytest      "pytest --color=yes"
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

# On Apple Silicon Macs, git ships as x86_64 (Rosetta). Pre-commit hooks
# invoked by git therefore run in an x86_64 context where universal Python
# binaries also run as x86_64, which cannot load arm64-compiled extensions
# (e.g. mypy .so files, cffi, cryptography). Probe for this condition at
# runtime: if the workspace venv Python runs as x86_64 but arch -arm64 can
# switch it to arm64, prefer the native arm64 path for Python-based checks.
_NATIVE_PYTHON=""
_VENV_PYTHON="$(pwd)/.venv/bin/python3"
if [[ -x "$_VENV_PYTHON" ]]; then
  _CURR_ARCH=$("$_VENV_PYTHON" -c "import platform; print(platform.machine())" 2>/dev/null || echo "")
  _ARM64_ARCH=$(arch -arm64 "$_VENV_PYTHON" -c "import platform; print(platform.machine())" 2>/dev/null || echo "")
  if [[ "$_CURR_ARCH" == "x86_64" ]] && [[ "$_ARM64_ARCH" == "arm64" ]]; then
    _NATIVE_PYTHON="arch -arm64 $_VENV_PYTHON"
  fi
fi

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
    "mypy": "mypy",
    "pytest": "pytest",
}

section_key = SECTION_FOR_CHECK.get(check)
if section_key is None:
    sys.stderr.write(f"error: unknown check-key {check!r}\n")
    sys.exit(2)

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

if [ -z "$applicable" ]; then
  echo "→ ${CHECK_KEY}: no applicable workspace members (nothing to run)"
  exit 0
fi

count=$(echo "$applicable" | wc -l | tr -d ' ')
echo "→ workspace-check: ${CHECK_KEY} (${CHECK_CMD} $*) across ${count} members"

failed=()
for member in $applicable; do
  name=$(basename "$member")
  # `uv run --directory` so each member runs with its own `cwd` —
  # ruff / mypy / pytest configs resolve paths relative to the
  # member root.
  # On Apple Silicon + Rosetta, use native arm64 Python for Python-based
  # checks to avoid loading arm64 extensions from an x86_64 Python process.
  # Ruff is a Rust binary that already runs natively so no prefix is needed.
  # shellcheck disable=SC2086 # CHECK_CMD may legitimately be multi-token
  if [[ -n "$_NATIVE_PYTHON" ]] && [[ "$CHECK_KEY" != "ruff" ]] && [[ "$CHECK_KEY" != "ruff-format" ]]; then
    if ! (cd "$member" && $_NATIVE_PYTHON -m $CHECK_CMD "$@"); then
      failed+=("$name")
    fi
  elif ! uv run --directory "$member" $CHECK_CMD "$@"; then
    failed+=("$name")
  fi
done

if [ "${#failed[@]}" -gt 0 ]; then
  echo "✗ ${CHECK_KEY} failed for: ${failed[*]}" >&2
  exit 1
fi
echo "✓ ${CHECK_KEY} passed for all ${count} applicable members"
