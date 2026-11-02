# Constitución — Servicio de Operaciones de Campo (`servicio-operaciones`)

> Reglas no negociables de este microservicio. Prevalecen sobre specs, planes y tareas.
> Si una spec contradice esta constitución, se corrige la spec o se enmienda la constitución; nunca se ignora.
> Las secciones marcadas con **[común]** son idénticas en los cuatro microservicios y solo se cambian en los cuatro a la vez. Excepción: la tabla «Permisos de este servicio» y el «Glosario de este servicio» son propios de cada microservicio y se enmiendan sin tocar los demás.

## 1. Propósito y límites

**Responsable de:**
- Labores agrícolas: programación y registro como realizadas, con sus consumos de insumos.
- Incidencias con fotografía (almacenada en S3) y, opcionalmente, el resultado de clasificación por IA.
- Recepción de operaciones offline desde Vue.js y Flutter, con idempotencia por UUID.
- **Coordinación (orquestación) de la Saga** labor → descuento de insumos → registro de costo.
- Consultas de labores e incidencias para n8n, GraphQL e `servicio-ia`.

**No es responsable de:**
- Stock de insumos → `servicio-inventario`.
- Costos e indicadores de campaña → `servicio-gestion`.
- Clasificación de imágenes → dispositivo (offline) o `servicio-ia` (online). Este servicio solo guarda el resultado.
- Envío de correos y recordatorios → n8n.
- Usuarios y roles → Keycloak.

**Fuera del alcance del sistema:** módulo de incidencias con seguimiento de acciones correctivas. El modo offline se limita a labores, incidencias y clasificación de imágenes.

**Trazabilidad:** CU-10 a CU-13 · RF-11 a RF-17 · RN-06 a RN-12 · RNF-09, RNF-10, RNF-22.

## 2. Stack

- PHP 8.3+ con Laravel (versión fijada en `composer.json`).
- Amazon DynamoDB y Amazon S3 mediante AWS SDK para PHP. No se usa Eloquent.
- RabbitMQ mediante `php-amqplib` o el paquete que apruebe el plan.
- Tests: Pest o PHPUnit, con DynamoDB Local, RabbitMQ y LocalStack (S3) en contenedores.
- Documentación de API: OpenAPI mantenida junto al código.
- Despliegue: imagen Docker en Amazon ECS con Fargate.
- No se introducen lenguajes, frameworks ni bases de datos nuevas sin una enmienda.

## 3. Arquitectura (Clean Architecture)

- Capas, de adentro hacia afuera:
  - `Domain`: entidades (`LaborAgricola`, `ConsumoInsumo`, `Incidencia`, `Saga`), enumeraciones y reglas.
  - `Application`: casos de uso e interfaces de gateways (repositorios, almacenamiento de archivos, mensajería, cliente de `servicio-gestion`).
  - `InterfaceAdapters`: controladores HTTP, presenters y consumidores de mensajes.
  - `Infrastructure`: repositorios DynamoDB, almacenamiento S3, publicador/consumidor RabbitMQ, cliente HTTP.
- Las dependencias apuntan solo hacia adentro. `Domain` y `Application` no usan facades, helpers ni clases de Laravel ni del AWS SDK.
- Laravel se limita a las capas externas: rutas, contenedor de dependencias, configuración y scheduler.
- La lógica de negocio solo vive en `Domain` y `Application`.
- Reglas del dominio:
  - Toda labor pertenece a una parcela y a una campaña (RN-06).
  - No se registran labores en campañas finalizadas (RN-06).
  - Una labor `PROGRAMADA` no descuenta insumos ni registra costos (RN-07).
  - Una labor realizada **sin insumos** pasa directo a `CONFIRMADA`, sin Saga (RN-07).
  - Una labor realizada **con insumos** queda `PENDIENTE` y activa la Saga (RN-07).
  - El responsable se toma del token (`sub` de Keycloak, más una copia del nombre); no es texto libre.
  - Los resultados de clasificación de IA se guardan como orientativos (RN-13).

### Estructura de directorios

