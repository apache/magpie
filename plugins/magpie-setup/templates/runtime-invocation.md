<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>` — runtime invocation](#todo-project-name--runtime-invocation)
  - [Build prerequisite](#build-prerequisite)
  - [Run a single file](#run-a-single-file)
  - [Runtimes by language (optional)](#runtimes-by-language-optional)
  - [Capture conventions](#capture-conventions)
  - [Network and dependency handling](#network-and-dependency-handling)
  - [Cross-references](#cross-references)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>` — runtime invocation

How to invoke the project's runtime on a single source file. Used
by [`issue-reproducer`](../../../skills/issue-reproducer/SKILL.md)
when running extracted code from issue descriptions.

The `<runtime>` placeholder resolves from the *Run a single file*
section below.

## Build prerequisite

How to build or install the project so its runtime is invocable.
Skip this section if the runtime is on `PATH` out-of-the-box.

TODO: replace with the project's actual prerequisite. Examples:

- JVM-language projects with Gradle: `./gradlew :installDist`
  followed by a `~/.<project>/<runtime>/bin/<command>` path.
- Python projects with build artefacts: `pip install -e .`.
- Shell-script projects: usually no prerequisite.
- Native binaries already on `PATH`: no prerequisite.

## Run a single file

TODO: the command that invokes the runtime on a path. Placeholders
the skill resolves at runtime:

- `<file>` — path to the source file the reproducer wrote.
- `<args>` — optional argv to pass.

Recipe:

```text
TODO-runtime <file> <args>
```

Concrete examples for common project types:

```text
# Apache Foo (a JVM scripting language): ~/.foo-runtime/bin/foo <file>
# Python project:                         python <file>
# Compiled binary already on PATH:        <project-name> run <file>
# Shell:                                  bash <file>
```

## Runtimes by language (optional)

Leave this section out when every reproducer runs on the one recipe above.
Fill it in when reporters post reproducers in more than one language (a
library with Python and JavaScript bindings, a JVM project whose issues carry
both a scripting-language snippet and a Java test). Each row maps a code
block's language, as `issue-reproducer`'s Step 1 records it, to the command
that runs a file in it. The recipe above stays the default for a block whose
language is `unknown`.

| Language | Command |
|---|---|
| TODO: e.g. `python` | TODO: e.g. `python <file>` |
| TODO: e.g. `java` | TODO: e.g. `java <file>` (single-file source launch) |

With the table present, a block in a language that has no row is not run:
the skill never rewrites a reproducer into another language to fit a runtime.

## Capture conventions

How to capture stdout, stderr, and exit code in a way the skill can
parse.

| Stream | Convention |
|---|---|
| `stdout` | TODO: usually no special handling needed |
| `stderr` | TODO: many projects emit failure indicators to stderr — capture both |
| `exit code` | TODO: 0 = success, non-zero = failure, by convention |
| `timeout` | TODO: 60s is a common default; raise for known long-running projects |

## Network and dependency handling

TODO: describe whether the runtime resolves dependencies at runtime
(Grape for JVM scripting languages, pip for Python, etc.) and how
the skill should handle resolution failures.

- If yes: the skill must check exit code AND output for resolution
  errors before claiming `passes` or `fails` — a swallowed
  resolution exception looks like the run completed but the body
  never executed.
- Where the project caches dependencies (e.g., `~/.<project>/cache/`),
  consider isolating per-campaign so the operator's everyday cache
  stays clean. The skill supports a `cache_isolation_flag` field
  declared here that it passes through on every invocation.

| Key | Value |
|---|---|
| `resolves_dependencies_at_runtime` | TODO: `true` or `false` |
| `cache_isolation_flag` | TODO: e.g. `-Dgrape.root=<scratch>` if applicable; omit if not |

## Cross-references

- [`reassess-pool-defaults.md`](reassess-pool-defaults.md) — named
  pools for `issue-reassess` sweeps.
- [`reproducer-conventions.md`](reproducer-conventions.md) —
  per-issue evidence-package directory layout.
- [`issue-tracker-config.md`](issue-tracker-config.md) — tracker
  URL and project key.
