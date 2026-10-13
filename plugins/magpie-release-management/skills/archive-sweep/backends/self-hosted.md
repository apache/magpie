<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Archive backend — `self-hosted`

**Listing.** Run the adopter-supplied listing command from `<project-config>/release-management-config.md`; `listing` prints no command.

**Archive.** Use the adopter-supplied archival command template from `<project-config>/release-management-config.md`, substituting `<ver>` and the archive destination:
pass it to `render --command-template '<template>'`, which substitutes `<ver>` / `<version>` and `<archive-url>` (shell-quoted) once per past-retention version, oldest first.
Without a template the render is refused; ask the RM for it rather than inventing one.
