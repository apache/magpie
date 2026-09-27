<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Real names

Briefs, reports, and drafted messages to the `<governance-body>` name a person as **Real Name (`handle`)** when the name comes from a source that can be checked, and by handle alone otherwise.

## Order

Take the first source that yields a name:

1. **The organization's people directory**, when the person has an account there — for ASF, `mcp__apache-projects__get_person(<apache_id>)`.
   `search_people(<name>)` may *confirm* a name already found elsewhere; it never supplies one on its own.
2. **The GitHub profile's `name` field** — `gh api users/<login> --jq '.name'`.
3. **The author name on the person's commits to `<upstream>`**, when every commit authored by the handle carries the same name.

When sources disagree, the directory wins and the brief notes the disagreement in one line.
When none yields a name, use the handle alone, and mark the name as unknown where the skill has a sentinel for it.

## Never

- infer a name from an email address, its local part, or a domain;
- infer a name from the handle;
- take a name from a mailing-list or chat display name that no confirmed identity ties to the handle (see [`community-signals.md` § Identity](community-signals.md#identity));
- include an email address in the output.
