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
# Render an authored terminal transcript to a static SVG.
#
# The family screenshots are written, not captured. A capture needs a
# terminal, a scratch project and a human, and it needs all three again the
# next time any output moves — which is what left nine family recordings
# showing the same thing for months. A transcript is a text file: it reviews
# as a diff, a contributor can fix a line without a recording session, and it
# costs a fraction of a PNG set in every source release.
#
# What a capture gives that authoring does not is a guarantee that the picture
# matches the program. This script buys back the half of that guarantee it can:
# rendering is deterministic — same .txt, same .svg, byte for byte — so
# check-quickstart-recording.py can prove every committed .svg still matches
# its source. The other half, that the .txt still matches what the skill
# prints, is a human's judgement and assets/quickstart/README.md says so.
#
# Nothing here shells out to Node. record-svg.sh needs svg-term-cli for the one
# real recording; this runs on a bare clone and in CI.
#
# Usage:
#   tools/dev/render-screenshot.sh <path.txt>   # write the sibling .svg
#   tools/dev/render-screenshot.sh --all        # render every transcript
#   tools/dev/render-screenshot.sh --check      # fail if any .svg is stale
set -euo pipefail

# Every authored transcript lives under here: the per-family screenshots and
# the first-run walkthrough. The one real recording, magpie-setup.svg, sits at
# the top of this tree with no transcript -- it is captured, not written.
SHOTS_DIR="assets/quickstart"
RECORDING="assets/quickstart/magpie-setup.svg"

# The recorder's palette, so the authored set and the one real recording read
# as one thing rather than two.
BG="#1d1f21"
BAR="#2b2e31"
DOT="#3f4448"
FG="#c5c8c6"
MUTED="#8a8f94"
CMD="#8abeb7"
OK="#7f9f7f"
WARN="#d8a657"
BAD="#cc6666"

# 18px in a monospace face advances 0.6em per cell. Everything below is
# integer arithmetic in tenths so the geometry is identical on every machine —
# a float formatted differently by a different awk would change the bytes.
FONT_SIZE=18
ADVANCE_TENTHS=108
LINE_HEIGHT=26
PAD_X=28
PAD_TOP=30
BAR_H=34
MIN_WIDTH=640

usage() {
    cat <<'USAGE'
Usage:
  tools/dev/render-screenshot.sh <path.txt>   # write the sibling .svg
  tools/dev/render-screenshot.sh --all        # render every transcript
  tools/dev/render-screenshot.sh --check      # fail if any .svg is stale
USAGE
}

licence_header() {
    cat <<'HEADER'
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

  GENERATED FILE — do not edit.

  Rendered from the .txt beside it by tools/dev/render-screenshot.sh.
  Edit the transcript and re-render; check-quickstart-recording.py fails
  the build when this file no longer matches its source.
-->
HEADER
}

