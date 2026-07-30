# AquaMind AI — FastAPI backend
#
# IMPORTANT — trained model artifacts (ai/*.pkl) are gitignored (the
# groundwater model alone was ~2GB before hyperparameter tuning brought it
# to ~145MB — still too large/volatile for a Docker image layer to be a
# good place for them). This image does NOT bake in .pkl files. Provide
# them one of two ways before the container starts serving:
#   1. Mount a volume containing pre-trained ai/*.pkl + *.metadata.json
#      over /app/ai at runtime (recommended — see docker-compose.yml), or
#   2. Run `py ai/train.py` once against a container/volume that has the
#      Aqua Dataset available, then persist the resulting ai/ directory.
# Without either, prediction endpoints raise a clear "retrain with
# `py ai\train.py`" error rather than silently failing.

FROM python:3.11-slim AS runtime
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY fastapi_app/requirements.txt ./fastapi_app/requirements.txt
COPY ai/requirements.txt ./ai/requirements.txt
RUN pip install --no-cache-dir -r fastapi_app/requirements.txt \
    && pip install --no-cache-dir -r ai/requirements.txt

COPY ai ./ai
COPY climate ./climate
COPY data ./data
COPY fastapi_app ./fastapi_app
COPY scripts ./scripts

ENV AQUAMIND_ENVIRONMENT=production
ENV PYTHONUNBUFFERED=1
EXPOSE 8000

# No --reload in production; workers scale via WEB_CONCURRENCY if needed.
CMD ["uvicorn", "fastapi_app.main:app", "--host", "0.0.0.0", "--port", "8000"]
