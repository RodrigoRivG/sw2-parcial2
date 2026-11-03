# Incidencias — `servicio-operaciones`

| Campo | Valor |
|---|---|
| Servicio | `servicio-operaciones` |
| Archivo | `specs/spec-incidencias.md` |
| Estado | Spec en borrador (2026-11-02) |
| Constitución | v2.8.0 (secciones 1, 4, 5, 7 y 10) |
| Trazabilidad | CU-11 (prioridad media; incluye CU-22 de n8n) · RF-12, RF-14 (y RF-31 de n8n; RF-20 y RF-21 como soporte) · RN-10, RN-13, RN-15 · RNF-05, RNF-08, RNF-09 |
| Depende de | `spec-labores.md` (Fase 0), `spec-saga.md` (conexión y publicador de RabbitMQ) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## Contexto

El técnico de campo registra lo que observa en una parcela (plaga, enfermedad, daño u otro) con una fotografía. Puede haber clasificado la foto antes, en el dispositivo (TensorFlow Lite o TensorFlow.js) o con `servicio-ia`; este servicio **solo guarda** ese resultado, como orientativo (RN-13). La foto va a un bucket S3 privado; DynamoDB guarda su clave (constitución §4). Al registrar, se publica un evento para que n8n notifique por correo según el tipo (RF-31).

```text
POST /incidencias (multipart: datos + foto) ─▶ S3 (foto) ─▶ DynamoDB (incidencia) ─▶ exchange "eventos"
                                                                                       operaciones.incidencia.registrada ─▶ n8n
```

## Escenarios de usuario y pruebas

### Historia 1 — Registrar una incidencia con fotografía (Prioridad: P1)

Como técnico de campo, quiero registrar una plaga con su foto, para que quede documentada y el administrador se entere.

**Por qué esta prioridad:** es el núcleo de CU-11.

**Prueba independiente:** con LocalStack y DynamoDB Local, se registra una incidencia y se verifica el objeto, el registro y la URL de la foto.

**Escenarios de aceptación:**

1. **Dado** un técnico autenticado, **cuando** registra una incidencia `PLAGA` en la parcela P1, campaña C1, con descripción, `fechaObservacion` y una foto JPEG de 3 MB, **entonces** recibe `201` con `Location`; la foto queda en S3 con la clave `incidencias/{id}/{sha256}.jpg`; la incidencia guarda la clave (nunca una URL pública), `registradaPor` del token y `fechaRecepcion`; y se audita `REGISTRAR_INCIDENCIA`.
2. **Dado** una incidencia sin campaña, **entonces** se acepta con `idCampania = null` (la campaña es opcional).
3. **Dado** una foto PNG, **entonces** se acepta con la extensión `.png`.
4. **Dado** un archivo GIF, un PDF renombrado a `.jpg` o una foto de más de 10 MB, **entonces** recibe `422 FOTO_INVALIDA` y no se guarda nada (ni en S3 ni en DynamoDB).
5. **Dado** una solicitud sin foto, **entonces** recibe `400 DATOS_INVALIDOS`.
6. **Dado** `fechaObservacion` más de 5 minutos en el futuro, **entonces** recibe `422 FECHA_OBSERVACION_INVALIDA`.
7. **Dado** un usuario sin `tecnico_campo`, **entonces** recibe `403 SIN_PERMISO`.

---

### Historia 2 — Guardar la clasificación de la fotografía (Prioridad: P2)

Como técnico de campo, quiero que se guarde lo que el modelo identificó en la foto, para que el administrador lo vea como referencia (RF-20, RF-21, RN-13).

**Prueba independiente:** se registra una incidencia con y sin `clasificacion` y se consulta.

**Escenarios de aceptación:**

1. **Dado** una incidencia con `clasificacion` `{ categoria: "roya", confianza: "0.8731", versionModelo: "clasificador-1.2.0", origen: "DISPOSITIVO" }`, **entonces** se guarda tal cual y la respuesta la devuelve con `orientativa: true`.
2. **Dado** `confianza` `"1.2"` o `"-0.1"`, **entonces** recibe `422 CONFIANZA_INVALIDA`; con `0.87` como número JSON o `"0.87315"`, `400 DATOS_INVALIDOS`.
3. **Dado** una incidencia sin `clasificacion`, **entonces** se guarda con `clasificacion = null`.

---

### Historia 3 — Avisar a n8n de cada incidencia (Prioridad: P1)

