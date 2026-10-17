<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Hand-off — unjustified NOTICE removal

**Likely cause:** the prep diff removes a `NOTICE` attribution for a dependency that still appears in the dependency tree or in vendored code (Golden rule 4).

**Remediation:** stop, do not propose the prep PR, and return:

```json
{
  "category_x_hit": false,
  "notice_removal_unjustified": true,
  "unjustified_removals": ["<the removed attribution, as `prepare notice` printed it>"],
  "handoff_reason": "NOTICE attribution removed for a dependency still present in the tree. Justify the removal or revert it."
}
```

The RM justifies the removal (the dependency is gone) or reverts it, then reruns `prep`.
A removal for a dependency that was cleanly removed from the project is allowed: note it in the prep PR body instead.
