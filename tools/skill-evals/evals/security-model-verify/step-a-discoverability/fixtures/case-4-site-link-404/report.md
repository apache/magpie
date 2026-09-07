<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

Repository: example/widget-docs, at commit b7712fe (default branch tip).

`AGENTS.md` — present, `## Security` section links `SECURITY.md`.

`SECURITY.md` — present, and its "## Threat model" section links to
https://widget.example.invalid/security/threat-model/

A HEAD request against that URL returns 404. The hostname resolves and
the site is otherwise up; only that path is missing. The project owns
that website.
