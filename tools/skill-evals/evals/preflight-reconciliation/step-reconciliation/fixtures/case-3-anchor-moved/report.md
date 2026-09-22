<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

This skill's frontmatter `name:` is `magpie-pr-management-code-review`.

Its pre-flight ran the checker, which answered:

```json
{
  "findings": [
    {
      "code": "fingerprint-moved",
      "facts": {
        "cause": "anchors",
        "current": "sha256:7c2a91ff408b6e33",
        "in_both_stores": false,
        "skill": "magpie-pr-management-code-review",
        "stamped": "sha256:1a0b77dd93e40c12"
      },
      "scope": "skill",
      "section": "step-4"
    }
  ],
  "rules": {
    "step-4": "## step-4 \u2014 the fingerprint moved, or was never stamped\n\nThe checker has already resolved which store holds this project's\n`skills` map, compared the fingerprints, and applied the already-shown\nsuppression. **Do not redo any of that** \u2014 it reported this finding\nbecause it is worth raising, so act on the `code` and the `facts` rather\nthan re-deriving them.\n\n**`code: \"fingerprint-moved\"`** \u2014 this skill's configuration was written\nagainst a different shape of this skill. `facts.cause` says which half\nmoved, and it selects the fix:\n\n- **`\"requires_config\"`** \u2014 an entry no longer resolves. Propose\n  `/magpie-setup config` for this skill. A `config-missing` finding\n  usually accompanies this one, naming the files.\n- **`\"anchors\"`** \u2014 every `requires_config` entry still resolves, so what\n  moved is a step heading or golden-rule name an override may anchor to.\n  Propose re-anchoring per *Reconciliation on framework upgrade*\n  (`docs/setup/agentic-overrides.md`). This is a proposal to make, not a\n  silence to keep: an override anchored to a heading that no longer\n  exists is applied partially and without complaint, which is the whole\n  failure this check exists to catch.\n\nPropose both when both findings are present.\n\n`facts.in_both_stores: true` is an expected transitional state, not a\nfault \u2014 someone configured the project before it adopted, on a machine\n`adopt` never ran from. The local entry wins; say that `/magpie-setup\nreconcile` offers to drop the redundant one.\n\n**`code: \"sweep-never-run\"`** \u2014 nothing in this project has ever been\nreconciled, so a per-skill fix would be guesswork about a baseline that\ndoes not exist. Propose the one-time `/magpie-setup reconcile` sweep\ninstead.\n\n**Record what you showed, the moment you show it.** Write\n`acknowledged.skills[\"<name>\"]: <facts.current>` for a `fingerprint-moved`\nproposal, or `acknowledged.sweep: <the stamp's own version>` for a sweep.\nRecorded on display, never on a decline this step does not wait for \u2014\nthat is what stops the same proposal reappearing on every later\ninvocation, and it is what the checker reads to suppress it.\n\n**Every write merges into `.apache-magpie-local/reconciled.json`; it\nnever replaces the file.** Read it, set the one key, write the whole\nobject back with every other key intact \u2014 and create the file, and\n`.apache-magpie-local/` itself, when either is absent."
  },
  "verdict": "action"
}
```
