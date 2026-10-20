<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

The project uses the trusted apache/magpie marketplace, requires version
0.3.0 of magpie-setup and magpie-agent-guard, and has project.md configured.
The running agent is Claude Code, but its `claude` executable is missing
from PATH. The operator supplied a previously captured listing using
`--plugin-list`: both plugins were installed at 0.2.0. The checker therefore
knows the floor is unmet even though no update command can run here.
The invoking skill is already reconciled to `sha256:2edc90a1b7f3440d`.

The pre-flight command printed:

```json
{
  "findings": [
    {
      "code": "below-floor",
      "facts": {
        "harness": null,
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
          }
        ],
        "restart_required": true
      },
      "scope": "project",
      "section": "step-3"
    }
  ],
  "rules": {
    "step-3": "## step-3 \u2014 the marketplace floor\n\n**`url` names something other than `apache/magpie`.** Run **nothing**. Name\nthe marketplace the lock points at, show the commands it would take, and\nlet the user decide: the skill stops until they have. A lock is a committed file in whatever repository\nhappened to be opened, and acting on it automatically would make opening a\nrepository enough to install someone else's code.\n\n**Comparing versions.** PEP 440, not strings: `0.10.0` is newer than\n`0.9.0`, and `0.2.0` is newer than `0.2.0.dev202609110041`. A dev build is\na version like any other \u2014 nothing strips the `.devN` segment or rounds to\nthe release segment. The reconciliation check in step 4 is gated on the\nfingerprint, never on this version delta.\n\n**Why an unreadable result is *unknown* rather than *absent*.** Inside a\nsandboxed session the plugin cache is read-denied and the running harness's\nown listing returns `[]` there \u2014 that reads exactly like \"nothing installed\"\nbut is not. Acting on it would propose installing a project's entire floor\non every sandboxed run.\n\nFor Codex, read only the `installed` list in its JSON envelope; available\ncatalogue entries are not installed versions. An unfamiliar name form or\nschema stays unknown. Require an exact floor plugin name before trusting\na Codex listing, and the exact `magpie` extension name on Gemini.\n\n**The actions.**  The `below-floor` finding names the harness its listing\ncame from (`facts.harness`); the commands differ per client, and naming one\nthe operator cannot run in this session wastes their turn:\n\n| Harness | a floor plugin absent | a floor plugin below `min_version` |\n|---|---|---|\n| Claude Code | `claude plugin install <plugin>@apache-magpie` | `claude plugin update <plugin>@apache-magpie` |\n| Codex | `codex plugin add <plugin>@apache-magpie` | `codex plugin marketplace upgrade apache-magpie` |\n| Gemini CLI | `gemini extensions install https://github.com/apache/magpie` | `gemini extensions update magpie` |\n\nGemini installs the framework as one extension, so on it the floor is\ncarried by the `magpie` extension as a whole: update that one extension\nrather than naming individual plugins.\n\n`facts.harness` is `null` when the caller supplied the listing and no\nharness with a listing command is running. Use the row of the harness this\nsession runs in; if that is not known, print every row rather than guess.\n\nCopilot CLI installs from a repo URL or catalogue and has no plugin CLI to\nread a listing or run an action with. There the floor stays unknown: run\nnothing, and leave it to the user.\n\nWhere there is no such CLI, run nothing and print the commands instead.\n\nThen step 5 applies: whichever of these you took, the session is still\nbelow the floor and has to be restarted."
  },
  "verdict": "action"
}
```
