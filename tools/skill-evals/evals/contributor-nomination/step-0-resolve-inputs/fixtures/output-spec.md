<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "real_name": "<resolved value or sentinel>",
  "apache_id": "<resolved value, '[none yet]', or sentinel>",
  "employer": "<resolved value, '[UNCONFIRMED — verify before sending]', or sentinel>",
  "real_name_warning": true | false,
  "apache_id_warning": true | false,
  "login_rejected": true | false,
  "rejection_reason": "<one sentence, or null>"
}
```

- `real_name`: the resolved display name, or `[NAME UNKNOWN — verify before sending]` if the API returned null/empty
- `apache_id`: the verified Apache ID for a pmc target, `[none yet]` for a committer target, or `[APACHE ID UNKNOWN — verify before sending]` if unverifiable
- `employer`: the confirmed employer, or `[UNCONFIRMED — verify before sending]` if unconfirmed
- `real_name_warning`: true when real_name is the unknown sentinel
- `apache_id_warning`: true when apache_id is the unknown sentinel
- `login_rejected`: true when the login fails validation and the skill must stop
- `rejection_reason`: one sentence explaining why the login was rejected, or null

Do not include any text outside the JSON object.
