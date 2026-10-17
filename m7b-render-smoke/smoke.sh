#!/usr/bin/env bash
set -u
printf 'M7B_RENDER_SMOKE_RC5_BEGIN\n'
uname -a || true
printf '%s\n' '--- df ---'
df -Pk / || true
printf '%s\n' '--- memory ---'
free -m || true
printf '%s\n' '--- tools ---'
for t in bash python3 git curl bwrap sha256sum; do command -v "$t" || true; done
printf '%s\n' '--- network ---'
if curl -fsSI --max-time 20 https://github.com/leanprover/lean4/releases/tag/v4.35.0 >/tmp/net.hdr 2>/tmp/net.err; then echo NETWORK_PASS; else echo NETWORK_FAIL; cat /tmp/net.err || true; fi
printf '%s\n' '--- bubblewrap ---'
set +e
bwrap --ro-bind / / --proc /proc --dev /dev --unshare-pid --unshare-uts /bin/true >/tmp/bwrap.out 2>/tmp/bwrap.err
rc=$?
set -e
if [ "$rc" -eq 0 ]; then echo BWRAP_PASS; else echo "BWRAP_FAIL rc=$rc"; cat /tmp/bwrap.err || true; fi
printf 'M7B_RENDER_SMOKE_RC5_END\n'
mkdir -p /app/www
cat > /app/www/index.txt <<EOF
M7B_RENDER_SMOKE_RC5
network=$(grep -q '^HTTP/' /tmp/net.hdr 2>/dev/null && echo observed || echo not_observed)
bwrap_rc=$rc
EOF
exec python3 -m http.server "${PORT:-10000}" --directory /app/www
