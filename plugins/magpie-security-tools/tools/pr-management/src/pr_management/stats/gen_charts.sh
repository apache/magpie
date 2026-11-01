#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
#
# gen_charts.sh — emit self-contained inline-SVG line charts for the
# pr-management-stats HTML dashboard (see `pr-management stats build`).
#
# No external JS/CSS — the SVG is embedded directly in dashboard.html so
# gistpreview.github.io renders it offline-of-CDN. GitHub-dark palette,
# gridlines, axis labels, data-point markers + value annotations.
#
# Usage:
#   chart <ymax> "<title>" "<name>:<color>:<v_oldest>,...,<v_newest>" [more series...]
#
#   - X positions are evenly spaced; pass the x-axis labels in $XLABELS
#     (oldest on the LEFT — a timeline reads past -> present).
#   - Colours: red #da3633  amber #d29922  blue #388bfd  green #2ea043  purple #a371f7
#
# Example (4 age buckets, 2 series):
#   XLABELS=(">12w" "8-12w" "4-8w" "2-4w" "0-2w")
#   chart 40 "Ready PRs by why they wait (oldest left -> newest right)" \
#     "never:#da3633:3,4,31,34,36" "approved:#2ea043:3,3,6,7,4"
set -u

# plot box
X0=55; X1=585; YT=25; YB=185
# default x positions for up to 5 points (override XS / XLABELS as needed)
XS=(${XS[@]:-55 188 320 452 585})
XLABELS=(${XLABELS[@]:-})

chart() {
  local ymax="$1" title="$2"; shift 2
  local n=${#XS[@]}
  echo "<svg viewBox=\"0 0 640 215\" width=\"100%\" style=\"max-width:640px;background:#0d1117;border:1px solid #30363d;border-radius:8px\">"
  # y gridlines + labels (5 lines)
  local i yv yp
  for i in 0 1 2 3 4; do
    yv=$(awk -v m="$ymax" -v i="$i" 'BEGIN{printf "%d", m*i/4}')
    yp=$(awk -v t="$YT" -v b="$YB" -v i="$i" 'BEGIN{printf "%.1f", b-(b-t)*i/4}')
    echo "<line x1=\"$X0\" y1=\"$yp\" x2=\"$X1\" y2=\"$yp\" stroke=\"#21262d\"/>"
    echo "<text x=\"48\" y=\"$(awk -v y=$yp 'BEGIN{print y+4}')\" fill=\"#8b949e\" font-size=\"10\" text-anchor=\"end\">$yv</text>"
  done
  # x labels
  for i in $(seq 0 $((n-1))); do
    [ -n "${XLABELS[$i]:-}" ] && echo "<text x=\"${XS[$i]}\" y=\"203\" fill=\"#8b949e\" font-size=\"10\" text-anchor=\"middle\">${XLABELS[$i]}</text>"
  done
  echo "<text x=\"$X0\" y=\"16\" fill=\"#e6edf3\" font-size=\"11\" font-weight=\"600\">$title</text>"
  # series
  local s color vals va pts
  for s in "$@"; do
    color="${s#*:}"; color="${color%%:*}"; vals="${s##*:}"
    IFS=',' read -ra va <<< "$vals"; pts=""
    for i in $(seq 0 $((n-1))); do
      yp=$(awk -v t="$YT" -v b="$YB" -v m="$ymax" -v v="${va[$i]}" 'BEGIN{printf "%.1f", b-(b-t)*v/m}')
      pts="$pts ${XS[$i]},$yp"
    done
    echo "<polyline points=\"$pts\" fill=\"none\" stroke=\"$color\" stroke-width=\"2.5\"/>"
    for i in $(seq 0 $((n-1))); do
      yp=$(awk -v t="$YT" -v b="$YB" -v m="$ymax" -v v="${va[$i]}" 'BEGIN{printf "%.1f", b-(b-t)*v/m}')
      echo "<circle cx=\"${XS[$i]}\" cy=\"$yp\" r=\"3\" fill=\"$color\"/>"
      echo "<text x=\"${XS[$i]}\" y=\"$(awk -v y=$yp 'BEGIN{print y-7}')\" fill=\"$color\" font-size=\"9\" text-anchor=\"middle\">${va[$i]}</text>"
    done
  done
  echo "</svg>"
}

# If sourced, callers use chart(); if run directly, emit a tiny demo.
if [ "${BASH_SOURCE[0]:-}" = "${0}" ]; then
  XLABELS=(">12w" "8-12w" "4-8w" "2-4w" "0-2w")
  chart 40 "demo: ready PRs by why they wait (oldest left -> newest right)" \
    "never:#da3633:3,4,31,34,36" "discussed:#388bfd:16,10,16,16,9" \
    "changes:#d29922:1,1,5,6,0" "approved:#2ea043:3,3,6,7,4"
fi
