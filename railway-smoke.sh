#!/bin/sh
set -u
printf '%s\n' M7B_RAILWAY_SMOKE_RC7_BEGIN
uname -a
printf '%s\n' '--- os ---'
cat /etc/os-release || true
printf '%s\n' '--- id ---'
id
printf '%s\n' '--- disk ---'
df -k /
printf '%s\n' '--- memory ---'
cat /proc/meminfo | head -n 5
printf '%s\n' '--- network ---'
if curl -fsSI --max-time 10 https://github.com >/dev/null; then echo NETWORK_PASS; else echo NETWORK_FAIL; fi
printf '%s\n' '--- unshare ---'
if unshare -Ur true 2>/tmp/unshare.err; then echo UNSHARE_USERNS_PASS; else rc=$?; echo UNSHARE_USERNS_FAIL rc=$rc; cat /tmp/unshare.err; fi
printf '%s\n' '--- bubblewrap ---'
if bwrap --unshare-user --unshare-pid --ro-bind / / --proc /proc --dev /dev /bin/true 2>/tmp/bwrap.err; then echo BWRAP_PASS; else rc=$?; echo BWRAP_FAIL rc=$rc; cat /tmp/bwrap.err; fi
printf '%s\n' M7B_RAILWAY_SMOKE_RC7_END
exec python3 -m http.server "${PORT:-8080}" --bind 0.0.0.0
