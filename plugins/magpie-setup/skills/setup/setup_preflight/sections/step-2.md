<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## step-2 — a snapshot install is out of sync

Two states send you here, and they need different remedies:

- **`.apache-magpie.local.lock` is missing** — the snapshot was never
  fetched on this machine. Stop and propose `/magpie-setup`.
- **`ref` / `commit` differ** — this machine is on a different framework
  version than the project pins. Stop and propose `/magpie-setup upgrade`.

Either way this is a stop, not a note: the rest of the skill would run
against a framework version the project did not choose.
