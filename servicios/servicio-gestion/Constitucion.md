# Constitución — Servicio de Gestión Agrícola (`servicio-gestion`)

> Reglas no negociables de este microservicio. Prevalecen sobre specs, planes y tareas.
> Si una spec contradice esta constitución, se corrige la spec o se enmienda la constitución; nunca se ignora.
> Las secciones marcadas con **[común]** son idénticas en los cuatro microservicios y solo se cambian en los cuatro a la vez. Excepción: la tabla «Permisos de este servicio» y el «Glosario de este servicio» son propios de cada microservicio y se enmiendan sin tocar los demás.

## 1. Propósito y límites

**Responsable de:**
- Parcelas, cultivos y campañas agrícolas (incluido el ciclo de estado de la campaña).
- Costos de campaña, tanto manuales como los recibidos desde la Saga.
- Producción de la campaña, registrada antes de finalizarla.
- Indicadores de rendimiento por hectárea y costo por hectárea.
- Datos históricos de campañas para el servicio de IA (solo lectura).

**No es responsable de:**
- Labores e incidencias → `servicio-operaciones`.
- Insumos, stock y movimientos → `servicio-inventario`.
- Usuarios, contraseñas y roles → Keycloak.
- Predicciones, agrupaciones y reportes → `servicio-ia`.

**Fuera del alcance del sistema:** ventas, rentabilidad, proveedores, historial avanzado de uso de parcelas y comparación compleja entre campañas.

**Trazabilidad:** CU-01 a CU-05 · RF-01 a RF-06 · RN-01, RN-02, RN-03, RN-06.

## 2. Stack

- Java 21 (LTS) + Spring Boot 3: Spring Web, Spring Data JPA, Spring Security (OAuth2 Resource Server), Spring AMQP, Actuator.
- PostgreSQL (Azure Database for PostgreSQL). Migraciones con Flyway.
- Tests: JUnit 5 + Testcontainers (PostgreSQL y RabbitMQ).
- Documentación de API: springdoc-openapi.
- Despliegue: imagen Docker en Azure Container Apps.
- No se introducen lenguajes, frameworks ni bases de datos nuevas sin una enmienda.

## 3. Arquitectura (DDD)

- Capas: `domain` → `application` → `infrastructure` / `interfaces`. Las dependencias apuntan solo hacia `domain`.
- `domain` es Java puro: sin anotaciones de Spring, JPA ni Jackson. Las entidades JPA viven en `infrastructure` y se mapean desde/hacia el dominio.
- Agregados:
  - `Parcela`.
  - `Cultivo`.
  - `Campania`, raíz que contiene sus `CostoCampania` y su `ProduccionCampania`.
- Los agregados se referencian entre sí solo por ID.
- Las invariantes se validan dentro del agregado, nunca en el controlador:
  - Superficie de la parcela > 0 (RN-01).
  - Fecha de fin posterior a la de inicio (RN-01).
  - Transiciones de estado solo `PLANIFICADA → EN_CURSO → FINALIZADA`; no se retrocede (RN-02).
  - Para pasar a `FINALIZADA`, la campaña debe tener producción registrada.
  - Una campaña `FINALIZADA` no admite nuevos costos ni modificaciones.
  - Un costo originado por la Saga no se modifica ni se elimina por la API; solo se anula por compensación.
- Una parcela tiene como máximo una campaña `EN_CURSO`. Como la regla abarca varias campañas, no puede validarse dentro de un agregado: se valida en el caso de uso que cambia el estado y se garantiza ante concurrencia con un índice único en la base de datos.
- La lógica de negocio vive en el dominio y en los casos de uso de `application` (un caso de uso por operación). Los controladores solo traducen HTTP ↔ caso de uso.
- Interfaces de repositorio en `domain`; implementaciones en `infrastructure`.
- Indicadores (RN-03): solo se calculan si existen producción y al menos un costo vigente. Si faltan datos, la API devuelve el indicador como `null` con su motivo; nunca `0`.

