# Constitución — Servicio de Gestión de Inventario (`servicio-inventario`)

> Reglas no negociables de este microservicio. Prevalecen sobre specs, planes y tareas.
> Si una spec contradice esta constitución, se corrige la spec o se enmienda la constitución; nunca se ignora.
> Las secciones marcadas con **[común]** son idénticas en los cuatro microservicios y solo se cambian en los cuatro a la vez. Excepción: la tabla «Permisos de este servicio» y el «Glosario de este servicio» son propios de cada microservicio y se enmiendan sin tocar los demás.

## 1. Propósito y límites

**Responsable de:**
- Insumos agrícolas: nombre, categoría, unidad de medida, stock, nivel mínimo y costo unitario.
- Movimientos de inventario (entradas y salidas) y el stock resultante.
- Descuento de insumos como participante de la Saga y su compensación.
- Detección de stock bajo y emisión del evento correspondiente.
- Consulta del estado del inventario frente al nivel mínimo.

**No es responsable de:**
- Labores y su registro → `servicio-operaciones`.
- Costos de campaña → `servicio-gestion` (este servicio solo informa el costo de lo descontado).
- Envío de correos y alertas al usuario → n8n.
- Usuarios y roles → Keycloak.

**Fuera del alcance del sistema:** proveedores, órdenes de compra y gestión de ventas.

**Trazabilidad:** CU-06 a CU-09, CU-24 · RF-07 a RF-10, RF-33 · RN-04, RN-05, RN-09.

## 2. Stack

- Node.js (LTS) + NestJS, TypeScript en modo `strict`.
- MongoDB Atlas (sobre Azure) con Mongoose. Se usan transacciones de MongoDB (requieren replica set).
- RabbitMQ con `amqplib` (y `amqp-connection-manager` para reconectar). No se usa el transporte de microservicios de NestJS: espera mensajes `{ pattern, data }`, incompatibles con el sobre común, y no ofrece reintentos con espera creciente ni Dead Letter Queue.
- Validación de entrada con `class-validator` / `class-transformer`.
- Tests: Jest + Supertest + Testcontainers (MongoDB en modo replica set y RabbitMQ).
- Documentación de API: `@nestjs/swagger`.
- Despliegue: imagen Docker en Azure Container Apps.
- No se introducen lenguajes, frameworks ni bases de datos nuevas sin una enmienda.

## 3. Arquitectura (Hexagonal)

- Estructura:
  - `domain/`: entidades (`Insumo`, `MovimientoInventario`), objetos de valor (`Cantidad`, `Dinero`) y reglas. TypeScript puro.
  - `application/`: casos de uso y puertos (interfaces de entrada y de salida, como `RepositorioInsumo` o `PublicadorEventos`).
  - `adapters/inbound/`: controladores HTTP y consumidores de RabbitMQ.
  - `adapters/outbound/`: repositorios Mongoose y publicador de RabbitMQ.
- `domain/` y `application/` no importan nada de `@nestjs/*`, `mongoose` ni `amqplib`. Los módulos de Nest solo conectan puertos con adaptadores.
- Los esquemas de Mongoose viven en el adaptador de salida y se mapean desde/hacia el dominio.
- La lógica de negocio solo vive en el dominio y en los casos de uso; los adaptadores solo traducen.
- Reglas del dominio:
  - El stock nunca es negativo. Un descuento mayor al disponible se rechaza completo (RN-04).
  - El stock solo cambia mediante movimientos. No existe una operación para editar el stock directamente; el stock inicial se registra como una entrada.
  - Toda cantidad de un movimiento es mayor a cero y se expresa en la unidad del insumo.
  - Categorías permitidas: `SEMILLA`, `FERTILIZANTE`, `FITOSANITARIO`.
  - Unidades de medida permitidas: `KILOGRAMO`, `LITRO`, `UNIDAD`. La unidad de un insumo no cambia una vez que tiene movimientos.
  - Cantidades, stock y nivel mínimo admiten hasta 3 decimales; con la unidad `UNIDAD`, solo valores enteros.
  - El costo unitario es mayor o igual a 0, en bolivianos (`BOB`), con hasta 4 decimales. Un costo de 0 es válido (insumo donado o sin costo).
  - Diferencias intencionales con el documento de requisitos: el costo unitario no figura en RF-07, pero sin él no existe el costo que la Saga registra en `servicio-gestion`; las unidades de medida son una lista cerrada, y no texto libre, para poder validar decimales; las cantidades usan decimales exactos, y no `Float`.
  - El nivel mínimo es mayor o igual a 0.

