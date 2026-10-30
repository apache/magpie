<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock`, no `.apache-magpie-overrides/` and no
`.apache-magpie-local/` at the repo root. The running agent is Claude Code
with magpie-setup 0.4.0 and magpie-pr-management 0.4.0 installed.

The user has already seen the initial general welcome guide on an earlier run.
The invoked skill's own frontmatter reads `name: pr-triage` and
`surface_hash: sha256:54dc4ba1be7b36d4`; it belongs to the pr-management family.
This is the first time a pr-management skill has run here.
The user asked it to "triage the open PRs".

The pre-flight command printed:

```json
{
  "findings": [
    {
      "code": "welcome",
      "facts": {
        "family": "pr-management",
        "guide": "# \ud83d\udc26 Magpie here \u2014 your PR-management sidekick\n\nA one-minute tour, then straight back to what you asked for.\n\n## \u2699\ufe0f Configure it\n\nStart with `<upstream>`, the project's review criteria and its area labels.\n`pr-management-code-review-criteria.md` names the criteria sources;\n`pr-management-config.md` carries the labels and queue rules.\n`reviewer-roster.md` tells reviewer routing who covers each area.\n\n- **Configure it for yourself** \u2014 personal configuration, nothing committed \u2014 `/magpie-setup:setup config`\n- **Adopted** \u2014 for your project: shared configuration committed to the repo \u2014 `/magpie-setup:setup adopt` (a maintainers' decision)\n\nOn a pinned-snapshot install, use `/magpie-setup config` or `/magpie-setup adopt`.\n\nOptional companion: roborev reviews your own branch before it becomes a PR;\nthis family helps you review and manage other people's PRs.\nNeither requires the other.\n\n## \ud83d\udd04 The typical flow\n\n1. **Triage the queue** \u2014 propose a disposition for each PR \u2014 *\"triage the open PRs\"*\n2. **Route reviewers** \u2014 use the roster to suggest the right people \u2014 *\"who should review this PR?\"*\n3. **Review** \u2014 inspect the diff and draft inline feedback \u2014 *\"review this PR against our criteria\"*\n4. **Quick-merge** \u2014 screen easy candidates and propose the command for you to run \u2014 *\"which PRs are ready for quick-merge?\"*\n5. **Mentor** \u2014 help a contributor through the next step \u2014 *\"draft helpful feedback for this contributor\"*\n6. **Stale sweep** \u2014 propose follow-ups for inactive PRs \u2014 *\"show me the stale PRs\"*\n7. **Stats** \u2014 see where the queue needs attention \u2014 *\"summarise the PR backlog by area\"*\n\nNothing is written, posted, labelled or closed without your explicit confirmation.\nQuick-merge never merges for you: it hands you the command.\n\n## \ud83d\udcac Just ask\n\n- *\"check my branch before I open my first PR\"*\n- *\"triage the PRs waiting for review\"*\n- *\"who should review this PR?\"*\n- *\"review this PR against our criteria\"*\n- *\"review this PR stack in dependency order\"*\n- *\"which PRs are ready for quick-merge?\"*\n- *\"help this contributor understand the requested change\"*\n- *\"what changed in the queue since the last sweep?\"*\n- *\"summarise the PR backlog by area\"*\n\n## \ud83c\udfa8 Make it yours\n\nChange a workflow by describing the change:\n\n- *\"from now on, group the backlog by our area labels\"*\n- *\"use our review criteria when drafting feedback\"*\n\nEach becomes an override for the PR-management skill it changes.\nUseful to other maintainers? *\"Upstream this change to Magpie\"* prepares a generic PR for you to review before it opens.\n\n## \ud83d\udc4b About this guide\n\n- **Continue** \u2014 show it again next time (three times at most)\n- **Dismiss** \u2014 hide it until the next Magpie upgrade\n- **Don't show again** \u2014 hide it for good; say *\"show the pr-management welcome again\"* to bring it back\n\nShow this again any time: `/magpie-setup:welcome-guide pr-management`\n(`/magpie-setup-welcome-guide pr-management` on a pinned snapshot).\n\n\ud83c\udf08 Prefer it in colour? Run this yourself \u2014 the `!` prefix runs it as a shell command:\n\n```text\n! PYTHONPATH=\"$(python3 -I -c 'import hashlib,os,sys;h,d,m,i=sys.argv[1:];r=os.path.realpath(os.curdir);s=os.stat(r);p=os.path.join(h,d,hashlib.sha256(r.encode()).hexdigest()[:16]);f=os.path.join(p,i);print(p if os.path.isdir(os.path.join(p,m)) and os.path.isfile(f) and open(f).read().split()==[str(s.st_dev),str(s.st_ino)] else h)' \"$HOME/.cache/apache-magpie/preflight\" projects setup_preflight root-id)\" python3 -P -m setup_preflight.welcome show --family pr-management --color=always\n```\n",
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
