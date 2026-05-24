#!/bin/bash
# Orchestrator - fetch all data then render the dashboard.
#
# Usage: run.sh [output-path]
#
# Env overrides:
#   TRACKER_STATS_CACHE          (default: /tmp/tracker-stats-cache)
#   TRACKER_STATS_OUT            (default: /tmp/airflow_s_monthly.html - or arg $1)
#   TRACKER_STATS_REPO           tracker repo (default: airflow-s/airflow-s)
#   TRACKER_STATS_BUCKETS        monthly | quarterly (overlay)
#   TRACKER_STATS_START          "YYYY-MM" / "YYYY-Qn" (overlay)
#   TRACKER_STATS_UPSTREAM_REPO  upstream repo slug or "none" (overlay)
#   TRACKER_STATS_CONFIG         path to a YAML overlay file
#
# render.py reads its config from `scripts/default-config.yaml`,
# optionally overlaid by $TRACKER_STATS_CONFIG and the env-var quick
# overrides above. See default-config.yaml for the schema.

set -e
HERE="$(cd "$(dirname "$0")" && pwd)"

if [ -n "$1" ]; then
  export TRACKER_STATS_OUT="$1"
fi

# Prefer python with PyYAML if available; render.py falls back to a tiny
# built-in YAML subset parser when pyyaml is missing. Adopters who use
# `uv` can opt in to a clean PyYAML invocation by setting
# TRACKER_STATS_PY=uv-yaml; default is plain python3.
PY="${TRACKER_STATS_PY:-python3}"
case "$PY" in
  uv-yaml)
    PY_CMD=(uv run --with pyyaml python3)
    ;;
  *)
    PY_CMD=("$PY")
    ;;
esac

echo "-> fetch_issues"
"${PY_CMD[@]}" "$HERE/fetch_issues.py"

echo "-> fetch_roster"
"${PY_CMD[@]}" "$HERE/fetch_roster.py"

echo "-> fetch_bodies"
"${PY_CMD[@]}" "$HERE/fetch_bodies.py"

echo "-> fetch_events"
"${PY_CMD[@]}" "$HERE/fetch_events.py"

echo "-> fetch_prs"
"${PY_CMD[@]}" "$HERE/fetch_prs.py"

echo "-> render"
"${PY_CMD[@]}" "$HERE/render.py"

echo "done: ${TRACKER_STATS_OUT:-/tmp/airflow_s_monthly.html}"
