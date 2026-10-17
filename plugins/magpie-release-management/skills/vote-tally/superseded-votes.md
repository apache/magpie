<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# One person, one vote

When someone votes more than once (a changed vote, or a member writing from two addresses), only their latest vote counts.
"Latest" is thread order, the order the list archive received the votes, so pass the votes to the tally in that order;
a sender sets their own `Date` header, so the date never decides.
The earlier votes are listed in `superseded_votes`; name them in the tally so the RM can see the change.
A vote whose date runs backwards against thread order is listed in `date_order_mismatches`: surface it to the RM.
A clear later vote replaces an earlier ambiguous one; an ambiguous latest vote still halts the tally.

A roster member's votes from their `Primary email` and from `<apache-id>@apache.org` are one voter.
An address written into the display name never binds and never supersedes another voter's vote.