### Estructura de directorios

```text
servicio-inventario/
├── src/
│   ├── main.ts
│   ├── app.module.ts
│   ├── domain/                                  # TypeScript puro
│   │   ├── supply/
│   │   │   ├── insumo.entidad.ts
│   │   │   ├── categoria-insumo.enum.ts
│   │   │   └── politica-stock-bajo.ts           # regla de stock bajo y 24 h
│   │   ├── movement/
│   │   │   ├── movimiento-inventario.entidad.ts
│   │   │   └── tipo-movimiento.enum.ts
│   │   └── shared/
│   │       ├── cantidad.vo.ts
│   │       ├── dinero.vo.ts
│   │       └── error-dominio.ts
│   ├── application/
│   │   ├── use-cases/                           # puertos de entrada
│   │   │   ├── crear-insumo.caso-uso.ts
│   │   │   ├── registrar-movimiento.caso-uso.ts
│   │   │   ├── descontar-insumos.caso-uso.ts
│   │   │   ├── restaurar-insumos.caso-uso.ts
│   │   │   └── consultar-estado-inventario.caso-uso.ts
│   │   └── ports/                               # puertos de salida
│   │       ├── repositorio-insumo.puerto.ts
│   │       ├── repositorio-movimiento.puerto.ts
│   │       ├── repositorio-saga-procesada.puerto.ts
│   │       ├── unidad-trabajo.puerto.ts         # transacciones
│   │       ├── publicador-eventos.puerto.ts
│   │       ├── registro-auditoria.puerto.ts
│   │       └── reloj.puerto.ts
│   ├── adapters/
│   │   ├── inbound/
│   │   │   ├── http/
│   │   │   │   ├── insumos.controlador.ts
│   │   │   │   ├── movimientos.controlador.ts
│   │   │   │   ├── estado-inventario.controlador.ts
│   │   │   │   ├── dto/
│   │   │   │   ├── auth/
│   │   │   │   │   ├── jwt.guardia.ts
│   │   │   │   │   └── roles.guardia.ts
│   │   │   │   ├── id-correlacion.middleware.ts
│   │   │   │   └── filtro-excepciones-http.ts
│   │   │   └── messaging/
│   │   │       └── comandos-saga.consumidor.ts
│   │   └── outbound/
│   │       ├── persistence/
│   │       │   ├── schemas/                     # esquemas Mongoose
│   │       │   │   ├── insumo.esquema.ts
│   │       │   │   ├── movimiento-inventario.esquema.ts
│   │       │   │   └── saga-procesada.esquema.ts
│   │       │   ├── mappers/
│   │       │   ├── repositorio-insumo.mongo.ts
│   │       │   ├── repositorio-movimiento.mongo.ts
│   │       │   └── unidad-trabajo.mongo.ts
│   │       └── messaging/
│   │           └── publicador-eventos.rabbitmq.ts
│   ├── modules/
│   │   └── inventario.modulo.ts                 # conecta puertos con adaptadores
│   └── config/
│       └── validacion-entorno.ts
├── migrations/                                  # índices y cambios de esquema
├── test/
│   ├── unit/
│   │   ├── domain/
│   │   └── application/
│   └── integration/                             # Supertest + Testcontainers
├── Dockerfile
├── package.json
├── tsconfig.json
└── Constitucion.md
```

- Las carpetas `domain`, `application` y `adapters` (con `inbound` y `outbound`) y su regla de dependencias son obligatorias. Los nombres concretos de archivos son de referencia y se definen en el plan.
- Todo lo que depende de NestJS, Mongoose o RabbitMQ vive en `adapters`, `modules` o `config`.
- Los tests replican la estructura de `src`.

## 4. Datos

