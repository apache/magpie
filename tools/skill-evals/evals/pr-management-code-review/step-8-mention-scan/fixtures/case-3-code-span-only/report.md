<!-- SPDX-License-Identifier: Apache-2.0
     https://www.apache.org/licenses/LICENSE-2.0 -->

**Review body (disposition: REQUEST_CHANGES):**

Found 1 blocking issue that needs to land before this can merge.

### Blocking — commit message references a private thread (`git log`)

The commit message quoted below leaks an internal discussion handle;
please reword it:

```text
Fix flaky heartbeat test

As discussed with @ashb and @potiuk on the private thread, bump the
timeout to 30s.
```

Also note `sched@daily` in the DAG definition is unrelated — the cron
alias, not a mention — and the `@pytest.fixture` decorator on the new
test is fine.

**Inline comments (1):**

1. `tests/test_heartbeat.py:12` — `@pytest.fixture(autouse=True)` here
   makes every test in the module pay the setup cost; scope it to the two
   tests that need it.
