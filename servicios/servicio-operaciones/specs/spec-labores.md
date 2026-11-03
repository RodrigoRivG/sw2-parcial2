# Labores agrícolas — `servicio-operaciones`

| Campo | Valor |
|---|---|
| Servicio | `servicio-operaciones` |
| Archivo | `specs/spec-labores.md` |
| Estado | Spec aprobada (2026-11-02) · Implementada (2026-11-02) |
| Constitución | v2.8.0 (secciones 3, 4, 5, 7 y 9) |
| Trazabilidad | CU-10 (prioridad alta) · RF-11, RF-14 (y RF-30 de n8n, RF-23 y RF-27 como soporte) · RN-06, RN-07, RN-10, RN-11, RN-15, RN-16 · RNF-05, RNF-08, RNF-09 |
| Depende de | — (incluye la Fase 0: base del servicio). Consume `GET /campanias/{id}/estado` de `servicio-gestion` |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## 1.1 Contexto

Una labor es una actividad en una parcela dentro de una campaña. Se **programa** (queda `PROGRAMADA`, sin efectos) o se **registra como realizada**, directamente o a partir de una programada. Una labor realizada sin insumos queda `CONFIRMADA`; con insumos queda `PENDIENTE` y la Saga (`spec-saga.md`) decide su estado final (RN-07).

Antes de aceptar una labor se consulta a `servicio-gestion` que la campaña exista, no esté finalizada y sea de esa parcela (RN-06). Si gestión no responde, la labor se guarda igual como `PENDIENTE` y la validación se reintenta: nunca se pierde una operación (constitución §5, RNF-09).

```text
POST /labores ─▶ ¿campaña válida? ── sí ──▶ PROGRAMADA | CONFIRMADA | PENDIENTE (+ Saga)
                      │ no  ──▶ 404 / 422, no se guarda
                      └ gestión no responde ──▶ PENDIENTE (validación diferida) ──tarea──▶ igual que arriba, o RECHAZADA
```

## 1.2 Escenarios de usuario y pruebas

### Historia 1 — Registrar una labor realizada (Prioridad: P1)

Como técnico de campo, quiero registrar una labor que acabo de hacer, con los insumos que usé, para que quede en el historial de la campaña y se descuente el inventario.

**Por qué esta prioridad:** es la operación diaria principal del sistema (CU-10).

**Prueba independiente:** con la respuesta de gestión simulada, se registra una labor con y sin insumos y se consulta.

**Escenarios de aceptación:**

1. **Dado** la campaña C1 `EN_CURSO` de la parcela P1, **cuando** un técnico registra una labor `RIEGO` en P1 y C1 con `fechaEjecucion` de hoy y sin insumos, **entonces** recibe `201` con `Location`, la labor queda `CONFIRMADA`, `validacionCampania = VALIDADA`, `responsable` con su `sub` y nombre, `fechaRecepcion` del servidor, y se audita `REGISTRAR_LABOR`.
2. **Dado** lo mismo con `insumos` `[{ Urea, "100" }, { Glifosato, "2.5" }]`, **entonces** la labor queda `PENDIENTE` con las cantidades `"100.000"` y `"2.500"`. (Con `spec-saga.md` implementada, además se inicia la Saga.)
3. **Dado** una campaña `PLANIFICADA` de P1, **entonces** la labor se acepta igual que en una `EN_CURSO` (RN-06 solo excluye las finalizadas).
4. **Dado** una campaña `FINALIZADA`, **entonces** recibe `422 CAMPANIA_FINALIZADA` y no se guarda nada (RN-06).
5. **Dado** una campaña inexistente, **entonces** recibe `404 CAMPANIA_NO_ENCONTRADA`; **dado** una campaña de otra parcela, recibe `422 PARCELA_NO_CORRESPONDE`.
6. **Dado** `fechaEjecucion` más de 5 minutos en el futuro, **entonces** recibe `422 FECHA_EJECUCION_INVALIDA`.
7. **Dado** un insumo con cantidad `"0"` o `"-1"`, **entonces** recibe `422 CANTIDAD_INVALIDA`; con `2.5` como número JSON, `"1.2345"` o el mismo `idInsumo` dos veces, recibe `400 DATOS_INVALIDOS`.
8. **Dado** un usuario `administrador` o `gerencia` sin `tecnico_campo`, **cuando** registra una labor realizada, **entonces** recibe `403 SIN_PERMISO`.

---

### Historia 2 — Programar una labor y registrarla después como realizada (Prioridad: P1)

Como administrador o técnico de campo, quiero programar labores futuras y, cuando se hagan, registrarlas como realizadas, para planificar el trabajo y recibir recordatorios (RF-11, RF-30).

**Por qué esta prioridad:** sin labores programadas no hay recordatorios de n8n.

**Prueba independiente:** se programa una labor, se consulta como `PROGRAMADA` y se registra su realización.

**Escenarios de aceptación:**

1. **Dado** la campaña C1 de P1, **cuando** un administrador programa una labor `FERTILIZACION` para el `2026-11-20`, **entonces** queda `PROGRAMADA`, con `responsable` y `programadaPor` = el administrador, sin insumos, y se audita `PROGRAMAR_LABOR`. No se envía nada a inventario ni a gestión (RN-07).
2. **Dado** `fechaProgramada` anterior a la fecha de `fechaCreacion`, **entonces** recibe `422 FECHA_PROGRAMADA_INVALIDA`.
3. **Dado** un cuerpo con `fechaProgramada` y `fechaEjecucion` a la vez, o sin ninguna, **entonces** recibe `400 DATOS_INVALIDOS`; **dado** una labor programada con `insumos`, también `400`.
4. **Dado** la labor programada L1, **cuando** un técnico registra su realización con `fechaEjecucion` e insumos, **entonces** recibe `200`, se vuelve a validar la campaña, la labor queda `PENDIENTE` (con insumos) o `CONFIRMADA` (sin insumos), `responsable` pasa a ser el técnico, `programadaPor` se conserva y se audita `REALIZAR_LABOR`.
5. **Dado** que la campaña de L1 se finalizó después de programarla, **cuando** se registra su realización, **entonces** recibe `422 CAMPANIA_FINALIZADA` y L1 sigue `PROGRAMADA`.
6. **Dado** una labor que ya no está `PROGRAMADA`, **cuando** se registra su realización con otro `idOperacion`, **entonces** recibe `422 LABOR_NO_PROGRAMADA`.

---

### Historia 3 — Reintentar una operación sin duplicarla (Prioridad: P1)

Como técnico de campo con mala señal, quiero que reenviar una labor no la registre dos veces, para no duplicar consumos ni costos (RN-10, RF-14).

**Por qué esta prioridad:** la constitución exige estos tres tests (§8) y la sincronización offline depende de ellos.

**Prueba independiente:** se envía la misma operación varias veces, con el mismo contenido y con otro.

**Escenarios de aceptación:**