### Estructura de directorios

```text
servicio-gestion/
├── src/main/java/com/agrosystem/gestion/
│   ├── AplicacionGestion.java
│   ├── domain/                              # Java puro, sin Spring ni JPA
│   │   ├── plot/
│   │   │   ├── Parcela.java
│   │   │   └── RepositorioParcela.java      # interfaz (puerto)
│   │   ├── crop/
│   │   │   ├── Cultivo.java
│   │   │   └── RepositorioCultivo.java
│   │   ├── campaign/
│   │   │   ├── Campania.java                # raíz del agregado
│   │   │   ├── CostoCampania.java
│   │   │   ├── ProduccionCampania.java
│   │   │   ├── EstadoCampania.java
│   │   │   ├── CategoriaCosto.java
│   │   │   ├── OrigenCosto.java
│   │   │   ├── IndicadoresCampania.java
│   │   │   └── RepositorioCampania.java
│   │   ├── saga/
│   │   │   ├── SagaProcesada.java
│   │   │   └── RepositorioSagaProcesada.java
│   │   └── shared/
│   │       ├── Dinero.java
│   │       ├── Hectareas.java
│   │       └── ExcepcionDominio.java
│   ├── application/                         # un caso de uso por operación
│   │   ├── plot/
│   │   │   ├── CrearParcelaCasoUso.java
│   │   │   └── ActualizarParcelaCasoUso.java
│   │   ├── crop/
│   │   │   └── CrearCultivoCasoUso.java
│   │   ├── campaign/
│   │   │   ├── CrearCampaniaCasoUso.java
│   │   │   ├── CambiarEstadoCampaniaCasoUso.java
│   │   │   ├── RegistrarCostoManualCasoUso.java
│   │   │   ├── RegistrarCostoSagaCasoUso.java
│   │   │   ├── AnularCostoSagaCasoUso.java
│   │   │   ├── RegistrarProduccionCasoUso.java
│   │   │   └── ConsultarIndicadoresCasoUso.java
│   │   └── port/
│   │       ├── PublicadorMensajes.java
│   │       └── RegistroAuditoria.java
│   ├── infrastructure/
│   │   ├── persistence/
│   │   │   ├── entity/                      # entidades JPA
│   │   │   │   ├── ParcelaEntidad.java
│   │   │   │   ├── CampaniaEntidad.java
│   │   │   │   └── CostoCampaniaEntidad.java
│   │   │   ├── mapper/
│   │   │   │   └── MapeadorCampania.java
│   │   │   ├── CampaniaSpringData.java
│   │   │   └── RepositorioCampaniaJpa.java  # implementa RepositorioCampania
│   │   ├── messaging/
│   │   │   ├── ConfiguracionRabbit.java
│   │   │   └── PublicadorMensajesRabbit.java
│   │   ├── security/
│   │   │   ├── ConfiguracionSeguridad.java
│   │   │   └── ConversorRolesKeycloak.java
│   │   └── audit/
│   │       └── RegistroAuditoriaJpa.java
│   └── interfaces/
│       ├── rest/
│       │   ├── ParcelaControlador.java
│       │   ├── CultivoControlador.java
│       │   ├── CampaniaControlador.java
│       │   ├── dto/
│       │   └── error/
│       │       ├── RespuestaError.java
│       │       └── ManejadorGlobalExcepciones.java
│       └── messaging/
│           ├── ConsumidorRegistrarCosto.java
│           └── ConsumidorAnularCosto.java
├── src/main/resources/
│   ├── application.yml
│   └── db/migration/
│       └── V1__crear_parcelas.sql
├── src/test/java/com/agrosystem/gestion/
│   ├── domain/                              # tests unitarios de invariantes
│   ├── application/
│   └── integration/                         # Testcontainers (sufijo IT, p. ej. CampaniaControladorIT.java)
├── Dockerfile
├── pom.xml
└── Constitucion.md
```

