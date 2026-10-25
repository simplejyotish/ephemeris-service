# syntax=docker/dockerfile:1
FROM python:3.11-slim AS builder
# pyswisseph compiles a C extension from sdist on some platforms (e.g. linux/arm64);
# the toolchain stays in the builder stage so the runtime image is slim.
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml README.md ./
COPY ephemeris_service ./ephemeris_service
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.11-slim AS runtime
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /install /usr/local
USER appuser
ENV PORT=8001
# Fail closed: production unless overridden (production requires EPHEMERIS_API_KEY and a
# real SOURCE_URL at startup).
ENV ENV=production
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import os,urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:%s/health' % os.environ.get('PORT','8001')).status==200 else 1)"
# exec so uvicorn is PID 1 and receives SIGTERM directly.
CMD exec uvicorn ephemeris_service.main:app --host 0.0.0.0 --port ${PORT:-8001}