1. **Dado** una operación nueva con `idOperacion` O1, **entonces** se crea la labor con `id` = O1 y responde `201`.
2. **Dado** que O1 ya se procesó, **cuando** llega otra vez con el mismo contenido, **entonces** responde `200` con el estado **actual** de la labor (por ejemplo, `CONFIRMADA` si la Saga ya terminó), sin volver a consultar gestión ni auditar.
3. **Dado** que O1 ya se procesó, **cuando** llega con otro contenido (otra cantidad, otra parcela u otro usuario), **entonces** responde `409 CONFLICTO_IDEMPOTENCIA` y la labor no cambia.
4. **Dado** que O1 fue rechazada con `422 CAMPANIA_FINALIZADA`, **cuando** se reenvía, **entonces** se vuelve a validar y responde lo mismo: lo rechazado en el momento no se guarda.
5. **Dado** dos envíos simultáneos de O1 con el mismo contenido, **entonces** existe una sola labor; uno responde `201` y el otro `200`.
6. **Dado** la realización de L1 con `idOperacion` O2 ya procesada, **cuando** llega otra vez con el mismo contenido, **entonces** responde `200` sin cambios; con otro contenido, `409 CONFLICTO_IDEMPOTENCIA`.

---

### Historia 4 — No perder la labor si gestión no responde (Prioridad: P1)

Como técnico de campo, quiero que mi labor se acepte aunque `servicio-gestion` esté caído, para no tener que volver a cargarla (RNF-08, RNF-09).

**Por qué esta prioridad:** la constitución (§5) prohíbe perder la operación.

**Prueba independiente:** con gestión simulada caída y un reloj fijo, se registra una labor y se ejecuta la tarea de revalidación.

**Escenarios de aceptación:**

1. **Dado** que gestión no responde en 2 s (o responde `5xx`, `401` o `403`), **cuando** se registra una labor, **entonces** responde `201` con `estado = PENDIENTE` y `validacionCampania = PENDIENTE`, y se registra una advertencia en el log.
2. **Dado** esa labor, **cuando** la tarea de revalidación se ejecuta y gestión ya responde que la campaña es válida, **entonces** la labor pasa al estado que le corresponde (`PROGRAMADA`, `CONFIRMADA`, o `PENDIENTE` con Saga) con `validacionCampania = VALIDADA`, y se audita `VALIDAR_CAMPANIA`.
3. **Dado** que la campaña resultó `FINALIZADA`, inexistente o de otra parcela, **entonces** la labor queda `RECHAZADA` con `motivo.codigo` = `CAMPANIA_FINALIZADA`, `CAMPANIA_NO_ENCONTRADA` o `PARCELA_NO_CORRESPONDE`. No se borra (RN-11, constitución §4).
4. **Dado** que gestión sigue sin responder, **entonces** la labor sigue `PENDIENTE` y el próximo intento se programa a 1, 2, 4, 8 y luego cada 15 minutos, sin límite.
5. **Dado** dos ejecuciones simultáneas de la tarea, **entonces** cada labor se valida una sola vez (actualización condicional).

---

### Historia 5 — Consultar labores (Prioridad: P1)

Como administrador o gerente, quiero ver las labores por campaña, estado o responsable; como técnico, mis labores y las programadas; como n8n, `servicio-ia` o GraphQL, leerlas con mi cuenta de servicio (RF-30, RF-23, RF-27).

**Por qué esta prioridad:** el técnico necesita ver el estado final de sus labores (RNF-14) y n8n, las programadas.

**Prueba independiente:** con labores cargadas, se consulta con cada rol y cada filtro.

**Escenarios de aceptación:**

1. **Dado** 30 labores de la campaña C1, **cuando** un gerente pide `?idCampania=C1`, **entonces** recibe 20 ordenadas por `fechaReferencia` descendente y un `siguienteCursor`; con ese cursor recibe las 10 restantes y `siguienteCursor = null`.
2. **Dado** labores programadas, **cuando** la cuenta de n8n (`lectura_operaciones`) pide `?estado=PROGRAMADA&fechaHasta=2026-11-01&orden=ASC`, **entonces** recibe las retrasadas; con `fechaDesde=2026-11-02&fechaHasta=2026-11-04`, las próximas.
3. **Dado** un técnico, **cuando** pide `?mias=true`, **entonces** recibe solo las labores de las que es responsable; con `?estado=PROGRAMADA`, todas las programadas.
4. **Dado** un técnico, **cuando** pide `?idCampania=C1` sin `estado=PROGRAMADA` ni `mias=true`, o el detalle de una labor que no es programada ni suya, **entonces** recibe `403 SIN_PERMISO`.
5. **Dado** un listado sin `idCampania`, `idResponsable`, `mias` ni `estado`, **entonces** recibe `400 DATOS_INVALIDOS`.
6. **Dado** un ID inexistente, **entonces** recibe `404 LABOR_NO_ENCONTRADA`.
7. **Dado** la cuenta `lectura_operaciones`, **cuando** intenta un `POST`, **entonces** recibe `403 SIN_PERMISO`.

---

### Casos borde

- `fechaCreacion` del dispositivo más de 5 minutos en el futuro: `422 FECHA_EJECUCION_INVALIDA` en una realizada y `FECHA_PROGRAMADA_INVALIDA` en una programada.
- Más de 20 insumos en una labor: `400 DATOS_INVALIDOS`.
- `idOperacion` que no es UUID: `400 DATOS_INVALIDOS`.
- Realización con el mismo `idOperacion` con que se creó la labor programada: `409 CONFLICTO_IDEMPOTENCIA` (cada operación tiene su propio UUID).
- Una labor programada cuya validación quedó diferida no se puede realizar hasta quedar `PROGRAMADA`: `422 LABOR_NO_PROGRAMADA`.
- Dos realizaciones simultáneas de L1 con distintos `idOperacion`: una responde `200`; la otra, `422 LABOR_NO_PROGRAMADA`.
- Cursor manipulado o de otro filtro: `400 DATOS_INVALIDOS`.
- La labor no valida que la parcela exista ni que los insumos existan: lo primero lo garantiza la campaña (la campaña pertenece a la parcela) y lo segundo lo rechaza inventario en la Saga.

## 1.3 Requisitos

### Requisitos funcionales

#### Registro

- **RQ-LAB-01**: El sistema debe permitir crear una labor con:
  - `idOperacion`: obligatorio, UUID (es el `id` de la labor, README D-06).
  - `fechaCreacion`: obligatoria, fecha y hora en que se creó en el dispositivo.
  - `tipoLabor`: obligatorio, `TipoLabor` (glosario de la constitución v2.8.0).
  - `idParcela`, `idCampania`: obligatorios, UUID.
  - Exactamente una de `fechaProgramada` (`AAAA-MM-DD`) o `fechaEjecucion` (fecha y hora UTC).
  - `observaciones`: opcional, hasta 500 caracteres.
  - `insumos`: opcional y solo con `fechaEjecucion`; hasta 20 elementos `{ idInsumo, cantidad }`, `idInsumo` UUID sin repetir, `cantidad` texto decimal > 0 con hasta 3 decimales (README D-01).
