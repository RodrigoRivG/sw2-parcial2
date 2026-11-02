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

# Librerías del sistema para OpenCV (headless) y WeasyPrint (PDF)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       libglib2.0-0 libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Usuario con UID 1000 (el mismo que tu usuario de Ubuntu) y entorno virtual
RUN useradd -m -u 1000 dev \
    && python -m venv /venv \
    && mkdir -p /cache \
    && chown -R 1000:1000 /venv /cache

USER dev
WORKDIR /app
EXPOSE 8000