Como administrador, quiero recibir un correo por cada incidencia, con prioridad según el tipo (RF-31).

**Prueba independiente:** con una cola de prueba enlazada al exchange `eventos`, se registra una incidencia y se lee el evento.

**Escenarios de aceptación:**

1. **Dado** una incidencia registrada, **entonces** se publica `IncidenciaRegistrada` con routing key `operaciones.incidencia.registrada`, `origen = servicio-operaciones`, `version = 1`, el `idCorrelacion` de la solicitud y `datos` `{ idIncidencia, tipo, descripcion, idParcela, idCampania, fechaObservacion, registradaPor: { id, nombre }, clasificacion }`.
2. **Dado** que RabbitMQ no acepta la publicación, **entonces** la incidencia queda registrada igual (`201`), con la notificación pendiente, y se registra el error en el log.
3. **Dado** una notificación pendiente de hace más de 1 minuto, **cuando** corre la tarea de republicación con RabbitMQ sano, **entonces** se publica el evento y la notificación deja de estar pendiente.
4. **Dado** una incidencia repetida (Historia 4), **entonces** no se publica un evento nuevo.

---

### Historia 4 — Reenviar una incidencia sin duplicarla (Prioridad: P1)

Como técnico con mala señal, quiero reenviar una incidencia sin que quede dos veces (RN-10).

**Escenarios de aceptación:**

1. **Dado** que la incidencia I1 (`idOperacion` = I1) ya se registró, **cuando** llega otra vez con los mismos datos y la misma foto, **entonces** responde `200` con la incidencia guardada, sin subir otra foto, sin auditar y sin evento.
2. **Dado** lo mismo con otra descripción u otra foto, **entonces** responde `409 CONFLICTO_IDEMPOTENCIA`; la foto original no cambia y la nueva no queda en S3.
3. **Dado** dos envíos simultáneos de I1 con los mismos datos, **entonces** existe una sola incidencia y un solo objeto en S3.

---

### Historia 5 — Consultar incidencias (Prioridad: P2)

Como administrador o gerente, quiero ver las incidencias por parcela o campaña con su foto; como técnico, las mías; como `servicio-ia`, n8n o GraphQL, leerlas con mi cuenta de servicio.

**Escenarios de aceptación:**

1. **Dado** incidencias de la parcela P1, **cuando** un gerente pide `?idParcela=P1&tipo=PLAGA`, **entonces** recibe las plagas de P1 ordenadas por `fechaObservacion` descendente, paginadas por cursor, cada una con `foto.url` prefirmada que vence en 10 minutos.
2. **Dado** la URL de la foto, **cuando** se abre antes de que venza, **entonces** descarga la imagen; después de vencer, S3 responde `403`.
3. **Dado** un técnico, **cuando** pide `?mias=true`, **entonces** recibe solo las que registró; con otro filtro sin `mias=true`, o el detalle de una ajena, recibe `403 SIN_PERMISO`.
4. **Dado** un listado sin `idParcela`, `idCampania` ni `mias`, **entonces** recibe `400 DATOS_INVALIDOS`.
5. **Dado** un ID inexistente, **entonces** recibe `404 INCIDENCIA_NO_ENCONTRADA`.

---

### Casos borde

- Foto con extensión `.png` y contenido JPEG: se acepta según el contenido (`image/jpeg`, `.jpg`); lo que manda es la firma del archivo.
- Foto de 0 bytes: `422 FOTO_INVALIDA`.
- S3 no responde: `500 ERROR_INTERNO` y no se guarda la incidencia; el cliente la reintenta con el mismo `idOperacion`.
- DynamoDB falla después de subir la foto: se intenta borrar el objeto; si tampoco se puede, queda huérfano bajo `incidencias/{id}/` y se registra en el log (no afecta a nadie: nada lo referencia).
- n8n recibe el evento dos veces (la tarea republica justo cuando la solicitud también lo publicó): el evento lleva `idIncidencia` para que n8n descarte duplicados; la entrega es "al menos una vez".
- `descripcion` de más de 1000 caracteres: `400 DATOS_INVALIDOS`.

## Requisitos

### Requisitos funcionales

#### Registro