```text
servicio-operaciones/
├── app/
│   ├── Domain/                                  # PHP puro, sin Laravel ni AWS SDK
│   │   ├── FieldTask/
│   │   │   ├── LaborAgricola.php
│   │   │   ├── EstadoLabor.php
│   │   │   ├── ConsumoInsumo.php
│   │   │   └── RepositorioLabor.php             # interfaz
│   │   ├── Incident/
│   │   │   ├── Incidencia.php
│   │   │   ├── TipoIncidencia.php
│   │   │   └── RepositorioIncidencia.php
│   │   ├── Saga/
│   │   │   ├── Saga.php
│   │   │   ├── PasoSaga.php
│   │   │   ├── EstadoSaga.php
│   │   │   └── RepositorioSaga.php
│   │   └── Shared/
│   │       ├── IdOperacion.php
│   │       └── ExcepcionDominio.php
│   ├── Application/
│   │   ├── UseCases/
│   │   │   ├── ScheduleFieldTask/
│   │   │   │   ├── ProgramarLaborCasoUso.php
│   │   │   │   └── ProgramarLaborEntrada.php
│   │   │   ├── RegisterFieldTask/
│   │   │   ├── RegisterIncident/
│   │   │   ├── SyncOfflineOperations/
│   │   │   └── Saga/
│   │   │       ├── IniciarSaga.php
│   │   │       ├── ManejarInsumosDescontados.php
│   │   │       ├── ManejarInsumosRechazados.php
│   │   │       ├── ManejarCostoRegistrado.php
│   │   │       ├── ManejarCostoRechazado.php
│   │   │       ├── ManejarCostoAnulado.php
│   │   │       ├── ManejarAnulacionRechazada.php
│   │   │       └── ReanudarSagasEstancadas.php
│   │   └── Contracts/                           # interfaces de gateways
│   │       ├── AlmacenIdempotencia.php
│   │       ├── PublicadorMensajes.php
│   │       ├── AlmacenamientoArchivos.php
│   │       ├── PasarelaCampania.php
│   │       ├── RegistroAuditoria.php
│   │       └── Reloj.php
│   ├── InterfaceAdapters/
│   │   ├── Http/
│   │   │   ├── Controllers/
│   │   │   │   ├── LaborControlador.php
│   │   │   │   ├── IncidenciaControlador.php
│   │   │   │   └── SincronizacionControlador.php
│   │   │   ├── Requests/                        # validación de entrada
│   │   │   ├── Resources/                       # presenters
│   │   │   └── Middleware/
│   │   │       ├── ValidarJwt.php
│   │   │       ├── RequerirRol.php
│   │   │       └── IdCorrelacion.php
│   │   ├── Messaging/
│   │   │   └── ConsumidorRespuestasSaga.php
│   │   └── Console/
│   │       ├── ConsumirMensajesComando.php
│   │       └── ReanudarSagasComando.php
│   └── Infrastructure/
│       ├── Persistence/DynamoDb/
│       │   ├── RepositorioLaborDynamo.php
│       │   ├── RepositorioIncidenciaDynamo.php
│       │   ├── RepositorioSagaDynamo.php
│       │   ├── AlmacenIdempotenciaDynamo.php
│       │   └── Mappers/
│       ├── Storage/
│       │   └── AlmacenamientoArchivosS3.php
│       ├── Messaging/
│       │   ├── ConexionRabbitMq.php
│       │   └── PublicadorRabbitMq.php
│       ├── Http/
│       │   └── ClienteServicioGestion.php           # implementa PasarelaCampania
│       └── Providers/
│           └── ProveedorDominio.php             # enlaza contratos con implementaciones
├── bootstrap/
├── config/
│   ├── aws.php
│   └── rabbitmq.php
├── database/dynamodb/
│   └── tablas.json                              # definición versionada de tablas
├── routes/
│   ├── api.php
│   └── console.php                              # scheduler
├── tests/
│   ├── Unit/
│   │   ├── Domain/
│   │   └── Application/
│   └── Integration/                             # DynamoDB Local, RabbitMQ, LocalStack
├── Dockerfile
├── composer.json
└── Constitucion.md
```

