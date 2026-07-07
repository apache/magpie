<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Output format

Return ONLY valid JSON with this structure:

```json
{
  "fired_rules": ["R1", "R2", ...],
  "top_priority": "high | medium | low | none",
  "top_action": "<slash command string>" | null
}
```

`fired_rules` is the list of recommendation rule IDs (R1–R7) that triggered,
in declaration order. `top_priority` is the highest priority among fired rules
("none" when only R7 fired — the no-urgent-actions case). `top_action` is the
`action` field of the highest-priority fired rule, or null when only R7 fired.
Do not include any text outside the JSON object.
