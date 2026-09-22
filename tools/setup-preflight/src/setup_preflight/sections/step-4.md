<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## step-4 — the fingerprint moved, or was never stamped

The checker has already resolved which store holds this project's
`skills` map, compared the fingerprints, and applied the already-shown
suppression. **Do not redo any of that** — it reported this finding
because it is worth raising, so act on the `code` and the `facts` rather
than re-deriving them.

**`code: "fingerprint-moved"`** — this skill's configuration was written
against a different shape of this skill. `facts.cause` says which half
moved, and it selects the fix:

- **`"requires_config"`** — an entry no longer resolves. Propose
  `/magpie-setup config` for this skill. A `config-missing` finding
  usually accompanies this one, naming the files.
- **`"anchors"`** — every `requires_config` entry still resolves, so what
  moved is a step heading or golden-rule name an override may anchor to.
  Propose re-anchoring per *Reconciliation on framework upgrade*
  (`docs/setup/agentic-overrides.md`). This is a proposal to make, not a
  silence to keep: an override anchored to a heading that no longer
  exists is applied partially and without complaint, which is the whole
  failure this check exists to catch.

Propose both when both findings are present.

`facts.in_both_stores: true` is an expected transitional state, not a
fault — someone configured the project before it adopted, on a machine
`adopt` never ran from. The local entry wins; say that `/magpie-setup
reconcile` offers to drop the redundant one.

**`code: "sweep-never-run"`** — nothing in this project has ever been
reconciled, so a per-skill fix would be guesswork about a baseline that
does not exist. Propose the one-time `/magpie-setup reconcile` sweep
instead.

**Record what you showed, the moment you show it.** Write
`acknowledged.skills["<name>"]: <facts.current>` for a `fingerprint-moved`
proposal, or `acknowledged.sweep: <the stamp's own version>` for a sweep.
Recorded on display, never on a decline this step does not wait for —
that is what stops the same proposal reappearing on every later
invocation, and it is what the checker reads to suppress it.

**Every write merges into `.apache-magpie-local/reconciled.json`; it
never replaces the file.** Read it, set the one key, write the whole
object back with every other key intact — and create the file, and
`.apache-magpie-local/` itself, when either is absent.
