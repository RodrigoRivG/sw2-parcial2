# Trabajos asíncronos — `servicio-ia`

| Campo | Valor |
|---|---|
| Servicio | `servicio-ia` |
| Archivo | `specs/spec-trabajos.md` |
| Estado | Implementada (2026-11-05) · pipeline en GitHub pendiente de confirmar |
| Fecha | 2026-11-04 |
| Constitución | v3.0.0 (secciones 3, 4, 7, 10 y 11) |
| Trazabilidad | Soporte de CU-16 (video), CU-17, CU-18 y CU-25 · RF-22, RF-23, RF-24 · RNF-08, RNF-11, RNF-22 |
| Depende de | `spec-base.md` (seguridad, errores, correlación, salud, logs) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## 1.1 Contexto

Las consultas a agentes, los reportes y el análisis de video tardan de segundos a minutos: no caben en una solicitud HTTP. La constitución (§3 y §7) fija el mecanismo: la API crea un **trabajo**, lo encola en RabbitMQ, un consumidor lo procesa y el cliente consulta su estado por ID (RF-24, "procesándolos de forma asíncrona con polling").

Esta spec construye ese mecanismo sin ningún tipo de trabajo real. Cada spec siguiente registra el suyo:

| Tipo de trabajo | Spec que lo registra |
|---|---|
| `CLASIFICACION_VIDEO` | `spec-vision.md` |
| `CONSULTA_AGENTE` | `spec-agentes.md` |
| `REPORTE` | `spec-reportes.md` |

Flujo:

```text
Cliente ──POST /<recurso>──▶ módulo ──crear()──▶ Firestore (EN_COLA) ──▶ RabbitMQ (servicio-ia.trabajos)
                                                                              │
Cliente ──GET /trabajos/{id}──▶ Firestore ◀── PROCESANDO / COMPLETADO / FALLIDO ◀── consumidor + manejador del tipo
```

## 1.2 Escenarios de usuario y pruebas

### Historia 1 — Encolar un trabajo y consultar su resultado (Prioridad: P1)

Como usuario de gerencia (o cuenta de servicio de n8n), quiero que mi solicitud larga se acepte al instante y poder consultar su estado hasta obtener el resultado, sin que la conexión quede abierta.

**Por qué esta prioridad:** es el mecanismo de RF-24; agentes, reportes y video dependen de él.

**Prueba independiente:** con un tipo de trabajo de prueba registrado solo en los tests (por ejemplo, uno que devuelve sus parámetros después de 0,2 s), Firestore emulado y RabbitMQ de Docker Compose.

**Escenarios de aceptación:**

1. **Dado** una solicitud válida, **cuando** un módulo crea el trabajo, **entonces** el cliente recibe `202` con `idTrabajo`, `estado = EN_COLA` y el header `Location: /api/ia/v1/trabajos/{id}`, y el trabajo queda guardado antes de encolarse.
2. **Dado** un trabajo encolado, **cuando** el consumidor lo toma, **entonces** pasa a `PROCESANDO` con `fechaInicio`, y al terminar a `COMPLETADO` con `resultado` y `fechaFin`.
3. **Dado** un trabajo `EN_COLA` o `PROCESANDO`, **cuando** el solicitante consulta `GET /trabajos/{id}`, **entonces** recibe `200` con el estado y el header `Retry-After: 2`; sin `resultado` ni `error`.
4. **Dado** un trabajo `COMPLETADO`, **entonces** la consulta devuelve `resultado`; **dado** uno `FALLIDO`, devuelve `error` con `codigo` y `mensaje`.
5. **Dado** un trabajo de otro usuario, o un ID inexistente o mal formado, **entonces** `404 TRABAJO_NO_ENCONTRADO` (no se revela que existe).
6. **Dado** cualquier trabajo, **entonces** guarda y devuelve el `idCorrelacion` de la solicitud que lo creó, y los logs del consumidor y las consultas a otros servicios hechas al procesarlo usan ese mismo id (RNF-22).

---

### Historia 2 — Terminar con un error claro, nunca colgado (Prioridad: P1)

Como solicitante, quiero que todo trabajo termine en `COMPLETADO` o `FALLIDO` en un tiempo acotado, aunque el manejador falle, se pase de tiempo o el proceso se reinicie (constitución §6: "el trabajo termina con error explicado, no queda colgado").

**Prueba independiente:** con tipos de prueba que fallan, tardan más que su límite o nunca se procesan.

**Escenarios de aceptación:**

