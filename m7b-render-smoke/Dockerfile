FROM debian:bookworm-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    bubblewrap ca-certificates curl git python3 procps coreutils findutils util-linux \
    && rm -rf /var/lib/apt/lists/*
RUN set -eux; echo M7B_RENDER_BUILD_NAMESPACE_PROBE_BEGIN; \
    unshare -Ur true; echo UNSHARE_USERNS_PASS; \
    bwrap --unshare-user --unshare-pid --ro-bind / / --proc /proc --dev /dev /bin/true; \
    echo BWRAP_BUILD_PASS; echo M7B_RENDER_BUILD_NAMESPACE_PROBE_END
WORKDIR /app
COPY smoke.sh /app/smoke.sh
RUN chmod +x /app/smoke.sh
ENV PORT=10000
CMD ["/app/smoke.sh"]
