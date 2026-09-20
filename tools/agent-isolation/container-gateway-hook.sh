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
# container-gateway-hook.sh — Claude Code SessionStart / SessionEnd hook.
#
# Starts the per-project container gateway when a session begins and stops
# it when the session ends, so sandboxed podman / docker commands have a
# socket to talk to. Runs outside the sandbox, like every hook. Never fails
# the session: every exit is 0, and a missing gateway is silently a no-op.
#
#   start   SessionStart — python3 -m container_gateway serve --project=<root> --daemon
#   stop    SessionEnd   — python3 -m container_gateway stop  --project=<root>
#
# Trust model: the hook executes only code from locations the operator installed
# or pinned, never from the repository being opened. This prevents a malicious repo
# from shipping a gateway binary executed with the operator's privileges on
# SessionStart. Sources are looked up in order: $MAGPIE_CONTAINER_GATEWAY_SRC
# (development override), $HOME/.claude/scripts/container-gateway/src (operator
# install), <root>/.apache-magpie/tools/container-gateway/src (pinned snapshot).
#
# Two inherited variables are part of that trust model, because a repository can
# set both through project settings:
#
#   PYTHONPATH is *replaced*, never extended. An inherited entry ahead of (or
#   behind) the gateway's own source directory can shadow a stdlib module the
#   package imports, which would run repository code inside the gateway process.
#
#   $MAGPIE_CONTAINER_GATEWAY_ARGS is allow-listed, token by token, against the
#   flags below (e.g. "--egress require"). Anything else -- notably
#   --extra-bind-root, which widens the bind-mount roots -- makes the hook ignore
#   the whole variable and log one line to stderr rather than start a gateway
#   with a policy the repository chose.
#
# MAGPIE_CONTAINER_GATEWAY_DRY_RUN=1 prints the command instead of running it.

set -uo pipefail

action="${1:-}"
case "$action" in
    start|stop) ;;
    *) printf '%s: expected start|stop, got "%s"\n' "${0##*/}" "$action" >&2; exit 0 ;;
esac

payload="$(cat 2>/dev/null || true)"
cwd="$(printf '%s' "$payload" | jq -r '.cwd // empty' 2>/dev/null || true)"
[[ -n $cwd ]] || cwd="$PWD"
root="$(git -C "$cwd" rev-parse --show-toplevel 2>/dev/null || printf '%s' "$cwd")"
root="$(cd "$root" 2>/dev/null && pwd -P)" || exit 0

src=""
for candidate in "${MAGPIE_CONTAINER_GATEWAY_SRC:-}" \
                 "$HOME/.claude/scripts/container-gateway/src" \
                 "$root/.apache-magpie/tools/container-gateway/src"; do
    if [[ -n $candidate && -d $candidate/container_gateway ]]; then
        src="$candidate"
        break
    fi
done
[[ -n $src ]] || exit 0

# The only serve flags the hook will pass on from the environment. A value
# may be attached (--egress=require) or follow as the next token
# (--egress require); nothing else is accepted, and one bad token drops the
# whole variable.
allowed_flag='^--(egress|egress-port|egress-host|backend|backend-timeout|idle-timeout|log-level)(=.*)?$'

vet_extra_args() {
    # Echoes the vetted tokens; returns 1 when the variable must be ignored.
    local expecting=0 token
    for token in "$@"; do
        if (( expecting )); then
            expecting=0
            continue
        fi
        [[ $token =~ $allowed_flag ]] || return 1
        [[ $token == *=* ]] || expecting=1
    done
    (( expecting == 0 )) || return 1
    printf '%s\n' "$@"
}

if [[ $action == start ]]; then
    # shellcheck disable=SC2206  # word-splitting the extra args is the point
    extra=(${MAGPIE_CONTAINER_GATEWAY_ARGS:-})
    if (( ${#extra[@]} )) && ! vet_extra_args "${extra[@]}" >/dev/null; then
        printf '%s: ignoring MAGPIE_CONTAINER_GATEWAY_ARGS: %s is not an accepted serve flag\n' \
            "${0##*/}" "${MAGPIE_CONTAINER_GATEWAY_ARGS}" >&2
        extra=()
    fi
    cmd=(python3 -m container_gateway serve --project="$root" --daemon "${extra[@]}")
else
    cmd=(python3 -m container_gateway stop --project="$root")
fi

if [[ -n ${MAGPIE_CONTAINER_GATEWAY_DRY_RUN:-} ]]; then
    printf 'PYTHONPATH=%s %s\n' "$src" "${cmd[*]}"
    exit 0
fi
# PYTHONPATH is replaced, not extended: see the trust-model note above.
PYTHONPATH="$src" "${cmd[@]}" >/dev/null 2>&1 || true
exit 0
