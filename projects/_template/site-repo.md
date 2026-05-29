<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**  *generated with [DocToc](https://github.com/thlorenz/doctoc)*

- [TODO: `<Project Name>`: site-repo configuration](#todo-project-name-site-repo-configuration)
  - [Repository](#repository)
  - [Files updated on release](#files-updated-on-release)
  - [Site build](#site-build)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->

<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# TODO: `<Project Name>`: site-repo configuration

**This file is a placeholder ahead of the release-management
skill family landing.** None of the `release-*` skills exist
yet, see
[`docs/release-management/README.md`](../../docs/release-management/README.md).
The values below are what `release-announce-draft` will read to
open the site-bump PR alongside the `[ANNOUNCE]` email.

The repository and file set the project's website lives in. Most
ASF projects publish their site from a separate repo
(`<project>-site` or `<project>-website`); a handful publish from
`docs/` inside the main repo. Either shape works.

## Repository

TODO: name the site repository.

Example shape:

> - **Repo:** `apache/<project>-site`
> - **Default branch:** `main`
> - **Site URL:** `https://<project>.apache.org`

If the site lives inside the main project repo, set:

> - **Repo:** `<same as upstream_repo in project.md>`
> - **Site root within repo:** `docs/`

## Files updated on release

TODO: list the files that change when a new release ships. Each
entry: path relative to the site repo root, what it carries, what
to update.

Example shape:

> - `landing-pages/site/content/en/_index.md`, homepage hero;
>   update the *current version* banner.
> - `landing-pages/site/content/en/announcements/<version>.md`,
>   per-release announcement post; new file per release.
> - `data/releases.yaml`, machine-readable release index;
>   append the new release entry.

`release-announce-draft` opens a single PR against the site repo
that touches every file listed here, with the appropriate values
filled in from the release planning issue.

## Site build

TODO: name the site's build invocation and verification command,
so reviewers can preview the site-bump PR locally.

Example shape:

> ```bash
> # Static-site preview
> hugo serve
> # Production-style build
> hugo --minify
> ```

The skill does not run the build itself; the value here is
documentation for the reviewer who picks the PR up.
