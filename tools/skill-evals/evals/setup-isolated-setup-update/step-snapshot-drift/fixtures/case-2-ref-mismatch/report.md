cat .apache-steward.lock:
  method: git-branch
  url: https://github.com/apache/airflow-steward.git
  ref: v0.9.5

cat .apache-steward.local.lock:
  method: git-branch
  url: https://github.com/apache/airflow-steward.git
  ref: v0.9.4

Result: ref mismatch — project pin is v0.9.5 but local snapshot is v0.9.4.
The method and URL are identical; only the ref differs.
