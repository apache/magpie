<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Footer — comment maintainer

Used for `COMMENT` from an account with confirmed write access (`admin` / `maintain` / `write`). `render` appends it verbatim from the tool's templates, with only `<PROJECT>` and the contributing-docs URL substituted (no URL configured: the last two lines are dropped rather than linking to a guess), and `verify_footer` confirms it before the post command is offered.
Never paraphrase or shorten it; per-PR edits must not drop it (Golden rule 5). `APPROVE` and `REQUEST_CHANGES` always carry the maintainer-confirmed wording because GitHub refuses them without write access; `COMMENT` has no such gate, so its wording follows the permission read.
