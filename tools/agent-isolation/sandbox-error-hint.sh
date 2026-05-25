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
# sandbox-error-hint.sh — Claude Code PostToolUse hook (Bash matcher).
#
# After every Bash tool call, scan stdout + stderr for the literal
# error strings the sandbox produces when it blocks a legitimate
# workflow (SSH agent socket unreachable, loopback port blocked,
# docker / podman socket denied). On a match, emit a one-line
# `[sandbox-hint] …` to stderr pointing at the matching entry in
# `docs/setup/sandbox-troubleshooting.md` — so the agent (and the
# user) sees the catalog reference at the moment of failure,
# without having to remember the catalog exists.
#
# Recommended placement: user-scope `~/.claude/settings.json`, so
# the hint fires across every session on the host. The hook does
# NOT modify the tool's behaviour — the tool call still failed;
# this is purely an annotation layer pointing at the fix.
#
# Behaviour:
# - Reads the PostToolUse JSON envelope on stdin.
# - Filters to `tool_name == "Bash"`; everything else exits 0
#   silently (the patterns below are Bash-stderr-shaped).
# - Extracts `tool_response.stdout + tool_response.stderr`. Falls
#   back to treating `tool_response` as a plain string if the
#   object form is not present (defensive against Claude Code
#   hook-schema changes).
# - Greps the combined output for known sandbox-shaped signatures
#   (catalogued in `docs/setup/sandbox-troubleshooting.md`).
# - On match, prints a `[sandbox-hint] …` line to stderr and exits
#   1 (a non-zero exit that is *not* 2 surfaces stderr to the
#   user / model as a tool-result annotation; exit 2 would block
#   the call retroactively, which is wrong — the tool already
#   ran).
# - On no match, on any JSON-parse failure, or on any unexpected
#   input shape, exits 0 silently. The hook is intentionally
#   fail-open: a broken hint should never break a legitimate tool
#   call.
#
# Wiring (user-scope, applies to every session on the host):
#
#   {
#     "hooks": {
#       "PostToolUse": [
#         {
#           "matcher": "Bash",
#           "hooks": [
#             { "type": "command",
#               "command": "~/.claude/scripts/sandbox-error-hint.sh" }
#           ]
#         }
#       ]
#     }
#   }
#
# See `docs/setup/secure-agent-setup.md` → "Sandbox-error hint hook"
# for install steps, the trade-offs, and the relationship with the
# `setup-isolated-setup-doctor` skill (the doctor is the in-session
# diagnostic; this hook is the just-in-time hint).

set -u

input=$(cat)

# Filter to Bash tool calls. Everything else passes through silent.
tool_name=$(printf '%s' "$input" | jq -r '.tool_name // ""' 2>/dev/null || echo "")
[ "$tool_name" = "Bash" ] || exit 0

# Extract combined stdout + stderr from the tool response. Object
# shape is the current Claude Code contract; string-shape fallback
# is defensive for older / future schema variants.
output=$(printf '%s' "$input" | jq -r '
  if (.tool_response | type) == "object" then
    (.tool_response.stdout // "") + "\n" + (.tool_response.stderr // "")
  else
    (.tool_response // "")
  end
' 2>/dev/null || echo "")

[ -n "$output" ] || exit 0

# Pattern set. Each entry is (literal regex against output, anchor
# in docs/setup/sandbox-troubleshooting.md). Keep the regex
# specific — fail-open is fine, false-positive hints are noise.
hint=""
doc_path="docs/setup/sandbox-troubleshooting.md"

match() { printf '%s' "$output" | grep -qE "$1"; }

if match 'Could not open a connection to your authentication agent|agent refused operation|ssh-add: error fetching identities for protocol|Permission denied \(publickey\)'; then
  hint="SSH agent / Yubikey appears unreachable from inside the sandbox. See ${doc_path}#ssh-agent--yubikey-appears-unreachable-from-inside-the-sandbox"
elif match 'Cannot connect to the Docker daemon|open /var/run/docker\.sock: operation not permitted|Cannot connect to Podman|connect: permission denied.*podman\.sock'; then
  hint="Docker / Podman runtime socket denied by the sandbox. See ${doc_path}#docker--podman-command-fails-with-a-socket-error"
elif match '127\.0\.0\.1.*[Pp]ermission denied|[Oo]peration not permitted.*bind|Errno 49.*assign requested address|HTTP.*Connection refused.*127\.0\.0\.1'; then
  hint="Localhost port-bind or loopback HTTP may be sandbox-blocked. See ${doc_path}#test-cannot-bind-to-a-localhost-port"
fi

[ -n "$hint" ] || exit 0

esc=$(printf '\033')
yellow="${esc}[1;33m"
reset="${esc}[0m"

printf '%s[sandbox-hint]%s %s\n' "$yellow" "$reset" "$hint" >&2
printf '%s              %s Run %s/setup-isolated-setup-doctor%s for a structured probe of all three failure modes.\n' "$yellow" "$reset" "${esc}[1m" "${esc}[0m" >&2

exit 1
