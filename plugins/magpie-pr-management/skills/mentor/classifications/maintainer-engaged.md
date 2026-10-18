<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

# Maintainer already engaged — exit silently

`mentor assess` returned `outcome: maintainer_engaged`: a maintainer (a `committers_team` member, or a resolved `write`+ collaborator) commented within the last `max_agent_turns` turns.
Do not draft. The agent does not talk over a human reviewer.
Record `declined-pre-draft` with `mentor log` and stop.
