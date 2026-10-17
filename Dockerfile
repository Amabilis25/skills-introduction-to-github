FROM debian:bookworm-slim
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
    bubblewrap ca-certificates curl git python3 procps coreutils util-linux \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY railway-smoke.sh /app/railway-smoke.sh
RUN chmod +x /app/railway-smoke.sh
ENV PORT=8080
CMD ["/app/railway-smoke.sh"]
