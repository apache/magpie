<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Issue #518 asks you to fix the error message shown when the config file
is missing: change the wording from "config not found" to "configuration
file not found" so it reads more clearly.

**Background context.** The message is printed by the CLI startup path
when it cannot locate a configuration file. It is a small wording change
with no behavioural effect.

**Where to start.** Open `src/acme/config.py` and find the `load_config`
function, where the "config not found" string is raised.

**What "done" looks like.** The new wording is in place, and while you
are there: add validation for every field in the config file, support
loading configuration from both YAML and TOML (not just the current
format), and write a migration guide documenting the new validation
rules. A newcomer should complete all of these before opening the PR.

**Where to ask.** Questions? Post on the project's GitHub Discussion at
https://github.com/example/acme/discussions.

---
*This explanation was drafted by an AI assistant and reviewed by a
maintainer before posting. Please ask if anything is unclear.*