- Las carpetas de capa (`domain`, `application`, `infrastructure`, `interfaces`) y su regla de dependencias son obligatorias. Los nombres concretos de archivos son de referencia y se definen en el plan.
- Dentro de `domain` y `application` se organiza por agregado, no por tipo técnico.
- Los tests replican la estructura de `src/main`.

## 4. Datos

- Este servicio es dueño exclusivo de su base de datos. Ningún otro servicio la lee ni la escribe.
- Identificadores: UUID.
- Montos, superficies y producción: `BigDecimal` en Java y `NUMERIC` en PostgreSQL. Nunca `float` ni `double`.
- Moneda única para todo el sistema: boliviano (`BOB`), con 2 decimales. Superficie en hectáreas y producción en kilogramos; cada cultivo guarda su unidad de medida de producción (RF-02), hoy solo `KILOGRAMO`.
- Todo cambio de esquema va en una migración Flyway versionada. `ddl-auto` solo se permite en tests.
- Un costo originado por la Saga guarda `idSaga` y `idLabor`, con restricción `UNIQUE` sobre `idSaga`.
- Se registra cada `idSaga` procesado con su resultado (`REGISTRADO`, `RECHAZADO` o `ANULADO`), para garantizar la idempotencia y rechazar comandos que lleguen después de una anulación.
- Un costo de la Saga anulado no se borra: queda marcado como anulado y deja de contar en totales e indicadores.
- Toda creación o modificación genera un registro de auditoría: usuario o servicio, acción, fecha y entidad.
- No se borran físicamente campañas con costos registrados.

## 5. Comunicación

- API REST con prefijo de servicio y versión: `/api/gestion/v1/...`. El API Gateway rutea todo `/api/gestion/**` a este servicio, y solo se accede a través de él.
- El contrato OpenAPI es la fuente de verdad. Un cambio incompatible exige una nueva versión (`/api/gestion/v2/...`); la anterior se mantiene mientras haya clientes que la usen (incluida la app Flutter instalada).
- **Rol en la Saga: participante, no coordinador.**
  - Consume el comando `RegistrarCostoCampania` (`idSaga`, `idLabor`, `idCampania`, `monto`, `categoria = INSUMO`).
  - Responde con `CostoCampaniaRegistrado` o `CostoCampaniaRechazado`, con el mismo `idCorrelacion`.
  - Rechaza si la campaña no existe o está `FINALIZADA` (RN-06), o si el `idSaga` ya fue anulado (`SAGA_ANULADA`).
  - Es idempotente: un `idSaga` ya procesado devuelve el mismo resultado sin duplicar el costo.
  - Consume la compensación `AnularCostoCampania` (`idSaga`, `idLabor`, `idCampania`): anula el costo de ese `idSaga` y responde `CostoCampaniaAnulado`. Si la campaña ya está `FINALIZADA` y el costo está registrado, responde `AnulacionCostoRechazada` y el costo se conserva.
  - Una anulación sobre un `idSaga` sin costo registrado responde `CostoCampaniaAnulado` sin efectos y deja el `idSaga` marcado como anulado. La anulación es idempotente (RN-09).
  - Las respuestas se envían a la cola del coordinador (`servicio-operaciones`).
- Endpoints de solo lectura para otros consumidores:
  - Consulta de campaña con su estado (usada por `servicio-operaciones` para validar labores).
  - Consulta de parcelas y campañas no finalizadas para `tecnico_campo` (selección al registrar labores).
  - Indicadores para el servidor GraphQL.
  - Datos históricos de campañas para `servicio-ia` (MCP y entrenamiento, RF-18).
- Este servicio no llama de forma síncrona a otros microservicios.

## 6. Calidad

