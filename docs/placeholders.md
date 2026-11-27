<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [Placeholders in skills and tool docs](#placeholders-in-skills-and-tool-docs)
  - [Placeholder convention used in skill files](#placeholder-convention-used-in-skill-files)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Placeholders in skills and tool docs

The substitution placeholders skills, tool-adapter docs and the repository-wide [`AGENTS.md`](../AGENTS.md) use instead of one project's concrete values, and where each resolves from. `AGENTS.md` points here before a task that writes, resolves or reviews one.

## Placeholder convention used in skill files

Skill files, tool-adapter docs, and this file use a small set of
substitution placeholders instead of baking in one project's concrete
values. Agents reading a skill must resolve these against the active
configuration before executing any command:

| Placeholder | Resolves to | Source |
|---|---|---|
| `<PROJECT>` | The project's **display name**, as written in prose, headings, and reporter-facing copy (example: `Apache Foo`). Upper-case throughout. Not interchangeable with `<project>` — see the note below the table. | `<project-config>/project.md` → `project_name` |
| `<project>` | The project's **infrastructure slug**, as it appears inside mailing-list addresses, roster URLs, and svn / dist paths (example: `foo` in `dev@foo.apache.org`, `svn.apache.org/repos/asf/foo/site`, `dist.apache.org/repos/dist/dev/foo`). Lower-case throughout. Not interchangeable with `<PROJECT>` — see the note below the table. | `<project-config>/project.md` → `short_name`, lowercased — equivalently the name half of `upstream_repo` |
| `<project-config>` | The adopting project's config directory in its tracker repo (alongside the gitignored `.apache-magpie/` snapshot, not inside it). Bootstrapped from `projects/_template/`. | Filesystem convention. |
| `<framework>` | The framework root — `.` in framework standalone, `.apache-magpie/` (the gitignored snapshot) on a pinned-snapshot install, and `~/.cache/apache-magpie/framework/current` on a marketplace install: a writable copy of the shipped tools that the `magpie-security-tools` plugin's session hook materialises for the installed version. Used in `uv run` and other invocations that address the framework's `tools/<name>/` subtrees; on every install `uv run --project <framework>/tools/<tool> …` works as written. | Filesystem convention. |
| `<workspace>` | The vetted-ops workspace: the `workspace` the active vetted-ops policy names (`uvx --from ~/.claude/magpie/vetted-ops vetted-op-read policy` prints it, and every body-file refusal names it). Every title, body or value file passed to `vetted-op` or `vetted-op-tracker` is written there, with the file-writing tool, since the write dispatchers read files from nowhere else, and they delete each body and title file once its write succeeds, so a file needed again later is kept in `<scratch>` and copied in; `--save` reads land in `<workspace>/saved/`. Other scratch files stay in the session scratch directory. | vetted-ops policy → `workspace` |
| `<tracker>` | GitHub slug of the (security) tracker repo (example: `airflow-s/airflow-s`). | `<project-config>/project.md` → `tracker_repo` |
| `<upstream>` | GitHub slug of the upstream codebase the fixes land in (example: `apache/airflow`). | `<project-config>/project.md` → `upstream_repo` |
| `<security-list>` | The project's security mailing list (example: `security@airflow.apache.org`). | `<project-config>/project.md` → `security_list` (under **Mailing lists**) |
| `<foundation-security-list>` | The org-level advisory-admin security address, distinct from the project's own `<security-list>` (example: `security@apache.org`). Inherited, not declared per-project. | organization manifest → `security_inbox.foundation_security_address` |
| `<issue-tracker>` | URL of the project's general-issue tracker, distinct from the security tracker. | `<project-config>/issue-tracker-config.md` → `url` |
| `<issue-tracker-project>` | Project key within the issue tracker (JIRA key or `owner/repo`). | `<project-config>/issue-tracker-config.md` → `project_key` |
| `<runtime>` | Recipe for invoking the project's runtime on a single source file. | `<project-config>/runtime-invocation.md` |
| `<product-name>` | The human-readable name a release is published under, in mail subjects, titles and announcements (example: `Apache Foo`). Display text, never an artefact name or dist path (those use `project_dist_name`). | `<project-config>/release-management-config.md` → `product_name`, else `<PROJECT>` |
| `<default-branch>` | The upstream repo's default branch (`master` or `main`). | `<project-config>/project.md` → `upstream_default_branch` |
| `<governance-body>` | The project's governing body, named in its own terms (example: `PMC`). | `project.md` → organization → `governance_vocabulary.governance_body` |
| `<project-stage>` | The project's lifecycle stage, if its organization has one (example: `incubating`). | `project.md` → organization → `governance_vocabulary.project_stage_vocab` |
| `<N>` | An issue or PR number. | The user's input to the skill |
| `<CVE-ID>` | A CVE identifier of the form `CVE-YYYY-NNNNN`. | Per-tracker |

**`<PROJECT>` and `<project>` are two different placeholders holding two
different values, not a casing preference for one.** `<PROJECT>` is the
display name (`Apache Foo`); `<project>` is the infrastructure slug (`foo`).
The rule of thumb: if the substitution sits inside a hostname, an email
address, or a URL path, it is `<project>`; if a human reads it as the
project's name, it is `<PROJECT>`. Substituting one where the other belongs
produces a value that is wrong rather than merely mis-cased — `Apache
Foo.apache.org` is not a hostname, and *"the foo security team"* is not how
the project is named to a reporter. Because the two differ only by case, a
fixed-string linter pattern written for one will not catch the other; keep
both spellings in mind when adding checks to
[`tools/dev/check-placeholders.sh`](../tools/dev/check-placeholders.sh).

Do not invent new placeholders; thread a needed value in via the project
manifest or the user config rather than reaching for a fresh convention.
Concretely, `gh issue view <N> --repo <tracker>` means "substitute
`<tracker>` for `<project-config>/project.md` → `tracker_repo` before
running this". Writing a literal project value directly into a skill is a
refactor bug — skills must stay project-agnostic so swapping projects is
a config change, not a code change.
