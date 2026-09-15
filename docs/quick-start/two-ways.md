<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Installation or Adoption?](#installation-or-adoption)

<!-- END doctoc -->

# Installation or Adoption?

**Installation** adds the Magpie marketplace and plugins to your agent.
It does not write to a repository.
Once installed, skills need repository-specific configuration, which can be local to your clone or shared through team adoption.

| | [**Individual use**](../setup/individual-use.md) | [**Team adoption**](../setup/team-adoption.md) |
|---|---|---|
| Who decides | You | The repository's maintainers |
| Configuration | Gitignored `.apache-magpie-local/` | Committed `.apache-magpie-overrides/` |
| Shared files | None | Recommended version and families, agent settings, and project configuration |
| Scope | Your clone, whether or not the project has adopted Magpie | Contributors who clone the repository |
| Effect on teammates | No shared configuration changes | Recommended families enabled on supported agents after repository trust |
| How to undo | Remove your local configuration or uninstall your plugins | Change the shared configuration through a PR |

**Example: reviewing PRs on your own.**
Install `magpie-pr-management` and run `/magpie-pr-management:triage`.
If required configuration is missing, the skill invokes `/magpie-setup config`.
The resulting files stay in your clone.
You can keep using this setup without adopting Magpie for the project.

**Example: sharing a working setup.**
After the maintainers agree on the recommended families and configuration, run `/magpie-setup adopt`.
Review the local files it proposes to promote into shared configuration.
Personal values and unresolved `TODO` entries should not be promoted.

Adoption does not prevent contributors from installing more families, using a newer version, or choosing not to use Magpie.
Start with the [quick start](../quick-start.md) for installation, or see [team adoption](../setup/team-adoption.md) for the shared-file workflow.
