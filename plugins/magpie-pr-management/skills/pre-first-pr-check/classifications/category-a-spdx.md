<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Category A failed — SPDX headers

Each listed new file has no `SPDX-License-Identifier` line in its first ten lines, or declares a licence other than the one `<project-config>/project.md` names.
Tell the contributor to add the header in the file's own comment syntax, e.g. for Markdown:

```html
<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->
```

and `#`-prefixed lines for Python or shell. Files with no comment syntax (JSON, images, lockfiles) are not checked.
