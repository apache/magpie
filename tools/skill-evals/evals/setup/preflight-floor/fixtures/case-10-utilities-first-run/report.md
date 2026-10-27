<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock`, no `.apache-magpie-overrides/` and no
`.apache-magpie-local/` at the repo root. The running agent is Claude Code
with magpie-setup 0.4.0 and magpie-utilities 0.4.0 installed.

The user has already seen the initial general welcome guide on an earlier run.
The invoked skill's own frontmatter reads `name: list-skills` and
`surface_hash: sha256:2edc90a1b7f3440d`; it belongs to the utilities family.
This is the first time a utilities skill has run here.
The user asked it to "list skills".

The pre-flight command printed:

```json
{
  "findings": [
    {
      "code": "welcome",
      "facts": {
        "family": "utilities",
        "guide": "# \ud83d\udc26 Magpie here \u2014 your skill-authoring sidekick\n\nA one-minute tour, then straight back to what you asked for.\n\n## \ud83d\udd04 The typical flow\n\n1. \ud83d\udccb **List** the skills installed here, grouped by family \u2014 *\"list skills\"*\n2. \u270d\ufe0f **Write** a new skill against framework conventions, with evals \u2014 *\"write a skill\"*\n3. \u26a1 **Optimize** an existing skill for brevity and token efficiency \u2014 *\"optimize a skill\"*\n4. \ud83d\udc1b **Report a framework issue** from where you hit it, after checking duplicates \u2014 *\"report an issue\"*\n5. \ud83d\udd01 **Reconcile** two near-duplicate skills and classify where they drifted \u2014 *\"reconcile <skill-A> and <skill-B>\"*\n\nNothing is written, modified, or posted without your OK.\n\n## \u2699\ufe0f Configure it\n\nNothing here has to be configured:\n\n- \ud83d\udee0\ufe0f **Authoring & help** \u2014 meta-skills work straight away in any directory or worktree\n- \ud83d\udcd6 **Optional project settings** \u2014 reads `project.md` when present, otherwise uses built-in framework defaults\n\nTwo ways to run Magpie when you are ready: personal install (`/magpie-setup:setup config`) or project adoption (`/magpie-setup:setup adopt`).\n\n## \ud83d\udcac Just ask\n\nTalk to Magpie in plain language:\n\n- *\"what skills are installed here?\"*\n- *\"write a skill that drafts PR release notes\"*\n- *\"optimize the write-skill instructions\"*\n- *\"file a bug about preflight caching\"*\n- *\"have these two skill copies drifted?\"*\n\n## \ud83c\udfa8 Make it yours\n\nMagpie ships default workflows and conventions.\nChange them by describing the change:\n\n- *\"from now on, always add a smoke test when writing a skill\"*\n- *\"group the skill list by capability instead of family\"*\n\nEach becomes an override for the utility skill it changes.\nUseful to everyone? *\"Upstream this change to Magpie\"* opens a generic `apache/magpie` PR for you to review first.\n\n## \ud83d\udc4b About this guide\n\n- **Continue** \u2014 show it again next time (three times at most)\n- **Dismiss** \u2014 hide it until the next Magpie upgrade\n- **Don't show again** \u2014 hide it for good; say *\"show the utilities welcome again\"* to bring it back\n\nShow this again any time: `/magpie-setup:welcome-guide utilities`\n(`/magpie-setup-welcome-guide utilities` on a pinned snapshot).\n\n\ud83c\udf08 Prefer it in colour? Run this yourself \u2014 the `!` prefix runs it as a shell command:\n\n```text\n! PYTHONPATH=\"$(git rev-parse --git-common-dir 2>/dev/null || { test -e .git || { test -f .svn/wc.db && echo .svn; }; })/apache-magpie\" python3 -P -m setup_preflight.welcome show --family utilities --color=always\n```\n",
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
