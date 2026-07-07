<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #318

Title: Decide on public API shape for the new plugin system

Body:
The new plugin system is taking shape internally but we have not yet
decided on the public interface that third-party plugins will implement.
We need to nail down:

- Whether plugins register via entry-points, a config file, or both.
- What the base class / protocol looks like (if any).
- How plugins discover project-specific config at runtime.
- Versioning and stability guarantees for the plugin API.

This decision will affect all downstream plugin authors and is a
prerequisite for the 2.0 release.

Relevant files: `src/acme/plugins/__init__.py`,
`src/acme/plugins/loader.py`, `docs/plugins.md`.

Labels: design, plugins, 2.0
