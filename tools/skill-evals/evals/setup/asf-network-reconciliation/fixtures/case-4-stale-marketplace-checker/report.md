<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

A marketplace plugin has updated to the current Magpie version, but the separate cached setup_preflight package is from an older release and lacks organization_network. The trusted checker refresh fails. The operator is attempting local network reconciliation.

No settings changes can be proposed or applied during this failed checker refresh. The target_scope field describes the destination of an actionable ASF-network settings change, not the location of existing settings being inspected. Historical permissions may still be inspected and reported, but this scenario has no actionable settings-change destination.