1. **Dado** un manejador que lanza un error esperado (por ejemplo, `MODELO_LENGUAJE_NO_DISPONIBLE`), **entonces** el trabajo queda `FALLIDO` con ese `codigo` y su `mensaje`.
2. **Dado** un manejador que lanza un error inesperado, **entonces** queda `FALLIDO` con `ERROR_INTERNO`, sin la traza en el `error`; la traza va al log con el `idCorrelacion`. No se reintenta.
3. **Dado** un manejador que supera el tiempo límite de su tipo, **entonces** queda `FALLIDO` con `TIEMPO_AGOTADO`; si el manejador termina después, su resultado se descarta.
4. **Dado** un trabajo `PROCESANDO` cuyo proceso se detuvo (reinicio, despliegue), **cuando** pasa su `fechaLimite`, **entonces** la revisión periódica lo marca `FALLIDO` con `TIEMPO_AGOTADO`.
5. **Dado** un trabajo que sigue `EN_COLA` 10 minutos después de creado (el mensaje se perdió o fue a la DLQ), **entonces** la revisión periódica lo marca `FALLIDO` con `TRABAJO_NO_PROCESADO`.
6. **Dado** un trabajo en `COMPLETADO` o `FALLIDO`, **entonces** ningún proceso puede cambiar su estado (estados terminales).

---

### Historia 3 — Procesar cada trabajo una sola vez (Prioridad: P1)

Como responsable del sistema, quiero que un mensaje duplicado o reentregado no procese dos veces el mismo trabajo (constitución §10: consumidores idempotentes).

**Escenarios de aceptación:**

1. **Dado** dos mensajes con el mismo `idTrabajo` entregados a la vez a dos consumidores, **entonces** solo uno lo pasa a `PROCESANDO` y ejecuta el manejador; el otro confirma el mensaje sin hacer nada.
2. **Dado** un mensaje de un trabajo que ya no está `EN_COLA`, **entonces** se confirma sin hacer nada.
3. **Dado** un mensaje cuyo `idTrabajo` no existe o cuyo sobre no se puede interpretar, **entonces** se registra el error y el mensaje va a la DLQ, no se descarta en silencio.

---

### Historia 4 — No perder mensajes si falla la infraestructura (Prioridad: P1)

Como responsable del sistema, quiero que una falla pasajera de Firestore al tomar un trabajo se reintente y, si persiste, el mensaje quede en una Dead Letter Queue (RNF-11).

**Escenarios de aceptación:**

1. **Dado** que Firestore falla al leer o actualizar el trabajo, **entonces** el consumidor reintenta 3 veces con espera de 1 s, 2 s y 4 s; si sigue fallando, hace `nack` sin reencolar y el mensaje va a `servicio-ia.trabajos.dlq`.
2. **Dado** que RabbitMQ no está disponible al crear el trabajo, **entonces** el cliente recibe `503 DEPENDENCIA_NO_DISPONIBLE` y el trabajo queda `FALLIDO` con `COLA_NO_DISPONIBLE` (si Firestore responde).
3. **Dado** que Firestore no está disponible al crear o consultar un trabajo, **entonces** `503 DEPENDENCIA_NO_DISPONIBLE`.
4. **Dado** que RabbitMQ se cae y vuelve, **entonces** el consumidor se reconecta solo y sigue procesando.
5. **Dado** que Firestore o RabbitMQ no responden, **entonces** `/salud/readiness` responde `503` con el componente en `DOWN`. Predicción y clasificación de imágenes, que no usan trabajos, siguen atendiendo (RNF-08).

### Casos borde

- **El manejador devuelve un resultado muy grande:** el resultado se guarda en el documento del trabajo, que en Firestore tiene un límite de 1 MiB. Un resultado de más de 100 KB al serializarse deja el trabajo `FALLIDO` con `ERROR_INTERNO` y un log de error: los manejadores con salidas grandes (reportes) guardan el archivo en Cloud Storage y devuelven solo su referencia.
- **Muchos trabajos a la vez:** el consumidor procesa como máximo `TRABAJOS_CONCURRENCIA` en paralelo; los demás esperan en la cola, en `EN_COLA`.
- **El proceso se apaga con un trabajo en curso:** el mensaje ya se confirmó al pasar a `PROCESANDO` (el estado está en Firestore), así que no se reentrega; la revisión periódica lo cierra como en la Historia 2, escenario 4.
- **Revisión periódica en varias instancias:** dos instancias pueden revisar a la vez; las transiciones son condicionales, así que un trabajo se cierra una sola vez.
- **Reloj:** todas las fechas en UTC, generadas por este servicio.