render() {
    local txt="$1"
    if [[ ! -f "${txt}" ]]; then
        echo "error: ${txt}: no such transcript" >&2
        return 1
    fi
    if [[ ! -s "${txt}" ]]; then
        echo "error: ${txt}: transcript is empty" >&2
        return 1
    fi

    licence_header
    BG="${BG}" BAR="${BAR}" DOT="${DOT}" FG="${FG}" MUTED="${MUTED}" \
    CMD="${CMD}" OK="${OK}" WARN="${WARN}" BAD="${BAD}" \
    FONT_SIZE="${FONT_SIZE}" ADVANCE_TENTHS="${ADVANCE_TENTHS}" \
    LINE_HEIGHT="${LINE_HEIGHT}" PAD_X="${PAD_X}" PAD_TOP="${PAD_TOP}" \
    BAR_H="${BAR_H}" MIN_WIDTH="${MIN_WIDTH}" TITLE="$(basename "${txt}" .txt)" \
    LC_ALL=C awk '
    function esc(s) {
        gsub(/&/, "\\&amp;", s)
        gsub(/</, "\\&lt;", s)
        gsub(/>/, "\\&gt;", s)
        return s
    }
    # Colour is a function of the line, never of a marker the transcript has
    # to carry: a transcript stays something you can read as a terminal.
    function colour(s,   t) {
        t = s
        sub(/^[ \t]+/, "", t)
        if (t ~ /^> /)              return ENVIRON["CMD"]
        if (t ~ /^\342\234\223/)    return ENVIRON["OK"]     # U+2713 check
        if (t ~ /^\342\232\240/)    return ENVIRON["WARN"]   # U+26A0 warning
        if (t ~ /^\342\234\227/)    return ENVIRON["BAD"]    # U+2717 ballot X
        if (t ~ /^[A-Z][A-Z0-9 _-]*$/ && length(t) > 1) return ENVIRON["WARN"]
        return ENVIRON["FG"]
    }
    # Width is measured in BYTES, under a forced LC_ALL=C, because length() in
    # awk is locale-dependent: measuring characters would make the output
    # depend on the locale of the machine that rendered it, and a renderer
    # whose bytes move between machines cannot be checked for staleness at all.
    # The cost is that a line carrying a multi-byte glyph measures a little
    # wide and the frame gains a few pixels of right-hand padding. Padding is
    # invisible; a false staleness failure is not.
    { line[NR] = $0; if (length($0) > cols) cols = length($0) }
    END {
        if (NR == 0) exit 1
        pad_x = ENVIRON["PAD_X"] + 0
        bar_h = ENVIRON["BAR_H"] + 0
        pad_top = ENVIRON["PAD_TOP"] + 0
        lh = ENVIRON["LINE_HEIGHT"] + 0
        adv = ENVIRON["ADVANCE_TENTHS"] + 0
        w = 2 * pad_x + int((cols * adv + 9) / 10)
        if (w < ENVIRON["MIN_WIDTH"] + 0) w = ENVIRON["MIN_WIDTH"] + 0
        h = bar_h + pad_top + NR * lh + pad_x

        printf "<svg xmlns=\"http://www.w3.org/2000/svg\" viewBox=\"0 0 %d %d\"\n", w, h
        printf "     width=\"%d\" height=\"%d\" role=\"img\"\n", w, h
        printf "     data-magpie-rendered=\"render-screenshot\"\n"
        printf "     aria-label=\"Terminal transcript: %s\">\n", ENVIRON["TITLE"]
        printf "  <title>%s</title>\n", ENVIRON["TITLE"]
        printf "  <rect width=\"%d\" height=\"%d\" rx=\"10\" fill=\"%s\"/>\n", w, h, ENVIRON["BG"]
        printf "  <rect x=\"0\" y=\"0\" width=\"%d\" height=\"%d\" rx=\"10\" fill=\"%s\"/>\n", w, bar_h, ENVIRON["BAR"]
        printf "  <rect x=\"0\" y=\"%d\" width=\"%d\" height=\"10\" fill=\"%s\"/>\n", bar_h - 10, w, ENVIRON["BAR"]
        printf "  <circle cx=\"22\" cy=\"17\" r=\"6\" fill=\"%s\"/>\n", ENVIRON["DOT"]
        printf "  <circle cx=\"44\" cy=\"17\" r=\"6\" fill=\"%s\"/>\n", ENVIRON["DOT"]
        printf "  <circle cx=\"66\" cy=\"17\" r=\"6\" fill=\"%s\"/>\n", ENVIRON["DOT"]
        printf "  <g font-family=\"ui-monospace,SFMono-Regular,Menlo,Consolas,monospace\""
        printf " font-size=\"%s\" xml:space=\"preserve\">\n", ENVIRON["FONT_SIZE"]
        for (i = 1; i <= NR; i++) {
            y = bar_h + pad_top + i * lh - 6
            if (line[i] ~ /^[ \t]*$/) continue
            printf "    <text x=\"%d\" y=\"%d\" fill=\"%s\">%s</text>\n", \
                pad_x, y, colour(line[i]), esc(line[i])
        }
        print "  </g>"
        print "</svg>"
    }
    ' "${txt}"
}

transcripts() {
    find "${SHOTS_DIR}" -name '*.txt' -type f | LC_ALL=C sort
}

write_one() {
    local txt="$1" svg="${1%.txt}.svg"
    render "${txt}" > "${svg}"
    echo "${svg}"
}

check_one() {
    local txt="$1" svg="${1%.txt}.svg"
    if [[ ! -f "${svg}" ]]; then
        echo "${svg}: missing — run tools/dev/render-screenshot.sh ${txt}" >&2
        return 1
    fi
    # Render to a file rather than comparing against a pipe: a sandbox that
    # denies the agent stdin turns `diff -` into a failure that reads exactly
    # like drift, and a staleness check nobody trusts is worse than none.
    local tmp
    tmp="$(mktemp "${TMPDIR:-/tmp}/render-screenshot.XXXXXX")"
    render "${txt}" > "${tmp}"
    if ! cmp -s "${tmp}" "${svg}"; then
        rm -f "${tmp}"
        echo "${svg}: stale — does not match ${txt}; re-render it" >&2
        return 1
    fi
    rm -f "${tmp}"
}

main() {
    case "${1:-}" in
        "" | -h | --help)
            usage
            [[ -z "${1:-}" ]] && return 2 || return 0
            ;;
        --all)
            local txt
            while IFS= read -r txt; do write_one "${txt}"; done < <(transcripts)
            ;;
        --check)
            local txt rc=0
            while IFS= read -r txt; do check_one "${txt}" || rc=1; done < <(transcripts)
            # An .svg with no .txt beside it is not this script's to render,
            # but it is exactly the state --check exists to refuse.
            local svg
            while IFS= read -r svg; do
                [[ "${svg}" == "${RECORDING}" ]] && continue
                [[ -f "${svg%.svg}.txt" ]] || { echo "${svg}: no transcript beside it" >&2; rc=1; }
            done < <(find "${SHOTS_DIR}" -name '*.svg' -type f | LC_ALL=C sort)
            return "${rc}"
            ;;
        -*)
            echo "error: unknown option ${1}" >&2
            usage >&2
            return 2
            ;;
        *)
            write_one "$1"
            ;;
    esac
}

main "$@"