- **RQ-LAB-02**: Con `fechaProgramada` la operación es "programar" (roles `administrador`, `tecnico_campo`); con `fechaEjecucion`, "registrar realizada" (rol `tecnico_campo`).
- **RQ-LAB-03**: Reglas del dominio (`422`): `fechaProgramada` ≥ fecha UTC de `fechaCreacion`; `fechaEjecucion` y `fechaCreacion` no más de 5 minutos en el futuro; cantidad > 0.
- **RQ-LAB-04**: `responsable` se toma del token (README D-11); en una programada, `programadaPor` es el mismo usuario.
- **RQ-LAB-05**: Validación de campaña (RN-06) con la respuesta de `GET /campanias/{id}/estado` de gestión (README D-12):

  | Respuesta de gestión | Resultado |
  |---|---|
  | `200`, estado ≠ `FINALIZADA` e `idParcela` igual | Válida |
  | `200` con `FINALIZADA` | `422 CAMPANIA_FINALIZADA` |
  | `200` con otra `idParcela` | `422 PARCELA_NO_CORRESPONDE` |
  | `404` | `404 CAMPANIA_NO_ENCONTRADA` |
  | Tiempo límite, error de conexión, `5xx`, `401` o `403` | No disponible → validación diferida (RQ-LAB-09) |

- **RQ-LAB-06**: Estado inicial con la campaña válida:

  | Operación | Insumos | Estado |
  |---|---|---|
  | Programar | — | `PROGRAMADA` |
  | Registrar realizada | Ninguno | `CONFIRMADA` |
  | Registrar realizada | Al menos uno | `PENDIENTE` (inicia la Saga, `spec-saga.md`) |

- **RQ-LAB-07**: El sistema debe permitir registrar como realizada una labor `PROGRAMADA` (`POST /labores/{id}/realizacion`) con `idOperacion`, `fechaCreacion`, `fechaEjecucion`, `observaciones` e `insumos` (mismas reglas de RQ-LAB-01 y RQ-LAB-03), rol `tecnico_campo`. Se valida otra vez la campaña (RQ-LAB-05) y el estado nuevo sigue la tabla de RQ-LAB-06. `responsable` pasa a ser quien la realiza; `programadaPor` y `fechaProgramada` se conservan. Si la labor no está `PROGRAMADA`: `422 LABOR_NO_PROGRAMADA`.
- **RQ-LAB-08**: Mientras `spec-saga.md` no esté implementada, una labor realizada con insumos queda `PENDIENTE` sin Saga.

#### Validación diferida

- **RQ-LAB-09**: Si gestión no está disponible, la labor (o su realización) se guarda con `estado = PENDIENTE`, `validacionCampania = PENDIENTE` y el próximo intento a 1 minuto. La respuesta es la misma que con la campaña válida (`201` o `200`), con ese estado.
- **RQ-LAB-10**: Una tarea programada cada minuto revalida las labores con `validacionCampania = PENDIENTE` cuyo próximo intento ya venció. Válida → estado de RQ-LAB-06 (si es una realización de una programada, igual); inválida → `RECHAZADA` con el código de RQ-LAB-05 en `motivo`; no disponible → próximo intento con espera 1, 2, 4, 8 y luego 15 minutos, sin límite.
- **RQ-LAB-11**: Una labor rechazada en la validación diferida no se borra: queda `RECHAZADA` con su motivo (RN-11, constitución §4).

#### Idempotencia

- **RQ-LAB-12**: Creación y realización son idempotentes por `idOperacion` (README D-06). La huella se calcula sobre el cuerpo normalizado (textos recortados, cantidades con escala 3, campos ordenados) más el `sub`. Misma huella → `200` con el estado actual, sin consultar gestión, sin auditar y sin efectos; otra huella → `409 CONFLICTO_IDEMPOTENCIA`.
- **RQ-LAB-13**: Lo rechazado en el momento (400, 403, 404, 409 o 422) no se guarda; un reenvío vuelve a validar.

#### Consultas

- **RQ-LAB-14**: Listado paginado por cursor (README D-05) con filtros `idCampania`, `idResponsable`, `mias` (= `idResponsable` del token), `estado`, `fechaDesde` y `fechaHasta` (sobre `fechaReferencia`, días completos UTC) y `orden` (`ASC` / `DESC`, por defecto `DESC`). Es obligatorio al menos uno de `idCampania`, `idResponsable`, `mias` o `estado`.
- **RQ-LAB-15**: `fechaReferencia` es `fechaProgramada` mientras la labor está programada y `fechaEjecucion` desde que se realiza.
- **RQ-LAB-16**: Detalle por ID, o `404 LABOR_NO_ENCONTRADA`.
- **RQ-LAB-17**: Visibilidad: `administrador`, `gerencia` y `lectura_operaciones` ven todas; quien solo tiene `tecnico_campo` ve las `PROGRAMADA` y las suyas (`responsable` o `programadaPor`). En el listado, un técnico sin `mias=true` debe filtrar `estado=PROGRAMADA`; si no, `403 SIN_PERMISO`.

#### Comunes

- **RQ-LAB-18**: Toda creación y cambio de estado genera auditoría (README D-09) con las acciones `PROGRAMAR_LABOR`, `REGISTRAR_LABOR`, `REALIZAR_LABOR` y `VALIDAR_CAMPANIA`.
- **RQ-LAB-19**: Esta versión no incluye editar, cancelar ni eliminar labores.

### Entidades clave

- **LaborAgricola**: `id`, `tipoLabor`, `idParcela`, `idCampania`, `estado`, `fechaProgramada`, `fechaEjecucion`, `fechaCreacion` (del dispositivo), `fechaRecepcion` y `fechaRecepcionEjecucion` (del servidor), `responsable` y `programadaPor` (`{ id, nombre }`), `observaciones`, `insumos` (lista de `ConsumoInsumo`), `validacionCampania` (`VALIDADA` / `PENDIENTE`), `idSaga`, `motivo` (`{ codigo, mensaje, detalles }`), `huellaCreacion`, `idOperacionRealizacion`, `huellaRealizacion`, `version`, `fechaActualizacion`.
- **ConsumoInsumo** (objeto de valor): `idInsumo`, `cantidad`.
- **EstadoLabor**: `PROGRAMADA` / `PENDIENTE` / `CONFIRMADA` / `RECHAZADA` / `PENDIENTE_REVISION` (glosario).
- **TipoLabor**: `PREPARACION_SUELO` / `SIEMBRA` / `FERTILIZACION` / `RIEGO` / `CONTROL_FITOSANITARIO` / `DESHIERBE` / `COSECHA` / `OTRA`.
- **EstadoCampaniaConsultado** (lectura de gestión): `id`, `idParcela`, `estado`.

## 1.4 Permisos

| Operación | Roles |
|---|---|
| Programar | `administrador`, `tecnico_campo` |
| Registrar realizada y realizar una programada | `tecnico_campo` |
| Listar y ver detalle (todas) | `administrador`, `gerencia`, `lectura_operaciones` |
| Listar y ver detalle (programadas y propias) | `tecnico_campo` |

