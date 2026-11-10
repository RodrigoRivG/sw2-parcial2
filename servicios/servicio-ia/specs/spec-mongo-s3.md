# Spec: Firestore → MongoDB y Cloud Storage → S3

**Motivo:** no hay cuenta de GCP. servicio-ia pasa a usar recursos que ya existen:
MongoDB (local: el `mongo` de Compose; nube: Atlas, el clúster de inventario) y S3
(local: LocalStack; nube: el bucket de operaciones).

Cambio de **infraestructura solamente**. No cambian la API, los eventos ni las reglas de
negocio. Tampoco cambian los Protocol de `app/integracion/`, los documentos (camelCase) ni
las rutas lógicas de los archivos. No se tocan las demás specs ni la Constitución.

---

## 1. Decisiones

| Tema | Decisión |
|---|---|
| Cliente Mongo | `pymongo` (`AsyncMongoClient`), con `tz_aware=True` para que las fechas vuelvan con zona horaria, como en Firestore, y `timeoutMS=5000` (equivale al `TIEMPO_LIMITE` actual). |
| Base Mongo | `MONGODB_BASE` (por defecto `ia_db`). **No** se usa la base del URI: el `MONGODB_URI` compartido apunta a `inventario_db`. |
| Colecciones | Los mismos nombres: `trabajos`, `versiones_modelo`, `predicciones`, `analisis`, `clasificaciones`. Más `publicaciones` (ver 3.2). |
| Clave | `_id` = `id` del documento (trabajos y resultados); `_id` = `"{nombre}-{version}"` en versiones. Siempre se lee con la proyección `{"_id": 0}`, así el documento devuelto es idéntico al de Firestore. |
| Cliente S3 | `boto3` síncrono dentro de `asyncio.to_thread`, igual que hoy con GCS. Sin reintentos (`retries={"max_attempts": 1}`), `connect_timeout=5` y `read_timeout=60`. |
| Bucket | `AWS_BUCKET` (el mismo nombre de variable que operaciones). Cada clave lleva el prefijo `S3_PREFIJO` (por defecto `ia/`), que agrega **el adaptador**. Las rutas guardadas en los documentos siguen sin prefijo (`modelos/...`, `reportes/...`). |
| Credenciales AWS | Las variables estándar que lee boto3: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_DEFAULT_REGION`. `AWS_ENDPOINT` es opcional: solo en local (LocalStack), y con él se usa path style. |
| Índices | Ninguno extra: el volumen es mínimo y la unicidad la da `_id`. |
| TTL y ciclo de vida | Fuera de alcance: la prueba en la nube dura de 1 a 4 días. |

## 2. Configuración (`app/config.py`)

- Eliminar `google_cloud_project` y `gcs_bucket`.
- Agregar `mongodb_uri: SecretStr`, `mongodb_base: TextoObligatorio = "ia_db"`,
  `aws_bucket: TextoObligatorio`, `aws_endpoint: str | None = None` y `s3_prefijo: str = "ia/"`.

## 3. Adaptadores (`app/integracion/`)

Cada adaptador captura `pymongo.errors.PyMongoError`, `TimeoutError` y `OSError`, y los
convierte en `ErrorInfraestructura("mongodb", tipo)`. Las fallas de S3 se convierten en
`ErrorInfraestructura("s3", tipo)`.

### 3.1 `mongodb.py` (reemplaza a `firestore.py`)

- `crear_cliente_mongo(uri) -> AsyncMongoClient`
- `comprobar_mongo(base)`: ejecuta `ping`.
- Mantener la constante `TIEMPO_LIMITE`.

### 3.2 Repositorios (renombrar `*Firestore` a `*Mongo`; reciben `AsyncDatabase`)

| Método | Implementación |
|---|---|
| `RepositorioTrabajos.guardar_nuevo` | `insert_one`. Si salta `DuplicateKeyError`, lanza `ValueError` (como `AlreadyExists` hoy). |
| `.obtener` | `find_one({"_id": id}, {"_id": 0})` |
| `.cambiar_estado` | `update_one({"_id": id, "estado": desde}, {"$set": {**cambios, "estado": hacia}})` y devuelve `matched_count == 1`. Es atómico sin transacción. |
| `.listar_vencidos` | Dos `find` con `$lt` y `limit`, igual que hoy. |
| `RepositorioVersiones.registrar_candidata` | Lee la versión máxima (`sort version -1`, `limit 1`) y hace `insert_one` con `_id` `nombre-version`. Ante `DuplicateKeyError`, vuelve a leer y reintenta (hasta 5 veces); después lanza `ErrorInfraestructura("mongodb", "contención")`. |
| `.obtener`, `.listar` y `.vigente` | Traducción directa de los filtros. `listar` conserva su orden actual en Python. |
| `.publicar` | Transacción (`start_session` + `with_transaction`). **Dentro de la transacción**, además de retirar las vigentes y marcar la candidata, hace un `update_one` con upsert en `publicaciones` (`{_id: nombre}`, `$set {version, fecha}`). Sin esa escritura común, dos publicaciones simultáneas no chocan y quedan dos `VIGENTE`, porque Mongo usa aislamiento por snapshot. Los errores de `verificar` se propagan tal cual. |
| `RepositorioResultados.guardar` | `insert_one` |
| `.obtener` | `find_one` |
| `.listar` | `count_documents(filtro)` + `find(filtro).sort("fecha", -1).skip(p*t).limit(t)` |

### 3.3 `almacen_archivos.py`

`AlmacenS3(bucket, prefijo, endpoint)` reemplaza a `AlmacenGcs`:

- `subir` usa `put_object` (con `ContentType`).
- `descargar` usa `get_object`. Si el código de `ClientError` es `NoSuchKey` o `404`, devuelve `None`.
- `borrar` usa `delete_object`; S3 no falla si el objeto no existe.

**Requisito de IAM (nube):** `s3:GetObject`, `s3:PutObject` y `s3:DeleteObject` sobre
`arn:aws:s3:::BUCKET/ia/*`, más `s3:ListBucket` sobre el bucket con la condición
`s3:prefix = ia/*`. Sin `ListBucket`, una clave inexistente responde 403 en vez de 404, y
fallan la carga del dataset (`preparar_imagenes`), los reportes y el cargador de modelos.

## 4. Puntos de uso

- `app/main.py`:
  - Crear el cliente Mongo y la base, y pasarle la base a los repositorios.
  - Usar `AlmacenS3`.
  - Componente de readiness `"mongodb"` (antes `"firestore"`), crítico.
  - Al cerrar: `await cliente.close()`.
- `app/ml/entrenar.py`, `app/ml/clasificador.py` y `app/ml/datos/preparar_imagenes.py`: el
  mismo cambio de construcción del almacén y del repositorio.
- `pyproject.toml`:
  - Quitar `google-cloud-firestore` y `google-cloud-storage`.
  - Agregar `pymongo` y `boto3`.
  - Agregar `boto3.*` y `botocore.*` a los overrides de mypy.
- Borrar `iniciar.py` y el `ENTRYPOINT` del `Dockerfile` (solo materializaba credenciales de GCP).
- Borrar `firestore.indexes.json`.

## 5. Entorno local (`docker-compose.yml`, `.env.example`)

- Eliminar los servicios `firestore`, `gcs` y `gcs-init`, y el volumen `gcs-data`.
- `localstack`: agregar `"ia"` a sus `profiles`.
- `servicio-ia`:
  - Variables:
    - `MONGODB_URI=mongodb://mongo:27017/?replicaSet=rs0`
    - `MONGODB_BASE=ia_db`
    - `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY` y `AWS_DEFAULT_REGION`, tomadas de `.env`
    - `AWS_ENDPOINT=http://localstack:4566`
    - `AWS_BUCKET=${S3_BUCKET}`
  - `depends_on`: `mongo` y `localstack` en `service_healthy`.
- `.env.example`: quitar `GCP_PROJECT_ID` y `GCS_BUCKET`.
- README raíz: actualizar las filas y notas de Firestore/GCS (tabla de perfiles, variables
  de IA, emuladores y problemas comunes).

Los modelos publicados en los emuladores se pierden: hay que entrenar y publicar de nuevo
en local, como ya pasaba tras cada reinicio.

## 6. Despliegue

- `despliegue/configuracion.py` (variables de IA):
  - Quitar `GOOGLE_CLOUD_PROJECT`, `GCS_BUCKET` y `GOOGLE_CREDENTIALS_JSON`.
  - Agregar:
    - `MONGODB_URI` como secreto (el mismo de inventario)
    - `MONGODB_BASE=ia_db`
    - `AWS_BUCKET`
    - `AWS_DEFAULT_REGION`
    - las claves AWS como secreto, como en operaciones
  - No agregar `AWS_ENDPOINT`.
- `scripts/validar-despliegue.py`: dejar de exigir `GOOGLE_CLOUD_PROJECT`, `GCS_BUCKET` y el
  archivo `GCP_IA_CREDENCIALES_ARCHIVO`.
- `.github/workflows/desplegar-azure.yml`: quitar el secret `GOOGLE_CREDENTIALS_JSON` y la
  escritura de `gcp-ia.json`.
- `.env.despliegue.example` y `despliegue/azure/README.md`: quitar la sección de Google y
  agregar la nota de IAM (3.3).
- **Atlas:** el usuario de base de datos necesita `readWrite` sobre `ia_db`, además de
  `inventario_db`.

## 7. Tests (solo adaptar; ninguno nuevo)

- `tests/conftest.py`:
  - Reemplazar los `setdefault` de los emuladores por `MONGODB_URI`, `AWS_ENDPOINT` y `AWS_BUCKET`.
  - `configuracion_de_prueba` usa los campos nuevos.
- `tests/integration/conftest.py`:
  - `proyecto_firestore` pasa a `base_mongo`: una base `pruebas-<uuid>` por test, que se borra al terminar.
  - `bucket_gcs` pasa a `prefijo_s3`: un prefijo `pruebas-<uuid>/` por test en el bucket de LocalStack, que se vacía al terminar.
  - `registrar_version` usa los adaptadores nuevos.
- Los tests que hoy leen o escriben directo en Firestore o GCS pasan a `pymongo.MongoClient`
  síncrono y `boto3`. No cambian los escenarios. Los que afirman el componente de readiness
  pasan de `"firestore"` a `"mongodb"`. Son estos:
  - `test_router_trabajos.py`
  - `test_infraestructura.py`
  - `test_router_vision.py`
  - `test_router_prediccion.py`
  - `test_versiones.py`
  - `test_salud.py`
- Renombrar `test_repositorio_trabajos_firestore.py` a `test_repositorio_trabajos_mongo.py`,
  con los mismos casos. `test_publicaciones_simultaneas_dejan_una_sola_vigente` es la prueba
  de 3.2.
- `tests/dobles.py`: solo actualizar el docstring.
- `despliegue/test_serverless.py`: ajustar las afirmaciones sobre `GOOGLE_CREDENTIALS_JSON`.
- `.github/workflows/servicio-ia.yml`:
  - `runs-on: ubuntu-22.04`, porque mongo:8.0 no arranca en el kernel de `ubuntu-latest`
    (ver `servicio-inventario.yml`).
  - Quitar los emuladores de Google.
  - Levantar `mongo:8.0 --replSet rs0` con `rs.initiate`, y `localstack` con el secreto
    `LOCALSTACK_AUTH_TOKEN`, igual que operaciones.
  - Crear el bucket de pruebas.
- La cobertura se mantiene en ≥ 80 %.

## 8. Verificación

1. `ruff check . && ruff format --check . && mypy && pytest --cov` dentro de `servicio-ia`.
2. `python3 -m unittest discover -s despliegue -p 'test_*.py'` en la raíz.
3. `docker compose --profile ia up`: readiness con `mongodb` y `rabbitmq` en `UP`; entrenar y
   publicar `rendimiento`; hacer una predicción; generar un reporte PDF.
4. `grep -rniE "firestore|gcs|google\.cloud" servicios/servicio-ia/app` no devuelve nada.
