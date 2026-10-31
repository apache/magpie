<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "dispatcher_installed": true | false,
  "installed_shims": ["<tool>", ...]
}
```

- `dispatcher_installed`: whether the proposal installs `~/.claude/git-hooks/git-hook-dispatcher.sh` and hook symlinks.
- `installed_shims`: lists every hook-manager binary copied to `~/.claude/bin/<tool>`. When multiple shims are installed, list them sorted alphabetically.
- Do not include any text outside the JSON object.
