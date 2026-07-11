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
# check-tool-updates.sh
#
# Read pinned-versions.toml and report on upstream releases that
# (a) are newer than the pinned versions, AND (b) have themselves
# aged past each tool's `cooldown_days` (default 7).
#
# Cooldown is per-tool — the manifest's `[tools.<name>]` table can
# carry a `cooldown_days = N` override of the 7-day default.
#
# `claude-code` is in the manifest with a `min_version` floor, not an
# exact `version` pin: the agent runtime installs at `@latest` (see
# pinned-versions.toml), so there is no pin to drift and nothing to
# age past a cooldown, and it is not reported here. Its floor is
# enforced (hard-fail) by `setup-isolated-setup-verify`, not by this
# update-check. Only the pinned sandbox primitives are surfaced.
#
# Output is informational only — the script never installs anything,
# never edits pinned-versions.toml, never opens a PR. It just
# surfaces candidates for the framework maintainer to review,
# matching the *propose-then-confirm* pattern used elsewhere in
# the framework.
#
# Recommended cadence: run weekly. The README in this directory
# suggests wiring it to `/schedule weekly` so the agent runtime
# surfaces candidates without manual prompting.

set -euo pipefail

# Resolve script directory so the script works whether invoked from
# anywhere in the repo or from a stale `cwd`.
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MANIFEST="${HERE}/pinned-versions.toml"

if [[ ! -r "$MANIFEST" ]]; then
  echo "error: cannot read $MANIFEST" >&2
  exit 1
fi

# Default cooldown window. Mirrors `[tool.uv] exclude-newer = "7 days"`
# in the root pyproject.toml and the dependabot weekly cooldown of 7
# days in `.github/dependabot.yml`. Per-tool overrides via the
# manifest's `cooldown_days` field take precedence — see
# `pinned-versions.toml` for the convention. Releases within a tool's
# cooldown window are NOT proposed as upgrade candidates yet.
DEFAULT_COOLDOWN_DAYS=7

now_epoch=$(date -u +%s)

# ---------------------------------------------------------------------
# Per-tool upstream lookup. Each function takes a per-tool cooldown
# window in days as its second argument and prints the latest
# aged-past-cooldown release in the form "version<TAB>YYYY-MM-DD". A
# non-zero exit code means the upstream lookup failed (rate limit,
# network error, etc.) — the caller continues with other tools.
# ---------------------------------------------------------------------

# GitHub releases lookup (used by bubblewrap and claude-code).
# Picks the most recent release whose `published_at` is at least
# `cooldown_days` old.
gh_latest_aged() {
  local repo="$1"
  local cooldown_days="$2"
  local cutoff=$(( now_epoch - cooldown_days * 86400 ))
  curl -fsSL "https://api.github.com/repos/${repo}/releases?per_page=20" \
    | python3 -c '
import json, sys
from datetime import datetime
cutoff = '"$cutoff"'
for r in json.load(sys.stdin):
    pub = datetime.fromisoformat(r["published_at"].replace("Z", "+00:00"))
    if pub.timestamp() <= cutoff:
        # strip a leading "v" so the script outputs PEP-440-ish version
        tag = r["tag_name"].lstrip("v")
        print(f"{tag}\t{pub.date().isoformat()}")
        break
'
}

