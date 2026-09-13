<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Updating Magpie](#updating-magpie)
  - [Building the framework](#building-the-framework)
  - [Reporting back](#reporting-back)
  - [Extending it instead](#extending-it-instead)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

# Updating Magpie

The rest of the documentation is about *using* Magpie. This section is about
working on it: how changes to the framework get built, what the project
expects of the text its skills produce, how it measures whether any of this is
helping, and what ships when a release is cut.

Not everything here is for contributors to `apache/magpie`. If you only want
to add a skill for your own project, [Extending
Magpie](extending.md) is the page you want — no fork, no PR to this
repository.

## Building the framework

- [**Spec-driven development**](spec-driven-development.md) — the build loop
  in [`tools/spec-loop/`](https://github.com/apache/magpie/tree/main/tools/spec-loop/),
  and how a change to the framework goes from spec to merged.
- [**Editorial guidelines**](editorial-guidelines.md) — the playbook for text
  the framework produces: canned responses, reporter-facing mail, status
  comments, CVE and tracker links, maintainer mentions.
- [**Source release contents**](source-release-contents.md) — what ends up in
  the signed artefact a `[VOTE]` thread votes on, and how `export-ignore`
  decides it.

## Reporting back

- [**Contributor-sentiment evaluation methodology**](contributor-sentiment.md) —
  how the project measures whether agentic maintainership is helping
  contributors rather than wearing them down. The gate evidence
  [RFC-AI-0004](rfcs/RFC-AI-0004.md) asks for.
- [**Pilot report template**](pilot-report-template.md) — the shape of a
  report from a project piloting a skill.

## Extending it instead

[**Extending Magpie**](extending.md) maps what you can extend, where an
extension can live, and who owns each kind — an adapter, a skill, a whole
family, in your own repository or an external skill source. Most of what
people want from "changing Magpie" is here, and none of it needs a change to
this repository.