- **RQ-INC-01**: El sistema debe permitir registrar una incidencia (`multipart/form-data`) con la parte `datos` (JSON) y la parte `foto` (archivo). `datos`:
  - `idOperacion`: obligatorio, UUID (es el `id`, README D-06); `fechaCreacion`: obligatoria.
  - `tipo`: obligatorio, `PLAGA` / `ENFERMEDAD` / `DANIO` / `OTRO`.
  - `descripcion`: obligatoria, de 1 a 1000 caracteres.
  - `fechaObservacion`: obligatoria, fecha y hora UTC, no más de 5 minutos en el futuro.
  - `idParcela`: obligatorio, UUID; `idCampania`: opcional, UUID.
  - `clasificacion`: opcional, `{ categoria (1 a 100 caracteres), confianza (texto decimal de 0 a 1, hasta 4 decimales), versionModelo (1 a 50 caracteres), origen (DISPOSITIVO / SERVIDOR) }`.
- **RQ-INC-02**: `foto`: obligatoria, JPEG o PNG según su firma (`FF D8 FF` o `89 50 4E 47 0D 0A 1A 0A`), de 1 byte a 10 MB; si no, `422 FOTO_INVALIDA`.
- **RQ-INC-03**: La foto se guarda en el bucket privado con la clave `incidencias/{id}/{sha256 del archivo}.{jpg|png}` y su `Content-Type`. La incidencia guarda clave, tipo de contenido y tamaño (constitución §4).
- **RQ-INC-04**: `registradaPor` se toma del token (README D-11).
- **RQ-INC-05**: Idempotencia por `idOperacion` (README D-06), con la huella de `datos` normalizado, el SHA-256 de la foto y el `sub`. Una repetición no sube la foto, no audita ni publica.
- **RQ-INC-06**: La campaña no se valida contra `servicio-gestion` (README AP-03, resuelta).

#### Evento

- **RQ-INC-07**: Tras guardar, se publica `IncidenciaRegistrada` en el exchange `eventos` con routing key `operaciones.incidencia.registrada` y los `datos` de la Historia 3 (constitución §7). El servicio no declara colas para el evento (constitución §10).
- **RQ-INC-08**: La incidencia se guarda con la notificación pendiente y se marca como notificada solo después de la confirmación del broker. Una tarea programada cada minuto republica las pendientes con más de 1 minuto desde la recepción.

#### Consultas

- **RQ-INC-09**: Listado paginado por cursor (README D-05) con filtros `idParcela`, `idCampania`, `mias`, `tipo`, `fechaDesde`, `fechaHasta` (sobre `fechaObservacion`) y `orden`; obligatorio al menos uno de `idParcela`, `idCampania` o `mias`.
- **RQ-INC-10**: Detalle por ID, o `404 INCIDENCIA_NO_ENCONTRADA`.
- **RQ-INC-11**: Cada incidencia devuelta incluye `foto` `{ url, tipoContenido, tamanio, expiraEn }`, con una URL prefirmada de 10 minutos.
- **RQ-INC-12**: Visibilidad: `administrador`, `gerencia` y `lectura_operaciones` ven todas; quien solo tiene `tecnico_campo`, las que registró (en el listado, con `mias=true`).
- **RQ-INC-13**: `clasificacion` se devuelve con `orientativa: true` (RN-13).

#### Comunes

- **RQ-INC-14**: La creación se audita con `REGISTRAR_INCIDENCIA` (README D-09). Esta versión no permite editar ni eliminar incidencias.

### Entidades clave

- **Incidencia**: `id`, `tipo`, `descripcion`, `fechaObservacion`, `idParcela`, `idCampania`, `foto` (`clave`, `tipoContenido`, `tamanio`), `clasificacion`, `registradaPor`, `fechaCreacion`, `fechaRecepcion`, `huella`, `notificacionPendiente`, `version`.
- **ClasificacionImagen** (objeto de valor): `categoria`, `confianza`, `versionModelo`, `origen` (`OrigenClasificacion`, glosario de la constitución v2.8.0).
- **TipoIncidencia**: `PLAGA` / `ENFERMEDAD` / `DANIO` / `OTRO` (glosario).

## Permisos

| Operación | Roles |
|---|---|
| Registrar | `tecnico_campo` |
| Listar y ver detalle (todas) | `administrador`, `gerencia`, `lectura_operaciones` |
| Listar y ver detalle (propias) | `tecnico_campo` |

## Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | `datos` ausente o no es JSON, campo inválido, decimal como número JSON, sin foto, listado sin filtro principal, cursor inválido |
| 404 | `INCIDENCIA_NO_ENCONTRADA` | El ID no existe |
| 409 | `CONFLICTO_IDEMPOTENCIA` | Mismo `idOperacion` con otro contenido |
| 422 | `FOTO_INVALIDA` | Formato distinto de JPEG o PNG, 0 bytes o más de 10 MB |
| 422 | `FECHA_OBSERVACION_INVALIDA` | Fecha de observación o de creación en el futuro |
| 422 | `CONFIANZA_INVALIDA` | Confianza fuera de 0 a 1 |

## Criterios de éxito

- **CE-INC-01**: Tests de idempotencia de la constitución §8 (nueva, repetida, mismo UUID con otro contenido) en verde para incidencias.
- **CE-INC-02**: Ninguna respuesta ni registro contiene una URL pública ni el binario de la foto; solo URL prefirmadas al consultar.
- **CE-INC-03**: Con RabbitMQ caído, las incidencias se registran igual y su evento se publica cuando vuelve (RNF-08).
- **CE-INC-04**: El registro con una foto de 5 MB responde en menos de 3 s, y el listado de 100 incidencias con sus URL, en menos de 3 s (RNF-05).

## Supuestos

- La clasificación online la pide el cliente a `servicio-ia` antes de registrar la incidencia; este servicio no llama a `servicio-ia` (constitución §7: una sola llamada síncrona, a gestión).
- n8n decide la prioridad del correo según `tipo` (RF-31) y usa `idIncidencia` para no repetir correos.
- Una foto de 8 MP en JPEG pesa entre 2 y 5 MB; 10 MB deja margen sin permitir originales sin comprimir.

## Aclaraciones

- **AC-01** — Resuelta (README AP-03): campaña sin validar y foto obligatoria de hasta 10 MB.
- **AC-02** — Resuelta (constitución v2.8.0): `OrigenClasificacion` y el evento `IncidenciaRegistrada` están en el glosario.

## Fuera de alcance

- Seguimiento y acciones correctivas de incidencias (constitución §1).
- Varias fotos por incidencia, videos o edición posterior de la clasificación.
- Llamar a `servicio-ia` desde este servicio.

---

# 2. Plan

Reutiliza la Fase 0 de `spec-labores.md` y la conexión de RabbitMQ de `spec-saga.md`. Es la primera funcionalidad con S3.

## 2.1 Dependencias y configuración

- Sin dependencias nuevas: S3 usa `aws/aws-sdk-php`.
- `ClienteS3`: cliente con `AWS_ENDPOINT` y `use_path_style_endpoint` para leer y escribir; un segundo cliente con `AWS_ENDPOINT_PUBLICO` (si tiene valor) solo para firmar URL, porque la firma incluye el host y `localstack:4566` no se resuelve desde el navegador (README D-16).
- `tablas.json` agrega `incidencias`.
- Los límites de PHP (`upload_max_filesize = 10M`, `post_max_size = 40M`) ya están en las imágenes desde la Fase 0.

## 2.2 Endpoints

Prefijo: `/api/operaciones/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /incidencias` (`multipart/form-data`) | `tecnico_campo` | `201` + `Location` + incidencia; `200` si se repite | 400, 401, 403, 409, 422 |
| `GET /incidencias?idParcela=&idCampania=&mias=&tipo=&fechaDesde=&fechaHasta=&orden=&limite=&cursor=` | `administrador`, `gerencia`, `lectura_operaciones`, `tecnico_campo` | `200` + página | 400, 401, 403 |
| `GET /incidencias/{id}` | Igual que el listado | `200` + incidencia | 401, 403, 404 |

**Parte `datos`:**

```json
{
  "idOperacion": "uuid",
  "fechaCreacion": "2026-11-02T10:05:00Z",
  "tipo": "PLAGA",
  "descripcion": "Manchas anaranjadas en hojas del borde norte",
  "fechaObservacion": "2026-11-02T10:00:00Z",
  "idParcela": "uuid",
  "idCampania": "uuid",
  "clasificacion": {
    "categoria": "roya",
    "confianza": "0.8731",
    "versionModelo": "clasificador-1.2.0",
    "origen": "DISPOSITIVO"
  }
}
```

**Respuesta de incidencia:**

