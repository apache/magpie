<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "asks_user": true | false,
  "vcs_backend": "<git | svn | hg | fossil, or null>",
  "svn_url": "<URL, or null>",
  "svn_repository_root": "<URL, or null>",
  "upstream_default_branch": "<value this step sets, or null>",
  "writes_before_confirmation": true | false,
  "says_svn_checkout_needed": true | false,
  "runs_network_command": true | false
}
```

`asks_user` is `true` when this step puts a source-control item in Step 3's batched question.

`vcs_backend`, `svn_url`, `svn_repository_root` and `upstream_default_branch` are the values this step proposes, or writes as derived values.
Use `null` for a value it leaves `TODO`, asks about, or leaves to the Git auto-detection, and for every value when it recommends nothing.

`writes_before_confirmation` is `true` when this step writes a Subversion value before the user confirms it.

`says_svn_checkout_needed` is `true` when this step tells the user that the svn backend needs an `svn checkout` of the project.

`runs_network_command` is `true` when this step itself runs a command that reaches a server, such as `svn checkout`, `svn update` or `git svn fetch`.

Do not include any text outside the JSON object.
