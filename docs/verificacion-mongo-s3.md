# Verificación de IA con MongoDB y S3

Fecha: 2026-11-10. Referencia: `servicios/servicio-ia/specs/spec-mongo-s3.md`.

IA selecciona `ia_db` aunque la URI compartida apunte a `inventario_db`.
El adaptador S3 agrega `ia/`; los documentos mantienen las rutas lógicas anteriores.
Se sustituyeron los adaptadores, la configuración, los comandos de entrenamiento,
Compose y los pipelines de IA y Azure. Firebase de n8n permanece.
No se modificaron las otras specs ni la Constitución; la spec de migración delimita
esta entrega y deja TTL y ciclo de vida fuera de alcance.

## Comprobaciones realizadas

- Ruff y formato: correctos. Mypy: sin errores en 82 archivos.
- Suite completa existente, adaptada: **433 pruebas correctas**, cobertura **96,55 %**.
  Incluye trabajos duplicados, publicación concurrente, reglas de métricas,
  exportaciones Keras/TFLite/TF.js, reportes, permisos y errores HTTP.
- Configuración de despliegue: **7 pruebas correctas** (valores ficticios, sin aplicar Azure).
- YAML de Compose y los dos workflows válido; `git diff --check` correcto.
- No hay referencias a Firestore, GCS o `google.cloud` en `servicio-ia/app`.
- API local: readiness `UP`, `mongodb` y `rabbitmq` `UP`; Whisper `UP`.
- CLI local: entrenamiento de rendimiento sobre 485 filas ERS, registro de candidata
  versión 1 en MongoDB y artefactos en LocalStack. MAE 641,55; R² 0,9146.
- Humo HTTP mediante TestClient con el almacenamiento local real: publicación del modelo
  entrenado por CLI, carga, predicción 201, reporte asíncrono completado y PDF descargable.
  Las claves de autenticación y los datos de los demás microservicios fueron simulados;
  esto no verifica el Gateway o Keycloak reales ni constituye entrenamiento en la nube.

Se reutilizaron las imágenes existentes. Se iniciaron MongoDB, RabbitMQ, LocalStack
y servicio-ia. No se construyeron imágenes de producción. Se instalaron pymongo y
boto3 en el volumen Python de desarrollo existente.

## Comprobación cloud y pendiente externo

La cuenta existente de Atlas permite conexión, lectura y actualización en `ia_db`
(se verificó un filtro inexistente sin upsert, sin modificar documentos).
Tras agregar la política IAM, S3 permite escritura, lectura y eliminación bajo
`ia/`. Se verificó con un archivo temporal que fue eliminado. La lectura de un
objeto inexistente devuelve la ausencia esperada (`None` en el adaptador).
La política privada está en `despliegue/generado/iam-ia-s3.json`; la plantilla
está en `despliegue/azure/README.md`. El cambio IAM lo aplicó el usuario.

No se desplegó Azure ni se entrenaron modelos en la nube. El entrenamiento de producción
sigue pendiente; la imagen incluye los datasets/manifiestos versionados para los comandos.
Ollama/Qwen permanecen locales; su conexión se resolverá al final.
