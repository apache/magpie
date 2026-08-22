<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

You are executing the pre-post validation from Step 7b / Step 8 of the
pr-management-code-review skill from the Apache Magpie framework.

Golden rule 5: every review body MUST end with a verbatim AI-attribution
footer before it is posted. The footer is a blockquote that begins with
one of exactly two exact sentences:

    "This review was drafted by an AI-assisted tool and confirmed by an
    <PROJECT> maintainer."

    "This review was drafted by an AI-assisted tool and posted by a
    contributor who does not have confirmed <PROJECT> maintainer access."

An `APPROVE` or `REQUEST_CHANGES` body always uses the first sentence.
A `COMMENT` body may use either sentence, since GitHub lets a `COMMENT`
post without confirmed maintainer access: which one is correct depends
on whether the poster's collaborator permission was confirmed, not on
the words themselves; either sentence, taken verbatim, satisfies the
rule. The footer ends with a link to the project's contributing
pull-requests doc (`contributing-docs/05_pull_requests.rst`). The
footer must be present verbatim: a paraphrase, a partial version, a
blend of the two sentences, or a missing footer all fail the rule.

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
