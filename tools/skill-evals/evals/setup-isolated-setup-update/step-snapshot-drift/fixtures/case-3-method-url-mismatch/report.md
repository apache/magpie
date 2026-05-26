cat .apache-steward.lock:
  method: svn-zip
  url: https://dist.apache.org/repos/dist/release/airflow/steward/airflow-steward-0.9.4-source.tar.gz
  ref: v0.9.4

cat .apache-steward.local.lock:
  method: git-branch
  url: https://github.com/apache/airflow-steward.git
  ref: v0.9.4

Result: method mismatch — committed lock specifies svn-zip but local snapshot
was fetched via git-branch. URL also differs. A full re-install is needed.