- Las carpetas `Domain`, `Application`, `InterfaceAdapters` e `Infrastructure` y su regla de dependencias son obligatorias. Los nombres concretos de archivos son de referencia y se definen en el plan.
- No existen `app/Models` ni lógica en las carpetas por defecto de Laravel; los providers propios viven en `Infrastructure/Providers` y se registran en `bootstrap/providers.php`.
- Cada caso de uso tiene su carpeta con el caso de uso y su objeto de entrada.
- Los tests replican la estructura de `app`.

## 4. Datos

- Este servicio es dueño exclusivo de sus tablas DynamoDB y de su bucket S3. Ningún otro servicio accede a ellos.
- Identificadores: UUID. El UUID de una operación offline se genera en el dispositivo.
- Los patrones de acceso a DynamoDB se definen en la spec antes de crear tablas o índices; la definición de tablas está versionada en el repositorio.
- Se guardan dos fechas: la de ejecución informada por el dispositivo y la de recepción en el servidor.
- Fotografías:
  - Bucket S3 privado. DynamoDB guarda la clave del objeto, nunca el binario ni una URL pública.
  - El acceso se da mediante URL prefirmadas de corta duración.
  - Solo se aceptan `.jpg` y `.png`, con un tamaño máximo definido en la spec.
- Las labores rechazadas o en revisión no se borran; quedan con su estado y motivo.
- Toda creación o modificación genera un registro de auditoría: usuario o servicio, acción, fecha y entidad.

## 5. Idempotencia y sincronización offline

- Toda operación de creación lleva un `idOperacion` (UUID generado en el dispositivo) (RN-10).
- La primera escritura usa una escritura condicional de DynamoDB (`attribute_not_exists`). Si el `idOperacion` ya existe, se devuelve el resultado guardado sin reprocesar.
- Si llega el mismo `idOperacion` con un contenido distinto, se responde `409 CONFLICTO_IDEMPOTENCIA`.
- Endpoint de sincronización por lotes:
  - Procesa las operaciones en orden cronológico según la fecha de creación en el dispositivo (RN-11).
  - Devuelve el resultado de cada operación por separado: `SINCRONIZADA` o `ERROR` con `codigo` y `mensaje` (RF-17, RNF-14).
  - El fallo de una operación no aborta el lote.
- La validación de que la campaña existe y no está finalizada se hace consultando a `servicio-gestion`. Si no responde, la labor se guarda como `PENDIENTE` y la validación se reintenta; nunca se pierde la operación (RNF-09).

## 6. Saga (orquestación)

- Este servicio es el **único coordinador** de la Saga. Los pasos se comunican solo por RabbitMQ, nunca accediendo a otra base de datos.
- Flujo:
  1. Registrar la labor como `PENDIENTE`.
  2. Enviar `DescontarInsumos` a `servicio-inventario`.
     - `InsumosRechazados` → labor `RECHAZADA`, sin más pasos (RN-08).
  3. Con `InsumosDescontados`, enviar `RegistrarCostoCampania` a `servicio-gestion` con el costo informado por inventario. Si el costo es `0.00`, no hay nada que registrar: la labor pasa a `CONFIRMADA` sin este paso.
     - `CostoCampaniaRegistrado` → labor `CONFIRMADA`.
     - `CostoCampaniaRechazado` → enviar `RestaurarInsumos`; labor `PENDIENTE_REVISION` (RN-08).
     - Tiempo límite o reintentos agotados sin respuesta → labor `PENDIENTE_REVISION` y enviar `AnularCostoCampania` a `servicio-gestion` (RN-08). Los insumos todavía no se restauran. La anulación es necesaria porque el costo pudo registrarse aunque la respuesta no haya llegado, o registrarse más tarde si el comando seguía en la cola.
     - `CostoCampaniaAnulado` → enviar `RestaurarInsumos` a `servicio-inventario`; la labor sigue `PENDIENTE_REVISION`.
     - `AnulacionCostoRechazada` (la campaña ya estaba finalizada con el costo registrado) → no se restauran los insumos: el descuento y el costo siguen vigentes y son coherentes entre sí. La labor sigue `PENDIENTE_REVISION` con ese motivo, para que la resuelva el administrador.
     - Sin respuesta a `AnularCostoCampania` → se reintenta con el mismo `idSaga` y los insumos no se restauran hasta conocer el resultado.
