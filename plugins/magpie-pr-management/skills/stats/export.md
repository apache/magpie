<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# export — always publish the dashboard as a self-contained HTML gist

`pr-management-stats` **always** produces a self-contained HTML
dashboard and publishes it to a **secret GitHub gist**, then returns
the `gistpreview.github.io` URL. This is not optional and not gated
behind a flag: every stats run ends with a published, link-shareable
dashboard. The inline terminal/markdown rendering (per
[`render.md`](render.md)) is still emitted for the maintainer reading
in-session; the gist is the durable, colour-rendered artefact they can
open in a browser and share.

This replaces any earlier "render inline only" behaviour — there is now
exactly one canonical export format (the dashboard described here and in
[`render.md`](render.md)), published the same way on every run, so a
maintainer's dashboards are directly comparable across days.

## Golden rule — one export, always, same shape

- **Always.** Every `pr-management-stats` invocation publishes the gist.
  No `--export` flag, no "ask first". The only exceptions are `dry-run`
  (compute + render inline, skip the publish) and a `gh auth status`
  token without `gist` scope (warn once, fall back to writing the HTML
  to `/tmp/pr-management-stats-<repo-slug>.html` and print the path).
- **Secret gist.** Use a secret gist (`gh gist create` defaults to
  secret) — URL-shareable but not publicly listed. The dashboard
  carries only aggregate public-PR metadata, but secret-by-default is
  the conservative choice for a maintainer's personal account.
- **Stable identity.** Reuse one gist per repo across runs (store its id
  in the session-state file `<adopter-repo>/.apache-magpie.session-state.json`
  under `stats_gist_id`, gitignored) so the same URL updates each run
  rather than littering the account with one gist per day. `PATCH` the
  existing gist's `dashboard.html` file in place; only create a new gist
  the first time.

## Publish recipe

```bash
# 1. write the self-contained HTML (see render.md + the template below)
#    to a local file
OUT=/tmp/pr-management-stats-<repo-slug>.html
# ... agent writes the dashboard HTML to $OUT ...

# 2. publish / update the secret gist (in place, same id across runs)
GID="$(read stats_gist_id from .apache-magpie.session-state.json, if any)"
if [ -z "$GID" ]; then
  URL=$(gh gist create "$OUT" --desc "<Project> — PR Backlog Dashboard (<date>)")
  GID=$(printf '%s' "$URL" | grep -oE '[0-9a-f]{20,}$')
  # persist GID into .apache-magpie.session-state.json -> stats_gist_id
else
  # update in place — keeps the URL stable
  jq -n --rawfile c "$OUT" '{files:{"dashboard.html":{content:$c}}}' \
    | gh api -X PATCH "gists/$GID" --input -
fi

# 3. return BOTH links to the maintainer
echo "Rendered (browser): https://gistpreview.github.io/?$GID"
echo "Raw gist:           https://gist.github.com/<viewer>/$GID"
```

`gistpreview.github.io/?<id>` renders the gist's `dashboard.html` as a
live page (it fetches the gist via the GitHub API, so it works for
secret gists too). Always return the `gistpreview` URL first — that is
the one the maintainer clicks.

**Confirmation:** publishing a gist writes to the maintainer's account.
Per the framework's "assistant proposes, user fires" norm the agent may
publish without a per-run prompt **because the maintainer invoked the
stats skill** (the export is the documented, expected output of that
invocation) — but it must surface the gist URL in the result, never
publish silently. If the project's agent-instructions require explicit
confirmation before any account write, honour that and print the local
HTML path instead, offering to publish on confirmation.

## The canonical dashboard (the "exact export")

The published HTML is the full panel set from [`render.md`](render.md),
self-contained (inline `<style>`, inline SVG charts — no external JS/CSS
so `gistpreview` renders it offline-of-CDN). A worked reference rendering
is checked in at
[`tools/pr-management-stats/examples/reference-dashboard.html`](../../../../tools/pr-management-stats/examples/reference-dashboard.html);
the inline SVG line charts are produced by
[`tools/pr-management-stats/gen_charts.sh`](../../../../tools/pr-management-stats/gen_charts.sh).

Required panels, in order (every one always rendered — see
[`render.md` Golden rule 8](render.md#golden-rules)):

1. **Context line** — repo, open count, cutoff, viewer, refresh timestamp.
2. **Hero cards (4)** — `Total open` · `Non-maintainer` (contributor-authored)
   · `Ready for review (non-maintainer)` · `Drafts (author's court)`. Maintainer-authored
   PRs are split out because triage/review skip collaborator PRs (they self-manage).
3. **Hero legend** — a boxed "What the numbers above mean" panel defining
   every hero number and every coloured split card in plain language.
   Dense dashboards are unreadable without it; this panel is **required**,
   not optional.
4. **Ready-for-review split (4 coloured cards)** — the ready queue broken
   down by *what each PR is actually waiting for* (see
   [`render.md` § Ready-for-review queue split](render.md#ready-for-review-queue-split-by-why-waiting)):
   <span style="red">never reviewed</span> / <span style="blue">discussed,
   no decision</span> / <span style="amber">changes requested</span> /
   <span style="green">approved, awaiting merge</span>. Same colours as the
   timeline chart in panel 7.
5. **Triage funnel (5 mutually-exclusive states)** — Ready · Responded ·
   Waiting (author silent) · Waiting for human maintainer comment · Drafts —
   with a prose block explaining **every** cell (whose court it is in).
6. **Trends over time** — inline SVG line charts: PRs opened/week by author
   class, merged/week, open backlog, and **drafts-vs-closes per week by
   triage attribution** (per-person; bot/backport excluded — see
   [`render.md` § Drafts & closes by person](render.md#drafts--closes-attribution-by-person)).
7. **Ready-for-review timeline** — the multi-line "why each ready PR is
   waiting" chart, **x-axis = age, oldest on the left → newest on the right**
   (a timeline reads past→present), same colours as panel 4. This is the
   panel that exposes the first-review gap (never-reviewed rising toward the
   newest bucket).
8. **Pressure by area**, **Closure velocity**, **Detailed tables**,
   **Methodology / legend** — as in [`render.md`](render.md).

## Mandatory data-integrity caveats

The GitHub Search API caps results at **1000**. Any series derived from
the closed/merged-since-cutoff fetch (velocity, momentum, backlog,
drafts-vs-closes) is therefore **truncated in the oldest weeks** once a
busy repo exceeds 1000 closes in the window. The dashboard MUST:

- annotate the affected weeks (mark them "cap-truncated" or omit them and
  say so) rather than drawing a misleading ramp, and
- state which weeks are authoritative (typically the most recent 3–4), and
- recommend, in the methodology panel, a **daily snapshot job** (a tiny
  scheduled Action writing `open_count / ready_count / per-area` to a CSV)
  as the only reliable way to get true uncapped historical trends.

Never present a cap-distorted absolute series as if it were real history.

## Cross-references

- [`render.md`](render.md) — panel-by-panel layout, colour scheme, the two
  new analytic panels (ready-for-review split; drafts/closes by person).
- [`SKILL.md` Step 7](SKILL.md#step-7--publish-the-dashboard-always) — the
  always-publish step in the skill flow.
- [`pr-management-triage/session-history.md`](../pr-triage/session-history.md)
  — the *separate* session-history gist (triage calibration log); the stats
  dashboard gist is its own artefact and reuses the same secret-gist +
  stable-id mechanics.