- Este servicio es dueño exclusivo de su base de datos. Ningún otro servicio la lee ni la escribe.
- Identificadores: UUID.
- Cantidades y montos se almacenan como `Decimal128` y se operan con una librería decimal (por ejemplo, `decimal.js`). Nunca aritmética con `number` de JavaScript para montos.
- El cambio de stock y el movimiento que lo origina se guardan en la misma transacción.
- El descuento se hace con una actualización atómica condicionada (`stock >= cantidad`) para evitar condiciones de carrera entre solicitudes concurrentes.
- Los movimientos originados por la Saga guardan `idSaga` y `idLabor` como referencia.
- Los movimientos son inmutables: un error se corrige con un movimiento inverso, no editando ni borrando.
- Se registra la saga procesada (`idSaga`, resultado `DESCONTADO`, `RECHAZADO` o `RESTAURADO`, costo total y los ítems con su cantidad y costo unitario), para garantizar la idempotencia y repetir exactamente la misma respuesta aunque el costo unitario cambie después.
- Toda creación o modificación genera un registro de auditoría: usuario o servicio, acción, fecha y entidad.
- Los índices y cambios de esquema se definen en código versionado y se aplican mediante scripts de migración.

## 5. Comunicación

- API REST con prefijo de servicio y versión: `/api/inventario/v1/...`. El API Gateway rutea todo `/api/inventario/**` a este servicio, y solo se accede a través de él.
- El contrato OpenAPI es la fuente de verdad. Un cambio incompatible exige una nueva versión (`/api/inventario/v2/...`); la anterior se mantiene mientras haya clientes que la usen (incluida la app Flutter instalada).
- **Rol en la Saga: participante, no coordinador.**
  - Colas: consume de `servicio-inventario.comandos` (con su Dead Letter Queue `servicio-inventario.comandos.dlq`) y responde en `servicio-operaciones.respuestas-saga`, la misma cola que usa `servicio-gestion`.
  - Consume `DescontarInsumos` (`idSaga`, `idLabor`, `items: [{ idInsumo, cantidad }]`).
  - `items` tiene al menos un elemento y cada `idInsumo` aparece una sola vez; si no, se rechaza con `DATOS_INVALIDOS`.
  - Es todo o nada: si un solo insumo no existe o no alcanza, se rechaza el comando completo sin cambios.
  - Responde `InsumosDescontados` (con el costo total calculado a partir del costo unitario de cada insumo, con precisión completa y redondeado al final a 2 decimales, mitad hacia arriba) o `InsumosRechazados` con un código (`DATOS_INVALIDOS`, `INSUMO_NO_ENCONTRADO`, `STOCK_INSUFICIENTE` o `SAGA_COMPENSADA`) y los insumos afectados.
  - Consume `RestaurarInsumos` (compensación, con `idSaga` e `idLabor`): registra entradas por exactamente las cantidades que descontó ese `idSaga`, leídas de sus movimientos y no del comando, con motivo "Compensación de saga {idSaga}", y responde `InsumosRestaurados`.
  - Ambos comandos son idempotentes (RN-09). Un comando repetido devuelve la misma respuesta de la primera vez.
  - Una compensación sobre un `idSaga` que nunca descontó, o que fue rechazado, responde `InsumosRestaurados` sin efectos. Si nunca descontó, el `idSaga` queda `RESTAURADO`, y un `DescontarInsumos` que llegue después se rechaza con `SAGA_COMPENSADA` sin tocar el stock. Así un descuento que seguía en la cola no deja stock perdido.
  - Los comandos de un mismo `idSaga` se procesan de forma serializada.
- **Stock bajo (RN-05):**
  - Tras cada movimiento, si `stock <= nivelMinimo`, publica el evento `inventario.stock.bajo` (`idInsumo`, `nombre`, `stock`, `nivelMinimo`, `unidad`).
  - No se publica más de un evento por insumo en 24 horas; se guarda la fecha de la última alerta solo después de publicarlo. El evento se publica tras el commit: si la publicación falla, se registra el error en el log y la alerta vuelve a intentarse en el siguiente movimiento.
  - El servicio no envía correos; eso lo hace n8n.
