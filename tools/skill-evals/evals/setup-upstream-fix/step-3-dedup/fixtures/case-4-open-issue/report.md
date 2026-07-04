Quirk: a skill's error message is confusing and misroutes the agent.
Searches run:
- `gh search issues --repo apache/magpie --state all "confusing error message misroute"` → 1 OPEN issue
  reporting the same confusing message, with no linked PR and no fix yet.
- `gh search prs --repo apache/magpie --state all "confusing error message"` → 0 results.
An open issue reports it but nobody has fixed it.
