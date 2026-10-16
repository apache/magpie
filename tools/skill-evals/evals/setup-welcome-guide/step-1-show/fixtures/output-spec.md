<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "family": "<the guide name passed to --family>",
  "command": "<the welcome show command run>",
  "outcome": "show-verbatim" | "list-available" | "propose-config",
  "enable": true | false
}
```

`family` is the guide name the skill resolved, as passed to `--family`.
`command` is the `python3 -m setup_preflight.welcome show …` command it ran.
`outcome` is `show-verbatim` when the command printed a guide and it is shown unchanged,
`list-available` when no guide has that name and the skill lists the ones that ship,
and `propose-config` when the checker module is not installed.
`enable` is `true` only if the skill also runs `welcome enable`.
Do not include any text outside the JSON object.
