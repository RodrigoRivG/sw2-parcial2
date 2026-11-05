# Imagen de servicio-ia para Google Cloud Run (spec-base.md 2.11).
# Las librerías del sistema de OpenCV y WeasyPrint se agregan en las specs que las usan.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY pyproject.toml ./
COPY app ./app
RUN pip install . \
    && useradd --create-home --uid 1000 servicio

USER servicio

# Cloud Run define PORT (8080 por defecto)
EXPOSE 8080
CMD ["sh", "-c", "exec uvicorn --factory app.main:crear_app --host 0.0.0.0 --port ${PORT:-8080} --no-access-log"]
