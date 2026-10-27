<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock`, no `.apache-magpie-overrides/` and no
`.apache-magpie-local/` at the repo root. The running agent is Claude Code
with magpie-setup 0.4.0 installed.

The user has already seen the general welcome guide on an earlier run.
This is the first time the `setup` skill has run here.
The user invoked `/magpie-setup:setup verify`.

The welcome check printed:

```json
{
  "findings": [
    {
      "code": "welcome",
      "facts": {
        "family": "setup",
        "guide": "# \ud83d\udc26 Magpie here \u2014 your setup sidekick\n\nA one-minute tour, then straight back to what you asked for.\n\n## \ud83d\udd04 The typical flow\n\n1. \ud83e\udded **Check status** \u2014 *\"show how Magpie is installed and adopted here\"*\n2. \ud83d\udee0\ufe0f **Install and configure** \u2014 *\"set up Magpie for me\"*\n3. \ud83d\udd10 **Isolate the agent** \u2014 *\"install the secure agent sandbox\"*\n4. \u2705 **Verify and diagnose** \u2014 *\"verify isolation\"* or *\"diagnose my sandbox\"*\n5. \ud83c\udd99 **Check for drift and upgrade** \u2014 *\"check my sandbox for drift\"* or *\"upgrade Magpie\"*\n6. \ud83c\udfd7\ufe0f **Adopt for the team** \u2014 *\"adopt Magpie for this repository\"*\n\nOther skills help configure LLM privacy, synchronize shared config, upstream useful overrides, propose framework bug fixes, and replay welcome guides.\n\nRead-only checks report findings.\nInstallation, adoption, upgrades, configuration writes, and repository changes follow their own approval steps.\nNever edit Magpie's gitignored, read-only framework snapshot directly.\n\n## \u2699\ufe0f Configure it\n\nNothing is required before using the Setup family:\n\n- \ud83d\udccb **Setup defaults** \u2014 optional `magpie-setup.md`\n- \ud83d\udd0f **Privacy policy** \u2014 optional `privacy-llm.md`\n- \ud83e\udde9 **Project identity** \u2014 optional `project.md`\n- \ud83d\udd17 **Trusted skill sources** \u2014 optional `skill-sources.md`\n\n`/magpie-setup:setup config` writes personal configuration.\n`/magpie-setup:setup adopt` proposes committed project-wide settings.\nReview the plan and confirm before any project-wide mutation.\n\n## \ud83d\udcac Just ask\n\nTalk to Magpie in plain language:\n\n- *\"show Magpie status in this checkout\"*\n- *\"install Magpie and configure it just for me\"*\n- *\"secure the agent with a sandbox and verify it\"*\n- *\"set up privacy rules for model access\"*\n- *\"check for configuration drift after an upgrade\"*\n- *\"prepare a framework fix for this broken setup helper\"*\n\n## \ud83c\udfa8 Make it yours\n\nDescribe how your setup should behave:\n\n- *\"use our approved skill sources\"*\n- *\"keep my personal privacy rules separate from project policy\"*\n\nMagpie records each request as an override of the setup skill it touches.\nIf other projects would want it too, say *\"upstream this change to Magpie\"* and review the generic `apache/magpie` PR it prepares.\n\n## \ud83d\udc4b About this guide\n\n- **Continue** \u2014 show it again next time (three times at most)\n- **Dismiss** \u2014 hide it until the next Magpie upgrade\n- **Don't show again** \u2014 hide it for good; say *\"show the setup welcome again\"* to bring it back\n\nShow this again any time: `/magpie-setup:welcome-guide setup`\n(`/magpie-setup-welcome-guide setup` on a pinned snapshot).\n\n\ud83c\udf08 Prefer it in colour? Run this yourself \u2014 the `!` prefix runs it as a shell command:\n\n```text\n! PYTHONPATH=\"$(git rev-parse --git-common-dir 2>/dev/null || { test -e .git || { test -f .svn/wc.db && echo .svn; }; })/apache-magpie\" python3 -P -m setup_preflight.welcome show --family setup --color=always\n```\n",
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
