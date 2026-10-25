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

# Not the hook's lookup ($MAGPIE_CONTAINER_GATEWAY_SRC, then the operator install
# in $HOME/.claude/scripts/container-gateway/src, never an in-repo copy): the
# hook runs outside the sandbox and must refuse sandbox-writable sources, while
# this probe runs inside it and only calls the read-only `status` subcommand, so
# an in-repo copy is safe here and keeps what the probe needs readable narrow.
# A marketplace install has neither in-repo copy, so fall back to the operator
# install the hook itself runs, which the reference `allowRead` already covers.
gw_src=".apache-magpie/tools/container-gateway/src"
[ -d "$gw_src/container_gateway" ] || gw_src="tools/container-gateway/src"
[ -d "$gw_src/container_gateway" ] || gw_src="$HOME/.claude/scripts/container-gateway/src"
status_json=""
status_rc=""
if [ -d "$gw_src/container_gateway" ]; then
  status_json=$(PYTHONPATH="$gw_src" python3 -m container_gateway status --project "$PWD" 2>/dev/null)
  status_rc=$?
fi

gw_state() {  # $1=backend -> serving | not-serving | not-running | refused | unknown
  # No status is unknown, not "not running": no gateway source at all, or a
  # source the PATH python3 cannot import. Only exit 2 without output is a
  # refusal: `status` raises SystemExit(2) when a run-directory component is
  # a symlink or has the wrong owner, type or mode.
  printf '%s' "$status_json" | python3 -c "
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print('refused' if '$status_rc' == '2' else 'unknown'); sys.exit()
if not d.get('running'):
    print('not-running')
elif '$1' in d.get('serving', []):
    print('serving')
else:
    print('not-serving')
" 2>/dev/null
}

_probe_timeout() {  # seconds cmd...; portable across GNU timeout, macOS Homebrew's gtimeout, or neither
  local secs="$1"
  shift
  if command -v timeout > /dev/null 2>&1; then
    timeout "$secs" "$@"
  elif command -v gtimeout > /dev/null 2>&1; then
    gtimeout "$secs" "$@"
  else
    "$@" &
    local cmd_pid=$!
    (sleep "$secs" && kill "$cmd_pid" 2> /dev/null) > /dev/null 2>&1 &
    local watchdog_pid=$!
    wait "$cmd_pid" 2> /dev/null
    local rc=$?
    kill "$watchdog_pid" 2> /dev/null
    wait "$watchdog_pid" 2> /dev/null
    return "$rc"
  fi
}

for rt in podman docker; do
  if ! command -v "$rt" > /dev/null 2>&1; then
    echo "PROBE: ${rt}-runtime → ⊘ ($rt not on PATH)"
    continue
  fi
  case "$rt" in podman) url="${CONTAINER_HOST:-}";; docker) url="${DOCKER_HOST:-}";; esac
  if [ -z "$url" ]; then
    echo "PROBE: ${rt}-runtime → ✗ ($( [ "$rt" = podman ] && echo CONTAINER_HOST || echo DOCKER_HOST ) unset — gateway not wired into settings)"
    continue
  fi
  # The CLIs read a unix:// URL's authority as a host component, so only the
  # absolute "unix:///path" spelling reaches the socket: "unix://./x" dials
  # "/.//x". A relative value still stats fine here (the socket does exist
  # relative to the cwd), so catch it by shape or the real cause is lost in
  # the generic failure branch below.
  case "$url" in
    unix:///*) ;;
    unix://*|unix:*)
      echo "PROBE: ${rt}-runtime → ✗ ($( [ "$rt" = podman ] && echo CONTAINER_HOST || echo DOCKER_HOST )=$url is not absolute — the CLIs do not resolve a relative unix:// value against the cwd; use unix:///<project>/.apache-magpie-local/run/$rt.sock if the project adopted Magpie, else unix:///<git-common-dir>/apache-magpie/run/<worktree-id>/$rt.sock)"
      continue ;;
  esac
  sock="${url#unix://}"
  case "$(gw_state "$rt")" in
    unknown)
      # Only `status` can vouch for the socket: a raw daemon socket answers
      # `<rt> info` just as well, so never pass without it.
      if [ -z "$status_rc" ]; then
        why="no gateway source in .apache-magpie/tools, tools/ or ~/.claude/scripts/container-gateway/src"
      else
        why="status exited rc=$status_rc without a report — is the python3 on PATH older than the gateway needs?"
      fi
      [ -S "$sock" ] && why="$why; a socket exists at $sock, but nothing confirms it is the gateway's"
      echo "PROBE: ${rt}-runtime → ✗ (gateway status unavailable — $why)"
      continue ;;
    refused)
      echo "PROBE: ${rt}-runtime → ✗ (gateway status refused the run directory — a component is a symlink or has the wrong owner, type or mode; inspect it from outside the sandbox)"
      continue ;;
    not-running)
      echo "PROBE: ${rt}-runtime → ✗ (gateway socket missing at $sock — container gateway not running)"
      continue ;;
    not-serving)
      case "$rt" in
        podman) hint="is the Podman machine started" ;;
        docker) hint="is Docker Desktop (or the docker daemon) started" ;;
      esac
      echo "PROBE: ${rt}-runtime → ✗ (gateway running without a $rt backend — $hint? start it, then restart the gateway)"
      continue ;;
  esac
  if [ ! -S "$sock" ]; then
    echo "PROBE: ${rt}-runtime → ✗ (gateway socket missing at $sock — container gateway not running)"
    continue
  fi
  # Held in a variable, not a file: /tmp is read-only inside the sandbox.
  out=$(_probe_timeout 15 "$rt" info 2>&1 > /dev/null); rc=$?
  if [ $rc -eq 0 ]; then
    echo "PROBE: ${rt}-runtime → ✓ ($rt reaches the container gateway at $sock)"
  else
    err=$(printf '%s\n' "$out" | head -1)
    case "$rc" in
      137|143)
        # The shell-fallback branch of _probe_timeout kills the child with
        # SIGTERM (rc 143) or, if it does not respond, SIGKILL (rc 137);
        # `$err` is typically empty in this case, so name the hang instead
        # of falling through to an uninformative "rc=143: ".
        echo "PROBE: ${rt}-runtime → ✗ (no response in 15s — $rt info hung; is the backend daemon stuck?)" ;;
      *)
        case "$err" in
          *"operation not permitted"*|*"Operation not permitted"*)
            echo "PROBE: ${rt}-runtime → ✗ (connect to $sock denied — add it to sandbox.network.allowUnixSockets)" ;;
          *"502"*|*"unreachable"*)
            echo "PROBE: ${rt}-runtime → ✗ (gateway up, backend down: $err)" ;;
          *) echo "PROBE: ${rt}-runtime → ✗ (rc=$rc: $err)" ;;
        esac ;;
    esac
  fi
done
