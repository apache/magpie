<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "action": "post | cancel",
  "post_indices": [<integer>, ...],
  "close_stale_indices": [<integer>, ...]
}
```

`post_indices` contains the 1-based indices of proposals to post (empty
when `action` is "cancel").
`close_stale_indices` contains the subset of `post_indices` that are
CLOSE-STALE proposals requiring the two-step close confirmation.
Do not include any text outside the JSON object.
