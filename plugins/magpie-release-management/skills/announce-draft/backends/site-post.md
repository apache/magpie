<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Announce backend — `site-post` (`non_asf`)

The render's `body` is a blog-post or release-notes markdown file for a static-site PR:
a `## <Product Name> <version> released` heading, prose paragraphs, and the Download Page and changelog as markdown hyperlinks.
There is no `@apache.org` sender reminder: `asf_address_reminder_present` is `false`.
The file goes into the site-bump PR (Step 3), where `site_pr_files` bounds what it may touch.
