<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

PR #71302 — "Fix N+1 query in scheduler on serialized dag load"

PR body:
> ## Summary
>
> The scheduler was issuing one DB query per dag when loading serialized
> dags, causing an N+1 pattern. This PR batches the query using
> `session.scalars(select(SerializedDagModel).where(...).in_(dag_ids))`.
>
> ## Testing
>
> - Added unit tests in `tests/core/test_scheduler.py` covering the
>   batch-load path and verifying query count with SQLAlchemy's
>   `count_queries` fixture.
>
> - [ ] I used generative AI tooling to help write some or all of this code.

Diff excerpt:
```diff
+        dag_ids = [dag.dag_id for dag in dags]
+        serialized = {
+            sdm.dag_id: sdm
+            for sdm in session.scalars(
+                select(SerializedDagModel).where(
+                    SerializedDagModel.dag_id.in_(dag_ids)
+                )
+            ).all()
+        }
```

Commit messages:
- "fix(scheduler): batch serialized dag query to avoid N+1"
