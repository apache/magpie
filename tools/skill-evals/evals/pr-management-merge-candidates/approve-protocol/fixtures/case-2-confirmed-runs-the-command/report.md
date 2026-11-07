<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

`quick-merge approve-check` printed:

```json
{
  "pr": 67452,
  "proceed": true,
  "command": "gh pr review 67452 --repo apache/airflow --approve",
  "confirm": "Submit an APPROVE review on #67452? This is your maintainer review of this change. [y/N]",
  "note": null,
  "merge_command": "gh pr merge 67452 --squash --repo apache/airflow"
}
```

You asked the confirmation question; the maintainer answered: `y`
