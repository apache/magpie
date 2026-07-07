<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the pre-post validation from Step 7b / Step 8 of the
pr-management-code-review skill from the Apache Magpie framework.

Golden rule 5: every review body MUST end with the verbatim AI-attribution
footer before it is posted. The footer is a blockquote that begins with the
exact sentence:

    "This review was drafted by an AI-assisted tool and confirmed by an
    <PROJECT> maintainer."

and ends with a link to the project's contributing pull-requests doc
(`contributing-docs/05_pull_requests.rst`). The footer must be present
verbatim — a paraphrase, a partial version, or a missing footer all fail
the rule.

Given the drafted review body below, determine whether it ends with this
footer. Set `footer_present` accordingly and choose an `action`: `post`
when the verbatim footer is present, `block` when it is missing or
paraphrased (the body must not be posted until the correct footer is
added).

The `reason` must state whether the verbatim AI-attribution footer is
present and, when blocking, that the body cannot be posted until the footer
is added.

## Output

Return ONLY valid JSON with this structure:
{
  "footer_present": true | false,
  "action": "post" | "block",
  "reason": "<one sentence>"
}

Do not include any text outside the JSON object.
