<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`.apache-magpie.lock` contains `method: marketplace`, `url: apache/magpie`,
`min_version: 0.2.0`, and a `plugins` list of magpie-setup, magpie-utilities
and magpie-agent-guard. It carries no `reconciled:` block.

`.apache-magpie-overrides/` exists and contains `project.md`.
`.apache-magpie-local/reconciled.json` does not exist, so no `reconciled:`
stamp exists in either store.

The invoked skill's own frontmatter reads `name: magpie-issue-triage` and
`surface_hash: sha256:2edc90a1b7f3440d`.

The running agent is Claude Code. `claude plugin list --json` reports all three
plugins, and magpie-vetted-ops, at 0.4.0 from the `apache-magpie` marketplace.

The pre-flight command printed:

```json
{
  "findings": [
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
    "step-4": "## step-4 \u2014 the fingerprint moved, or was never stamped\n\nThe checker has already resolved which store holds this project's\n`skills` map, compared the fingerprints, and applied the already-shown\nsuppression. **Do not redo any of that** \u2014 it reported this finding\nbecause it is worth raising, so act on the `code` and the `facts` rather\nthan re-deriving them.\n\n**`code: \"fingerprint-moved\"`** \u2014 this skill's configuration was written\nagainst a different shape of this skill. `facts.cause` says which half\nmoved, and it selects the fix:\n\n- **`\"requires_config\"`** \u2014 an entry no longer resolves. Propose\n  `/magpie-setup:setup config` for this skill. A `config-missing` finding\n  usually accompanies this one, naming the files.\n- **`\"anchors\"`** \u2014 every `requires_config` entry still resolves, so what\n  moved is a step heading or golden-rule name an override may anchor to.\n  Propose re-anchoring per *Reconciliation on framework upgrade*\n  (`docs/setup/agentic-overrides.md`). This is a proposal to make, not a\n  silence to keep: an override anchored to a heading that no longer\n  exists is applied partially and without complaint, which is the whole\n  failure this check exists to catch.\n\nPropose both when both findings are present.\n\n`facts.in_both_stores: true` is an expected transitional state, not a\nfault \u2014 someone configured the project before it adopted, on a machine\n`adopt` never ran from. The local entry wins; say that `/magpie-setup:setup\nreconcile` offers to drop the redundant one.\n\n**`code: \"sweep-never-run\"`** \u2014 nothing in this project has ever been\nreconciled, so a per-skill fix would be guesswork about a baseline that\ndoes not exist. Propose the one-time `/magpie-setup:setup reconcile` sweep\ninstead.\n\n**Record what you showed, the moment you show it.** Write\n`acknowledged.skills[\"<name>\"]: <facts.current>` for a `fingerprint-moved`\nproposal, or `acknowledged.sweep: <the stamp's own version>` for a sweep.\nRecorded on display, never on a decline this step does not wait for \u2014\nthat is what stops the same proposal reappearing on every later\ninvocation, and it is what the checker reads to suppress it.\n\n**Every write merges into the personal layer's `reconciled.json`\n(the `personal_dir` that `python3 -m setup_preflight.layers` prints); it\nnever replaces the file.** Read it, set the one key, write the whole\nobject back with every other key intact \u2014 and create the file, and\nthe personal layer itself, when either is absent \u2014 but only in the place\nthat command names, never an in-tree `.apache-magpie-local/` in a project\nthat has not adopted Magpie."
  },
  "verdict": "action"
}
```
