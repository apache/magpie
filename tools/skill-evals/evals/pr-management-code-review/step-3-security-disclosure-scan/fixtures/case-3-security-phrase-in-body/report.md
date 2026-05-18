Title: Improve input validation in REST API

Body:
The existing endpoint did not sanitise the dag_id parameter, allowing
SQL injection via crafted requests. This PR adds parameterised queries
throughout the affected handlers.

Commit messages:
- "Add parameterised queries to REST API handlers"
- "Add regression tests for input validation"