- Todo endpoint tiene tests de integración con Testcontainers.
- Toda invariante del dominio y la regla de una campaña `EN_CURSO` por parcela tienen al menos un test unitario.
- Los handlers de la Saga tienen tests para: éxito, rechazo, mensaje duplicado, anulación, anulación duplicada, anulación sin registro previo, anulación rechazada por campaña finalizada y registro tardío después de una anulación.
- Cobertura mínima: 80 % de líneas en `domain` y `application`, medida con JaCoCo. El pipeline falla si baja.
- Ninguna tarea se da por terminada con tests fallando.
- Las consultas REST responden en menos de 3 s (RNF-05).

## 7. Seguridad [común]

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
| Crear y modificar parcelas, cultivos, campañas, costos manuales y producción | `administrador` |
| Consultar parcelas, cultivos, campañas, costos, producción e indicadores | `administrador`, `gerencia` |
| Consultar parcelas y campañas no finalizadas, sin datos económicos (para registrar labores) | `tecnico_campo` |
| Lectura para integración | cuentas de servicio autorizadas |

## 8. Mensajería [común]

- Broker: RabbitMQ sobre AMQPS. Solo en desarrollo local y tests con contenedores se permite AMQP sin TLS, dentro de la red de Docker.
- Los comandos van a la cola del servicio destino; los eventos se publican en un exchange de tipo topic con routing key `<servicio>.<entidad>.<evento>` (por ejemplo, `inventario.stock.bajo`).
- Todo mensaje usa este sobre:

```json
{
  "idMensaje": "uuid",
  "idCorrelacion": "uuid (el idSaga en mensajes de Saga)",
  "tipo": "RegistrarCostoCampania",
  "version": 1,
  "fechaOcurrencia": "2026-10-31T12:00:00Z",
  "origen": "servicio-operaciones",
  "datos": {}
}
```

- Todo consumidor es idempotente por `idMensaje` (y por `idSaga` en comandos de Saga).
- Un mensaje que falla se reintenta 3 veces con espera creciente y luego va a una Dead Letter Queue (RNF-11). Nunca se descarta en silencio.
- Un cambio incompatible en un mensaje incrementa `version`; los consumidores aceptan la versión anterior mientras dure la transición.

## 9. Errores y observabilidad [común]

- Toda respuesta de error usa este formato:

```json
{
  "codigo": "CAMPANIA_FINALIZADA",
  "mensaje": "La campaña está finalizada y no admite cambios.",
  "detalles": [],
  "idCorrelacion": "uuid"
}
```

- `codigo` en mayúsculas con guion bajo, estable y documentado en OpenAPI. `mensaje` apto para mostrar al usuario.
- Códigos HTTP: 400 validación · 401 sin autenticación · 403 sin permiso · 404 no encontrado · 409 conflicto o duplicado · 422 regla de negocio violada.
- Logs estructurados en JSON con `idCorrelacion`. El header `X-Correlation-Id` se recibe del Gateway (o se genera si falta) y se propaga a respuestas y mensajes (RNF-22).
- Endpoint `/salud` con liveness y readiness (incluye base de datos y RabbitMQ).
- La caída de otro microservicio no impide que este siga atendiendo sus propias operaciones (RNF-08).

## 10. Simplicidad

- No se construye nada que no esté en una spec.
- Cada dependencia nueva se justifica en el plan.
- Sin abstracciones "por si acaso": una interfaz existe porque hay al menos un puerto real que la necesita.

## 11. Convenciones [común]

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
| Parcela | `Parcela` | `/parcelas` | `parcela` |
| Cultivo | `Cultivo` | `/cultivos` | `cultivo` |
| Campaña | `Campania` | `/campanias` | `campania` |
| Costo de campaña | `CostoCampania` | `/campanias/{id}/costos` | `costo_campania` |
| Producción de campaña | `ProduccionCampania` | `/campanias/{id}/produccion` | `produccion_campania` |
| Indicadores | `IndicadoresCampania` | `/campanias/{id}/indicadores` | — |
| Históricos de campañas | — | `/campanias/historicos` | — |
| Saga procesada | `SagaProcesada` | — | `saga_procesada` |
| Mensaje procesado | `MensajeProcesado` | — | `mensaje_procesado` |
| Registro de auditoría | `RegistroAuditoria` | — | `registro_auditoria` |