## 1.3 Requisitos

### Requisitos funcionales

- **RQ-TRA-01:** ofrecer a los módulos una operación `crear(tipo, parametros, solicitante)` que guarde el trabajo en `EN_COLA`, publique su mensaje y devuelva el trabajo; y un helper que arme la respuesta `202` con `Location`.
- **RQ-TRA-02:** mantener un registro de tipos de trabajo, cada uno con su manejador y su tiempo límite. Crear un trabajo de un tipo no registrado es un error de programación (excepción al arrancar o al crear, nunca un trabajo huérfano).
- **RQ-TRA-03:** procesar los mensajes de `servicio-ia.trabajos` con las transiciones `EN_COLA → PROCESANDO → COMPLETADO | FALLIDO` y `EN_COLA → FALLIDO`, todas condicionales al estado actual.
- **RQ-TRA-04:** aplicar el tiempo límite del tipo y la revisión periódica de la Historia 2.
- **RQ-TRA-05:** exponer `GET /api/ia/v1/trabajos/{id}` solo al solicitante.
- **RQ-TRA-06:** propagar el `idCorrelacion` de la solicitud al trabajo, al mensaje y al contexto del manejador.
- **RQ-TRA-07:** reintentos e infraestructura de mensajes según la constitución §10 y README D-15.
- **RQ-TRA-08:** registrar Firestore y RabbitMQ como comprobaciones críticas de readiness.
- **RQ-TRA-09:** borrar los trabajos `TRABAJOS_RETENCION_DIAS` días después de terminar (por defecto 30), con la política TTL de Firestore sobre `fechaExpiracion`.

### Entidades clave

**Trabajo** (colección `trabajos`, documento con ID = `id`):

| Campo | Tipo | Descripción |
|---|---|---|
| `id` | UUID | Generado al crear |
| `tipo` | `TipoTrabajo` | `CLASIFICACION_VIDEO`, `CONSULTA_AGENTE`, `REPORTE` (cada spec agrega el suyo) |
| `estado` | `EstadoTrabajo` | `EN_COLA`, `PROCESANDO`, `COMPLETADO`, `FALLIDO` |
| `idSolicitante` | texto | `sub` del token que lo creó |
| `idCorrelacion` | texto | De la solicitud que lo creó |
| `parametros` | mapa | Entrada ya validada por el esquema del módulo |
| `resultado` | mapa o nulo | Solo en `COMPLETADO` |
| `error` | `{ codigo, mensaje }` o nulo | Solo en `FALLIDO` |
| `fechaCreacion`, `fechaInicio`, `fechaFin` | fecha y hora UTC | `fechaInicio` al pasar a `PROCESANDO`; `fechaFin` al terminar |
| `fechaLimite` | fecha y hora UTC | `fechaInicio` + tiempo límite del tipo + 30 s de margen |
| `fechaExpiracion` | fecha y hora UTC | `fechaFin` + retención; nula mientras no termina |

No se guarda el nombre del solicitante ni su token.

## 1.4 Permisos

| Operación | Acceso |
|---|---|
| `GET /trabajos/{id}` | Cualquier token válido; solo ve sus propios trabajos (`idSolicitante = sub`) |
| Crear trabajos | No hay endpoint propio: lo hace cada módulo con los permisos de su spec (constitución §9) |

## 1.5 Errores de esta funcionalidad

**Respuestas HTTP:**

| HTTP | Código | Cuándo |
|---|---|---|
| 401 | `NO_AUTENTICADO` | Sin token o token inválido |
| 404 | `TRABAJO_NO_ENCONTRADO` | El trabajo no existe, el ID no es un UUID o es de otro solicitante. Mensaje: "El trabajo solicitado no existe." |
| 503 | `DEPENDENCIA_NO_DISPONIBLE` | Firestore o RabbitMQ no disponibles al crear o consultar |

**Códigos en el campo `error` de un trabajo `FALLIDO`** (no son HTTP):

| Código | Mensaje | Cuándo |
|---|---|---|
| `TIEMPO_AGOTADO` | "El trabajo superó el tiempo máximo de procesamiento." | Historia 2, escenarios 3 y 4 |
| `TRABAJO_NO_PROCESADO` | "El trabajo no pudo procesarse. Intente nuevamente." | Historia 2, escenario 5 |
| `COLA_NO_DISPONIBLE` | "El trabajo no pudo encolarse. Intente nuevamente." | Historia 4, escenario 2 |
| `ERROR_INTERNO` | "Ocurrió un error inesperado." | Historia 2, escenario 2; resultado demasiado grande |
| Los de cada manejador | Definidos en su spec | Historia 2, escenario 1 |

