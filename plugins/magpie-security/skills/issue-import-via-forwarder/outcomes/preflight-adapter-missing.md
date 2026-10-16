<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-via-forwarder — a declared adapter is not installed

`preflight` printed `outcome: abort` and exited `2`. From Step 0:

2. **Each `name` under `forwarders.enabled` resolves to an installed adapter.** For each name, verify there is a directory `tools/forwarder-relay/<name>/` (or the reference doc the adapter points at — for the ASF default, [`tools/gmail/asf-relay.md`](../../../../../tools/gmail/asf-relay.md)) documenting the adapter's preamble / credit / addressing rules.
   If a name has no matching adapter on disk, stop and surface *"adapter `<name>` declared in `forwarders.enabled` but not installed under `tools/forwarder-relay/`; aborting"*.
