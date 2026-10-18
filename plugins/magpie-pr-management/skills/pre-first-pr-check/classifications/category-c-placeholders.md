<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Category C failed — un-substituted placeholders

A non-template file carries a declared placeholder (`<upstream>`, `<default-branch>`, `<project-config>`, `<tracker>`, `<PROJECT>`).
Substitute the concrete value, or — if the file is meant to be a template — move it under a `_template/` directory.
See [`AGENTS.md` § Placeholder convention](../../../../../AGENTS.md#placeholder-convention-used-in-skill-files).
