Three probes collected after user reported git push failure and dev-server startup failure.

PROBE: ssh-agent → ✗ (socket file at SSH_AUTH_SOCK not stat-able from inside sandbox)
       SSH_AUTH_SOCK=/run/user/1000/gnupg/S.gpg-agent.ssh
PROBE: localhost-bind → ✗ (bind ok, loopback GET: urllib.error.URLError: <urlopen error [Errno 110] Connection timed out>)
PROBE: docker-runtime → ⊘ (docker not on PATH)