| Enumeración | Valores |
|---|---|
| `EstadoCampania` | `PLANIFICADA` / `EN_CURSO` / `FINALIZADA` |
| `CategoriaCosto` | `INSUMO` / `MANO_DE_OBRA` / `MAQUINARIA` / `OTRO` |
| `UnidadProduccion` | `KILOGRAMO` |
| `OrigenCosto` | `MANUAL` / `SAGA` |
| `MotivoIndicadorNoDisponible` | `SIN_PRODUCCION` / `SIN_COSTOS` |
| `ResultadoSagaProcesada` | `REGISTRADO` / `RECHAZADO` / `ANULADO` |

| Mensaje | Tipo | Dirección |
|---|---|---|
| `RegistrarCostoCampania` | Comando | Entrada |
| `AnularCostoCampania` | Comando de compensación | Entrada |
| `CostoCampaniaRegistrado` / `CostoCampaniaRechazado` | Respuesta | Salida |
| `CostoCampaniaAnulado` / `AnulacionCostoRechazada` | Respuesta | Salida |

## Enmiendas

- Versión: 2.4.0 (2026-11-01)
- Cambiar una regla requiere actualizar este documento, registrar el motivo y subir la versión:
  - MAJOR: se elimina o redefine una regla.
  - MINOR: se agrega una regla.
  - PATCH: aclaraciones de redacción sin cambio de significado.
- Un cambio en una sección **[común]** se aplica a los cuatro microservicios en la misma versión.

| Versión | Fecha | Motivo |
|---|---|---|
| 1.0.0 | 2026-10-31 | Versión inicial. |
| 2.0.0 | 2026-11-01 | Todo nombre pasa a español (rutas, campos, enumeraciones, códigos de error, mensajes, eventos y servicios). Rutas con prefijo de servicio y versión (`/api/<servicio>/v1/...`). Servicios renombrados a `servicio-*`. Health check en `/salud`. |
| 2.1.0 | 2026-11-01 | **[común]** Decimales como texto en JSON (REST y mensajes); fechas sin hora como `AAAA-MM-DD` en los cuatro servicios; la tabla de permisos y el glosario son propios de cada servicio. **Propio:** moneda `BOB`, superficie en ha y producción en kg; producción obligatoria para finalizar; máximo una campaña `EN_CURSO` por parcela; compensación `AnularCostoCampania` y rechazo `SAGA_ANULADA`; lectura de parcelas y campañas no finalizadas para `tecnico_campo`; glosario ampliado (producción, históricos, saga procesada, `OrigenCosto`, `MotivoIndicadorNoDisponible`, `ResultadoSagaProcesada`, mensajes). Origen: specs 001–008 de `servicio-gestion`. |
| 2.2.0 | 2026-11-01 | **Propio:** enumeración `UnidadProduccion` (`KILOGRAMO`) y unidad de medida de producción en el cultivo, exigida por RF-02 del documento de requisitos. Sin cambios comunes. |
| 2.3.0 | 2026-11-01 | **[común]** El sistema vive en un solo repositorio: cada pipeline está en `.github/workflows/<servicio>.yml`, en la raíz, y se filtra por `servicios/<servicio>/**`. Se permite AMQP sin TLS solo en desarrollo local y tests con contenedores. Los cuatro servicios quedan en la misma versión. Sin cambios propios. |
| 2.4.0 | 2026-11-01 | **Propio:** la regla de una campaña `EN_CURSO` por parcela se valida en el caso de uso y con un índice único, porque un agregado no conoce las demás campañas. La tabla de permisos incluye la lectura de cultivos, costos y producción. Glosario ampliado (mensaje procesado y registro de auditoría). Sin cambios comunes. |
