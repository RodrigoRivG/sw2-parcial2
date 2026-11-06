# Imagen de servicio-ia para Google Cloud Run (spec-base.md 2.11).
FROM python:3.12-slim

# OpenCV (headless) para leer video (spec-vision.md 2.9) y WeasyPrint para los PDF, con una
# fuente con tildes y ñ (spec-reportes.md 2.11)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libglib2.0-0 \
        libpango-1.0-0 \
        libpangoft2-1.0-0 \
        libharfbuzz0b \
        libharfbuzz-subset0 \
        fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    WHISPER_CARPETA=/modelos/whisper

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install . \
    && useradd --create-home --uid 1000 servicio

# El modelo de Whisper va en la imagen para no descargarlo en cada instancia (spec-reportes.md
# 1.7). Cambiar WHISPER_MODEL al desplegar exige reconstruir con el mismo argumento.
ARG WHISPER_MODEL=small
RUN python -c "from faster_whisper import WhisperModel; \
WhisperModel('${WHISPER_MODEL}', device='cpu', compute_type='int8', download_root='/modelos/whisper')" \
    && chown -R servicio /modelos

USER servicio

# Cloud Run define PORT (8080 por defecto)
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn --factory app.main:crear_app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]