- El estado de cada Saga se persiste en DynamoDB **antes** de enviar el siguiente comando: `idSaga`, `idLabor`, estado general y, por paso, estado, intentos, fecha y error (RNF-22).
- `idSaga` es el `idCorrelacion` de todos los mensajes de esa Saga.
- Cada paso tiene un tiempo límite configurable. Agotados los reintentos, la labor queda `PENDIENTE_REVISION` y se envían las compensaciones de todos los pasos que pudieron aplicarse —incluido el paso cuyo resultado se desconoce— en orden inverso y una a la vez: cada una espera el resultado de la anterior.
- Recuperación (RNF-10): una tarea programada retoma las Sagas en estado no terminal cuya última actualización superó el tiempo límite.
- Todas las compensaciones son idempotentes (RN-09).

## 7. Comunicación

- API REST con prefijo de servicio y versión: `/api/operaciones/v1/...`. El API Gateway rutea todo `/api/operaciones/**` a este servicio, y solo se accede a través de él.
- El contrato OpenAPI es la fuente de verdad. Un cambio incompatible exige una nueva versión (`/api/operaciones/v2/...`); la anterior se mantiene mientras haya clientes que la usen (incluida la app Flutter instalada).
- Publica el evento `operaciones.incidencia.registrada` (tipo, parcela, campaña, fecha) para que n8n notifique según prioridad (RF-31).
- Expone consultas de labores por estado y rango de fechas (recordatorios de n8n, RF-30) y de incidencias, para n8n, GraphQL e `servicio-ia`.
- Única llamada síncrona permitida a otro servicio: la consulta de campaña a `servicio-gestion`, con tiempo límite y manejo de fallo.

## 8. Calidad

- Todo endpoint tiene tests de integración.
- Toda regla del dominio tiene al menos un test unitario.
- Tests obligatorios de idempotencia: operación nueva, operación repetida y mismo UUID con contenido distinto.
- Tests obligatorios de la Saga: éxito, costo total `0.00` sin registro de costo, stock insuficiente, fallo al registrar costo con compensación, tiempo límite en el registro de costo con anulación seguida de restauración, anulación rechazada sin restauración, anulación sin respuesta sin restauración, mensaje duplicado y recuperación tras reinicio del coordinador.
- Test de sincronización por lotes con resultados mixtos y orden cronológico.
- Cobertura mínima: 80 % de líneas en `Domain` y `Application`. El pipeline falla si baja.
- Ninguna tarea se da por terminada con tests fallando.
- Las consultas REST responden en menos de 3 s (RNF-05).

## 9. Seguridad [común]

- Toda ruta, excepto `/salud` y la documentación OpenAPI, exige un JWT emitido por Keycloak.
- Se validan firma (JWKS de Keycloak), emisor (`iss`), audiencia (`aud`) y vigencia (`exp`) en cada solicitud (RNF-02).
- Los permisos se verifican en el servidor, nunca solo en el frontend (RN-16). Roles: `administrador`, `tecnico_campo`, `gerencia`, más cuentas de servicio por cliente (n8n, `servicio-ia`, GraphQL, otros microservicios). Un usuario puede tener más de un rol.
- El servicio no gestiona contraseñas ni credenciales de usuario; eso es exclusivo de Keycloak.
- Secretos y configuración solo por variables de entorno o gestor de secretos; nunca en el repositorio (RNF-03).
- Comunicación externa por HTTPS/TLS; conexión a RabbitMQ por AMQPS (RNF-01), salvo la excepción local indicada en Mensajería.
- Los logs no contienen tokens, secretos ni datos personales más allá del ID de usuario.

**Permisos de este servicio:**

| Operación | Roles |
|---|---|
| Registrar labores, incidencias y sincronizar | `tecnico_campo` |
| Programar labores | `administrador`, `tecnico_campo` |
| Consultar labores, incidencias y estado de Sagas | `administrador`, `gerencia` |
| Consultar labores programadas y las labores e incidencias que registró el propio usuario | `tecnico_campo` |
| Resolver labores `PENDIENTE_REVISION` | `administrador` |
| Lectura para integración | cuentas de servicio autorizadas |

## 10. Mensajería [común]

