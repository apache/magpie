<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing Step 5 (confirm with user) of the security-issue-triage
skill from the Apache Magpie framework.

The user has been shown a numbered list of triage proposals and has replied
with a confirmation string. Your task: parse the reply and return the
structured action plan.

## Confirmation grammar

The user's reply is one or more of the following tokens, separated by
whitespace or commas:

  all                      — post every proposal exactly as drafted
  none  |  cancel          — abort; post nothing
  <N>                      — post item N as drafted (used when listing
                             specific items, e.g. "1,3,5")
  <N>:skip                 — omit item N from the post list
  <N>:edit <freeform>      — apply the freeform instruction to item N
                             before posting; re-draft required
  <N>:downgrade <CLASS>    — change item N's disposition to CLASS
  <N>:upgrade <CLASS>      — change item N's disposition to CLASS

CLASS must be one of: VALID, DEFENSE-IN-DEPTH, INFO-ONLY, NOT-CVE-WORTHY,
PROBABLE-DUP.

## Ambiguity rule

If the reply is ambiguous (e.g. a bare number with no context when "all"
was not said, or an unrecognised token), set action to "ambiguous" and
populate the ambiguous_tokens list. Do not guess intent.

## Output

Return ONLY valid JSON with these fields:
{
  "action": "post" | "cancel" | "ambiguous",
  "post_items": [<int>, ...],
  "skip_items": [<int>, ...],
  "edits": [{"item": <int>, "instruction": "<freeform string>"}],
  "reclassifications": [{"item": <int>, "new_class": "<CLASS>"}],
  "ambiguous_tokens": ["<token>", ...]
}

post_items contains every item number that should be posted, after applying
skips. If action is "cancel" or "ambiguous", post_items is empty.
ambiguous_tokens is empty unless action is "ambiguous".

Do not include any text outside the JSON object.
