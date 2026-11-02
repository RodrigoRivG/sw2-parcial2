#!/bin/sh
# LocalStack ejecuta este script cuando está listo: crea el bucket de evidencias de servicio-operaciones.
awslocal s3 mb "s3://${S3_BUCKET:-evidencias}" 2>/dev/null || true
