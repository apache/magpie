<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock`, no `.apache-magpie-overrides/` and no
`.apache-magpie-local/` at the repo root. The running agent is Claude Code
with magpie-setup 0.4.0 and magpie-mentoring 0.4.0 installed.

The user has already seen the initial general welcome guide on an earlier run.
The invoked skill's own frontmatter reads `name: welcome` and
`surface_hash: sha256:a61c6575d69da08a`; it belongs to the mentoring family.
This is the first time a mentoring skill has run here.
The user asked it to "welcome the first-time contributor on PR 123".

The pre-flight command printed:

```json
{
  "findings": [
    {
      "code": "welcome",
      "facts": {
        "family": "mentoring",
        "guide": "# \ud83d\udc26 Magpie here \u2014 your newcomer-mentoring sidekick\n\nA one-minute tour, then straight back to what you asked for.\n\n## \ud83d\udd04 The typical flow\n\n1. \ud83d\udc4b **Welcome** a first-time contributor with project guidance \u2014 *\"welcome the newcomer on PR 123\"*\n2. \ud83d\udd0e **Sweep** the backlog for newcomer-ready tasks \u2014 *\"find good first issues\"*\n3. \u270d\ufe0f **Author** one self-contained beginner issue \u2014 *\"draft a good first issue for this small task\"*\n4. \ud83d\udcd6 **Explain** an existing issue in beginner terms \u2014 *\"explain issue 123 to a newcomer\"*\n\nMagpie drafts first. Comments, new issues, and labels require explicit maintainer confirmation.\n\n## \u2699\ufe0f Configure it\n\nSet up the project context before using these skills:\n\n- \ud83d\uddc2\ufe0f **Project** \u2014 `project.md` identifies the repository and project context for every mentoring skill\n- \ud83c\udff7\ufe0f **Good first issues** \u2014 `good-first-issue-config.md` and `issue-tracker-config.md` are required for sweep and author\n- \ud83d\udcac **Optional guidance** \u2014 `mentoring-welcome-config.md` controls welcomes; `newcomer-issue-explainer-config.md` shapes explanations\n\nConfigure personally with `/magpie-setup:setup config`.\nProject adoption with `/magpie-setup:setup adopt` is a maintainer decision.\n\n## \ud83d\udcac Just ask\n\nTalk to Magpie in plain language:\n\n- *\"welcome the first-time contributor on issue 123\"*\n- *\"find newcomer-ready issues in the backlog\"*\n- *\"which issues need changes before getting a good first issue label?\"*\n- *\"draft a good first issue from this small task\"*\n- *\"explain issue 123 with the files to read and what done looks like\"*\n\nSecurity-sensitive threads are not suitable for these newcomer workflows.\nContributors who were already welcomed, and threads already handled, are skipped.\n\n## \ud83c\udfa8 Make it yours\n\nDescribe how your project's mentoring should work:\n\n- *\"make newcomer explanations include a first test to run\"*\n- *\"use our contribution guide when drafting welcome messages\"*\n\nReview the proposed override before using it.\nUseful to others? Ask *\"upstream this change to Magpie\"* to prepare a reusable contribution for review.\n\n## \ud83d\udc4b About this guide\n\n- **Continue** \u2014 show it again next time (three times at most)\n- **Dismiss** \u2014 hide it until the next Magpie upgrade\n- **Don't show again** \u2014 hide it for good; say *\"show the mentoring welcome again\"* to bring it back\n\nShow this again any time: `/magpie-setup:welcome-guide mentoring`\n(`/magpie-setup-welcome-guide mentoring` on a pinned snapshot).\n\n\ud83c\udf08 Prefer it in colour? Run this yourself \u2014 the `!` prefix runs it as a shell command:\n\n```text\n! PYTHONPATH=\"$(git rev-parse --git-common-dir 2>/dev/null || { test -e .git || { test -f .svn/wc.db && echo .svn; }; })/apache-magpie\" python3 -P -m setup_preflight.welcome show --family mentoring --color=always\n```\n",
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
