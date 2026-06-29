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

# check-placeholders.sh
#
# Verifies that framework-level skill / tool docs refer to
# adopting-project specifics through placeholders only:
#
#   <PROJECT>   — adopting project's display name
#   <tracker>   — adopting project's private tracker repo slug
#   <upstream>  — adopting project's public source repo slug
#
# Hardcoded references to "apache/airflow", "airflow-s/airflow-s",
# "Apache Airflow", or related concrete project names slip in
# whenever someone copy-pastes from the legacy Airflow content.
# This linter catches them before merge.
#
# Intentional callouts that **explain** the placeholder convention
# (example blocks, "for Airflow, see..." pointers, title-prefix
# rendering examples) are allowlisted via inline markers
# (`example:`, `e.g.`, `for Airflow`, lines inside `<!-- ... -->`
# HTML comment blocks). Regular prose that names Airflow without
# such a marker is the surface this linter is built to catch.
#
# Run from repo root:
#   tools/dev/check-placeholders.sh
#
# Pre-commit invocation: see `.pre-commit-config.yaml`.

set -euo pipefail

# Patterns that should never appear outside the allowlist below.
# Each pattern must be a fixed string (grep -F).
FORBIDDEN_PATTERNS=(
  "apache/airflow"
  "airflow-s/airflow-s"
  "Apache Airflow"
  "apache.org/airflow"
)

# Files / directories where Airflow references are intentional:
# the framework's own onboarding / contributor docs use Airflow as
# the canonical example adopter; the bootstrap scaffold under
# `projects/_template/` may reference Airflow in pointers; this
# linter file itself contains the patterns to look for.
ALLOWLIST_PATHS=(
  "README.md"
  "AGENTS.md"
  "CONTRIBUTING.md"
  "docs/setup/secure-agent-setup.md"
  "docs/security/how-to-fix-a-security-issue.md"
  "docs/security/new-members-onboarding.md"
  "pyproject.toml"
  "projects/_template/"
  "organizations/"
  "tools/dev/check-placeholders.sh"
  ".github/"
  ".asf.yaml"
  "NOTICE"
  "LICENSE"
  # Eval fixture reports simulate real inbound emails and must contain
  # the concrete project name — they are not skill / tool docs.
  "tools/skill-evals/evals/"
)

# Inline markers that signal an intentional explanatory mention
# of Airflow on the same line. Lines matching any of these are
# treated as allowlisted.
# Entries are matched as literal bash substrings, not regex patterns.
INLINE_ALLOW_MARKERS=(
  "example:"
  "e.g."
  "for Airflow"
  "the Airflow"
  "legacy"
  "renamed"
  "future-renamed"
  "originally"
  "vendor>: <product>"
)

# Where to look. Only `.md` files under skills + tool adapter docs
# are scoped; Python sources under `tools/*/src/` and `tools/*/tests/`
# may legitimately mention Airflow in fixtures and docstrings.
SCAN_PATHS=(
  "skills"
  "tools"
)

is_path_allowlisted() {
  local file="$1"
  for allow in "${ALLOWLIST_PATHS[@]}"; do
    if [[ "$file" == "$allow"* ]]; then
      return 0
    fi
  done
  return 1
}

line_has_inline_allow_marker() {
  local line="$1"
  for marker in "${INLINE_ALLOW_MARKERS[@]}"; do
    if [[ "$line" == *"$marker"* ]]; then
      return 0
    fi
  done
  return 1
}

main() {
  local repo_root
  repo_root="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
  cd "$repo_root"

  local exit_code=0
  local matches_total=0

  echo "check-placeholders: scanning ${SCAN_PATHS[*]} for hardcoded project references..."

  for pattern in "${FORBIDDEN_PATTERNS[@]}"; do
    local matches
    matches=$(grep -rFn \
      --include='*.md' \
      "$pattern" \
      "${SCAN_PATHS[@]}" 2>/dev/null || true)

    if [[ -z "$matches" ]]; then
      continue
    fi

    while IFS= read -r match_line; do
      local file="${match_line%%:*}"
      local rest="${match_line#*:}"
      local _line_no="${rest%%:*}"
      local content="${rest#*:}"

      if is_path_allowlisted "$file"; then
        continue
      fi
      if line_has_inline_allow_marker "$content"; then
        continue
      fi

      if [[ $matches_total -eq 0 ]]; then
        {
          echo ""
          echo "FORBIDDEN: hardcoded project references found."
          echo ""
          echo "Skill / tool docs must use the placeholders <PROJECT>,"
          echo "<tracker>, and <upstream> instead of the concrete strings"
          echo "below. See AGENTS.md#placeholder-convention-used-in-skill-files."
          echo ""
          echo "Lines that explain the placeholder convention with an"
          echo "intentional example are allowlisted by including one of:"
          echo "  example:, e.g., for Airflow, the Airflow, legacy,"
          echo "  renamed, future-renamed, originally, vendor>: <product>"
          echo ""
        } >&2
      fi
      echo "  $match_line" >&2
      matches_total=$((matches_total + 1))
      exit_code=1
    done <<< "$matches"
  done

  if [[ $exit_code -eq 0 ]]; then
    echo "check-placeholders: OK (no hardcoded references in skills / tool docs)."
  else
    echo "" >&2
    echo "check-placeholders: $matches_total violation(s) — fix before commit." >&2
  fi

  return $exit_code
}

main "$@"
