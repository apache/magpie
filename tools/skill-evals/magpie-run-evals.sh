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
# magpie-run-evals.sh — run one eval suite, step, or case against
# `claude -p` from inside the agent sandbox.
#
# THIS FILE IS THE SOURCE OF TRUTH FOR A USER-SCOPE COPY.
# The copy at ~/.claude/scripts/magpie-run-evals.sh is what
# `sandbox.excludedCommands` names, alongside a copy of the runner
# package at ~/.claude/scripts/skill_evals/. Same idiom as
# tools/agent-isolation/gpg-touch-overlay.sh; `setup-isolated-setup-verify`
# hash-compares the copies against these originals, and
# `setup-isolated-setup-update` reports drift.
#
# WHY THE EXECUTED CODE LIVES OUTSIDE THE REPOSITORY
#
# Excluding a command from the sandbox makes whatever that command
# executes run unsandboxed, so the executed code must not be writable
# by the thing being sandboxed. Two earlier shapes fail that test:
#
#   - Excluding the eval runner directly. `--cli` is an arbitrary
#     shell command, so the exclusion would not carve out the eval
#     harness, it would carve out `--cli "curl …"`. Pinning `--cli`
#     inside the exclusion *pattern* does not help either: argparse is
#     last-wins, so a second `--cli` later on the line still matches
#     the prefix.
#
#   - Excluding an in-repo wrapper and denying edits to it. A deny
#     stops the agent's editing tools, but the wrapper only matters
#     because of what it `exec`s, so tools/skill-evals/src/** would
#     have to be denied as well — a tree this repository develops.
#     (The mechanical cost of an in-repo deny is already handled and
#     is not the objection: `Edit(path)` denies merge into
#     `sandbox.filesystem.denyWrite`, so the path must also join the
#     `sandbox_write_denied` anchor in `.pre-commit-config.yaml` or
#     the three whitespace hooks abort `prek run --all-files`, per
#     #1309 — at the cost of those hooks no longer covering it.)
#
# ~/.claude/scripts/ is outside every `sandbox.filesystem.allowWrite`
# root, so the copies are already unwritable from sandboxed Bash
# without any deny rule touching a tracked path;
# `Edit(~/.claude/scripts/**)` closes the agent's editing tools over
# the same directory.
#
# WHAT IS STILL IN REACH, AND WHY THAT IS ACCEPTABLE
#
# The eval *fixtures* stay in the repository and remain agent-writable.
# They are data: the runner reads them, renders prompts, and pipes text
# to `claude -p`. Nothing under `evals/` is executed. Editing a fixture
# can change what a case asserts — a review problem, caught by the diff
# — but cannot run code outside the sandbox. It can route repository
# text to the model, which the session's own API access already allows.
#
# Usage, from the repository root:
#
#   ~/.claude/scripts/magpie-run-evals.sh tools/skill-evals/evals/<skill>/
#   ~/.claude/scripts/magpie-run-evals.sh tools/skill-evals/evals/<skill>/<step>/fixtures/<case>
#
# Invoke it by that exact path, alone on the line. `bash ~/…`, a
# relative spelling, or any pipe, redirect or `$(…)` in the same
# command stops the call matching the exclusion and it runs sandboxed
# again — reported, confusingly, as `Not logged in`. The same gotcha
# the `gh *` exclusion has.
set -euo pipefail

readonly EVALS_REL="tools/skill-evals/evals"

script_dir="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Installed layout mirrors container-gateway's — the package keeps its
# src/ shape under a named directory beside this script. In-repo layout
# (running the original rather than the copy) is this file's own
# tools/skill-evals/src/. Keeping one file valid in both places lets the
# drift check be a plain hash compare.
if [ -d "$script_dir/skill-evals/src/skill_evals" ]; then
  pythonpath="$script_dir/skill-evals/src"
elif [ -d "$script_dir/src/skill_evals" ]; then
  pythonpath="$script_dir/src"
else
  echo "magpie-run-evals.sh: no skill_evals package found near $script_dir" >&2
  echo "  reinstall the user-scope copy — see tools/skill-evals/README.md" >&2
  exit 2
fi

usage() {
  cat >&2 <<EOF
usage: magpie-run-evals.sh <path-under-$EVALS_REL/>

Runs the eval runner over exactly that path with --cli "claude -p",
from the current directory (the repository root).

Takes one argument and accepts no flags, because the exclusion that
lets this run unsandboxed rests on that shape. For any other shape
— --verbose, --tag, a different --cli or --grader-cli — call the
runner directly with the ! prefix, outside the sandbox:

  PYTHONPATH=tools/skill-evals/src python3 -m skill_evals.runner --help
EOF
  exit 2
}

[ "$#" -eq 1 ] || usage

target="$1"
case "$target" in
  -* | *..*) usage ;;
  "$EVALS_REL" | "$EVALS_REL"/*) ;;
  *) usage ;;
esac

[ -d "$target" ] || {
  echo "magpie-run-evals.sh: no such eval path: $target" >&2
  echo "  run from the repository root; paths are relative to it" >&2
  exit 2
}

export PYTHONPATH="$pythonpath"
exec python3 -m skill_evals.runner --cli "claude -p" -- "$target"
