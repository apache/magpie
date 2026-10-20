<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

There is no `.apache-magpie.lock`, no `.apache-magpie-overrides/` and no
`.apache-magpie-local/` at the repo root, and no personal layer at
`.git/apache-magpie/` either. The running agent is Claude Code
with magpie-setup 0.4.0 and magpie-issue 0.4.0 installed.

The invoked skill declares `requires_config: [issue-tracker-config.md,
project.md]`. Neither file resolves in either directory.

The user also asked to hear once about the project-adoption option,
but did not ask to run adoption.

The pre-flight command printed:

```json
{
  "findings": [
    {
      "code": "config-missing",
      "facts": {
        "files": [
          "issue-tracker-config.md",
          "project.md"
        ]
      },
      "scope": "skill",
      "section": "step-7"
    }
  ],
  "rules": {
    "step-7": "## step-7 \u2014 a required config file is missing\n\nRunning `/magpie-setup:setup config` unasked is safe because of what it touches:\nonly the personal layer \u2014 `<git-common-dir>/apache-magpie/` when the\nproject has not adopted Magpie, the gitignored `.apache-magpie-local/` when\nit has (the main checkout's, from a linked worktree that has none) \u2014 which\nis invisible to every other person and every other clone and undone by\ndeleting a directory. It stages nothing, commits nothing, writes nothing\ninto the working tree of an unadopted project, and changes nothing about\nthe repository anyone else sees.\n\nUnlike a plugin below the floor, this needs no restart: the files are\nwritten and read in the same turn, so the interruption ends and the command\nproceeds.\n\nThe two prohibitions are in the block itself because they bind whether or\nnot this file was read: never fabricate a value, and never continue past a\nvalue the skill needs but does not have."
  },
  "verdict": "action"
}
```