## 1.5 Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Formato, campo ausente o no permitido, decimal como número JSON, insumo repetido, más de 20 insumos, ambas o ninguna fecha, insumos en una programada, listado sin filtro principal, cursor inválido |
| 404 | `LABOR_NO_ENCONTRADA` | El ID no existe |
| 404 | `CAMPANIA_NO_ENCONTRADA` | Gestión responde que la campaña no existe |
| 409 | `CONFLICTO_IDEMPOTENCIA` | Mismo `idOperacion` con otro contenido |
| 409 | `CONFLICTO_CONCURRENCIA` | La labor cambió durante la operación |
| 422 | `CAMPANIA_FINALIZADA` | La campaña está finalizada (RN-06) |
| 422 | `PARCELA_NO_CORRESPONDE` | La campaña es de otra parcela |
| 422 | `CANTIDAD_INVALIDA` | Cantidad ≤ 0 |
| 422 | `FECHA_PROGRAMADA_INVALIDA` | Fecha programada anterior a la creación, o creación en el futuro |
| 422 | `FECHA_EJECUCION_INVALIDA` | Ejecución o creación más de 5 minutos en el futuro |
| 422 | `LABOR_NO_PROGRAMADA` | Realización de una labor que no está `PROGRAMADA` |

## 1.6 Criterios de éxito

- **CE-LAB-01**: Tests obligatorios de idempotencia de la constitución §8 en verde: operación nueva, repetida y mismo UUID con otro contenido, en la creación y en la realización.
- **CE-LAB-02**: Con 20 envíos simultáneos del mismo `idOperacion`, existe una sola labor y una sola auditoría de creación.
- **CE-LAB-03**: Con gestión caída, ninguna labor se pierde: todas quedan `PENDIENTE` y llegan a su estado final cuando gestión vuelve (RNF-09).
- **CE-LAB-04**: Listado y detalle responden en menos de 3 s con 1.000 labores cargadas (RNF-05).
- **CE-LAB-05**: Toda creación y cambio de estado tiene su auditoría.

## 1.7 Supuestos

- El cliente (Vue.js o Flutter) descarga las parcelas y campañas de gestión y el catálogo de insumos de inventario para armar la labor; este servicio solo valida la campaña.
- Los recordatorios de n8n van al `responsable` de la labor programada; n8n obtiene su correo desde Keycloak con el `id` (este servicio no guarda correos).
- La labor programada no lleva insumos planificados: los insumos se informan al realizarla.

## 1.8 Aclaraciones

- **AC-01** — Resuelta (contrato de gestión, `spec-consultas-integracion.md` RQ-INT-01): la consulta de estado devuelve `id`, `idParcela`, `idCultivo`, `estado`, `fechaInicio` y `fechaFin`; este servicio usa `estado` e `idParcela`.
- **AC-02** — Resuelta (constitución v2.8.0): `TipoLabor`, el rol `lectura_operaciones` y la ruta de realización están en el glosario y la tabla de permisos.

## 1.9 Fuera de alcance

- Editar, cancelar o eliminar labores.
- Asignar una labor programada a otro usuario.
- Validar contra las fechas planificadas de la campaña.

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución, sin dependencias fuera del stack de la constitución y de D-15 del README.

**Documentos que debe tener a mano quien implemente:** la constitución de operaciones (`servicios/servicio-operaciones/Constitucion.md`), `specs/README.md` y este archivo.

## 2.1 Fase 0 — Base del servicio

Se construye una sola vez, con esta funcionalidad, y la reutilizan todas las demás.

### Proyecto y dependencias

- El proyecto se crea con `composer create-project laravel/laravel` en una carpeta temporal y se copia a `servicios/servicio-operaciones` (la carpeta ya tiene `Constitucion.md` y `specs/`). Se borran `app/Models`, `database/migrations`, `database/factories`, `database/seeders`, `routes/web.php` y las vistas; no se ejecuta `php artisan install:api` (instalaría Sanctum).

| Dependencia | Para qué |
|---|---|
| `laravel/framework` | Rutas, contenedor, configuración, consola y scheduler (constitución §3) |
| `aws/aws-sdk-php` | DynamoDB y S3 (constitución §2) |
| `firebase/php-jwt` | Validación del JWT con JWKS |
| Dev: `pestphp/pest`, `laravel/pint`, `mockery/mockery` | Tests y estilo (Pint viene con el esqueleto) |

`php-amqplib/php-amqplib` se agrega recién en `spec-saga.md`, la primera funcionalidad con RabbitMQ.

### Configuración

- `config/aws.php` (región, credenciales, `DYNAMODB_ENDPOINT`, `AWS_ENDPOINT`, `AWS_ENDPOINT_PUBLICO`, `AWS_USE_PATH_STYLE_ENDPOINT`, `AWS_BUCKET`, `DYNAMODB_PREFIJO_TABLAS`), `config/keycloak.php` (`KEYCLOAK_ISSUER`, `KEYCLOAK_JWKS_URI`, `KEYCLOAK_AUDIENCE`, `KEYCLOAK_TOKEN_URL`, `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`) y `config/servicios.php` (`API_GATEWAY_URL`).
- `ValidadorEntorno` (en `Infrastructure/Providers`): al arrancar, verifica las variables obligatorias de README D-16; si falta una, lanza una excepción y el proceso termina con el error en el log.
- `bootstrap/app.php`:
  - `withRouting(api: routes/api.php, apiPrefix: 'api/operaciones/v1', commands: routes/console.php, then: ...)`; en `then` se registran `/salud*` y `/api-docs` sin prefijo y sin token.
  - `withMiddleware`: `IdCorrelacion` global y primero; alias `jwt` (`ValidarJwt`) y `rol` (`RequerirRol`). Sin middleware de sesión ni CSRF.
  - `withExceptions`: el render de errores de 2.1 "Errores".
- `bootstrap/providers.php` registra `Infrastructure/Providers/ProveedorDominio`, que enlaza cada contrato con su implementación.

### DynamoDB y unidad de trabajo

- `ClienteDynamoDb`: singleton del `DynamoDbClient` del SDK, con `endpoint` solo si `DYNAMODB_ENDPOINT` tiene valor. `NombresTablas` antepone `DYNAMODB_PREFIJO_TABLAS`.
- `database/dynamodb/tablas.json`: definición de tablas e índices (README, "Mapa de la base de datos"). `php artisan dynamodb:crear-tablas` crea las que faltan (y sus índices) y espera a que estén `ACTIVE`; es idempotente. Docker Compose lo ejecuta antes de `php artisan serve`; los tests, en su arranque.
- **Unidad de trabajo** (`UnidadTrabajo`, contrato en `Application/Contracts`): `ejecutar(callable)` abre una lista de escrituras; dentro, los repositorios y la auditoría **agregan** `Put`/`Update` con su condición en lugar de ejecutarlos, y al final se envía un solo `TransactWriteItems` (README D-08). Las lecturas se ejecutan en el momento. Una `TransactionCanceledException` por `ConditionalCheckFailed` se traduce a `ConflictoEscritura` con el índice del ítem que falló, para que el caso de uso decida (idempotencia o `CONFLICTO_CONCURRENCIA`).
- Atributos en snake_case; decimales y fechas como `S` (README D-03, D-04); `version` como `N`.

### Seguridad