- Broker: RabbitMQ sobre AMQPS. Solo en desarrollo local y tests con contenedores se permite AMQP sin TLS, dentro de la red de Docker.
- Los comandos van a la cola del servicio destino; los eventos se publican en un exchange de tipo topic con routing key `<servicio>.<entidad>.<evento>` (por ejemplo, `inventario.stock.bajo`).
- Todo mensaje usa este sobre:

```json
{
  "idMensaje": "uuid",
  "idCorrelacion": "uuid (el idSaga en mensajes de Saga)",
  "tipo": "DescontarInsumos",
  "version": 1,
  "fechaOcurrencia": "2026-10-31T12:00:00Z",
  "origen": "servicio-operaciones",
  "datos": {}
}
```

- Todo consumidor es idempotente por `idMensaje` (y por `idSaga` en comandos de Saga).
- Un mensaje que falla se reintenta 3 veces con espera creciente y luego va a una Dead Letter Queue (RNF-11). Nunca se descarta en silencio.
- Un cambio incompatible en un mensaje incrementa `version`; los consumidores aceptan la versión anterior mientras dure la transición.

## 11. Errores y observabilidad [común]

- Toda respuesta de error usa este formato:

```json
{
  "codigo": "CAMPANIA_FINALIZADA",
  "mensaje": "No se pueden registrar labores en una campaña finalizada.",
  "detalles": [],
  "idCorrelacion": "uuid"
}
```

- `codigo` en mayúsculas con guion bajo, estable y documentado en OpenAPI. `mensaje` apto para mostrar al usuario.
- Códigos HTTP: 400 validación · 401 sin autenticación · 403 sin permiso · 404 no encontrado · 409 conflicto o duplicado · 422 regla de negocio violada.
- Logs estructurados en JSON con `idCorrelacion`. El header `X-Correlation-Id` se recibe del Gateway (o se genera si falta) y se propaga a respuestas y mensajes (RNF-22).
- Endpoint `/salud` con liveness y readiness (incluye DynamoDB y RabbitMQ).
- La caída de otro microservicio no impide que este siga atendiendo sus propias operaciones (RNF-08).

## 12. Simplicidad

- No se construye nada que no esté en una spec.
- Cada dependencia nueva se justifica en el plan.
- Sin abstracciones "por si acaso": una interfaz de gateway existe porque hay al menos una implementación real.

## 13. Convenciones [común]

- Todo nombre se escribe en español y sin tildes ni ñ (`Campania`, `Danio`): archivos, clases, interfaces, tipos, métodos, variables, rutas, campos JSON, tablas, columnas, colecciones, valores de enumeraciones, códigos de error, tipos de mensaje, routing keys y nombres de servicio.
- Estilo de escritura:
  - Clases, interfaces y tipos en PascalCase (`CostoCampania`).
  - Métodos, variables y campos JSON en camelCase (`fechaInicio`, `cambiarEstado()`). En Python el código usa snake_case (`fecha_inicio`), pero el JSON expuesto sigue en camelCase.
  - Tablas y columnas en snake_case (`costo_campania`, `fecha_inicio`).
  - Rutas en minúsculas, con guiones y recursos en plural (`/api/gestion/v1/campanias/{id}/costos`).
  - Valores de enumeraciones y códigos de error en mayúsculas con guion bajo (`EN_CURSO`, `STOCK_INSUFICIENTE`).
  - Routing keys en minúsculas separadas por puntos (`inventario.stock.bajo`).
- Excepciones, que se quedan en inglés:
  - Carpetas (`domain`, `application`, `adapters`, `infrastructure`…).
  - Archivos y nombres impuestos por frameworks o herramientas (`pom.xml`, `main.ts`, `app.module.ts`, `application.yml`, `routes/api.php`, `main.py`, `__init__.py`, `pyproject.toml`, `Dockerfile`, métodos derivados de Spring Data como `findByEstado`).
  - Headers HTTP estándar (`Authorization`, `X-Correlation-Id`) y claims de JWT (`sub`, `iss`, `aud`, `exp`).
  - Términos técnicos sin traducción habitual (`stock`, `token`, `saga`, `items`).
