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
#   start   SessionStart — python3 -m container_gateway serve --project <root> --daemon
#   stop    SessionEnd   — python3 -m container_gateway stop  --project <root>
#
# Sources are looked up in order: $MAGPIE_CONTAINER_GATEWAY_SRC,
# <root>/.apache-magpie/tools/container-gateway/src (snapshot adopters),
# <root>/tools/container-gateway/src (the framework repo itself).
# Extra serve flags: $MAGPIE_CONTAINER_GATEWAY_ARGS (e.g. "--egress require").
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
                 "$root/.apache-magpie/tools/container-gateway/src" \
                 "$root/tools/container-gateway/src"; do
    if [[ -n $candidate && -d $candidate/container_gateway ]]; then
        src="$candidate"
        break
    fi
done
[[ -n $src ]] || exit 0

if [[ $action == start ]]; then
    # shellcheck disable=SC2206  # word-splitting the extra args is the point
    extra=(${MAGPIE_CONTAINER_GATEWAY_ARGS:-})
    cmd=(python3 -m container_gateway serve --project "$root" --daemon "${extra[@]}")
else
    cmd=(python3 -m container_gateway stop --project "$root")
fi

if [[ -n ${MAGPIE_CONTAINER_GATEWAY_DRY_RUN:-} ]]; then
    printf 'PYTHONPATH=%s %s\n' "$src" "${cmd[*]}"
    exit 0
fi
PYTHONPATH="$src${PYTHONPATH:+:$PYTHONPATH}" "${cmd[@]}" >/dev/null 2>&1 || true
exit 0
