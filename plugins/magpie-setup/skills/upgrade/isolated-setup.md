<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# The isolated setup when its state is unknown or absent

Read from [Gather](SKILL.md#gather) and [Plan](SKILL.md#plan) when `isolated.state` is `unknown`, or the offer is pending.

## No isolated setup

When `isolated.state` is `unknown` (`python3 -P -m setup_preflight.isolated configured` printed `{"configured": false}` and the personal layer's `reconciled.json` does not carry `"isolated_setup": {"enabled": false}`), the state is *not known*: inside the sandbox the user-scope settings are read-denied.
[Plan](#the-offer-in-the-plan) holds the rule: a `[bypass]` *Check* item reads `~/.claude/settings.json` for `sandbox.enabled`, and the offer waits until that read confirms absence.
The offer is two or three plain lines: the agent then runs in a sandbox that cannot read credentials or reach arbitrary hosts, forge and git operations go through guarded and audited paths, and pre-disclosure security content stays on the machine.
It proposes [`setup-isolated-setup-install`](../isolated-setup-install/SKILL.md) after this run, as one question folded into the plan's approval message.
On a decline, drop the *Isolated setup* area from gathering and the plan, complete every other area, and record the decline so the next run does not ask again: merge `"isolated_setup": {"enabled": false}` into the `reconciled.json` in `layers.stamp_dir` as a JSON edit that preserves every other key (no CLI owns this key; [`setup-isolated-setup-update`](../isolated-setup-update/SKILL.md#when-the-pre-flight-proposes-this-skill) has users set it by hand).
The summary says how to undo it: remove that key, or run `setup-isolated-setup-install`.

## The offer in the plan

The isolated-setup offer is made only when absence is confirmed: the user-scope settings, read outside the sandbox, enable no sandbox, and `reconciled.json` has no `"isolated_setup": {"enabled": false}` opt-out.
A `configured: false` read inside the sandbox means *unknown*: the plan carries a `[bypass]` *Check* item that reads those settings with the harness's file-read tool or `/usr/bin/jq` (never the personal layer's `setup_preflight` outside the sandbox) and makes no offer yet; the offer may follow in the second plan once that *Check* confirms absence.
