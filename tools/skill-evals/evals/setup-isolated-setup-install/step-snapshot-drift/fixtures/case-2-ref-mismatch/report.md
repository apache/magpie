## Snapshot lock file state

cat .apache-magpie.lock:
  method: git-branch
  url: https://github.com/apache/airflow-steward.git
  ref: v0.9.3

cat .apache-magpie.local.lock:
  method: git-branch
  url: https://github.com/apache/airflow-steward.git
  ref: v0.9.2

Result: ref mismatch — project pin is v0.9.3 but local snapshot is v0.9.2.
The method and URL are identical; only the ref differs.
