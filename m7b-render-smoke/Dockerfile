FROM debian:bookworm-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    bubblewrap ca-certificates curl git python3 procps coreutils findutils util-linux \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY smoke.sh /app/smoke.sh
RUN chmod +x /app/smoke.sh
ENV PORT=10000
CMD ["/app/smoke.sh"]