- **`ValidarJwt`**: lee `Authorization: Bearer`, valida con `JWT::decode($token, JWK::parseKeySet($jwks))` y comprueba `iss` = `KEYCLOAK_ISSUER` y que `aud` (texto o lista) contenga `KEYCLOAK_AUDIENCE`; `exp` lo valida la librería. Deja en la solicitud un `UsuarioAutenticado` (`id` = `sub`, `nombre`, `roles` de `realm_access.roles`). Sin token o inválido: `401 NO_AUTENTICADO`.
- **JWKS:** `ProveedorClavesJwks` descarga `KEYCLOAK_JWKS_URI` por la red interna, lo guarda 10 minutos en caché y, si llega un `kid` desconocido, lo descarga una vez más. El emisor solo se compara (igual que gestión e inventario).
- **`RequerirRol`** (`rol:administrador,gerencia`): si el usuario no tiene ninguno, `403 SIN_PERMISO`. Las reglas que dependen del cuerpo o del recurso (RQ-LAB-02, RQ-LAB-17) las aplica el caso de uso con los roles del `UsuarioAutenticado`.
- Los tests generan un par RSA, firman sus propios tokens con `firebase/php-jwt` y reemplazan `ProveedorClavesJwks` por uno con la clave local: se prueban firma, `iss`, `aud` y `exp` sin Keycloak.

### Errores

- **`ExcepcionDominio`** (`Domain/Shared`): `codigo`, `mensaje`, `tipo` (`NO_ENCONTRADO`, `CONFLICTO`, `REGLA_NEGOCIO`) y `detalles`. El dominio no conoce HTTP.
- Render común `{ codigo, mensaje, detalles, idCorrelacion }`:

  | Origen | HTTP | Código |
  |---|---|---|
  | `ValidationException` (Laravel responde 422 por defecto; aquí se cambia) o JSON mal formado | 400 | `DATOS_INVALIDOS`, un detalle por campo |
  | `PostTooLargeException` | 400 | `DATOS_INVALIDOS` |
  | Falta de token o token inválido | 401 | `NO_AUTENTICADO` |
  | Rol insuficiente | 403 | `SIN_PERMISO` |
  | `ExcepcionDominio` `NO_ENCONTRADO` | 404 | El de la excepción |
  | `NotFoundHttpException` (ruta inexistente) | 404 | `RECURSO_NO_ENCONTRADO` |
  | `MethodNotAllowedHttpException` | 405 | `METODO_NO_PERMITIDO` |
  | `ExcepcionDominio` `CONFLICTO` | 409 | El de la excepción |
  | `ExcepcionDominio` `REGLA_NEGOCIO` | 422 | El de la excepción |
  | Cualquier otra | 500 | `ERROR_INTERNO`, sin detalles; el error completo va al log |

### Correlación y logs

- **`IdCorrelacion`**: toma `X-Correlation-Id` o genera un UUID, lo guarda con `Context::add('idCorrelacion', ...)` y lo devuelve en el header de la respuesta, también en 401 y 403.
- Canal de log `stderr` con `Monolog\Formatter\JsonFormatter`; el `Context` de Laravel agrega `idCorrelacion` a cada registro. Los logs no incluyen tokens ni nombres: solo el `sub`.

### Auditoría

- Contrato `RegistroAuditoria` (`Application/Contracts`): `registrar(actor, accion, entidad, idEntidad)`.
- `RegistroAuditoriaDynamo` agrega un `Put` en `registros_auditoria` (`id`, `actor`, `accion`, `entidad`, `id_entidad`, `entidad_id` = `"LABOR#<id>"`, `id_correlacion`, `fecha`) a la unidad de trabajo activa.

### Reloj

Contrato `Reloj` (`ahora(): DateTimeImmutable` en UTC) con implementación del sistema; los tests usan uno fijo.

### Formato JSON

- Decimales: en la entrada, regla `['string', 'regex:/^-?\d{1,12}(\.\d{1,3})?$/']`; un número JSON falla `string` (README D-03). El signo negativo pasa a propósito: el dominio responde `422 CANTIDAD_INVALIDA`.
- `Cantidad` (objeto de valor) normaliza a escala 3 con `bcadd($valor, '0', 3)` y compara con `bccomp`.
- Fechas con hora: regla `date_format:Y-m-d\TH:i:s\Z` (también se acepta con milisegundos); fechas sin hora: `date_format:Y-m-d`. Salida en UTC con `Z`.

### Paginación (común a todos los listados)

- `CodificadorCursor`: `LastEvaluatedKey` ↔ base64url de su JSON. Un cursor que no decodifica o cuyas claves no son las del índice elegido → `400 DATOS_INVALIDOS`.
- Respuesta `{ items, siguienteCursor }`.

### Salud

- `GET /salud/liveness`: `200 { "estado": "UP" }`.
- `GET /salud/readiness`: `DescribeTable` de `labores` (y RabbitMQ desde `spec-saga.md`). `200` si todo responde; `503` con el detalle si algo falla.
- `GET /salud`: igual que readiness.

### OpenAPI

- `openapi.yaml` en la raíz del servicio, escrito a mano (README D-15), servido en `/api-docs` sin token.
- Un test recorre `Route::getRoutes()` y falla si una ruta del prefijo no está documentada con sus códigos de error.

### Empaquetado, entorno local y pipeline

- **`Dockerfile`** del servicio sobre `php:8.4-apache`: extensiones `bcmath`, `sockets` y `pcntl`, `composer install --no-dev --optimize-autoloader`, `DocumentRoot` en `public` con `mod_rewrite`, `upload_max_filesize = 10M` y `post_max_size = 40M`. La misma imagen corre el programador y, desde `spec-saga.md`, el consumidor, cambiando el comando.
- **`docker/laravel/Dockerfile`** (imagen de desarrollo): se agrega `pcov` (`pecl install pcov && docker-php-ext-enable pcov`, para la cobertura) y el mismo `php.ini` de límites. No cambia nada para los demás servicios: la imagen solo la usa operaciones.
- **`docker-compose.yml`**:
  - `servicio-operaciones`: comando `composer install && php artisan dynamodb:crear-tablas && php artisan serve --host=0.0.0.0 --port=8000`, con `PHP_CLI_SERVER_WORKERS: 4` (si no, el servidor embebido atiende una solicitud a la vez) y las variables nuevas de README D-16.
  - `servicio-operaciones` agrega un `healthcheck` sin `curl` (la imagen no lo trae): `php -r "exit(@file_get_contents('http://localhost:8000/salud/liveness') === false ? 1 : 0);"`, con `start_period` de 60 s para el primer `composer install`.
  - Nuevo `servicio-operaciones-programador` (misma imagen, volumen y variables): `php artisan schedule:work`, perfiles iguales a los de `servicio-operaciones`, `mem_limit: 128m` y `depends_on: servicio-operaciones: condition: service_healthy`. Así no ejecuta `composer install` al mismo tiempo sobre el mismo volumen; solo `servicio-operaciones` instala dependencias y crea las tablas.
- **`.github/workflows/servicio-operaciones.yml`** (en la raíz, filtrado por `servicios/servicio-operaciones/**`): contenedores de servicio `amazon/dynamodb-local`, `rabbitmq:4-management-alpine` y `localstack/localstack` (con el secreto `LOCALSTACK_AUTH_TOKEN`); `shivammathur/setup-php` con PHP 8.4 y `pcov`; `composer install`, `vendor/bin/pint --test`, `vendor/bin/pest --coverage --min=80` y `docker build`.
- `phpunit.xml`: la cobertura se mide solo sobre `app/Domain` y `app/Application` (constitución §8).

### Tests

