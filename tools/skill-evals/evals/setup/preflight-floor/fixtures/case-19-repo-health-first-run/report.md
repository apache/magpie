<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock`, no `.apache-magpie-overrides/` and no
`.apache-magpie-local/` at the repo root. The running agent is Claude Code
with magpie-setup 0.4.0 and magpie-repo-health 0.4.0 installed.

The user has already seen the initial general welcome guide on an earlier run.
The invoked skill's own frontmatter reads `name: ci-runner-audit` and
`surface_hash: sha256:c6da72e64ac4808d`; it belongs to the repo-health family.
This is the first time a repo-health skill has run here.
The user asked it to "audit our CI runners".

The pre-flight command printed:

```json
{
  "findings": [
    {
      "code": "welcome",
      "facts": {
        "family": "repo-health",
        "guide": "# \ud83d\udc26 Magpie here \u2014 your repository-health sidekick\n\nA one-minute tour, then straight back to what you asked for.\n\n## \ud83d\udd04 The typical flow\n\n1. \ud83c\udfc3 **Audit CI runners** for outdated labels \u2014 *\"audit our CI runners\"*\n2. \ud83d\udd12 **Check workflows** for security risks \u2014 *\"audit workflow security\"*\n3. \ud83d\udce6 **Audit dependencies** for vulnerabilities and licenses \u2014 *\"audit dependencies\"* / *\"check dependency licenses\"*\n4. \ud83d\udcdc **Check compliance** across LICENSE and NOTICE \u2014 *\"check license compliance\"*\n5. \ud83e\uddea **Triage flaky tests** to separate flakes from regressions \u2014 *\"find flaky tests\"*\n6. \ud83d\udee0\ufe0f **Draft a fix** for an audit finding \u2014 *\"draft a fix for this finding\"*\n\nThe six audit skills report findings without modifying project files.\n`audit-finding-fix` edits and commits a fix locally, asking before each write; `--draft-pr` opens a draft PR only after a further explicit OK.\n\n## \u2699\ufe0f Configure it\n\nSome skills need project-specific settings:\n\n- \u2699\ufe0f **Audit policy** \u2014 `repo-health-config.md` for dependency, workflow-security, license-compliance and flaky-test audits\n- \ud83d\udee0\ufe0f **Fix workflow** \u2014 `fix-workflow.md` and `runtime-invocation.md` for `audit-finding-fix`\n- \ud83d\udccb **Other audits** \u2014 CI runner and dependency-license audits have no required config\n\nConfigure personally with `/magpie-setup:setup config`.\nProject adoption with `/magpie-setup:setup adopt` is a maintainer decision.\n\n## \ud83d\udcac Just ask\n\nTalk to Magpie in plain language:\n\n- *\"find obsolete CI runner labels\"*\n- *\"check GitHub Actions permissions and triggers\"*\n- *\"audit dependency vulnerabilities and licenses\"*\n- *\"check LICENSE and NOTICE compliance\"*\n- *\"investigate flaky tests in CI\"*\n- *\"draft a tested fix for this audit finding\"*\n\n## \ud83c\udfa8 Make it yours\n\nDescribe the checks or reporting style you prefer:\n\n- *\"use our project's flaky-test thresholds\"*\n- *\"focus workflow security findings on high-risk triggers\"*\n\nEach becomes an override for the repo-health skill it changes.\nUseful elsewhere? Ask *\"upstream this change to Magpie\"* to prepare a contribution for review.\n\n## \ud83d\udc4b About this guide\n\n- **Continue** \u2014 show it again next time (three times at most)\n- **Dismiss** \u2014 hide it until the next Magpie upgrade\n- **Don't show again** \u2014 hide it for good; say *\"show the repo-health welcome again\"* to bring it back\n\nShow this again any time: `/magpie-setup:welcome-guide repo-health`\n(`/magpie-setup-welcome-guide repo-health` on a pinned snapshot).\n\n\ud83c\udf08 Prefer it in colour? Run this yourself \u2014 the `!` prefix runs it as a shell command:\n\n```text\n! PYTHONPATH=\".apache-magpie-local:$(git rev-parse --git-common-dir 2>/dev/null || echo .git)/../.apache-magpie-local:$(git rev-parse --git-common-dir 2>/dev/null || echo .git)/apache-magpie:.svn/apache-magpie\" python3 -m setup_preflight.welcome show --family repo-health --color=always\n```\n",
        "max_shown": 3,
        "reason": "first-run",
        "shown": 0
      },
      "scope": "family",
      "section": "welcome"
    }
  ],
  "rules": {
    "welcome": "## welcome \u2014 a first-run welcome guide is due\n\nA welcome guide is due on this run: `facts.family` names it\n(`general`, for the first Magpie skill this user runs here, or the skill's own family),\nand `facts.reason` says why (`first-run`, `again`, or `upgraded` after a dismissal).\n`facts.guide` is the guide. The checker shows at most one guide per run and has already picked it.\n\n1. **Show `facts.guide` to the user verbatim**, as Markdown, before the work they asked for.\n   Do not summarise, reword, trim, or add to it, and substitute nothing in it:\n   its placeholders (`<security-list>`, `<tracker>`, `<family>`, \u2026) are meant to be read as written.\n2. **Offer the three choices in one line**:\n   **Continue** (show again next time) \u00b7 **Dismiss** (hide until the next Magpie upgrade) \u00b7 **Don't show again**.\n3. **Record `seen` at once**, which is what no answer means, then carry on with the user's request in the same turn.\n   Never block the requested work on the guide, and never wait for an answer before starting it.\n4. **When the user picks Dismiss or Don't show again** \u2014 now or later in the session \u2014 record that choice;\n   it replaces `seen`. Continue needs nothing further.\n\n```bash\nPYTHONPATH=\".apache-magpie-local:$(git rev-parse --git-common-dir 2>/dev/null || echo .git)/../.apache-magpie-local:$(git rev-parse --git-common-dir 2>/dev/null || echo .git)/apache-magpie:.svn/apache-magpie\" \\\n  python3 -m setup_preflight.welcome record --family <facts.family> --choice <seen|dismiss|never>\n```\n\n`seen` brings the guide back on a later run, `facts.max_shown` recorded showings in all (`facts.shown` so far);\n`dismiss` hides it until the framework version changes; `never` hides it until re-enabled.\nEvery write merges into the personal layer's `reconciled.json` under `welcome.<facts.family>`, keeping every other key;\nnever write it by hand.\nIf the command exits non-zero, say nothing more about it and carry on.\n\nAny guide can be shown again on request with `/magpie-setup:welcome-guide [<family>]`,\nwhich also turns a hidden one back on."
  },
  "verdict": "action"
}
```
