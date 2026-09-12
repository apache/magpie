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

# record-svg.sh
#
# Record one Magpie run and write it to the animated SVG the docs embed.
#
# Eleven recordings, one per target:
#
#   setup      -> assets/quickstart/magpie-setup.svg
#                 embedded by docs/quick-start.md, Step 2
#   <family>   -> assets/quickstart/families/<family>-first-run.svg
#                 embedded by that family's README, Install & first runs
#
# These replaced fourteen still screenshots of a plugin list. A still could
# only ever show that a plugin was installed; what a reader actually needs to
# see is the thing running — and for a family, the first run is the
# interesting one, because 65 of the 74 skills open with a silent pre-flight
# that stops and proposes `/magpie-setup` when the project is not adopted.
# That is the moment the recording is for.
#
# Why SVG and not a GIF: the output is text. It goes through review as a
# diff, it carries its own Apache licence header, it loops natively in a
# GitHub README, it stays sharp at any width, and it costs a fraction of the
# bytes a terminal GIF would add to every source release.
#
# Usage (from the repo root):
#
#     tools/dev/record-svg.sh setup            # the quick-start recording
#     tools/dev/record-svg.sh security         # a family first-run recording
#     tools/dev/record-svg.sh --list           # every valid target
#     tools/dev/record-svg.sh security --from 2000   # drop the first 2s
#     tools/dev/record-svg.sh security --cast run.cast  # convert a cast
#     tools/dev/record-svg.sh security --keep-cast   # keep it for retrims
#
# Run it from your own terminal, in a scratch project — not in this repo and
# not inside an agent's shell.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SETUP_OUT="assets/quickstart/magpie-setup.svg"
FAMILY_DIR="assets/quickstart/families"
EXAMPLE_DIR="assets/examples"
COLS=145
ROWS=35
# The checker's hard cap. Warn here first, so you find out before committing.
SOFT_CAP_KB=1024
# Set once the scratch directory exists, for the failure trap.
WORKDIR=""
SLUG=""
TARGET=""

usage() {
    sed -n '19,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

# Families come from the live `family:` frontmatter, so this cannot drift from
# the set the plugins are generated from.
families() {
    grep -h '^family:' "${REPO_ROOT}"/skills/*/SKILL.md |
        sed 's/family: *//' | sort -u
}

# The skills a family plugin actually ships, from the generated symlinks —
# so an example target cannot name a command that does not exist.
family_skills() {
    local family="$1"
    [[ -d "${REPO_ROOT}/plugins/magpie-${family}/skills" ]] || return 0
    ls "${REPO_ROOT}/plugins/magpie-${family}/skills"
}

# One family's docs directory is not named after the family.
family_docs_dir() {
    case "$1" in
    issue) echo "docs/issue-management" ;;
    *) echo "docs/$1" ;;
    esac
}

list_targets() {
    printf 'The quick-start recording:\n'
    printf '  %-20s -> %s\n' "setup" "${SETUP_OUT}"
    printf '\nFamily first-run recordings:\n'
    local family
    while read -r family; do
        [[ "${family}" == "setup" ]] && continue
        printf '  %-20s -> %s\n' "${family}" "${FAMILY_DIR}/${family}-first-run.svg"
    done < <(families)
    printf '\nThe setup family has no first-run recording of its own: its first run\n'
    printf 'IS the quick-start recording above, so docs/setup/README.md embeds that.\n'
    printf '\nExample-command recordings:\n'
    printf '  <family>:<skill>     -> %s/<family>-<skill>.svg\n' "${EXAMPLE_DIR}"
    printf '  spelled exactly like the slash command, e.g. pairing:self-review\n'
    printf '  Any skill a family plugin ships is a valid target; only the ones a\n'
    printf '  README embeds are expected to exist. Currently recorded:\n'
    local existing
    existing="$(ls "${REPO_ROOT}/${EXAMPLE_DIR}" 2>/dev/null || true)"
    if [[ -z "${existing}" ]]; then
        printf '    (none yet)\n'
    else
        printf '    %s\n' ${existing}
    fi
}