- Documentación, specs y mensajes al usuario en español.
- Commits con Conventional Commits (tipo en inglés, descripción en español).
- Fechas y horas en ISO 8601 UTC. Las fechas sin hora (por ejemplo, inicio y fin de campaña) se expresan como `AAAA-MM-DD` (`LocalDate` en Java).
- Los valores decimales (montos, cantidades, superficies, producción) se transmiten en JSON, tanto en REST como en mensajes, como texto con punto decimal y sin separador de miles (`"820.50"`); nunca como número JSON, para no perder precisión entre lenguajes.
- El sistema vive en un solo repositorio. Cada microservicio tiene su propio pipeline en GitHub Actions: build, tests e imagen Docker (RNF-20). Cada pipeline está en `.github/workflows/<servicio>.yml`, en la raíz, y se filtra por `servicios/<servicio>/**`.
- Todo el sistema se levanta en local con Docker Compose (RNF-19).

### Glosario de este servicio

| Concepto | Clase / archivo | Ruta REST | Tabla |
|---|---|---|---|
| Labor agrícola | `LaborAgricola` | `/labores` | `labores` |
| Consumo de insumo | `ConsumoInsumo` | dentro de la labor | — |
| Incidencia | `Incidencia` | `/incidencias` | `incidencias` |
| Sincronización | — | `/sincronizacion` | — |
| Saga | `Saga` | `/sagas` | `sagas` |
| UUID de operación | `IdOperacion` | campo `idOperacion` | — |

| Enumeración | Valores |
|---|---|
| `EstadoLabor` | `PROGRAMADA` / `PENDIENTE` / `CONFIRMADA` / `RECHAZADA` / `PENDIENTE_REVISION` |
| `TipoIncidencia` | `PLAGA` / `ENFERMEDAD` / `DANIO` / `OTRO` |
| Resultado de sincronización | `SINCRONIZADA` / `ERROR` |

## Enmiendas

- Versión: 2.5.0 (2026-11-01)
- Cambiar una regla requiere actualizar este documento, registrar el motivo y subir la versión:
  - MAJOR: se elimina o redefine una regla.
  - MINOR: se agrega una regla.
  - PATCH: aclaraciones de redacción sin cambio de significado.
- Un cambio en una sección **[común]** se aplica a los cuatro microservicios en la misma versión.

| Versión | Fecha | Motivo |
|---|---|---|
| 1.0.0 | 2026-10-31 | Versión inicial. |
| 2.0.0 | 2026-11-01 | Todo nombre pasa a español (rutas, campos, enumeraciones, códigos de error, mensajes, eventos y servicios). Rutas con prefijo de servicio y versión (`/api/<servicio>/v1/...`). Servicios renombrados a `servicio-*`. Health check en `/salud`. |
| 2.1.0 | 2026-11-01 | **[común]** Decimales como texto en JSON (REST y mensajes); fechas sin hora como `AAAA-MM-DD` en los cuatro servicios; la tabla de permisos y el glosario son propios de cada servicio. **Propio:** ante tiempo límite en el registro de costo, el coordinador envía `AnularCostoCampania` además de `RestaurarInsumos`; manejo de `AnulacionCostoRechazada`; tests de la Saga ampliados. Origen: spec 005 de `servicio-gestion`. |
| 2.3.0 | 2026-11-01 | **[común]** El sistema vive en un solo repositorio: cada pipeline está en `.github/workflows/<servicio>.yml`, en la raíz, y se filtra por `servicios/<servicio>/**`. Se permite AMQP sin TLS solo en desarrollo local y tests con contenedores. Los cuatro servicios quedan en la misma versión. **Propio:** `tecnico_campo` puede consultar las labores programadas y las labores e incidencias que registró. |
| 2.4.0 | 2026-11-01 | **Propio:** las compensaciones se envían en orden inverso y una a la vez. Ante tiempo límite en el registro de costo, `RestaurarInsumos` solo se envía después de `CostoCampaniaAnulado`, para que una `AnulacionCostoRechazada` no deje el stock restaurado con el costo vigente. Sin cambios comunes. |
| 2.5.0 | 2026-11-01 | **Propio:** con costo total `0.00` no se envía `RegistrarCostoCampania` y la labor pasa a `CONFIRMADA`, porque `servicio-gestion` solo admite montos mayores a 0. Sin cambios comunes. |
