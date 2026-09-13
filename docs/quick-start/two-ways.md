<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->

- [Installation or Adoption?](#installation-or-adoption)

<!-- END doctoc -->

# Installation or Adoption?

**Installing** puts the **Apache Magpie Marketplace** and the plugins into
your agent and writes
nothing to any repository. That is what the steps below do, it is complete on
its own, and it is all most people ever need.

From here the two ways to use it differ in one thing only — whether anything is
committed for other people.

| | [**Individual use**](../setup/individual-use.md) | [**Team adoption**](../setup/team-adoption.md) |
|---|---|---|
| Who decides | You | The repo's maintainers |
| What it commits | Nothing — configuration lives in gitignored `.apache-magpie-local/` | The floor, and the project's configuration in `.apache-magpie-overrides/` |
| Which repos | Any — adopted or not, whether or not your teammates use Magpie | The one repo, for everyone who clones it |
| What a teammate sees | Nothing at all | The default families already enabled on arrival |
| Undone by | You, any time | A maintainer, via a PR |

**Individual use is the default, and it is not a waiting room.** You can work
this way indefinitely, on a repo whose maintainers have never heard of Magpie.
Nothing on this page asks the project for permission — including the
configuration a skill needs, which `/magpie-setup config` writes into a
gitignored directory only your clone sees. A skill that finds it missing runs
that itself.

**Adoption is a recommendation, not a restriction.** A repo that has adopted
Magpie gives contributors a sensible floor on clone — it never limits what
anyone may install for themselves, and it never obliges a contributor to use
what it recommends.

Neither one is an install method. Installing is what the
[quick start](../quick-start.md) walks you through; these are what you then do
with it. Follow it either way — [adoption](../setup/team-adoption.md) is a
later, separate act by the repo's maintainers, and nothing in the quick start
requires it.
