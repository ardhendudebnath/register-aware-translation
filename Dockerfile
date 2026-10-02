# Setu — the app and the register layer, nothing else.
#
# Deliberately thin. The register layer is pure standard library, so the image
# needs Python and about thirty megabytes of pure-Python packages; the heavy
# optional extras (Whisper, transformers) are not installed and the app
# degrades to the browser's own speech APIs without them, which is the path
# almost every visitor takes anyway.
#
#     docker build -t setu .
#     docker run -p 5000:5000 -e SETU_SHARED=1 setu
#
# SETU_SHARED matters the moment more than one person can reach it. See
# DEPLOY.md: it closes relationship memory and stops writing anybody's
# sentences to disk.

FROM python:3.12-slim AS base

# PYTHONDONTWRITEBYTECODE: the image is read-only in practice, so .pyc files
# are dead weight. PYTHONUNBUFFERED: logs appear while the container runs
# rather than when it stops.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Requirements first, so a code change does not reinstall the world.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Run as nobody in particular. The app writes only to data/, and a shared
# deployment writes nothing at all.
RUN useradd --create-home --uid 10001 setu \
    && mkdir -p /app/data \
    && chown -R setu:setu /app/data
USER setu

ENV SETU_HOST=0.0.0.0 \
    SETU_PORT=5000
EXPOSE 5000

# The health endpoint answers from the filesystem and never loads a model, so
# it is honest about readiness without costing a minute of start-up.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:5000/api/health', timeout=4).status == 200 else 1)"

CMD ["python", "app.py"]
