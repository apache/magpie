<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-via-forwarder — no forwarder configured

`preflight` printed `outcome: no-forwarder-config`. From Step 0:

1. **`forwarders.enabled` is non-empty.** Read the value from [`<project-config>/project.md → forwarders.enabled`](../../../../../<project-config>/project.md#forwarders).
   When the list is empty, **return immediately** with `match: null, sub_skill_applied: false` and a one-line note *"forwarders.enabled is empty — no relay handling configured; parent skill proceeds with the direct-reporter path"*.
   The parent keeps its own direct-reporter classification.
