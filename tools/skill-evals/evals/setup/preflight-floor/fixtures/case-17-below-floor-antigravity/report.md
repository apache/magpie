<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.3.0`, and a `plugins` list of magpie-setup and
magpie-agent-guard.

`.apache-magpie-overrides/` exists and contains `project.md`.

The running agent is Google Antigravity CLI (`ANTIGRAVITY_CONVERSATION_ID` is set). There
is no `claude` executable on PATH and no Codex session markers in the
environment. The installed Magpie plugin reports version 0.2.0:
`agy plugin list --json` prints
`[{"name": "magpie", "version": "0.2.0"}]`.

The pre-flight command printed:

```json
{
  "findings": [
    {
      "code": "below-floor",
      "facts": {
        "harness": "antigravity",
        "missing": [],
        "outdated": [
          {
            "floor": "0.3.0",
            "installed": "0.2.0",
            "plugin": "magpie-setup"
          },
          {
            "floor": "0.3.0",
            "installed": "0.2.0",
            "plugin": "magpie-agent-guard"
          },
          {
            "floor": "0.3.0",
            "installed": "0.2.0",
            "plugin": "magpie-vetted-ops"
          }
        ],
        "restart_required": true
      },
      "scope": "project",
      "section": "step-3"
    },
    {
      "code": "sweep-never-run",
      "facts": {
        "skill": "issue-triage"
      },
      "scope": "skill",
      "section": "step-4"
    }
  ],
  "rules": {
    "step-3": "## step-3 \u2014 the marketplace floor\n\n**`url` names something other than `apache/magpie`.** Run **nothing**. Name\nthe marketplace the lock points at, show the commands it would take, and\nlet the user decide: the skill stops until they have. A lock is a committed file in whatever repository\nhappened to be opened, and acting on it automatically would make opening a\nrepository enough to install someone else's code.\n\n**Comparing versions.** PEP 440, not strings: `0.10.0` is newer than\n`0.9.0`, and `0.2.0` is newer than `0.2.0.dev202609110041`. A dev build is\na version like any other \u2014 nothing strips the `.devN` segment or rounds to\nthe release segment. The reconciliation check in step 4 is gated on the\nfingerprint, never on this version delta.\n\n**Why an unreadable result is *unknown* rather than *absent*.** Inside a\nsandboxed session the plugin cache is read-denied and the running harness's\nown listing returns `[]` there \u2014 that reads exactly like \"nothing installed\"\nbut is not. Acting on it would propose installing a project's entire floor\non every sandboxed run.\n\nFor Codex, read only the `installed` list in its JSON envelope; available\ncatalogue entries are not installed versions. An unfamiliar name form or\nschema stays unknown. Require an exact floor plugin name before trusting\na Codex listing, and the exact `magpie` plugin name on Antigravity.\n\n**The actions.**  The `below-floor` finding names the harness its listing\ncame from (`facts.harness`); the commands differ per client, and naming one\nthe operator cannot run in this session wastes their turn:\n\n| Harness | a floor plugin absent | a floor plugin below `min_version` |\n|---|---|---|\n| Claude Code | `claude plugin install <plugin>@apache-magpie` | `claude plugin update <plugin>@apache-magpie` |\n| Codex | `codex plugin add <plugin>@apache-magpie` | `codex plugin marketplace upgrade apache-magpie` |\n| Antigravity | `agy plugin install https://github.com/apache/magpie` | `agy plugin install https://github.com/apache/magpie` |\n\nAntigravity installs the framework as one plugin, so on it the floor is\ncarried by the `magpie` plugin as a whole: re-install that one plugin\nrather than naming individual plugins. Its listing also shows plugins\nwithout a version, such as Google's own; they are not Magpie's.\n\n`facts.harness` is `null` when the caller supplied the listing and no\nharness with a listing command is running. Use the row of the harness this\nsession runs in; if that is not known, print every row rather than guess.\n\nCopilot CLI installs from a repo URL or catalogue and has no plugin CLI to\nread a listing or run an action with. There the floor stays unknown: run\nnothing, and leave it to the user.\n\nWhere there is no such CLI, run nothing and print the commands instead.\n\nThen step 5 applies: whichever of these you took, the session is still\nbelow the floor and has to be restarted.",
    "step-4": "## step-4 \u2014 the fingerprint moved, or was never stamped\n\nThe checker has already resolved which store holds this project's\n`skills` map, compared the fingerprints, and applied the already-shown\nsuppression. **Do not redo any of that** \u2014 it reported this finding\nbecause it is worth raising, so act on the `code` and the `facts` rather\nthan re-deriving them.\n\n**`code: \"fingerprint-moved\"`** \u2014 this skill's configuration was written\nagainst a different shape of this skill. `facts.cause` says which half\nmoved, and it selects the fix:\n\n- **`\"requires_config\"`** \u2014 an entry no longer resolves. Propose\n  `/magpie-setup:setup config` for this skill. A `config-missing` finding\n  usually accompanies this one, naming the files.\n- **`\"anchors\"`** \u2014 every `requires_config` entry still resolves, so what\n  moved is a step heading or golden-rule name an override may anchor to.\n  Propose re-anchoring per *Reconciliation on framework upgrade*\n  (`docs/setup/agentic-overrides.md`). This is a proposal to make, not a\n  silence to keep: an override anchored to a heading that no longer\n  exists is applied partially and without complaint, which is the whole\n  failure this check exists to catch.\n\nPropose both when both findings are present.\n\n`facts.in_both_stores: true` is an expected transitional state, not a\nfault \u2014 someone configured the project before it adopted, on a machine\n`adopt` never ran from. The local entry wins; say that `/magpie-setup:setup\nreconcile` offers to drop the redundant one.\n\n**`code: \"sweep-never-run\"`** \u2014 nothing in this project has ever been\nreconciled, so a per-skill fix would be guesswork about a baseline that\ndoes not exist. Propose the one-time `/magpie-setup:setup reconcile` sweep\ninstead.\n\n**Record what you showed, the moment you show it.** Write\n`acknowledged.skills[\"<name>\"]: <facts.current>` for a `fingerprint-moved`\nproposal, or `acknowledged.sweep: <the stamp's own version>` for a sweep.\nRecorded on display, never on a decline this step does not wait for \u2014\nthat is what stops the same proposal reappearing on every later\ninvocation, and it is what the checker reads to suppress it.\n\n**Every write merges into the personal layer's `reconciled.json`\n(the `personal_dir` that `python3 -m setup_preflight.layers` prints); it\nnever replaces the file.** Read it, set the one key, write the whole\nobject back with every other key intact \u2014 and create the file, and\nthe personal layer itself, when either is absent \u2014 but only in the place\nthat command names, never an in-tree `.apache-magpie-local/` in a project\nthat has not adopted Magpie."
  },
  "verdict": "action"
}
```