resolve_output() {
    local target="$1"

    # <family>:<skill> — an example recording of one command. The target is
    # spelled exactly like the slash command it records.
    if [[ "${target}" == *:* ]]; then
        local family="${target%%:*}" skill="${target#*:}"
        families | grep -qx "${family}" || return 1
        family_skills "${family}" | grep -qx "${skill}" || return 1
        echo "${EXAMPLE_DIR}/${family}-${skill}.svg"
        return 0
    fi

    if [[ "${target}" == "setup" ]]; then
        echo "${SETUP_OUT}"
        return 0
    fi
    if families | grep -qx "${target}"; then
        echo "${FAMILY_DIR}/${target}-first-run.svg"
        return 0
    fi
    # `setup` is handled above: it is a family, but its first run is the
    # quick-start recording, so there is no families/setup-first-run.svg.
    return 1
}

# What to record, per target. Kept here rather than only in
# assets/quickstart/README.md so it is in front of you at recording time.
brief() {
    local target="$1"

    if [[ "${target}" == *:* ]]; then
        local family="${target%%:*}" skill="${target#*:}"
        cat <<BRIEF
Record ONE run of a single command, on a project that is already set up:

    /magpie-${family}:${skill}

This is an example of what the command does, not a first-run recording — no
pre-flight failure, no setup. Show the command and its result, and stop.

Frame a result a reader can learn the shape of: the summary line and the
findings, not a wall of scrollback. Use a small, made-up change as the
subject — a real one puts real code in a public repository forever.
BRIEF
    elif [[ "${target}" == "setup" ]]; then
        cat <<'BRIEF'
Record the quick start's two steps, in one take:

    /plugin marketplace add apache/magpie
    /plugin install magpie-setup@apache-magpie
    /magpie-setup

Let `/magpie-setup` run far enough to show it working: the method it picks,
the plan it prints, and the approval prompt. Stop at the first prompt — the
recording shows the shape of a run, not a whole install.
BRIEF
    else
        cat <<BRIEF
Record this family's FIRST run in a project that has not been adopted yet.
The pre-flight is the point of the shot:

    /plugin install magpie-${target}@apache-magpie
    <the first command from $(family_docs_dir "${target}")/README.md, "Try these first">

What the take must show, in order:

  1. the skill starting and its silent pre-flight finding no <project-config>;
  2. it STOPPING and proposing \`/magpie-setup\` rather than guessing;
  3. setup running;
  4. the same command again, now working.

That arc is why this recording exists. A take that skips straight to a
working run shows the one thing a reader can already assume.
BRIEF
    fi

    cat <<'COMMON'

Before you start:

  * Record in a SCRATCH project, not in a magpie checkout. This repo commits
    the auto-install block and is already adopted, so there is no pre-flight
    failure to show and the install step records as a no-op.
  * Nothing secret on screen — tokens, private repo names, reporter
    addresses, the window title, the status line. This file is TEXT: anything
    on screen is greppable in the repository forever. For the security
    family in particular, point it at a scratch tracker, never a real one.
  * KEEP IT SHORT. Every redraw of the TUI is frames in the SVG, and a
    spinner left running is pure weight. Thirty seconds is plenty; a couple
    of minutes will blow the size cap.
  * Dark theme, to match the other recordings.
COMMON
}

# asciinema 3 renamed --cols/--rows to --window-size and records asciicast v3,
# which svg-term-cli cannot open — it reads v1 and v2 only. Ask the binary in
# front of us which spelling it takes rather than parsing a version string.
asciinema_takes() {
    asciinema rec --help 2>/dev/null | grep -q -- "$1"
}

# Every flag the recording needs, one per line. Getting the size flag wrong is
# silent: asciinema 3 accepts --cols/--rows and ignores them, so the take comes
# out 80x24 while svg-term is told COLSxROWS and the frame no longer matches.
record_flags() {
    if asciinema_takes --window-size; then
        printf '%s\n' --window-size "${COLS}x${ROWS}"
    else
        printf '%s\n' --cols "${COLS}" --rows "${ROWS}"
    fi
    # asciinema 3 defaults to v3; pin v2 so no conversion is needed. asciinema
    # 2 has no such flag and already writes v2.
    if asciinema_takes --output-format; then
        printf '%s\n' --output-format asciicast-v2
    fi
}

# A conversion that dies must not cost you the take — a recording cannot be
# repeated, and npx reaching the network is the least reliable step here. Leave
# the cast where it is and say how to resume from it.
on_failure() {
    local status=$?
    [[ "${status}" -ne 0 ]] || return 0
    [[ -n "${WORKDIR}" && -f "${WORKDIR}/${SLUG}.cast" ]] || return 0
    echo >&2
    echo "The recording survived — retry the conversion without re-recording:" >&2
    echo "    tools/dev/record-svg.sh ${TARGET} --cast ${WORKDIR}/${SLUG}.cast" >&2
}
trap on_failure EXIT

# svg-term-cli opens v1 and v2 only, and fails with "only asciicast v1 and v2
# formats can be opened". A v3 cast still reaches here when --cast hands us one
# recorded elsewhere.
cast_is_v3() {
    head -c 512 "$1" | grep -q '"version"[[:space:]]*:[[:space:]]*3'
}

main() {
    local target="" cast="" keep_cast=0 from="" to=""
    while [[ $# -gt 0 ]]; do
        case "$1" in
        --list)
            cd "${REPO_ROOT}" && list_targets
            exit 0
            ;;
        -h | --help) usage 0 ;;
        --cast)
            cast="${2:?--cast needs a path}"
            keep_cast=1
            shift 2
            ;;
        --keep-cast)
            keep_cast=1
            shift
            ;;
        --from)
            from="${2:?--from needs milliseconds}"
            shift 2
            ;;
        --to)
            to="${2:?--to needs milliseconds}"
            shift 2
            ;;
        -*)
            echo "unknown option: $1" >&2
            usage 2 >&2
            ;;
        *)
            target="$1"
            shift
            ;;
        esac
    done

    cd "${REPO_ROOT}"

    [[ -n "${target}" ]] || {
        echo "error: name a target. Try --list." >&2
        exit 2
    }

    local out
    if ! out="$(resolve_output "${target}")"; then
        echo "error: '${target}' is neither 'setup' nor a live skill family." >&2
        echo >&2
        list_targets >&2
        exit 2
    fi

    command -v npx >/dev/null || {
        echo "error: npx not found — needed for svg-term-cli. Install Node." >&2
        exit 1
    }

    # One scratch directory for the cast and everything derived from it. BSD
    # mktemp only expands X's at the end of a template, so a per-file template
    # with a .cast suffix would hand back that literal name every run.
    local slug workdir
    slug="${target//[^A-Za-z0-9]/-}"
    workdir="$(mktemp -d "${TMPDIR:-/tmp}/magpie-rec.XXXXXX")"
    TARGET="${target}"
    SLUG="${slug}"
    WORKDIR="${workdir}"

    if [[ -z "${cast}" ]]; then
        command -v asciinema >/dev/null || {
            echo "error: asciinema not found. Install it:" >&2
            echo "    brew install asciinema      # macOS" >&2
            echo "    pipx install asciinema      # anywhere" >&2
            echo "Already have a recording? Pass it with --cast <file>." >&2
            exit 1
        }
        cast="${workdir}/${slug}.cast"
        echo "Target : ${out}"
        echo
        brief "${target}"
        echo
        read -r -p "Press Return to start recording (Ctrl-D to stop)... " _
        local -a rec_flags=()
        while IFS= read -r flag; do rec_flags+=("${flag}"); done < <(record_flags)
        asciinema rec "${rec_flags[@]}" "${cast}"
    fi

    [[ -s "${cast}" ]] || {
        echo "error: no recording captured — ${out} left as it was." >&2
        exit 1
    }

    local svg_in="${cast}"
    if cast_is_v3 "${cast}"; then
        if ! command -v asciinema >/dev/null || ! asciinema convert --help >/dev/null 2>&1; then
            echo "error: ${cast} is an asciicast v3 recording, and svg-term-cli" >&2
            echo "reads v1 and v2 only. Converting it needs asciinema 3:" >&2
            echo "    brew install asciinema      # macOS" >&2
            echo "    pipx install asciinema      # anywhere" >&2
            exit 1
        fi
        svg_in="${workdir}/${slug}.v2.cast"
        echo
        echo "Converting asciicast v3 -> v2 (svg-term-cli reads v1 and v2 only)..."
        asciinema convert --output-format asciicast-v2 --overwrite "${cast}" "${svg_in}"
    fi

    local -a trim=()
    [[ -n "${from}" ]] && trim+=(--from "${from}")
    [[ -n "${to}" ]] && trim+=(--to "${to}")

    local tmp_svg="${workdir}/${slug}.svg"
    echo
    echo "Converting to animated SVG..."
    npx --yes svg-term-cli \
        --in "${svg_in}" \
        --out "${tmp_svg}" \
        --window \
        --width "${COLS}" \
        --height "${ROWS}" \
        "${trim[@]}"

    # svg-term emits a bare <svg>. RAT wants an Apache header on a text file,
    # and a reviewer wants to know what the file is without opening the docs,
    # so both go in before the root element.
    {
        cat <<HEADER
<?xml version="1.0" encoding="UTF-8"?>
<!--
  Licensed to the Apache Software Foundation (ASF) under one
  or more contributor license agreements.  See the NOTICE file
  distributed with this work for additional information
  regarding copyright ownership.  The ASF licenses this file
  to you under the Apache License, Version 2.0 (the
  "License"); you may not use this file except in compliance
  with the License.  You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

  Unless required by applicable law or agreed to in writing,
  software distributed under the License is distributed on an
  "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
  KIND, either express or implied.  See the License for the
  specific language governing permissions and limitations
  under the License.

  A recording of a Magpie run (target: ${target}), embedded by the docs.
  Regenerate with tools/dev/record-svg.sh — do not hand-edit.
-->
HEADER
        cat "${tmp_svg}"
    } >"${out}"

    if [[ "${keep_cast}" -eq 1 ]]; then
        echo "Cast kept at ${cast} — retrim with --cast/--from/--to."
        # Removes the scratch directory only when --cast supplied the recording
        # from outside it; the kept cast keeps its own directory alive.
        rm -f "${tmp_svg}" "${workdir}/${slug}.v2.cast"
        rmdir "${workdir}" 2>/dev/null || true
    else
        rm -rf "${workdir}"
    fi

    local kb=$(($(wc -c <"${out}") / 1024))
    echo
    echo "Wrote ${out} (${kb} KB)"
    if [[ "${kb}" -gt "${SOFT_CAP_KB}" ]]; then
        echo
        echo "WARNING: ${kb} KB is over the ${SOFT_CAP_KB} KB guideline and may fail" >&2
        echo "the commit check. Re-record something shorter, or trim this one:" >&2
        echo "    tools/dev/record-svg.sh ${target} --cast <cast> --from 3000 --to 25000" >&2
        echo "(pass --keep-cast next time so the cast survives for retrimming)" >&2
    fi
    echo
    echo "Check it renders and animates, then:"
    echo "    python3 tools/dev/check-quickstart-recording.py"
    echo "    git add ${out}"
}

main "$@"
