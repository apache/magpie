<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #1173 "release-verify-rc: validate rc jars" (open)
Request, as a checklist in the body:
  1. POM declares ALv2
  2. incubator disclaimer present
  3. sources jar present
  4. javadoc jar present
  5. Nexus staging repository matches the artefacts
  6. reproducible-build check
  7. namespace check
  8. jar signatures verified against KEYS

Commits on main mentioning #1173 (issue_refs.py):
  closing: none
  referencing: 9c075618 (#1415), 78032a90 (#1505), 3d4054b6 (#1506), 0b1d2e7f (#1619)

On main: release_management/verify_rc/jvm.py implements checks 1–7; no code verifies jar signatures against KEYS.