- `tests/Unit` (sin infraestructura) y `tests/Integration` (DynamoDB Local; RabbitMQ y LocalStack desde las specs que los usan), con la estructura de `app` (constitución §3).
- `tests/bootstrap.php` (el `bootstrap` de `phpunit.xml`) crea al inicio las tablas con el prefijo `pruebas_<aleatorio>_` y registra su borrado al terminar (README D-17). Cada test usa UUID propios, así no se pisan.
- `tests/Support/EnParalelo.php`: `ejecutar(n, callable)` lanza `n` procesos con `pcntl_fork`, cada uno con su propia aplicación, y devuelve los resultados; lo usan las pruebas de concurrencia (README D-17).
- La consulta a gestión y el token de cuenta de servicio se simulan con `Http::fake()`; no hay gateway en los tests.

## 2.2 Endpoints

Prefijo: `/api/operaciones/v1`.

| Método y ruta | Roles (middleware) | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /labores` | `administrador`, `tecnico_campo` (RQ-LAB-02 en el caso de uso) | `201` + `Location` + labor; `200` si se repite | 400, 401, 403, 404 `CAMPANIA_NO_ENCONTRADA`, 409, 422 |
| `POST /labores/{id}/realizacion` | `tecnico_campo` | `200` + labor | 400, 401, 403, 404 `LABOR_NO_ENCONTRADA` o `CAMPANIA_NO_ENCONTRADA`, 409, 422 |
| `GET /labores?idCampania=&idResponsable=&mias=&estado=&fechaDesde=&fechaHasta=&orden=&limite=&cursor=` | `administrador`, `gerencia`, `lectura_operaciones`, `tecnico_campo` | `200` + página | 400, 401, 403 |
| `GET /labores/{id}` | Igual que el listado | `200` + labor | 401, 403, 404 `LABOR_NO_ENCONTRADA` |

**Solicitud de creación (realizada):**

```json
{
  "idOperacion": "6f1c…",
  "fechaCreacion": "2026-11-02T13:58:00Z",
  "tipoLabor": "FERTILIZACION",
  "idParcela": "uuid",
  "idCampania": "uuid",
  "fechaEjecucion": "2026-11-02T13:30:00Z",
  "observaciones": "Aplicación al voleo",
  "insumos": [
    { "idInsumo": "uuid", "cantidad": "100" },
    { "idInsumo": "uuid", "cantidad": "2.5" }
  ]
}
```

Programada: lo mismo con `fechaProgramada` (`"2026-11-20"`) en lugar de `fechaEjecucion` y sin `insumos`.

**Solicitud de realización:** `idOperacion`, `fechaCreacion`, `fechaEjecucion`, `observaciones` e `insumos`.

**Respuesta de labor:**

```json
{
  "id": "6f1c…",
  "tipoLabor": "FERTILIZACION",
  "idParcela": "uuid",
  "idCampania": "uuid",
  "estado": "PENDIENTE",
  "fechaReferencia": "2026-11-02T13:30:00Z",
  "fechaProgramada": null,
  "fechaEjecucion": "2026-11-02T13:30:00Z",
  "fechaCreacion": "2026-11-02T13:58:00Z",
  "fechaRecepcion": "2026-11-02T14:00:05Z",
  "fechaRecepcionEjecucion": "2026-11-02T14:00:05Z",
  "responsable": { "id": "sub", "nombre": "Ana Quispe" },
  "programadaPor": null,
  "observaciones": "Aplicación al voleo",
  "insumos": [
    { "idInsumo": "uuid", "cantidad": "100.000" },
    { "idInsumo": "uuid", "cantidad": "2.500" }
  ],
  "validacionCampania": "VALIDADA",
  "idSaga": null,
  "motivo": null,
  "version": 0,
  "fechaActualizacion": "2026-11-02T14:00:05Z"
}
```

`motivo`, cuando existe: `{ "codigo": "STOCK_INSUFICIENTE", "mensaje": "…", "detalles": [ … ] }`. `spec-saga.md` llena `idSaga` y `spec-revision-labores.md` agrega `resolucion`.

**Validaciones del `FormRequest`** (responden `400 DATOS_INVALIDOS`):

| Campo | Regla |
|---|---|
| `idOperacion`, `idParcela`, `idCampania`, `insumos.*.idInsumo` | `required`, `uuid` |
| `fechaCreacion`, `fechaEjecucion` | Fecha y hora UTC (2.1 "Formato JSON") |
| `fechaProgramada` | `date_format:Y-m-d` |
| `fechaProgramada` / `fechaEjecucion` | Exactamente una (`required_without` + `prohibits`) |
| `tipoLabor` | `Rule::enum(TipoLabor::class)` |
| `observaciones` | `nullable`, `string`, `max:500` |
| `insumos` | `array`, `max:20`, `prohibited` con `fechaProgramada`, `idInsumo` `distinct` |
| `insumos.*.cantidad` | Decimal como texto, hasta 3 decimales |
| Campos no declarados | Se rechazan (`FormRequest` propio que compara las claves recibidas con las reglas) |

## 2.3 Modelo de datos

Tabla `labores` (clave `id`):

| Atributo | Tipo | Nota |
|---|---|---|
| `id` | `S` | `idOperacion` de la creación |
| `tipo_labor`, `estado`, `validacion_campania` | `S` | Enumeraciones |
| `id_parcela`, `id_campania` | `S` | |
| `fecha_programada` | `S` | `AAAA-MM-DD` o ausente |
| `fecha_ejecucion`, `fecha_creacion_dispositivo`, `fecha_recepcion`, `fecha_recepcion_ejecucion`, `fecha_actualizacion` | `S` | ISO 8601 UTC |
| `fecha_referencia` | `S` | RQ-LAB-15; clave de orden de los índices |
| `id_responsable`, `nombre_responsable`, `id_programada_por`, `nombre_programada_por` | `S` | |
| `observaciones` | `S` | Opcional |
| `insumos` | `L` de `M` `{ id_insumo, cantidad }` | `cantidad` como `S` |
| `id_saga` | `S` | Desde `spec-saga.md` |
| `motivo` | `M` `{ codigo, mensaje, detalles }` | Opcional |
| `huella_creacion`, `id_operacion_realizacion`, `huella_realizacion` | `S` | Idempotencia (README D-06) |
| `validacion_pendiente` | `S` = `"1"` | Solo mientras la validación está diferida (índice disperso) |
| `fecha_proximo_validacion`, `intentos_validacion` | `S`, `N` | Solo con validación diferida |
| `version` | `N` | README D-07 |

Índices (README, mapa de la base de datos):

| Índice | Clave de partición | Clave de orden | Patrón de acceso |
|---|---|---|---|
| `gsi_estado` | `estado` | `fecha_referencia` | Programadas para n8n; labores por estado |
| `gsi_campania` | `id_campania` | `fecha_referencia` | Labores de una campaña (gerencia, IA, GraphQL) |
| `gsi_responsable` | `id_responsable` | `fecha_referencia` | "Mis labores" |
| `gsi_validacion_pendiente` | `validacion_pendiente` | `fecha_proximo_validacion` | Tarea de revalidación |

- El listado elige el índice por el primer filtro presente en este orden: `idCampania`, `idResponsable`/`mias`, `estado`. Los demás filtros van en `FilterExpression`.
- `fechaDesde`/`fechaHasta` usan `BETWEEN :desde AND :hastaT99` sobre `fecha_referencia`: incluye las fechas sin hora y todas las horas del día `hasta`, porque `"2026-11-20" < "2026-11-20T23:59:59Z" < "2026-11-20T99"`.
- `orden` se traduce a `ScanIndexForward`.

## 2.4 Diseño por capas

| Capa | Archivo | Responsabilidad |
|---|---|---|
| `Domain/Shared` | `ExcepcionDominio.php`, `IdOperacion.php`, `Cantidad.php`, `Huella.php` | Errores, UUID, cantidad con `bcmath`, SHA-256 del contenido normalizado |
| `Domain/FieldTask` | `LaborAgricola.php`, `EstadoLabor.php`, `TipoLabor.php`, `ConsumoInsumo.php`, `Responsable.php`, `ValidacionCampania.php`, `RepositorioLabor.php` | `LaborAgricola::programar(...)`, `registrarRealizada(...)`, `realizar(...)`, `aplicarValidacion(resultado)`, reglas de fechas y estado inicial (RQ-LAB-03, RQ-LAB-06) |
| `Domain/FieldTask` | `PoliticaVisibilidadLabor.php` | RQ-LAB-17 |
| `Application/Contracts` | `UnidadTrabajo.php`, `RegistroAuditoria.php`, `Reloj.php`, `PasarelaCampania.php` | `PasarelaCampania::consultarEstado(idCampania): EstadoCampaniaConsultado` o `CampaniaNoDisponible` |
| `Application/UseCases/ScheduleFieldTask` | `ProgramarLaborCasoUso.php`, `ProgramarLaborEntrada.php` | |
| `Application/UseCases/RegisterFieldTask` | `RegistrarLaborCasoUso.php`, `RealizarLaborCasoUso.php` y sus entradas | Idempotencia, permisos por operación, validación de campaña, guardado y auditoría |
| `Application/UseCases/RevalidateCampaign` | `RevalidarCampaniasCasoUso.php` | RQ-LAB-10 |
| `Application/UseCases/QueryFieldTasks` | `ConsultarLaboresCasoUso.php` | Detalle y listado con visibilidad |
| `InterfaceAdapters/Http` | `LaborControlador.php`, `Requests/`, `Resources/LaborRecurso.php`, `Middleware/` | Traduce HTTP ↔ caso de uso |
| `InterfaceAdapters/Console` | `CrearTablasComando.php`, `RevalidarCampaniasComando.php` | `dynamodb:crear-tablas`, `labores:revalidar-campanias` (cada minuto en `routes/console.php`, `withoutOverlapping`) |
| `Infrastructure/Persistence/DynamoDb` | `ClienteDynamoDb.php`, `UnidadTrabajoDynamo.php`, `RepositorioLaborDynamo.php`, `RegistroAuditoriaDynamo.php`, `Mappers/LaborMapper.php` | 2.1 y 2.3 |
| `Infrastructure/Http` | `ClienteServicioGestion.php`, `TokenCuentaServicio.php` | README D-12, con la tabla de RQ-LAB-05 |

**Flujo de `RegistrarLaborCasoUso`:**

```text
1. Permiso según la operación (RQ-LAB-02).
2. Huella del contenido + sub.
3. Si existe la labor con id = idOperacion → misma huella: devolver actual (repetida); otra: CONFLICTO_IDEMPOTENCIA.
4. Reglas del dominio (RQ-LAB-03).
5. pasarelaCampania.consultarEstado(idCampania) → válida / error 404-422 / no disponible.
6. UnidadTrabajo: Put labor (attribute_not_exists(id)) + auditoría.
   ConflictoEscritura en la labor → releer y volver al paso 3 (otra solicitud ganó la carrera).
