<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Apache Magpie — expectations for AI-assisted contributions](#apache-magpie--expectations-for-ai-assisted-contributions)
  - [1. AI-assisted contributions are welcome](#1-ai-assisted-contributions-are-welcome)
  - [2. Licensing conditions (ASF guidance, `#include-in-contributions`)](#2-licensing-conditions-asf-guidance-include-in-contributions)
  - [3. Disclosure](#3-disclosure)
  - [4. Human ownership and review](#4-human-ownership-and-review)
  - [5. What this policy does not do](#5-what-this-policy-does-not-do)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Apache Magpie — expectations for AI-assisted contributions

This document states what Apache Magpie expects from AI-assisted contributions.
The `contributor-to-committer` and `contributor-nomination` skills read it through
`automated_contribution_expectations`, and `pr-management-code-review` links to it.
It restates the
[ASF Generative Tooling Guidance](https://www.apache.org/legal/generative-tooling.html)
for this project and adds the project's own norms from
[`CONTRIBUTING.md` → Authoring with an agent](../CONTRIBUTING.md#authoring-with-an-agent).
Where this file and the ASF guidance differ, the ASF guidance wins.

## 1. AI-assisted contributions are welcome

Most contributions to Apache Magpie are authored with a coding agent.
Using one is neither a negative nor a positive signal in itself.
What is assessed is the contribution and the contributor's ownership of it.

## 2. Licensing conditions (ASF guidance, `#include-in-contributions`)

A contribution that includes AI-generated content is acceptable only when:

1. **The tool's terms are compatible.**
   The tool's terms and conditions place no restriction on use of the output
   that is inconsistent with the Open Source Definition.
2. **No incompatible third-party material.**
   At least one holds: the output is not copyrightable,
   it contains no third-party material,
   or any third-party material is used with permission
   (for example under a compatible open-source licence).
3. **Reasonable certainty.**
   The contributor has reasonable certainty that condition 2 is met
   (see ASF `#handling-references`).
   Third-party material that is identified follows the
   [ASF 3rd Party Licensing Policy](https://www.apache.org/legal/resolved.html).

## 3. Disclosure

1. **Commit trailer.** AI-assisted commits carry a `Generated-by: <tool and version>` trailer,
   as the ASF guidance recommends and as this project's
   [`commit-attribution.toml`](../.apache-magpie-overrides/commit-attribution.toml) (`convention = "generated-by"`) requires.
   A `Co-Authored-By:` trailer naming an AI tool is **not** acceptable:
   the tool is not an author.
2. **PR description.** The PR body states that generative AI was used,
   via the Gen-AI disclosure block that `gh pr create --web` pre-fills.
3. **Public content.** Text published on a public surface
   (a PR comment, an issue, a mailing-list post) is either reviewed by the
   contributor before it is posted or labelled as AI-generated
   (ASF `#what-about-publishing-ai-generated-content-publicly`).

## 4. Human ownership and review

1. **The contributor is the author.**
   They have read every line of the diff, can explain it,
   and answer review questions themselves rather than relaying them to the agent.
2. **Verification before review.**
   `prek run --all-files`, the affected package's tests,
   and — for a skill change — the affected eval suite are run before review is requested.
3. **Review comments carry the reviewer's own judgement.**
   A comment that only restates the PR description, the diff,
   or earlier comments adds no review signal.
4. **Maintainer pushback is addressed, not regenerated.**
   A contribution that drew pushback as looking generated or unreviewed
   is fixed by the contributor engaging with the feedback,
   not by resubmitting a fresh generation.

## 5. What this policy does not do

It does not approve or forbid particular tools:
the ASF deliberately keeps no approved-tools list (ASF `#approved-tools-list`).
If a representation made under section 2 later proves inaccurate,
the contributor notifies `legal-private@apache.org`, as the ASF guidance requires.