## 1.6 Criterios de éxito

- **CE-TRA-01:** los escenarios de las historias 1 a 4 pasan como tests automáticos con el emulador de Firestore y RabbitMQ.
- **CE-TRA-02:** un trabajo de prueba de 0,2 s pasa de `EN_COLA` a `COMPLETADO` en menos de 2 s con la cola vacía.
- **CE-TRA-03:** la creación de un trabajo (guardar y publicar) responde en menos de 500 ms (p95 en 50 creaciones seguidas, en local).
- **CE-TRA-04:** con 20 mensajes duplicados del mismo trabajo, el manejador se ejecuta exactamente una vez.
- **CE-TRA-05:** cobertura ≥ 80 % (README D-13), Ruff y mypy sin errores, pipeline en verde.

## 1.7 Supuestos

- En la nube, Cloud Run corre con al menos una instancia y la CPU siempre asignada, para que el consumidor siga escuchando la cola sin solicitudes HTTP. Se documenta en el despliegue; no cambia el código.
- El emulador de Firestore no aplica políticas TTL: en local los trabajos no se borran solos. La política se crea en GCP sobre `trabajos.fechaExpiracion`.
- RabbitMQ es el broker del sistema (Docker Compose en local, Amazon MQ en la nube, con AMQPS).

## 1.8 Aclaraciones

- **AC-01 — ¿Por qué el consumidor corre en el mismo proceso que la API?** Los manejadores necesitan los mismos modelos cargados que la API (MobileNetV3 para el video, por ejemplo). Un proceso aparte los cargaría dos veces y duplicaría la memoria, en local (`mem_limit: 3g`) y en Cloud Run. Se puede desactivar con `TRABAJOS_CONSUMIDOR_ACTIVO=false` (los tests de la API lo usan).
- **AC-02 — ¿Por qué no se reintenta un manejador que falla?** Un fallo del manejador es del trabajo, no del mensaje (un modelo de lenguaje caído, un dato inexistente). Reintentarlo alargaría la espera del usuario y, en reportes, repetiría consultas. El usuario puede volver a pedirlo. Los reintentos de la constitución §10 se aplican a la infraestructura del mensaje (Historia 4).
- **AC-03 — ¿Por qué la idempotencia es por estado y no por `idMensaje`?** La transición condicional `EN_COLA → PROCESANDO` ya garantiza una sola ejecución por trabajo, aunque lleguen mensajes distintos para el mismo `idTrabajo` (por ejemplo, uno republicado a mano desde la DLQ). Cumple la constitución §10 sin una colección extra de mensajes procesados.
- **AC-04 — ¿Por qué no se republican los trabajos `EN_COLA` atascados?** Republicar exigiría contar intentos para no repetir sin fin. Con un solo intento y el cierre a los 10 minutos, el comportamiento es simple y el usuario recibe un error claro.
- **AC-05 — ¿Por qué no hay listado de trabajos?** Ningún caso de uso lo pide todavía. Si `spec-reportes.md` necesita un historial de reportes, lo agrega.

## 1.9 Fuera de alcance

- Cancelar un trabajo en curso.
- Prioridades entre tipos de trabajo.
- Publicar eventos al terminar un trabajo (`ia.reporte.completado` lo agrega `spec-reportes.md`).
- Listar trabajos.

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución. Reutiliza la base (`spec-base.md`).

**Documentos que debe tener a mano quien implemente:** la constitución, `specs/README.md`, `spec-base.md` y este archivo.

## 2.1 Dependencias

| Dependencia | Para qué |
|---|---|
| `google-cloud-firestore` | Repositorio de trabajos (`AsyncClient`, transacciones). Usa el emulador si existe `FIRESTORE_EMULATOR_HOST` |
| `aio-pika` | Publicación y consumo en RabbitMQ con reconexión automática (`connect_robust`), compatible con asyncio |

## 2.2 Configuración

Se agregan a `Configuracion`:

| Variable | Obligatoria | Uso | Valor local |
|---|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | Sí | Proyecto de Firestore | Ya en Docker Compose |
| `FIRESTORE_EMULATOR_HOST` | No | Lo lee la librería; vacío en la nube | Ya en Docker Compose |
| `RABBITMQ_URL` | Sí | `amqp://` en local, `amqps://` en la nube (constitución §10) | Ya en Docker Compose |
| `TRABAJOS_COLA` | No (`servicio-ia.trabajos`) | Nombre de la cola; los tests usan uno propio | — |
| `TRABAJOS_CONCURRENCIA` | No (2) | `prefetch_count` del consumidor | — |
| `TRABAJOS_CONSUMIDOR_ACTIVO` | No (`true`) | Arranca o no el consumidor y la revisión periódica | — |
| `TRABAJOS_RETENCION_DIAS` | No (30) | Cálculo de `fechaExpiracion` | — |

## 2.3 Estructura

```text
app/
├── integracion/
│   ├── firestore.py          # cliente AsyncClient compartido
│   ├── rabbitmq.py           # conexión robusta, canal, declaración de colas, publicar()
│   └── repositorio_trabajos.py  # Protocol RepositorioTrabajos + RepositorioTrabajosFirestore
└── trabajos/
    ├── esquemas.py           # Trabajo, ErrorTrabajo, RespuestaTrabajo, RespuestaTrabajoCreado
    ├── estados.py            # EstadoTrabajo, TipoTrabajo, transiciones (funciones puras)
    ├── registro.py           # RegistroTipos, DefinicionTipo, Manejador (Protocol del manejador)
    ├── servicio.py           # ServicioTrabajos: crear(), obtener_para()
    ├── consumidor.py         # ConsumidorTrabajos: procesar mensaje, tiempo límite, reintentos
    ├── revision.py           # revisar_vencidos(): cierre de atascados
    └── router.py             # GET /trabajos/{id}
```

`trabajos/registro.py` define el `Protocol` del manejador: no es un borde externo, es el contrato que implementan los módulos (constitución §3 permite a todos usar `trabajos`).

## 2.4 Reglas puras (`trabajos/estados.py`)

- `TRANSICIONES = { EN_COLA: {PROCESANDO, FALLIDO}, PROCESANDO: {COMPLETADO, FALLIDO}, COMPLETADO: ∅, FALLIDO: ∅ }`.
- `puede_pasar(desde, hacia) -> bool`.
- `calcular_fecha_limite(fecha_inicio, tiempo_limite)`: suma 30 s de margen.
- `esta_vencido(trabajo, ahora) -> bool`: `PROCESANDO` con `fechaLimite < ahora`, o `EN_COLA` con `fechaCreacion < ahora - 10 min`.
- `calcular_fecha_expiracion(fecha_fin, dias)`.

## 2.5 Repositorio (`integracion/repositorio_trabajos.py`)

`Protocol RepositorioTrabajos`:

| Método | Comportamiento |
|---|---|
| `guardar_nuevo(trabajo)` | `create()` del documento (falla si el ID existe) |
| `obtener(id) -> Trabajo \| None` | Lectura simple |
| `cambiar_estado(id, desde, hacia, cambios) -> bool` | Transacción: lee, verifica `estado == desde` y `puede_pasar`, aplica `cambios` (fechas, resultado, error); devuelve `False` si el estado no coincide |
| `listar_vencidos(ahora, limite=100) -> list[Trabajo]` | Dos consultas: `estado == PROCESANDO and fechaLimite < ahora`; `estado == EN_COLA and fechaCreacion < ahora - 10 min` |

- `RepositorioTrabajosFirestore` lo implementa con `firestore.AsyncClient`. Documentos en camelCase (como los JSON del sistema). Fechas como `Timestamp` de Firestore. Excepciones de `google.api_core` → `ErrorInfraestructura` (propia de `integracion`), que el consumidor reintenta y la API traduce a `503 DEPENDENCIA_NO_DISPONIBLE`.
  - Todas las llamadas van con `retry=None` y tiempo límite de 5 s: con los reintentos internos del cliente, un Firestore caído tarda cerca de un minuto en fallar. Los reintentos los hace el consumidor (1 s, 2 s, 4 s).
  - Si la transacción agota sus intentos por contención (la librería lanza `ValueError`), también es `ErrorInfraestructura`: el consumidor reintenta y ve el estado ya cambiado.
  - El Protocol trabaja con documentos (diccionarios en camelCase) y `trabajos/` los convierte en `Trabajo`, para que `integracion` no importe un módulo de capacidad (constitución §3).