```json
{
  "id": "uuid",
  "tipo": "PLAGA",
  "descripcion": "Manchas anaranjadas en hojas del borde norte",
  "fechaObservacion": "2026-11-02T10:00:00Z",
  "idParcela": "uuid",
  "idCampania": "uuid",
  "foto": {
    "url": "https://…/incidencias/uuid/9f2c….jpg?X-Amz-…",
    "tipoContenido": "image/jpeg",
    "tamanio": 3145728,
    "expiraEn": "2026-11-02T14:10:00Z"
  },
  "clasificacion": {
    "categoria": "roya",
    "confianza": "0.8731",
    "versionModelo": "clasificador-1.2.0",
    "origen": "DISPOSITIVO",
    "orientativa": true
  },
  "registradaPor": { "id": "sub", "nombre": "Ana Quispe" },
  "fechaCreacion": "2026-11-02T10:05:00Z",
  "fechaRecepcion": "2026-11-02T14:00:00Z"
}
```

La validación de `datos` se hace con las mismas reglas de `FormRequest` sobre el JSON decodificado (un `datos` que no es JSON → `400`). La foto se valida en el dominio (`FotoIncidencia`), que lee los primeros 8 bytes y el tamaño.

## 2.3 Modelo de datos

Tabla `incidencias` (clave `id`):

| Atributo | Tipo | Nota |
|---|---|---|
| `id`, `tipo`, `descripcion`, `id_parcela`, `id_campania` | `S` | `id_campania` ausente si no hay |
| `fecha_observacion`, `fecha_creacion_dispositivo`, `fecha_recepcion` | `S` | |
| `clave_foto`, `tipo_contenido_foto` | `S` | |
| `tamanio_foto` | `N` | |
| `clasificacion` | `M` `{ categoria, confianza, version_modelo, origen }` | `confianza` como `S` |
| `id_registrador`, `nombre_registrador` | `S` | |
| `huella` | `S` | |
| `notificacion_pendiente` | `S` = `"1"` | Solo mientras falta publicar (índice disperso) |
| `version` | `N` | |

| Índice | Partición | Orden | Patrón de acceso |
|---|---|---|---|
| `gsi_parcela` | `id_parcela` | `fecha_observacion` | Incidencias de una parcela (gerencia, IA) |
| `gsi_campania` | `id_campania` | `fecha_observacion` | Incidencias de una campaña (solo las que tienen campaña) |
| `gsi_registrador` | `id_registrador` | `fecha_observacion` | "Mis incidencias" |
| `gsi_notificacion_pendiente` | `notificacion_pendiente` | `fecha_recepcion` | Republicación del evento |

Selección de índice y filtros como en `spec-labores.md` 2.3, en el orden `idParcela`, `idCampania`, `mias`; `tipo` va en `FilterExpression`.

## 2.4 Flujo de registro

```text
1. Validar datos (FormRequest) y foto (FotoIncidencia: firma y tamaño) → 400 / 422.
2. Huella = SHA-256(datos normalizado + sha256 foto + sub).
3. ¿Existe incidencia id = idOperacion? misma huella → 200 actual; otra → 409.
4. AlmacenamientoArchivos.guardar(clave, contenido, tipo).                 ← S3 PutObject
5. UnidadTrabajo: Put incidencia (attribute_not_exists(id), notificacion_pendiente = "1") + auditoría.
     ConflictoEscritura → releer: misma huella → 200 (la clave es la misma: no hay huérfano);
                          otra → borrar el objeto subido en 4 si su clave no es la guardada → 409.
     Otro error → borrar el objeto (mejor esfuerzo) → 500.
6. PublicadorMensajes.publicarEvento("operaciones.incidencia.registrada", …)  ← PublicacionFallida: solo log
7. Si se publicó: Update REMOVE notificacion_pendiente.
8. 201 con la incidencia.
```

## 2.5 Diseño por capas

