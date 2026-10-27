<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock`, no `.apache-magpie-overrides/` and no
`.apache-magpie-local/` at the repo root, and no personal layer at
`.git/apache-magpie/` either. The running agent is Claude Code
with magpie-setup 0.4.0 and magpie-security 0.4.0 installed.

The invoked skill's own frontmatter reads `name: issue-sync` and
`surface_hash: sha256:2edc90a1b7f3440d`; it declares no `requires_config:`.
This is the first Magpie skill this user has run here.
The user asked it to "sync 123".

The pre-flight command printed:

```json
{
  "findings": [
    {
      "code": "welcome",
      "facts": {
        "family": "general",
        "guide": "# \ud83d\udc26 Hello from Magpie \u2014 your project's maintainer sidekick\n\nOne minute, then straight back to what you asked for.\n\n## \ud83d\ude80 Getting started\n\n- \ud83d\udce6 **Install** from your agent's marketplace (Claude Code shown):\n  `/plugin marketplace add apache/magpie`,\n  then `/plugin install magpie-setup@apache-magpie` and one `/plugin install magpie-<family>@apache-magpie` per family you want\n- \ud83d\ude4b **Configure it for yourself** \u2014 personal settings, nothing committed \u2014 `/magpie-setup:setup config`\n- \ud83d\udc65 **Adopt it for your project** \u2014 the configuration is committed to your repo and shared with every contributor \u2014\n  `/magpie-setup:setup adopt` (a maintainers' decision)\n\nOn a pinned-snapshot install the commands are shorter: `/magpie-setup config`, `/magpie-setup adopt`.\n\n## \ud83d\udd04 Staying current\n\n- \u270b **By hand:** `claude plugin marketplace update apache-magpie`, then `claude plugin update <plugin>@apache-magpie`\n- \ud83e\udd16 **Automatically (Claude Code):** `/plugin` \u2192 **Marketplaces** \u2192 **apache-magpie** \u2192 **Enable auto-update** \u2014\n  it is off by default for third-party marketplaces like this one\n- \ud83e\udde9 Codex has no auto-update, so run `codex plugin marketplace upgrade apache-magpie`; on Antigravity, re-run `agy plugin install https://github.com/apache/magpie`\n\nAfter an update, the next skill you run checks your configuration against it and proposes any fixes;\n`/magpie-setup:setup reconcile` checks everything at once (on a pinned snapshot, `/magpie-setup upgrade` does the update).\n\n## \ud83d\udcac Just ask\n\nTalk to Magpie in plain language \u2014 no syntax to learn.\nNothing is written, posted, or sent without your OK.\nInterrupt at any time, say no, or change your mind halfway through.\n\n## \ud83c\udfa8 You are the creator\n\nDescribe what you want a skill to do for you:\n\n- *\"from now on, always ask me before closing a stale issue\"*\n- *\"when you triage PRs, leave the bot-authored ones alone\"*\n\nMagpie records it as an override for that skill (`/magpie-setup:setup override <skill>`).\nWorth sharing? Say *\"upstream this change to Magpie\"* \u2014 it makes the change generic and opens a PR to `apache/magpie` for you to review (`/magpie-setup:override-upstream`).\n\n## \ud83d\udcda More guides\n\nEach family can bring its own short guide, shown the first time you use it:\n\n- `contributor-growth` \u2014 `/magpie-setup:welcome-guide contributor-growth`\n- `issue` \u2014 `/magpie-setup:welcome-guide issue`\n- `mentoring` \u2014 `/magpie-setup:welcome-guide mentoring`\n- `pairing` \u2014 `/magpie-setup:welcome-guide pairing`\n- `pr-management` \u2014 `/magpie-setup:welcome-guide pr-management`\n- `release-management` \u2014 `/magpie-setup:welcome-guide release-management`\n- `repo-health` \u2014 `/magpie-setup:welcome-guide repo-health`\n- `security` \u2014 `/magpie-setup:welcome-guide security`\n- `setup` \u2014 `/magpie-setup:welcome-guide setup`\n- `utilities` \u2014 `/magpie-setup:welcome-guide utilities`\n\n## \ud83d\udc4b About this guide\n\n- **Continue** \u2014 show it again next time (three times at most)\n- **Dismiss** \u2014 hide it until the next Magpie upgrade\n- **Don't show again** \u2014 hide it for good; say *\"show the Magpie welcome again\"* to bring it back\n\nShow this again any time: `/magpie-setup:welcome-guide [<family>]`\n(`/magpie-setup-welcome-guide [<family>]` on a pinned snapshot).\n\n\ud83c\udf08 Prefer it in colour? Run this yourself \u2014 the `!` prefix runs it as a shell command:\n\n```text\n! PYTHONPATH=\"$(python3 -I -c 'import hashlib,os,sys;h,d,m,i=sys.argv[1:];r=os.path.realpath(os.curdir);s=os.stat(r);p=os.path.join(h,d,hashlib.sha256(r.encode()).hexdigest()[:16]);f=os.path.join(p,i);print(p if os.path.isdir(os.path.join(p,m)) and os.path.isfile(f) and open(f).read().split()==[str(s.st_dev),str(s.st_ino)] else h)' \"$HOME/.cache/apache-magpie/preflight\" projects setup_preflight root-id)\" python3 -P -m setup_preflight.welcome show --family general --color=always\n```\n",
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