- Índices compuestos (`estado` + `fechaLimite`, `estado` + `fechaCreacion`): el emulador no los exige; para GCP se versionan en `firestore.indexes.json` en la raíz del servicio, junto con la política TTL de `fechaExpiracion` documentada.
- `RepositorioTrabajosMemoria` en `tests/` (doble de pruebas para los tests unitarios de `ServicioTrabajos`, el consumidor y la revisión).

## 2.6 Mensajería (`integracion/rabbitmq.py`)

- `ConexionRabbitMq`: conexión robusta de `aio_pika` iniciada en segundo plano desde el `lifespan`, con un reintento cada 5 s si RabbitMQ no está: el servicio arranca igual, con `rabbitmq` en `DOWN` en readiness (RNF-08). Un canal para publicar (con confirmaciones del broker) y otro para consumir. Se crea el `RobustConnection` y se llama a `connect()` por separado (no `connect_robust`), porque `connect_robust` deja viva su tarea interna de reconexión si se cancela a mitad de un intento, y el proceso no termina al apagarse.
- Declaración idempotente al arrancar (README D-15):
  - `servicio-ia.trabajos`: durable, `x-dead-letter-exchange: ""`, `x-dead-letter-routing-key: servicio-ia.trabajos.dlq`.
  - `servicio-ia.trabajos.dlq`: durable, sin argumentos.
- `publicar(cola, sobre)`: mensaje persistente (`delivery_mode=2`), `content_type=application/json`, `message_id = idMensaje`, `correlation_id = idCorrelacion`, por el exchange por defecto. Espera la confirmación del broker (tiempo límite 3 s).
- Sobre del mensaje (constitución §10):

  ```json
  {
    "idMensaje": "uuid",
    "idCorrelacion": "uuid",
    "tipo": "ProcesarTrabajo",
    "version": 1,
    "fechaOcurrencia": "2026-11-04T12:00:00Z",
    "origen": "servicio-ia",
    "datos": { "idTrabajo": "uuid" }
  }
  ```

  Solo viaja el ID: los parámetros ya están en Firestore.

## 2.7 Registro de tipos (`trabajos/registro.py`)

- `Manejador` (`Protocol`): `async def __call__(self, trabajo: Trabajo) -> dict[str, Any]`. Los errores esperados se lanzan como `ErrorAplicacion` (de `comun/errores.py`): su `codigo` y `mensaje` van al `error` del trabajo.
- `DefinicionTipo`: `tipo`, `manejador`, `tiempo_limite: timedelta`.
- `RegistroTipos` (en `app.state`): `registrar(definicion)` (falla si el tipo ya está), `obtener(tipo)` (falla si no está). Cada spec registra su tipo en `crear_app()`.

## 2.8 Servicio (`trabajos/servicio.py`)

- `crear(tipo, parametros, solicitante) -> Trabajo`:
  1. Verifica que el tipo esté registrado.
  2. Arma el trabajo `EN_COLA` con `id = uuid4()`, `idSolicitante = solicitante.id` e `idCorrelacion` del contexto.
  3. `guardar_nuevo()`. Si falla → `503 DEPENDENCIA_NO_DISPONIBLE`.
  4. Publica el sobre. Si falla → `cambiar_estado(EN_COLA → FALLIDO, error COLA_NO_DISPONIBLE)` y `503 DEPENDENCIA_NO_DISPONIBLE`.
- `obtener_para(id, solicitante) -> Trabajo`: ID no UUID, inexistente o de otro `idSolicitante` → `404 TRABAJO_NO_ENCONTRADO`.
- `respuesta_creado(trabajo) -> JSONResponse`: `202`, cuerpo `{ idTrabajo, estado, fechaCreacion }` y `Location`.

## 2.9 Consumidor (`trabajos/consumidor.py`)

Arranca en el `lifespan` si `TRABAJOS_CONSUMIDOR_ACTIVO`, con `prefetch_count = TRABAJOS_CONCURRENCIA`. Por cada mensaje:

1. Interpreta el sobre y valida `datos.idTrabajo`. Si no se puede → log `ERROR` y `nack(requeue=False)` (DLQ).
2. Pone `idCorrelacion` del sobre en el contexto (`comun/correlacion.py`).
3. Lee el trabajo. Inexistente → log `ERROR` y DLQ. No `EN_COLA` → `ack` (Historia 3).
4. `cambiar_estado(EN_COLA → PROCESANDO, fechaInicio, fechaLimite)`. `False` → `ack` (otro consumidor lo tomó).
5. `ack` del mensaje: desde aquí el estado vive en Firestore.
6. Ejecuta el manejador con `asyncio.wait_for(tiempo_limite)`. Los manejadores que hacen trabajo de CPU (modelos, PDF) lo pasan a un hilo con `asyncio.to_thread`; el hilo no se puede cancelar, pero su resultado se descarta porque el trabajo ya no está `PROCESANDO`.
7. Resultado:
   - éxito y tamaño ≤ 100 KB → `PROCESANDO → COMPLETADO` con `resultado`, `fechaFin`, `fechaExpiracion`;
   - `ErrorAplicacion` → `FALLIDO` con su `codigo` y `mensaje`;
   - `TimeoutError` → `FALLIDO` con `TIEMPO_AGOTADO`;
   - otra excepción o resultado demasiado grande → `FALLIDO` con `ERROR_INTERNO` y `logger.exception`.
8. Log `INFO` "trabajo terminado" con `idTrabajo`, `tipo`, `estado`, `duracionMs` y, si falló, `codigo`.

Pasos 3 y 4 con `ErrorInfraestructura`: 3 reintentos con 1 s, 2 s y 4 s; agotados → `nack(requeue=False)` (README D-15). Una falla de Firestore en el paso 7 se reintenta igual; si se agota, el trabajo queda `PROCESANDO` y lo cierra la revisión periódica.

## 2.10 Revisión periódica (`trabajos/revision.py`)

Tarea de fondo en el `lifespan` (con el consumidor): cada 60 s, `listar_vencidos(ahora)` y, por cada uno, `cambiar_estado` a `FALLIDO` con `TIEMPO_AGOTADO` (`PROCESANDO`) o `TRABAJO_NO_PROCESADO` (`EN_COLA`). Un `False` se ignora (otro proceso lo cerró). Un error de Firestore se registra y se reintenta en la siguiente vuelta.

## 2.11 Endpoint

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `GET /api/ia/v1/trabajos/{id}` | Cualquier token válido (solo el solicitante) | `200` + trabajo; `Retry-After: 2` si `EN_COLA` o `PROCESANDO` | 401, 404 `TRABAJO_NO_ENCONTRADO`, 503 `DEPENDENCIA_NO_DISPONIBLE` |

```json
{
  "idTrabajo": "uuid",
  "tipo": "REPORTE",
  "estado": "COMPLETADO",
  "fechaCreacion": "2026-11-04T12:00:00Z",
  "fechaInicio": "2026-11-04T12:00:01Z",
  "fechaFin": "2026-11-04T12:00:09Z",
  "idCorrelacion": "uuid",
  "resultado": { },
  "error": null
}
```

`resultado` lo define el esquema de cada tipo en su spec; aquí es un objeto JSON. No se devuelven `parametros`, `idSolicitante` ni `fechaLimite`.

## 2.12 Salud

En `crear_app()` se registran como comprobaciones críticas (`spec-base.md` 2.8):

- `firestore`: lectura de `trabajos` con `limit(1)`.
- `rabbitmq`: la conexión robusta está abierta y el canal de publicación responde.

## 2.13 Entorno local y pipeline

- **`docker-compose.yml`** (`servicio-ia`): sin variables nuevas obligatorias (ya están `GOOGLE_CLOUD_PROJECT`, `FIRESTORE_EMULATOR_HOST` y `RABBITMQ_URL`). `depends_on.firestore` ya existe.
- **Tests locales:** se ejecutan dentro del contenedor (`docker compose exec servicio-ia pytest`), donde `firestore` y `rabbitmq` resuelven.
- **`.github/workflows/servicio-ia.yml`:** agrega el contenedor de servicio `rabbitmq:4-management-alpine` (mismo que Docker Compose) y un paso que levanta el emulador de Firestore con `docker run -d` y la imagen de Docker Compose (los contenedores de servicio de GitHub Actions no aceptan `command`), esperando a que el puerto responda. Variables: `FIRESTORE_EMULATOR_HOST=localhost:8080`, `GOOGLE_CLOUD_PROJECT=sw2-ci`, `RABBITMQ_URL=amqp://sw2:sw2pass@localhost:5672`.
- **Aislamiento de tests (README D-12):** cada sesión de tests usa un proyecto de Firestore propio (`pruebas-<aleatorio>`; el emulador acepta cualquiera y los separa) y colas propias (`pruebas-<aleatorio>.servicio-ia.trabajos` y su DLQ), que borra al terminar. Así no chocan con el servicio que esté corriendo en Docker Compose.