# socat upstream is a static HTML index; scrape the highest version
# tarball whose mtime is older than `cooldown_days`.
#
# Implementation note — portability. Both `tac` (used to reverse a
# sorted list) and `date -d <RFC-2822-string>` (used to parse the
# server's Last-Modified header) are GNU-only. macOS ships BSD
# coreutils which have neither. The version reversal is folded into
# `sort -uVr` (descending unique versions); date parsing is delegated
# to python3's `email.utils.parsedate_to_datetime`, which is the
# stdlib HTTP-date parser and is available everywhere python3 is.
socat_latest_aged() {
  local cooldown_days="$1"
  local cutoff=$(( now_epoch - cooldown_days * 86400 ))
  # The download index has a fairly stable shape — `socat-X.Y.Z.W.tar.gz`
  # rows in a directory listing. Pick the highest version whose
  # `Last-Modified` (per HEAD) is older than the cutoff.
  local index versions
  index="$(curl -fsSL http://www.dest-unreach.org/socat/download/)" || return 1
  versions=$(echo "$index" | grep -oE 'socat-[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+\.tar\.gz' | sort -uVr)
  for v in $versions; do
    local ver mtime parsed mtime_epoch mtime_date
    ver="${v#socat-}"
    ver="${ver%.tar.gz}"
    mtime=$(curl -sI "http://www.dest-unreach.org/socat/download/${v}" \
              | awk -F': ' '/^[Ll]ast-[Mm]odified:/ {print $2}' | tr -d '\r')
    if [[ -z "$mtime" ]]; then
      continue
    fi
    parsed=$(MTIME="$mtime" python3 <<'PY' || true
import os
from email.utils import parsedate_to_datetime
try:
    dt = parsedate_to_datetime(os.environ["MTIME"])
    print(f"{int(dt.timestamp())}\t{dt.strftime('%Y-%m-%d')}")
except Exception:
    raise SystemExit(1)
PY
)
    [[ -z "$parsed" ]] && continue
    mtime_epoch=${parsed%%$'\t'*}
    mtime_date=${parsed##*$'\t'}
    if (( mtime_epoch <= cutoff )); then
      printf '%s\t%s\n' "$ver" "$mtime_date"
      return 0
    fi
  done
  return 1
}

# ---------------------------------------------------------------------
# Manifest parsing. Each `[tools.<name>]` table that carries an exact
# `version` pin contributes one pinned (version, released) tuple.
# Tables that carry only a `min_version` floor (the agent runtime,
# `claude-code`, which tracks `@latest`) are NOT bump candidates and
# are skipped here — the floor is enforced by
# `setup-isolated-setup-verify`, not by this update-check.
# ---------------------------------------------------------------------

read_pinned() {
  python3 - "$MANIFEST" "$DEFAULT_COOLDOWN_DAYS" <<'PY'
import sys, tomllib
default_cooldown = int(sys.argv[2])
with open(sys.argv[1], "rb") as f:
    cfg = tomllib.load(f)
for name, t in cfg.get("tools", {}).items():
    if "version" not in t:            # min_version-only tool (e.g. claude-code) — not a pin
        continue
    cooldown = int(t.get("cooldown_days", default_cooldown))
    print(f"{name}\t{t['version']}\t{t['released']}\t{cooldown}")
PY
}

# ---------------------------------------------------------------------
# Report.
# ---------------------------------------------------------------------

printf '%-14s %-10s %-12s %-10s %-12s %s\n' \
  TOOL PINNED 'PINNED@' UPSTREAM 'UPSTREAM@' STATUS
printf '%-14s %-10s %-12s %-10s %-12s %s\n' \
  ------ ------ ------- -------- --------- ------

while IFS=$'\t' read -r name pinned_ver pinned_date cooldown_days; do
  case "$name" in
    bubblewrap)
      latest_line="$(gh_latest_aged containers/bubblewrap "$cooldown_days" || true)"
      ;;
    socat)
      latest_line="$(socat_latest_aged "$cooldown_days" || true)"
      ;;
    *)
      latest_line=""
      ;;
  esac

  if [[ -z "$latest_line" ]]; then
    printf '%-14s %-10s %-12s %-10s %-12s %s\n' \
      "$name" "$pinned_ver" "$pinned_date" "?" "?" \
      'upstream lookup failed (rate limit / network)'
    continue
  fi

  upstream_ver="${latest_line%%$'\t'*}"
  upstream_date="${latest_line##*$'\t'}"

  if [[ "$upstream_ver" == "$pinned_ver" ]]; then
    status='✓ up to date'
  else
    # Note: this lexical comparison is a heuristic — semver-aware
    # comparison would be better, but every tool we track here uses
    # well-formed dotted-version strings, so plain `<` does the
    # right thing for ordered output. The maintainer is the actual
    # decision-maker; the script just surfaces candidates.
    status="upgrade candidate (aged past ${cooldown_days}-day cooldown)"
  fi

  printf '%-14s %-10s %-12s %-10s %-12s %s\n' \
    "$name" "$pinned_ver" "$pinned_date" "$upstream_ver" "$upstream_date" "$status"
done < <(read_pinned)

cat <<'EOF'

To bump a pinned tool:
  1. Confirm the candidate's release-notes / changelog are clean.
  2. Edit `tools/agent-isolation/pinned-versions.toml` — update both
     `version` and `released` for that tool, plus the top-level
     `pinned_at` field to today's date.
  3. Update the install command in `docs/setup/secure-agent-setup.md` if the
     distro package version has shifted.
  4. Open the bump as its own PR with a short rationale.

Each tool's cooldown is the floor for *eligibility*, not a mandate
to upgrade — the framework maintainer is welcome to defer a bump
indefinitely if the new version doesn't add value. The default
cooldown is 7 days; tools can override via `cooldown_days = N` in
the manifest. `claude-code` is not pinned or reported here — the
agent runtime tracks `@latest` for the newest security fixes and
carries a `min_version` floor that setup-isolated-setup-verify
enforces (hard-fail) instead.
EOF
