<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock`, no `.apache-magpie-overrides/` and no
`.apache-magpie-local/` at the repo root. The running agent is Claude Code
with magpie-setup 0.4.0 and magpie-pairing 0.4.0 installed.

The user has already seen the initial general welcome guide on an earlier run.
The invoked skill's own frontmatter reads `name: self-review` and
`surface_hash: sha256:ea0a2e29bb2aa0e0`; it belongs to the pairing family.
This is the first time a pairing skill has run here.
The user asked it to "review my diff before I push".

The pre-flight command printed:

```json
{
  "findings": [
    {
      "code": "welcome",
      "facts": {
        "family": "pairing",
        "guide": "# \ud83d\udc26 Magpie here \u2014 your pre-PR review sidekick\n\nA one-minute tour, then straight back to what you asked for.\n\n## \ud83d\udd04 The typical flow\n\n1. \ud83d\udd0d **Self-review** your local diff before pushing \u2014 *\"review my diff before I push\"*\n2. \ud83d\udee1\ufe0f **Multi-agent review** the diff with independent correctness, security, and conventions passes \u2014 *\"run independent reviews of my branch\"*\n\nBoth skills return review reports. They never edit files, post comments, open PRs, push, or merge.\n\n## \u2699\ufe0f Configure it\n\nNothing is required before your first review:\n\n- \ud83d\udcd6 **Project context** \u2014 optionally use `project.md` for project-scoped references; otherwise the skills use their defaults\n- \ud83c\udfaf **Review scope** \u2014 choose a base ref, staged changes, or a path filter when needed\n\nConfigure it for yourself with `/magpie-setup:setup config`.\nAdopting shared configuration with `/magpie-setup:setup adopt` is a project maintainer decision.\n\n## \ud83d\udcac Just ask\n\nTalk to Magpie in plain language:\n\n- *\"review my diff before I push\"*\n- *\"check my staged changes for correctness and security\"*\n- *\"review only the files under this directory\"*\n- *\"run three independent review passes on my branch\"*\n- *\"compare the correctness, security, and conventions findings\"*\n\nFor an already-open PR, use the PR-management code-review workflow instead.\n\n## \ud83c\udfa8 Make it yours\n\nDescribe how you want the review workflow to behave:\n\n- *\"focus my self-review on error handling and security risks\"*\n- *\"make the conventions review check our project's documented style\"*\n\nReview the proposed skill override before applying it.\nUseful to others? Ask *\"upstream this change to Magpie\"* to prepare a reusable contribution for your review.\n\n## \ud83d\udc4b About this guide\n\n- **Continue** \u2014 show it again next time (three times at most)\n- **Dismiss** \u2014 hide it until the next Magpie upgrade\n- **Don't show again** \u2014 hide it for good; say *\"show the pairing welcome again\"* to bring it back\n\nShow this again any time: `/magpie-setup:welcome-guide pairing`\n(`/magpie-setup-welcome-guide pairing` on a pinned snapshot).\n\n\ud83c\udf08 Prefer it in colour? Run this yourself \u2014 the `!` prefix runs it as a shell command:\n\n```text\n! PYTHONPATH=\".apache-magpie-local:$(git rev-parse --git-common-dir)/../.apache-magpie-local:$(git rev-parse --git-common-dir)/apache-magpie\" python3 -m setup_preflight.welcome show --family pairing --color=always\n```\n",
        "max_shown": 3,
        "reason": "first-run",
        "shown": 0
      },
      "scope": "family",
      "section": "welcome"
    }
  ],
  "rules": {
    "welcome": "## welcome \u2014 a first-run welcome guide is due\n\nA welcome guide is due on this run: `facts.family` names it\n(`general`, for the first Magpie skill this user runs here, or the skill's own family),\nand `facts.reason` says why (`first-run`, `again`, or `upgraded` after a dismissal).\n`facts.guide` is the guide. The checker shows at most one guide per run and has already picked it.\n\n1. **Show `facts.guide` to the user verbatim**, as Markdown, before the work they asked for.\n   Do not summarise, reword, trim, or add to it, and substitute nothing in it:\n   its placeholders (`<security-list>`, `<tracker>`, `<family>`, \u2026) are meant to be read as written.\n2. **Offer the three choices in one line**:\n   **Continue** (show again next time) \u00b7 **Dismiss** (hide until the next Magpie upgrade) \u00b7 **Don't show again**.\n3. **Record `seen` at once**, which is what no answer means, then carry on with the user's request in the same turn.\n   Never block the requested work on the guide, and never wait for an answer before starting it.\n4. **When the user picks Dismiss or Don't show again** \u2014 now or later in the session \u2014 record that choice;\n   it replaces `seen`. Continue needs nothing further.\n\n```bash\nPYTHONPATH=\".apache-magpie-local:$(git rev-parse --git-common-dir)/../.apache-magpie-local:$(git rev-parse --git-common-dir)/apache-magpie\" \\\n  python3 -m setup_preflight.welcome record --family <facts.family> --choice <seen|dismiss|never>\n```\n\n`seen` brings the guide back on a later run, `facts.max_shown` recorded showings in all (`facts.shown` so far);\n`dismiss` hides it until the framework version changes; `never` hides it until re-enabled.\nEvery write merges into the personal layer's `reconciled.json` under `welcome.<facts.family>`, keeping every other key;\nnever write it by hand.\nIf the command exits non-zero, say nothing more about it and carry on.\n\nAny guide can be shown again on request with `/magpie-setup:welcome-guide [<family>]`,\nwhich also turns a hidden one back on."
  },
  "verdict": "action"
}
```