- Endpoint de estado del inventario con indicador de stock bajo por insumo (RF-33), para Angular, GraphQL e `servicio-ia`.
- Este servicio no llama de forma síncrona a otros microservicios.

## 6. Calidad

- Todo endpoint tiene tests de integración (Supertest + Testcontainers).
- Toda regla del dominio tiene al menos un test unitario.
- Tests obligatorios para la Saga: descuento exitoso, stock insuficiente, insumo inexistente, insumo repetido en `items`, comando duplicado con la misma respuesta aunque cambie el costo unitario, compensación, compensación duplicada, compensación sin descuento previo, descuento tardío después de una compensación y redondeo del costo total.
- Test de concurrencia: dos descuentos simultáneos sobre el mismo insumo nunca dejan stock negativo.
- Test del evento de stock bajo, incluida la regla de 24 horas.
- Cobertura mínima: 80 % de líneas en `domain` y `application`. El pipeline falla si baja.
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
| Crear y modificar insumos, registrar entradas y salidas | `administrador` |
| Consultar insumos, movimientos y estado del inventario | `administrador`, `gerencia` |
| Consultar insumos disponibles, sin costo unitario ni otros datos económicos (para registrar labores, también sin conexión; el documento de requisitos no lo menciona, pero `ConsumoInsumo` referencia el insumo) | `tecnico_campo` |
| Lectura para integración (insumos y estado del inventario) | rol `lectura_inventario`: cuentas de servicio de `servicio-ia`, GraphQL y n8n |

## 8. Mensajería [común]

- Broker: RabbitMQ sobre AMQPS. Solo en desarrollo local y tests con contenedores se permite AMQP sin TLS, dentro de la red de Docker.
- Los comandos van a la cola del servicio destino; los eventos se publican en el exchange de tipo topic `eventos` (durable), con routing key `<servicio>.<entidad>.<evento>` (por ejemplo, `inventario.stock.bajo`). Cada consumidor de eventos crea su propia cola enlazada a ese exchange. n8n recibe los eventos con su disparador de RabbitMQ; ningún servicio llama webhooks de n8n.
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

## 9. Errores y observabilidad [común]

- Toda respuesta de error usa este formato:

```json
{
  "codigo": "STOCK_INSUFICIENTE",
  "mensaje": "No hay stock suficiente del insumo solicitado.",
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
- Sin abstracciones "por si acaso": un puerto existe porque hay al menos un adaptador real que lo implementa.

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

| Concepto | Clase / archivo | Ruta REST | Colección |
|---|---|---|---|
| Insumo | `Insumo` | `/insumos` | `insumos` |
| Movimiento de inventario | `MovimientoInventario` | `/movimientos` | `movimientos_inventario` |
| Estado del inventario | — | `/estado-inventario` | — |
| Nivel mínimo | — | campo `nivelMinimo` | — |
| Costo unitario | — | campo `costoUnitario` | — |
| Fecha de la última alerta de stock bajo | — | campo `fechaUltimaAlerta` | — |
| Saga procesada | `SagaProcesada` | — | `sagas_procesadas` |
| Registro de auditoría | `RegistroAuditoria` | — | `registros_auditoria` |
| Migración aplicada | — | — | `migraciones` |

| Enumeración | Valores |
|---|---|
| `CategoriaInsumo` | `SEMILLA` / `FERTILIZANTE` / `FITOSANITARIO` |
| `TipoMovimiento` | `ENTRADA` / `SALIDA` |
| `UnidadMedida` | `KILOGRAMO` / `LITRO` / `UNIDAD` |
| `ResultadoSagaProcesada` | `DESCONTADO` / `RECHAZADO` / `RESTAURADO` |
| Códigos de `InsumosRechazados` | `DATOS_INVALIDOS` / `INSUMO_NO_ENCONTRADO` / `STOCK_INSUFICIENTE` / `SAGA_COMPENSADA` |

| Mensaje | Tipo | Dirección |
|---|---|---|
| `DescontarInsumos` | Comando | Entrada |
| `RestaurarInsumos` | Comando de compensación | Entrada |
| `InsumosDescontados` / `InsumosRechazados` | Respuesta | Salida |
| `InsumosRestaurados` | Respuesta | Salida |
| `StockBajo` (routing key `inventario.stock.bajo`) | Evento | Salida (exchange `eventos`) |

## Enmiendas

- Versión: 2.8.0 (2026-11-02)
- Cambiar una regla requiere actualizar este documento, registrar el motivo y subir la versión:
  - MAJOR: se elimina o redefine una regla.
  - MINOR: se agrega una regla.
  - PATCH: aclaraciones de redacción sin cambio de significado.
- Un cambio en una sección **[común]** se aplica a los cuatro microservicios en la misma versión.

| Versión | Fecha | Motivo |
|---|---|---|
| 1.0.0 | 2026-10-31 | Versión inicial. |
| 2.0.0 | 2026-11-01 | Todo nombre pasa a español (rutas, campos, enumeraciones, códigos de error, mensajes, eventos y servicios). Rutas con prefijo de servicio y versión (`/api/<servicio>/v1/...`). Servicios renombrados a `servicio-*`. Health check en `/salud`. |
| 2.1.0 | 2026-11-01 | **[común]** Decimales como texto en JSON (REST y mensajes), lo que incluye `cantidad` en `DescontarInsumos` y el costo total de `InsumosDescontados`; fechas sin hora como `AAAA-MM-DD` en los cuatro servicios; la tabla de permisos y el glosario son propios de cada servicio. Sin cambios propios. |
| 2.3.0 | 2026-11-01 | **[común]** El sistema vive en un solo repositorio: cada pipeline está en `.github/workflows/<servicio>.yml`, en la raíz, y se filtra por `servicios/<servicio>/**`. Se permite AMQP sin TLS solo en desarrollo local y tests con contenedores. Los cuatro servicios quedan en la misma versión. Sin cambios propios. |
| 2.4.0 | 2026-11-01 | **Propio:** el costo total de `InsumosDescontados` se redondea a 2 decimales, mitad hacia arriba, porque `servicio-gestion` no admite más decimales. Sin cambios comunes. |
| 2.6.0 | 2026-11-02 | **[común]** Los eventos se publican en el exchange de tipo topic `eventos` (durable); cada consumidor crea su propia cola enlazada a él, para que n8n y los demás sepan dónde suscribirse. **Propio:** el descuento tardío tras una compensación se rechaza con `SAGA_COMPENSADA`; `RestaurarInsumos` devuelve exactamente lo que descontó ese `idSaga`; la saga procesada guarda costo total e ítems para repetir la misma respuesta; RabbitMQ con `amqplib`, sin el transporte de NestJS; unidades de medida, decimales, costo unitario y nivel mínimo definidos; validación de `items`; códigos de rechazo; `tecnico_campo` sin datos económicos; rol `lectura_inventario`; la alerta de stock bajo solo cuenta como enviada si se publicó. |
| 2.7.0 | 2026-11-02 | **[común]** n8n recibe los eventos con su disparador de RabbitMQ, desde una cola propia enlazada al exchange `eventos`; ningún servicio llama webhooks de n8n. Así un evento no se pierde si n8n está caído y se respeta la regla de no hacer llamadas síncronas entre servicios. Es una diferencia intencional con el proceso 3 del documento de requisitos, que menciona un webhook. **Propio:** la cuenta de servicio de n8n recibe el rol `lectura_inventario`, porque el flujo de stock bajo consulta la información actualizada antes de enviar la alerta (RF-29, proceso 3). Se documentan como diferencias intencionales con el documento de requisitos el costo unitario, las unidades de medida cerradas y la lectura del catálogo por `tecnico_campo`. |
| 2.8.0 | 2026-11-02 | **Propio:** `administrador` y `gerencia` consultan los movimientos de inventario (trazabilidad del stock; `lectura_inventario` sigue limitado a insumos y estado del inventario). Glosario ampliado con `fechaUltimaAlerta`, `registros_auditoria`, `migraciones` y el tipo de mensaje `StockBajo` del evento `inventario.stock.bajo`. Origen: specs 001–005 de `servicio-inventario`. Sin cambios comunes. |
