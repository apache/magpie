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

# capture-screenshot.sh
#
# Capture one quick-start screenshot and drop it at the exact path
# `docs/quick-start.md` (or a family README) already references, at the
# size and cleanliness the rest of `assets/` uses.
#
# The screenshots ship as generated placeholders reading "screenshot
# pending" so the pages render and the offline link check passes; this
# script is how a real capture replaces one. Nothing in the docs changes
# — the alt text already describes each shot.
#
# It captures a whole window — you click the one you want and get it
# framed to its own bounds, so every shot in a set is cropped the same way
# instead of by however steady the drag was. What is *in* that window is
# still yours to arrange, so the brief prints before the camera opens: the
# framing is the part that is easy to get wrong and expensive to notice
# later (six plugins in a shot that argues for installing one).
#
# Usage (from the repo root):
#
#     tools/dev/capture-screenshot.sh security          # a family shot
#     tools/dev/capture-screenshot.sh claude-code       # a harness shot
#     tools/dev/capture-screenshot.sh gemini --delay 5  # 5s before the camera
#     tools/dev/capture-screenshot.sh --list
#
# macOS only: `screencapture` is a system binary and has no portable
# equivalent. Run it from your own terminal — Screen Recording permission
# is granted per calling application, so invoking it from inside an agent's
# shell tends to fail silently rather than prompt.

set -euo pipefail

WIDTH=1700 # matches the existing assets/session-*.png captures
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FAMILY_DIR="assets/quickstart/families"
HARNESS_DIR="assets/quickstart"

HARNESSES=("claude-code" "codex" "vscode" "gemini")

usage() {
    # 19 to the first blank line: the whole header block, whatever it grows to.
    sed -n '19,/^$/p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
    exit "${1:-0}"
}

# Families come from the live `family:` frontmatter, so this cannot drift
# from the set the plugins are generated from.
families() {
    grep -h '^family:' "${REPO_ROOT}"/skills/*/SKILL.md |
        sed 's/family: *//' | sort -u
}

list_targets() {
    echo "Harness shots:"
    printf '  %s\n' "${HARNESSES[@]}"
    echo "Family shots:"
    families | sed 's/^/  /'
}

# What to frame, per target. Kept here rather than only in
# assets/quickstart/README.md so it is in front of you at capture time.
brief() {
    local target="$1"
    case "${target}" in
    claude-code)
        echo "Run: /plugin marketplace add apache/magpie"
        echo "     /plugin install magpie-setup@apache-magpie"
        echo "     /plugin install magpie-pr-management@apache-magpie"
        echo "     /plugin"
        echo "Frame: the plugin list with BOTH family plugins installed and enabled."
        echo "       Do not capture the all-in-one 'magpie' plugin — per-family is"
        echo "       the recommended install and the shot should show that."
        ;;
    codex)
        echo "Run: codex plugin marketplace add apache/magpie"
        echo "     codex plugin install magpie"
        echo "     /plugins        (inside Codex, or 'codex plugin list')"
        echo "Frame: the output listing magpie as installed."
        ;;
    vscode)
        echo "Install from the repo URL: https://github.com/apache/magpie"
        echo "Frame: the VS Code plugin view showing Apache Magpie installed."
        ;;
    gemini)
        echo "Run: gemini extensions install https://github.com/apache/magpie"
        echo "     gemini extensions list"
        echo "Frame: the terminal output showing the magpie extension."
        ;;
    *)
        echo "Run: /plugin marketplace add apache/magpie"
        echo "     /plugin install magpie-${target}@apache-magpie"
        echo "     /plugin"
        echo "Frame: the plugin list showing ONLY magpie-${target} installed and"
        echo "       enabled. One family per shot."
        ;;
    esac
    echo
    case "${target}" in
    codex | vscode | gemini) ;;
    *)
        # Every Claude Code shot lists plugins, and a project that commits the
        # auto-install block arrives with three of them already enabled — so
        # the "only this one" framing above is unreproducible there.
        echo "Capture this in a project WITHOUT the auto-install block in its"
        echo ".claude/settings.json, and with no magpie-* entries in your own"
        echo "user-scope enabledPlugins. Otherwise magpie-setup, magpie-utilities"
        echo "and magpie-agent-guard are already in the list and the shot shows"
        echo "four plugins where it should show one."
        echo
        ;;
    esac
    echo "The whole clicked window is captured, so check before you click: no"
    echo "tokens, private repo names, or reporter addresses anywhere in it —"
    echo "including the title bar, the status line, and any tab titles."
    echo "Keep light/dark consistent across all the shots in a set."
}

resolve_output() {
    local target="$1"
    for h in "${HARNESSES[@]}"; do
        if [[ "${target}" == "${h}" ]]; then
            echo "${HARNESS_DIR}/${target}-install.png"
            return 0
        fi
    done
    if families | grep -qx "${target}"; then
        echo "${FAMILY_DIR}/${target}-install.png"
        return 0
    fi
    return 1
}

main() {
    local target="" delay=0
    while [[ $# -gt 0 ]]; do
        case "$1" in
        --list)
            list_targets
            exit 0
            ;;
        -h | --help) usage 0 ;;
        --delay)
            delay="${2:?--delay needs a number of seconds}"
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

    [[ -n "${target}" ]] || {
        echo "error: name a target. Try --list." >&2
        exit 2
    }

    local out
    if ! out="$(resolve_output "${target}")"; then
        echo "error: '${target}' is neither a harness nor a live skill family." >&2
        echo >&2
        list_targets >&2
        exit 2
    fi

    command -v screencapture >/dev/null || {
        echo "error: screencapture not found — this script is macOS-only." >&2
        exit 1
    }

    cd "${REPO_ROOT}"
    echo "Target : ${out}"
    echo
    brief "${target}"
    echo
    read -r -p "Set the window up, then press Return and click the window to capture... " _

    local tmp
    tmp="$(mktemp -t magpie-shot).png"
    # -i interactive, -w restricted to window selection so a click grabs the
    # whole window rather than a hand-dragged region, -o drops the window
    # shadow so the image crops flush.
    if [[ "${delay}" -gt 0 ]]; then
        screencapture -T "${delay}" -i -w -o "${tmp}"
    else
        screencapture -i -w -o "${tmp}"
    fi

    [[ -s "${tmp}" ]] || {
        echo "Cancelled — ${out} left as it was." >&2
        rm -f "${tmp}"
        exit 1
    }

    # Resize to the width the other assets use and drop EXIF: a screen
    # capture carries display and device metadata that has no business in a
    # published asset.
    if command -v magick >/dev/null; then
        magick "${tmp}" -resize "${WIDTH}x>" -strip "${out}"
    elif command -v sips >/dev/null; then
        sips --resampleWidth "${WIDTH}" "${tmp}" --out "${out}" >/dev/null
        echo "note: used sips; EXIF not stripped. Install ImageMagick for that." >&2
    else
        echo "error: neither magick nor sips found — cannot normalise." >&2
        rm -f "${tmp}"
        exit 1
    fi
    rm -f "${tmp}"

    echo
    echo "Wrote ${out}"
    command -v magick >/dev/null && magick identify -format '       %wx%h, %b%n' "${out}"
    echo "Review it, then: git add ${out}"
}

main "$@"
