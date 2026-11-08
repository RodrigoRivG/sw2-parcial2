# Imagen de desarrollo para servicio-ia (FastAPI).
# El código se monta en /app. Las dependencias se instalan al arrancar desde
# pyproject.toml (pip install -e .) en un entorno virtual guardado en un volumen.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    VIRTUAL_ENV=/venv \
    PATH=/venv/bin:$PATH \
    HF_HOME=/cache/huggingface

# Librerías del sistema para OpenCV (headless) y WeasyPrint (PDF), las mismas que la imagen de producción
# (servicios/servicio-ia/Dockerfile). libharfbuzz-subset0 hace que WeasyPrint recorte las fuentes con HarfBuzz;
# sin ella usa fontTools, y el primer PDF de cada proceso bloqueaba la API unos 8 s (2026-11-08).
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libglib2.0-0 libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libharfbuzz-subset0 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Usuario con UID 1000 (el mismo que tu usuario de Ubuntu) y entorno virtual
RUN useradd -m -u 1000 dev \
    && python -m venv /venv \
    && mkdir -p /cache \
    && chown -R 1000:1000 /venv /cache

USER dev
WORKDIR /app
EXPOSE 8000
