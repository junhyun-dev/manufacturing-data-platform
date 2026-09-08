FROM python:3.12.13-slim-bookworm@sha256:4766d8b510c428e595d74b9cc5bbb2fae8e26316fffb4adc89908d79aacd58a2

ARG RELEASE_VERSION=0.1.0-dev
ARG VCS_REF=unknown

LABEL org.opencontainers.image.title="Telemetry Review" \
      org.opencontainers.image.description="Review telemetry CSV files and export a version-pinned result" \
      org.opencontainers.image.source="https://github.com/junhyun-dev/manufacturing-data-platform" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.version="${RELEASE_VERSION}" \
      org.opencontainers.image.revision="${VCS_REF}"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    MFG_REVIEW_DB=/var/lib/telemetry-review/review.sqlite3 \
    MFG_REVIEW_MODE=full \
    MFG_REVIEW_RELEASE=${RELEASE_VERSION} \
    MFG_REVIEW_REVISION=${VCS_REF}

WORKDIR /app

COPY requirements-service.lock ./
RUN python -m pip install --no-cache-dir --disable-pip-version-check \
      -r requirements-service.lock \
    && groupadd --gid 10001 review \
    && useradd --uid 10001 --gid 10001 --no-create-home --shell /usr/sbin/nologin review \
    && mkdir -p /var/lib/telemetry-review \
    && chown review:review /var/lib/telemetry-review

COPY --chown=review:review src ./src

USER 10001:10001
EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=10s --retries=3 \
  CMD ["python", "-c", "import json,urllib.request; assert json.load(urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=2))['status']=='ok'"]

CMD ["python", "-m", "uvicorn", "manufacturing_data_platform.file_review.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--limit-concurrency", "16", "--timeout-keep-alive", "5", "--no-server-header"]