## 2.14 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/unit/trabajos/test_estados.py` | Transiciones permitidas y prohibidas, terminales, `fechaLimite`, `esta_vencido` en los dos casos, `fechaExpiracion` |
| Unitario | `tests/unit/trabajos/test_registro.py` | Tipo duplicado y tipo no registrado |
| Unitario | `tests/unit/trabajos/test_consumidor.py` | Pasos 1 a 8 con `RepositorioTrabajosMemoria` y mensajes simulados: duplicados, estado no `EN_COLA`, inexistente → DLQ, cada resultado del paso 7, tiempo límite con resultado tardío descartado, resultado > 100 KB, reintentos 1 s/2 s/4 s (con espera simulada) |
| Unitario | `tests/unit/trabajos/test_revision.py` | Historia 2, escenarios 4 y 5, y la carrera con otro proceso (`False`) |
| Unitario | `tests/unit/trabajos/test_servicio.py` | `obtener_para`: ajeno, inexistente y ID inválido → 404 |
| Integración | `tests/integration/integracion/test_repositorio_trabajos_firestore.py` | Contra el emulador: `guardar_nuevo` duplicado, `cambiar_estado` condicional y concurrente (dos tareas a la vez, una gana), `listar_vencidos` |
| Integración | `tests/integration/trabajos/test_flujo_trabajos.py` | Historia 1 completa con RabbitMQ y el emulador, con el tipo de prueba y una ruta de prueba que crea trabajos; CE-TRA-02 y CE-TRA-04 |
| Integración | `tests/integration/trabajos/test_infraestructura.py` | Historia 4: publicación fallida (RabbitMQ con URL inválida) → 503 y `COLA_NO_DISPONIBLE`; mensaje mal formado en la DLQ; readiness con componente caído |
| Integración | `tests/integration/trabajos/test_router_trabajos.py` | Endpoint: `200` con `Retry-After`, `resultado` y `error` según estado, 404 para ajeno, 401 sin token, documentación OpenAPI de sus errores |

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

- [x] **T01** — Agregar las dependencias y variables de 2.1 y 2.2; crear `trabajos/estados.py` y `trabajos/esquemas.py`. *Hecho cuando:* pasa `test_estados.py`.
- [x] **T02** — Implementar `integracion/firestore.py` y `RepositorioTrabajosFirestore`; crear `firestore.indexes.json`. *Hecho cuando:* pasa `test_repositorio_trabajos_firestore.py` contra el emulador.
- [x] **T03** [P] — Implementar `integracion/rabbitmq.py` con la declaración de colas y la publicación confirmada. *Hecho cuando:* un test de integración publica y lee un mensaje de la cola de prueba.
- [x] **T04** — Implementar `trabajos/registro.py`, `trabajos/servicio.py` y `RepositorioTrabajosMemoria`. *Hecho cuando:* pasan `test_registro.py` y `test_servicio.py`.
- [x] **T05** — Implementar `trabajos/consumidor.py` y `trabajos/revision.py`, y arrancarlos en el `lifespan`. *Hecho cuando:* pasan `test_consumidor.py` y `test_revision.py`.
- [x] **T06** — Implementar `trabajos/router.py` y registrar las comprobaciones de salud. *Hecho cuando:* pasa `test_router_trabajos.py`.
- [x] **T07** — Escribir `test_flujo_trabajos.py` y `test_infraestructura.py`. *Hecho cuando:* pasan y se cumplen CE-TRA-02 a CE-TRA-04.
- [x] **T08** [P] — Actualizar `.github/workflows/servicio-ia.yml` (2.13). *Hecho cuando:* el pipeline corre en verde con Firestore y RabbitMQ. Escrito y con los mismos pasos verificados en local; falta confirmar la ejecución en GitHub Actions al hacer push.
- [x] **T09** — Verificación local: `docker compose --profile ia up -d` deja el servicio sano, la cola y la DLQ aparecen en el panel de RabbitMQ (`localhost:15672`) y `/salud/readiness` muestra `firestore` y `rabbitmq` en `UP`. *Hecho cuando:* se anota el resultado en esta tarea. Verificado en local (2026-11-05): contenedor `healthy`; readiness `{"firestore":"UP","rabbitmq":"UP"}`; `servicio-ia.trabajos` durable con `x-dead-letter-routing-key: servicio-ia.trabajos.dlq` y 1 consumidor; `servicio-ia.trabajos.dlq` durable; los tests no dejan colas `pruebas-*` al terminar.
