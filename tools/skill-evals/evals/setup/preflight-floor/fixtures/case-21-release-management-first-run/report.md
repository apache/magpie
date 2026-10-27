<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock`, no `.apache-magpie-overrides/` and no
`.apache-magpie-local/` at the repo root. The running agent is Claude Code
with magpie-setup 0.4.0 and magpie-release-management 0.4.0 installed.

The user has already seen the initial general welcome guide on an earlier run.
The invoked skill's own frontmatter reads `name: rc-cut` and
`surface_hash: sha256:60623e456e72bbf6`; it belongs to the
release-management family. This is the first time a release-management
skill has run here. The user asked it to "cut rc1 for the next release".

The pre-flight command printed:

```json
{
  "findings": [
    {
      "code": "welcome",
      "facts": {
        "family": "release-management",
        "guide": "# \ud83d\udc26 Magpie here \u2014 your release-management sidekick\n\nA one-minute tour, then straight back to what you asked for.\n\n## \ud83d\udd04 The typical flow\n\n1. \ud83d\udccb **Prepare** the release plan and version bump \u2014 *\"plan our next release\"*\n2. \ud83d\udd11 **Check KEYS** before RC signing \u2014 *\"sync the release signing key\"*\n3. \ud83d\udce6 **Cut an RC** and prepare signing/staging commands \u2014 *\"cut rc1 for this version\"*\n4. \u2705 **Verify the RC** before a vote \u2014 *\"verify the staged release candidate\"*\n5. \ud83d\uddf3\ufe0f **Draft the vote**, then tally results \u2014 *\"draft the vote email\"* / *\"tally the votes\"*\n6. \ud83d\ude80 **Promote** a release only after approval \u2014 *\"prepare promotion commands\"*\n7. \ud83d\udce3 **Draft the announcement**, then review archive cleanup \u2014 *\"draft the announcement\"*\n8. \ud83d\udcca **Audit** the completed release evidence \u2014 *\"prepare the release audit report\"*\n\nThese steps are guided workflows, not autonomous publishing.\nThe Release Manager keeps the signing key and runs signing and publication commands.\nVote and announcement emails are drafts, never automatically sent.\nReview and explicitly approve proposed external or repository changes.\n\n## \u2699\ufe0f Configure it\n\nRelease skills use project-specific configuration:\n\n- \u2699\ufe0f **Release policy** \u2014 `release-management-config.md` for planning, votes, announcements, archives, audit reports and KEYS\n- \ud83d\udce6 **Build and staging** \u2014 `release-build.md` for `rc-cut` and `verify-rc`\n- \ud83d\uddf3\ufe0f **Approval roster** \u2014 `pmc-roster.md` for `vote-tally` and `promote`\n- \ud83d\ude86 **Release trains** \u2014 `release-trains.md` for `prepare` and `archive-sweep`\n\nThe distribution, approval and announcement backends are set in `release-management-config.md`.\nConfigure personally with `/magpie-setup:setup config`.\nTeam adoption with `/magpie-setup:setup adopt` is a maintainer decision.\n\n## \ud83d\udcac Just ask\n\nTalk to Magpie in plain language:\n\n- *\"prepare the release plan for our next version\"*\n- *\"check that my public signing key is in KEYS\"*\n- *\"give me the commands to cut and verify rc1\"*\n- *\"draft a vote email for this verified RC\"*\n- *\"tally the release vote and prepare the result draft\"*\n- *\"prepare promotion and announcement after the vote passes\"*\n- *\"review old release archives and generate an audit report\"*\n\n## \ud83c\udfa8 Make it yours\n\nDescribe your release policy and preferred backend:\n\n- *\"use a 96-hour vote window instead of 72\"*\n- *\"always run the KEYS check before cutting an RC\"*\n\nReview proposed configuration or override changes before applying them.\nUseful elsewhere? Ask *\"upstream this change to Magpie\"* to prepare a contribution for review.\n\n## \ud83d\udc4b About this guide\n\n- **Continue** \u2014 show it again next time (three times at most)\n- **Dismiss** \u2014 hide it until the next Magpie upgrade\n- **Don't show again** \u2014 hide it for good; say *\"show the release-management welcome again\"* to bring it back\n\nShow this again any time: `/magpie-setup:welcome-guide release-management`\n(`/magpie-setup-welcome-guide release-management` on a pinned snapshot).\n\n\ud83c\udf08 Prefer it in colour? Run this yourself \u2014 the `!` prefix runs it as a shell command:\n\n```text\n! PYTHONPATH=\"$(python3 -I -c 'import hashlib,os,sys;h,d,m,i=sys.argv[1:];r=os.path.realpath(os.curdir);s=os.stat(r);p=os.path.join(h,d,hashlib.sha256(r.encode()).hexdigest()[:16]);f=os.path.join(p,i);print(p if os.path.isdir(os.path.join(p,m)) and os.path.isfile(f) and open(f).read().split()==[str(s.st_dev),str(s.st_ino)] else h)' \"$HOME/.cache/apache-magpie/preflight\" projects setup_preflight root-id)\" python3 -P -m setup_preflight.welcome show --family release-management --color=always\n```\n",
        "max_shown": 3,
        "reason": "first-run",
        "shown": 0
      },
      "scope": "family",
      "section": "welcome"
    }
  ],
  "rules": {
    "welcome": "## welcome \u2014 a first-run welcome guide is due\n\nA welcome guide is due on this run: `facts.family` names it\n(`general`, for the first Magpie skill this user runs here, or the skill's own family),\nand `facts.reason` says why (`first-run`, `again`, or `upgraded` after a dismissal).\n`facts.guide` is the guide. The checker shows at most one guide per run and has already picked it.\n\n1. **Show `facts.guide` to the user verbatim**, as Markdown, before the work they asked for.\n   Do not summarise, reword, trim, or add to it, and substitute nothing in it:\n   its placeholders (`<security-list>`, `<tracker>`, `<family>`, \u2026) are meant to be read as written.\n2. **Offer the three choices in one line**:\n   **Continue** (show again next time) \u00b7 **Dismiss** (hide until the next Magpie upgrade) \u00b7 **Don't show again**.\n3. **Record `seen` at once**, which is what no answer means, then carry on with the user's request in the same turn.\n   Never block the requested work on the guide, and never wait for an answer before starting it.\n4. **When the user picks Dismiss or Don't show again** \u2014 now or later in the session \u2014 record that choice;\n   it replaces `seen`. Continue needs nothing further.\n\n```bash\nPYTHONPATH=\"$(python3 -I -c 'import hashlib,os,sys;h,d,m,i=sys.argv[1:];r=os.path.realpath(os.curdir);s=os.stat(r);p=os.path.join(h,d,hashlib.sha256(r.encode()).hexdigest()[:16]);f=os.path.join(p,i);print(p if os.path.isdir(os.path.join(p,m)) and os.path.isfile(f) and open(f).read().split()==[str(s.st_dev),str(s.st_ino)] else h)' \"$HOME/.cache/apache-magpie/preflight\" projects setup_preflight root-id)\" \\\n  python3 -P -m setup_preflight.welcome record --family <facts.family> --choice <seen|dismiss|never>\n```\n\n`seen` brings the guide back on a later run, `facts.max_shown` recorded showings in all (`facts.shown` so far);\n`dismiss` hides it until the framework version changes; `never` hides it until re-enabled.\nEvery write merges into the personal layer's `reconciled.json` under `welcome.<facts.family>`, keeping every other key;\nnever write it by hand.\nIf the command exits non-zero, say nothing more about it and carry on.\n\nAny guide can be shown again on request with `/magpie-setup:welcome-guide [<family>]`,\nwhich also turns a hidden one back on."
  },
  "verdict": "action"
}
```
