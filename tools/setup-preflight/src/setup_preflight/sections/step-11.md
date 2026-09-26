<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## step-11 — the isolated setup may be out of date on this machine

Suggest `setup-isolated-setup-update` (`/magpie-setup:isolated-setup-update`
on a marketplace install), once, and say which reason applies:

- **`isolated-setup-changed`** — the framework's secure-setup files (sandbox
  wrapper and helper scripts, agent-guard, container gateway, the dogfooded
  `.claude/settings.json`) changed since the update skill last ran here, usually
  because of an upgrade. `recorded: null` means it has never been recorded on
  this machine. The installed copies may now be behind the framework's.
- **`isolated-setup-update-due`** — `days_since` days since it last ran or was
  last suggested, against an interval of `interval_days`. The pinned sandbox
  tools and the agent harness move upstream even when this repository does not.

Then record that it was shown, whether or not the user takes it:

```bash
PYTHONPATH=.apache-magpie-local python3 -m setup_preflight.isolated record-reminder
```

That re-arms the timer and this particular change, so the same suggestion is
not repeated inside one window. Never write the fingerprint by hand.

Do not run the update unasked, and do not block on it: make the suggestion in
one or two lines and carry on with the work the user asked for. The update
skill is read-only; it reports drift and the user applies what they choose.

The interval is `isolated_setup_update_interval_days` — personal
`.apache-magpie-local/project.md` first, then `.apache-magpie-overrides/project.md`,
default 7; `0` turns the timer off while still reporting changes. Someone who
does not use the isolated setup here can silence both with
`"isolated_setup": {"enabled": false}` in `.apache-magpie-local/reconciled.json`.