7. Devolver la labor (nueva).
```

`RealizarLaborCasoUso` es igual, pero el paso 3 compara `id_operacion_realizacion` y el paso 6 es un `Update` condicionado a `estado = PROGRAMADA AND version = :v`; si la condición falla y la labor tiene ese `id_operacion_realizacion`, se trata como repetición, y si no, `LABOR_NO_PROGRAMADA`.

**Revalidación:** `Query` de `gsi_validacion_pendiente` con `fecha_proximo_validacion <= ahora` (hasta 100 por ejecución); por cada labor, consulta la campaña y aplica `aplicarValidacion` con un `Update` condicionado a `version`. Si la condición falla, otra ejecución ya la procesó y se sigue con la siguiente.

Ajustes respecto del plan original:

- Versiones fijadas al crear el proyecto: Laravel 13.39, Pest 4.7 (PHPUnit 12) y `firebase/php-jwt` 7.2. La serie 6.x tiene un aviso de seguridad (PKSA-y2cr-5h3j-g3ys) y Composer no la instala.
- El listado usa un puerto de lectura propio, `ConsultaLabores` (`Application/Contracts`), en lugar de ampliar `RepositorioLabor`, porque `FiltroLabores` y `Pagina` son tipos de Application y el repositorio está en Domain. `RepositorioLaborDynamo` implementa los dos.
- `CrearTablasComando` vive en `Infrastructure/Persistence/DynamoDb/Console`, no en `InterfaceAdapters/Console`: solo maneja el esquema de DynamoDB y desde InterfaceAdapters violaría la regla de dependencias.
- `ExigirJsonValido` (middleware del grupo de la API) rechaza con `400` un cuerpo JSON mal formado: Laravel lo ignoraría y respondería otro error.
- Un `id` que no es UUID en la ruta (`/labores/abc`) no coincide con la ruta y responde `404 RECURSO_NO_ENCONTRADO`; los UUID inválidos del cuerpo o de la consulta responden `400`.
- `ClienteServicioGestion` trata un `404` como "campaña inexistente" solo si el cuerpo trae `CAMPANIA_NO_ENCONTRADA`; un `404` del Gateway (por ejemplo, ruta sin configurar) cuenta como "no disponible". Un `401` o `403` de gestión borra el token en caché.
- El tiempo límite de 2 s se configura en el cliente HTTP (`GESTION_TIEMPO_LIMITE_SEGUNDOS`); los tests simulan su efecto con una `ConnectionException`, no esperan 2 s reales.
- `ValidadorEntorno` solo corre en solicitudes HTTP y en los comandos propios (`dynamodb:`, `labores:`, `schedule:`…), para que `composer install` (que ejecuta `package:discover`) funcione sin variables en la construcción de la imagen.
- La imagen escucha en el puerto 8080 con el usuario `www-data` (Apache no puede abrir el 80 sin root).
- `.env.testing` (solo comentarios) se versiona para que Laravel no busque `.env` en los tests; el `.gitignore` raíz tiene la excepción. Los avisos de `phpdotenv` por la falta de `.env` hacían ruido en cada test.
- `EnParalelo` termina cada proceso hijo con `SIGKILL` después de escribir su resultado, para que no ejecute las funciones de cierre de PHPUnit ni el borrado de tablas del proceso padre.
- El healthcheck de `localstack` en `docker-compose.yml` usaba `curl`, que la imagen `localstack/localstack:latest` ya no trae; ahora usa Python. Sin ese cambio, el perfil `operaciones` no arrancaba.
- El workflow levanta DynamoDB Local y RabbitMQ; LocalStack se agrega en `spec-incidencias.md` (T02), la primera que usa S3, junto con el secreto `LOCALSTACK_AUTH_TOKEN`, para que el pipeline no falle antes de necesitarlo.

## 2.5 Tests

| Tipo | Archivo | Qué verifica |
|---|---|---|
| Unitario | `tests/Unit/Domain/Shared/CantidadTest.php`, `HuellaTest.php` | ≤ 0, escala 3, comparación exacta; misma huella con distinto orden de campos y espacios, distinta con otro `sub` |
| Unitario | `tests/Unit/Domain/FieldTask/LaborAgricolaTest.php` | Estado inicial de RQ-LAB-06, fechas, realización solo desde `PROGRAMADA`, `aplicarValidacion` en cada caso, `fechaReferencia` |
| Unitario | `tests/Unit/Domain/FieldTask/PoliticaVisibilidadLaborTest.php` | RQ-LAB-17 con roles combinados |
| Unitario | `tests/Unit/Application/RegistrarLaborCasoUsoTest.php`, `RealizarLaborCasoUsoTest.php`, `RevalidarCampaniasCasoUsoTest.php` | Con dobles: repetición, conflicto, carrera perdida, cada fila de RQ-LAB-05, espera creciente |
| Integración | `tests/Integration/Http/LaboresTest.php` | Historias 1, 2 y 5 con DynamoDB Local y gestión simulada, con auditoría |
| Integración | `tests/Integration/Http/IdempotenciaLaboresTest.php` | Historia 3, incluidos 20 envíos simultáneos (CE-LAB-02, con `EnParalelo` sobre el caso de uso) y dos realizaciones simultáneas con distinto `idOperacion` |
| Integración | `tests/Integration/Console/RevalidarCampaniasTest.php` | Historia 4 con reloj fijo (CE-LAB-03) |
| Integración | `tests/Integration/Http/LaboresRendimientoTest.php` | 1.000 labores, listado y detalle en menos de 3 s (CE-LAB-04) |
| Integración | `tests/Integration/Http/SeguridadTest.php` | Sin token → 401; firma, `iss`, `aud` o `exp` inválidos → 401; rol sin permiso → 403; `/salud` y `/api-docs` sin token; `X-Correlation-Id` en 401 y 403 |
| Integración | `tests/Integration/Http/ErroresTest.php` | Formato común en 400 (JSON mal formado, UUID inválido), 404 de ruta, 405 y 500 |
| Integración | `tests/Integration/Http/SaludTest.php` | Liveness y readiness `UP`; readiness `503` con DynamoDB inalcanzable |
| Integración | `tests/Integration/Persistence/UnidadTrabajoTest.php` | Escritura atómica de labor y auditoría; una condición fallida no escribe nada |
| Integración | `tests/Integration/Http/ClienteServicioGestionTest.php` | Token en caché, tiempo límite de 2 s, cada fila de RQ-LAB-05 con `Http::fake()` |
| Integración | `tests/Integration/OpenApiTest.php` | Toda ruta documentada |

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

## Fase 0 — Base del servicio

- [x] **T01** — Crear el proyecto Laravel, quitar lo que no se usa, crear las carpetas de la constitución y agregar las dependencias de 2.1. *Hecho cuando:* `composer install` y `php artisan about` funcionan con la imagen de desarrollo.
- [x] **T02** — Implementar la configuración, `ValidadorEntorno`, `ClienteDynamoDb`, `tablas.json` (solo `registros_auditoria` y `labores`), `dynamodb:crear-tablas` y `UnidadTrabajoDynamo`. *Hecho cuando:* pasa `UnidadTrabajoTest.php` y el comando crea las tablas en el DynamoDB de Docker Compose dos veces sin error.
- [x] **T03** — Implementar las rutas de salud. *Hecho cuando:* pasa `SaludTest.php`.
- [x] **T04** — Implementar `ValidarJwt`, `ProveedorClavesJwks`, `RequerirRol` y el soporte de tokens de prueba. *Hecho cuando:* pasa `SeguridadTest.php`.
- [x] **T05** [P] — Implementar `ExcepcionDominio` y el render de errores. *Hecho cuando:* pasa `ErroresTest.php`.
- [x] **T06** [P] — Implementar `IdCorrelacion` y el log JSON. *Hecho cuando:* la respuesta devuelve el `X-Correlation-Id` recibido o uno generado, y aparece en los logs.
- [x] **T07** — Implementar `RegistroAuditoriaDynamo`, `Reloj`, `CodificadorCursor`, `tests/bootstrap.php`, `EnParalelo` y `openapi.yaml` con `/salud`. *Hecho cuando:* pasa `OpenApiTest.php`.
- [x] **T08** [P] — Escribir el `Dockerfile`, ajustar `docker/laravel/Dockerfile` y `docker-compose.yml` (2.1) y crear `.github/workflows/servicio-operaciones.yml`. *Hecho cuando:* `docker compose --profile operaciones up -d` deja el servicio respondiendo `/salud` y el pipeline corre en verde. Verificado en local: el perfil arranca sano, el programador ejecuta `labores:revalidar-campanias` cada minuto, la imagen de producción responde `/salud/liveness`, y los pasos del pipeline (Pint, Pest con cobertura y `docker build`) pasan. Pipeline en verde en GitHub Actions (2026-11-03).

## Fase 1 — Labores

- [x] **T09** — Crear `Cantidad`, `Huella`, `LaborAgricola` y sus enumeraciones, con sus tests unitarios.
- [x] **T10** — Implementar `RepositorioLaborDynamo`, su mapper y los índices de 2.3.
- [x] **T11** — Implementar `ClienteServicioGestion` y `TokenCuentaServicio`. *Hecho cuando:* pasa `ClienteServicioGestionTest.php`.
- [x] **T12** — Implementar `ProgramarLaborCasoUso`, `RegistrarLaborCasoUso` y `POST /labores`. *Hecho cuando:* pasan la Historia 1, los escenarios 1 a 3 de la Historia 2 y la Historia 3 (salvo el escenario 6).
- [x] **T13** — Implementar `RealizarLaborCasoUso` y `POST /labores/{id}/realizacion`. *Hecho cuando:* pasan los escenarios 4 a 6 de la Historia 2 y el escenario 6 de la Historia 3.
- [x] **T14** — Implementar la validación diferida, `RevalidarCampaniasCasoUso` y el comando programado. *Hecho cuando:* pasa `RevalidarCampaniasTest.php`.
- [x] **T15** — Implementar `ConsultarLaboresCasoUso` y los dos `GET`, con la visibilidad. *Hecho cuando:* pasa la Historia 5.
- [x] **T16** [P] — Escribir `IdempotenciaLaboresTest.php` (incluido CE-LAB-02) y `LaboresRendimientoTest.php` (CE-LAB-04).
- [x] **T17** — Documentar en `openapi.yaml` los cuatro endpoints con sus errores.
- [x] **T18** — Verificación final: `vendor/bin/pest --coverage --min=80` en verde y criterios CE-LAB-01 a CE-LAB-05 cubiertos por al menos un test. Resultado: 174 tests, cobertura de `Domain` y `Application` 99,1 %. Listado de 100 labores sobre 1.000 en 0,07 s y detalle en 0,01 s (CE-LAB-04).
