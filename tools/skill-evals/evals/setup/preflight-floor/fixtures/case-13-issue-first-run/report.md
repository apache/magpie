<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock`, no `.apache-magpie-overrides/` and no
`.apache-magpie-local/` at the repo root. The running agent is Claude Code
with magpie-setup 0.4.0 and magpie-issue 0.4.0 installed.

The user has already seen the initial general welcome guide on an earlier run.
The invoked skill's own frontmatter reads `name: triage` and
`surface_hash: sha256:fb90bdc45aec5f8a`; it belongs to the issue family.
This is the first time an issue-family skill has run here.
The user asked it to "triage these incoming issues".

The pre-flight command printed:

```json
{
  "findings": [
    {
      "code": "welcome",
      "facts": {
        "family": "issue",
        "guide": "# \ud83d\udc26 Magpie here \u2014 your issue-management sidekick\n\nA one-minute tour, then straight back to what you asked for.\n\n## \ud83d\udd04 The typical flow\n\n1. \ud83c\udff7\ufe0f **Triage** incoming issues and draft tracker replies \u2014 *\"triage the open issues\"*\n2. \ud83d\udd01 **Deduplicate** related reports and propose which to keep \u2014 *\"find duplicate issues\"*\n3. \ud83e\uddea **Reproduce** a reported bug from its code \u2014 *\"reproduce issue ABC-123\"*\n4. \ud83d\udd0d **Reassess** resolved or end-of-life issues against today's code \u2014 *\"re-assess old issues\"*\n5. \ud83d\udee0\ufe0f **Draft a fix** with tests and a hand-back \u2014 *\"draft a fix for ABC-123\"*\n6. \ud83e\uddf9 **Sweep stale issues** and review proposed actions \u2014 *\"find stale issues\"*\n7. \ud83d\udcca **Report** backlog and reassessment statistics \u2014 *\"show backlog statistics\"*\n\n`reassess-stats` reports on reassessment results; `backlog-stats` reports on the backlog.\nTracker comments and issue closures require confirmation.\nStale closures need a second confirmation.\nThe fix workflow opens a draft PR only with `--draft-pr` and explicit approval.\n\n## \u2699\ufe0f Configure it\n\nDifferent skills need different project settings:\n\n- \ud83d\uddc2\ufe0f **Tracker** \u2014 `issue-tracker-config.md` for triage, deduplication, reproduction, stale sweep, reassessment and statistics\n- \ud83d\udcd6 **Project** \u2014 `project.md` additionally for triage and stale sweep\n- \ud83e\uddea **Investigation** \u2014 `reproducer-conventions.md` and `runtime-invocation.md` for reproduction; `reassess-pool-defaults.md` for reassessment\n- \ud83d\udee0\ufe0f **Fixes** \u2014 `fix-workflow.md` and `runtime-invocation.md` for drafting fixes\n\nConfigure personally with `/magpie-setup:setup config`.\nShared adoption with `/magpie-setup:setup adopt` is a maintainer decision.\n\n## \ud83d\udcac Just ask\n\nTalk to Magpie in plain language:\n\n- *\"triage these incoming bugs and show me draft replies\"*\n- *\"find duplicates without closing anything\"*\n- *\"reproduce this issue and explain what you found\"*\n- *\"reassess the issue backlog and summarize the results\"*\n- *\"draft a fix for this confirmed bug\"*\n- *\"review stale issues before posting or closing\"*\n- *\"show backlog and reassessment statistics\"*\n\n## \ud83c\udfa8 Make it yours\n\nDescribe how you want the issue workflow to behave:\n\n- *\"use our tracker conventions when drafting triage replies\"*\n- *\"adjust the stale-issue thresholds for this project\"*\n\nReview configuration or override proposals before applying them.\nUseful elsewhere? Ask *\"upstream this change to Magpie\"* to prepare a contribution for review.\n\n## \ud83d\udc4b About this guide\n\n- **Continue** \u2014 show it again next time (three times at most)\n- **Dismiss** \u2014 hide it until the next Magpie upgrade\n- **Don't show again** \u2014 hide it for good; say *\"show the issue welcome again\"* to bring it back\n\nShow this again any time: `/magpie-setup:welcome-guide issue`\n(`/magpie-setup-welcome-guide issue` on a pinned snapshot).\n\n\ud83c\udf08 Prefer it in colour? Run this yourself \u2014 the `!` prefix runs it as a shell command:\n\n```text\n! PYTHONPATH=\"$(git rev-parse --git-common-dir 2>/dev/null || { test -e .git || { test -f .svn/wc.db && echo .svn; }; })/apache-magpie\" python3 -P -m setup_preflight.welcome show --family issue --color=always\n```\n",
        "max_shown": 3,
        "reason": "first-run",
        "shown": 0
      },
      "scope": "family",
      "section": "welcome"
    }
  ],
  "rules": {
    "welcome": "## welcome \u2014 a first-run welcome guide is due\n\nA welcome guide is due on this run: `facts.family` names it\n(`general`, for the first Magpie skill this user runs here, or the skill's own family),\nand `facts.reason` says why (`first-run`, `again`, or `upgraded` after a dismissal).\n`facts.guide` is the guide. The checker shows at most one guide per run and has already picked it.\n\n1. **Show `facts.guide` to the user verbatim**, as Markdown, before the work they asked for.\n   Do not summarise, reword, trim, or add to it, and substitute nothing in it:\n   its placeholders (`<security-list>`, `<tracker>`, `<family>`, \u2026) are meant to be read as written.\n2. **Offer the three choices in one line**:\n   **Continue** (show again next time) \u00b7 **Dismiss** (hide until the next Magpie upgrade) \u00b7 **Don't show again**.\n3. **Record `seen` at once**, which is what no answer means, then carry on with the user's request in the same turn.\n   Never block the requested work on the guide, and never wait for an answer before starting it.\n4. **When the user picks Dismiss or Don't show again** \u2014 now or later in the session \u2014 record that choice;\n   it replaces `seen`. Continue needs nothing further.\n\n```bash\nPYTHONPATH=\"$(git rev-parse --git-common-dir 2>/dev/null || { test -e .git || { test -f .svn/wc.db && echo .svn; }; })/apache-magpie\" \\\n  python3 -P -m setup_preflight.welcome record --family <facts.family> --choice <seen|dismiss|never>\n```\n\n`seen` brings the guide back on a later run, `facts.max_shown` recorded showings in all (`facts.shown` so far);\n`dismiss` hides it until the framework version changes; `never` hides it until re-enabled.\nEvery write merges into the personal layer's `reconciled.json` under `welcome.<facts.family>`, keeping every other key;\nnever write it by hand.\nIf the command exits non-zero, say nothing more about it and carry on.\n\nAny guide can be shown again on request with `/magpie-setup:welcome-guide [<family>]`,\nwhich also turns a hidden one back on."
  },
  "verdict": "action"
}
```
