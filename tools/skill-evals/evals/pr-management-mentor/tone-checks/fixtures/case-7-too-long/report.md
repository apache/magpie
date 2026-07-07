<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

@grace — Could you add a `CHANGELOG` entry for this change?

The project tracks user-visible changes in `newsfragments/`. Each PR that
touches user-visible behaviour needs a fragment. The fragment filename
should match your PR number. The fragment type should reflect the kind of
change: `feature`, `bugfix`, `doc`, `removal`, or `misc`. The content
should be a one-line summary written for an end user, not a developer.
You can find examples of existing fragments in the `newsfragments/` directory.
Run `towncrier check` locally to verify the fragment is picked up correctly.

<ai_attribution_footer>
