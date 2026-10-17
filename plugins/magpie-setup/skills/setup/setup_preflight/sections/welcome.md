<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## welcome — a first-run welcome guide is due

A welcome guide is due on this run: `facts.family` names it
(`general`, for the first Magpie skill this user runs here, or the skill's own family),
and `facts.reason` says why (`first-run`, `again`, or `upgraded` after a dismissal).
`facts.guide` is the guide. The checker shows at most one guide per run and has already picked it.

1. **Show `facts.guide` to the user verbatim**, as Markdown, before the work they asked for.
   Do not summarise, reword, trim, or add to it, and substitute nothing in it:
   its placeholders (`<security-list>`, `<tracker>`, `<family>`, …) are meant to be read as written.
2. **Offer the three choices in one line**:
   **Continue** (show again next time) · **Dismiss** (hide until the next Magpie upgrade) · **Don't show again**.
3. **Record `seen` at once**, which is what no answer means, then carry on with the user's request in the same turn.
   Never block the requested work on the guide, and never wait for an answer before starting it.
4. **When the user picks Dismiss or Don't show again** — now or later in the session — record that choice;
   it replaces `seen`. Continue needs nothing further.

```bash
PYTHONPATH=".apache-magpie-local:$(git rev-parse --git-common-dir)/../.apache-magpie-local:$(git rev-parse --git-common-dir)/apache-magpie" \
  python3 -m setup_preflight.welcome record --family <facts.family> --choice <seen|dismiss|never>
```

`seen` brings the guide back on a later run, `facts.max_shown` recorded showings in all (`facts.shown` so far);
`dismiss` hides it until the framework version changes; `never` hides it until re-enabled.
Every write merges into the personal layer's `reconciled.json` under `welcome.<facts.family>`, keeping every other key;
never write it by hand.
If the command exits non-zero, say nothing more about it and carry on.

Any guide can be shown again on request with `/magpie-setup:welcome-guide [<family>]`,
which also turns a hidden one back on.