| Capa | Archivo | Responsabilidad |
|---|---|---|
| `Domain/Incident` | `Incidencia.php`, `TipoIncidencia.php`, `ClasificacionImagen.php`, `OrigenClasificacion.php`, `FotoIncidencia.php`, `RepositorioIncidencia.php` | Reglas de RQ-INC-01, RQ-INC-02 y RQ-INC-12; clave de la foto |
| `Application/Contracts` | `AlmacenamientoArchivos.php` | `guardar(clave, contenido, tipo)`, `borrar(clave)`, `urlTemporal(clave, minutos)` |
| `Application/Contracts` | `PublicadorMensajes.php` (se amplía) | `publicarEvento(routingKey, tipo, datos, idCorrelacion)` |
| `Application/UseCases/RegisterIncident` | `RegistrarIncidenciaCasoUso.php`, `RegistrarIncidenciaEntrada.php` | 2.4 |
| `Application/UseCases/RegisterIncident` | `RepublicarEventosIncidenciasCasoUso.php` | RQ-INC-08 |
| `Application/UseCases/QueryIncidents` | `ConsultarIncidenciasCasoUso.php` | Detalle, listado y URL temporales |
| `InterfaceAdapters/Http` | `IncidenciaControlador.php`, `Requests/RegistrarIncidenciaRequest.php`, `Resources/IncidenciaRecurso.php` | |
| `InterfaceAdapters/Console` | `RepublicarEventosComando.php` | `incidencias:republicar-eventos`, cada minuto con `withoutOverlapping` |
| `Infrastructure/Storage` | `AlmacenamientoArchivosS3.php` | `PutObject`, `DeleteObject`, `createPresignedRequest` con el cliente público |
| `Infrastructure/Messaging` | `PublicadorRabbitMq.php` (se amplía) | Declara el exchange `eventos` (topic, durable) y publica con confirmación |
| `Infrastructure/Persistence/DynamoDb` | `RepositorioIncidenciaDynamo.php`, `Mappers/IncidenciaMapper.php` | 2.3 |

## 2.6 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/Unit/Domain/Incident/FotoIncidenciaTest.php` | Firmas JPEG y PNG, GIF, PDF, 0 bytes, 10 MB exactos y 10 MB + 1 byte, extensión según contenido |
| Unitario | `tests/Unit/Domain/Incident/IncidenciaTest.php` | Fechas, confianza 0, 1 y fuera de rango, visibilidad |
| Unitario | `tests/Unit/Application/RegistrarIncidenciaCasoUsoTest.php` | Con dobles: repetición sin subir foto, conflicto con borrado del objeto, fallo de DynamoDB con borrado, publicación fallida |
| Integración | `tests/Integration/Http/IncidenciasTest.php` | Historias 1, 2 y 5 con LocalStack y DynamoDB Local; URL prefirmada descargable (CE-INC-02) |
| Integración | `tests/Integration/Http/IdempotenciaIncidenciasTest.php` | Historia 4, incluidos envíos simultáneos con `EnParalelo` y un solo objeto en S3 |
| Integración | `tests/Integration/Messaging/EventoIncidenciaTest.php` | Historia 3 con una cola de prueba enlazada a `eventos`; RabbitMQ inalcanzable y republicación (CE-INC-03) |
| Integración | `tests/Integration/Http/IncidenciasRendimientoTest.php` | CE-INC-04 |

Los tests usan el bucket `evidencias-pruebas` (README D-17), que crea el arranque de los tests, y cada uno usa claves bajo su propio `id`.

---

# 3. Tareas

- [ ] **T01** — Crear `Incidencia`, `TipoIncidencia`, `ClasificacionImagen`, `OrigenClasificacion` y `FotoIncidencia`, con sus tests unitarios.
- [ ] **T02** — Implementar `ClienteS3` y `AlmacenamientoArchivosS3`, y crear el bucket de pruebas en el arranque de los tests. *Hecho cuando:* un test de integración guarda, firma, descarga y borra un objeto en LocalStack.
- [ ] **T03** — Agregar `incidencias` a `tablas.json` e implementar `RepositorioIncidenciaDynamo`.
- [ ] **T04** — Implementar `RegistrarIncidenciaCasoUso` y `POST /incidencias` (sin evento). *Hecho cuando:* pasan las Historias 1, 2 y 4.
- [ ] **T05** — Ampliar `PublicadorRabbitMq` con `publicarEvento`, conectar el evento y crear `incidencias:republicar-eventos`. *Hecho cuando:* pasa `EventoIncidenciaTest.php`.
- [ ] **T06** — Implementar `ConsultarIncidenciasCasoUso` y los dos `GET`. *Hecho cuando:* pasa la Historia 5.
- [ ] **T07** [P] — Escribir `IncidenciasRendimientoTest.php` y documentar los endpoints en `openapi.yaml`.
- [ ] **T08** — Verificación final: `vendor/bin/pest --coverage --min=80` en verde y criterios CE-INC-01 a CE-INC-04 cubiertos.
