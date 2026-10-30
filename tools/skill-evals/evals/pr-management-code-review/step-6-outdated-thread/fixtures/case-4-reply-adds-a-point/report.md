<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

## Outdated thread

Thread by `rex` on `src/acme/operators/exec.py`:

> `retries` is hardcoded to 3 here, so a caller has no way to turn
> retries off for a non-idempotent command. Could it be a parameter?

Reply by `rex`:

> Also, please reject a negative value; `run_with_retries` loops forever on one.

## Current diff of src/acme/operators/exec.py

```diff
+class ExecOperator(BaseOperator):
+    def __init__(self, *, command: list[str], retries: int = 3, **kwargs) -> None:
+        super().__init__(**kwargs)
+        self.command = command
+        self.retries = retries
+
+    def execute(self, context):
+        return run_with_retries(self.command, attempts=self.retries)
```
