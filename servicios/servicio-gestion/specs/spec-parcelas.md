# Parcelas — `servicio-gestion`

| Campo | Valor |
|---|---|
| Servicio | `servicio-gestion` |
| Archivo | `specs/spec-parcelas.md` |
| Estado | Spec aprobada (2026-11-01) · Plan y tareas en borrador |
| Constitución | v2.4.0 |
| Trazabilidad | CU-01 (prioridad alta) · RF-01 · RN-01, RN-15, RN-16 · RNF-05 |
| Depende de | — (incluye la Fase 0: base del servicio) |

Contenido:

1. [Spec](#1-spec): qué debe hacer el servicio.
2. [Plan](#2-plan): cómo se construye.
3. [Tareas](#3-tareas): en qué orden se implementa.

---

# 1. Spec

## 1.1 Escenarios de usuario y pruebas

### Historia 1 — Registrar una parcela (Prioridad: P1)

Como administrador, quiero registrar las parcelas del establecimiento con su superficie, para poder planificar campañas sobre ellas.

**Por qué esta prioridad:** sin parcelas no existen campañas, costos ni indicadores. Es la base de todo el servicio.

**Prueba independiente:** se puede probar creando una parcela y consultándola; entrega valor por sí sola como catálogo de parcelas.

**Escenarios de aceptación:**

1. **Dado** un administrador autenticado, **cuando** registra una parcela con nombre "Lote Norte" y superficie 25,5 ha, **entonces** la parcela se crea con un identificador UUID y se devuelve con todos sus datos.
2. **Dado** un administrador autenticado, **cuando** registra una parcela con superficie 0 o negativa, **entonces** se rechaza con `422 SUPERFICIE_INVALIDA` y no se crea nada.
3. **Dado** que ya existe la parcela "Lote Norte", **cuando** se registra otra con el nombre "lote norte", **entonces** se rechaza con `409 NOMBRE_PARCELA_DUPLICADO`.
4. **Dado** un usuario con rol `gerencia`, **cuando** intenta registrar una parcela, **entonces** se rechaza con `403 SIN_PERMISO`.

### Historia 2 — Consultar parcelas (Prioridad: P1)

Como administrador, gerente o técnico de campo, quiero ver el listado de parcelas y el detalle de cada una, para conocer la superficie disponible o elegir la parcela al registrar una labor.

**Por qué esta prioridad:** es necesaria para elegir la parcela al crear una campaña y para la vista de gerencia.

**Prueba independiente:** con parcelas cargadas, se listan y se consulta una por ID.

**Escenarios de aceptación:**

1. **Dado** que existen 30 parcelas, **cuando** se pide el listado sin parámetros, **entonces** se devuelven las primeras 20 ordenadas por nombre, con el total de registros.
2. **Dado** que existen "Lote Norte" y "Lote Sur", **cuando** se filtra por el texto "norte", **entonces** solo se devuelve "Lote Norte".
3. **Dado** un ID que no existe, **cuando** se consulta el detalle, **entonces** se responde `404 PARCELA_NO_ENCONTRADA`.
4. **Dado** un usuario con rol `tecnico_campo`, **cuando** consulta el listado o el detalle de parcelas, **entonces** recibe los mismos datos que un administrador (las parcelas no tienen datos económicos).

### Historia 3 — Modificar una parcela (Prioridad: P2)

Como administrador, quiero corregir los datos de una parcela (nombre, superficie, ubicación, descripción), para mantener el catálogo al día.

**Por qué esta prioridad:** corrige errores de carga, pero el servicio funciona sin ella.

**Prueba independiente:** se modifica una parcela existente y se verifica el cambio y su registro de auditoría.

**Escenarios de aceptación:**

1. **Dado** una parcela de 25,5 ha, **cuando** el administrador cambia su superficie a 27 ha, **entonces** la parcela queda con 27 ha y se registra la auditoría con usuario, acción, fecha y entidad.
2. **Dado** una parcela con una campaña creada cuando medía 25,5 ha, **cuando** su superficie cambia a 27 ha, **entonces** la campaña conserva 25,5 ha y sus indicadores no cambian (ver `spec-campanias.md`).
3. **Dado** una parcela, **cuando** se le asigna el nombre de otra parcela existente, **entonces** se rechaza con `409 NOMBRE_PARCELA_DUPLICADO`.

### Casos borde

- Superficie con más decimales de los admitidos (por ejemplo 10,12345 ha): `400 DATOS_INVALIDOS`, no se redondea en silencio.
- Superficie enviada como texto no numérico o ausente: `400 DATOS_INVALIDOS`.
- Nombre con espacios al inicio o al final: se recortan antes de validar unicidad y longitud.
- Dos solicitudes simultáneas que crean parcelas con el mismo nombre: solo una se crea; la otra recibe `409 NOMBRE_PARCELA_DUPLICADO`.
- Dos modificaciones simultáneas de la misma parcela: la segunda recibe `409 CONFLICTO_CONCURRENCIA`; ningún cambio se pierde en silencio.

## 1.2 Requisitos

### Requisitos funcionales

- **RQ-PAR-01**: El sistema debe permitir registrar una parcela con:
  - `nombre`: obligatorio, de 1 a 100 caracteres, único sin distinguir mayúsculas ni minúsculas.
  - `superficieHectareas`: obligatoria, decimal mayor a 0, hasta 4 decimales.
  - `ubicacion`: opcional, texto libre de hasta 200 caracteres.
  - `descripcion`: opcional, hasta 500 caracteres.
- **RQ-PAR-02**: La regla "superficie mayor a 0" (RN-01) se valida en el dominio. Su violación responde `422 SUPERFICIE_INVALIDA`.
- **RQ-PAR-03**: Un nombre repetido responde `409 NOMBRE_PARCELA_DUPLICADO`.
- **RQ-PAR-04**: El sistema debe permitir modificar `nombre`, `superficieHectareas`, `ubicacion` y `descripcion`, con las mismas reglas de RQ-PAR-01 a RQ-PAR-03.
- **RQ-PAR-05**: Modificar la superficie de una parcela no altera la superficie registrada en sus campañas existentes.
- **RQ-PAR-06**: El sistema debe listar parcelas paginadas, ordenadas por nombre ascendente, con filtro opcional por texto contenido en el nombre (sin distinguir mayúsculas).
- **RQ-PAR-07**: El sistema debe devolver el detalle de una parcela por ID, o `404 PARCELA_NO_ENCONTRADA`.
- **RQ-PAR-08**: Toda creación y modificación genera un registro de auditoría (usuario, acción, fecha y entidad).
- **RQ-PAR-09**: Esta versión no incluye eliminación de parcelas.

### Entidades clave

- **Parcela** (agregado): `id` (UUID), `nombre`, `superficieHectareas`, `ubicacion`, `descripcion`, `fechaCreacion`, `fechaActualizacion`.

## 1.3 Permisos

| Operación | Roles |
|---|---|
| Registrar y modificar | `administrador` |
| Listar y ver detalle | `administrador`, `gerencia`, `tecnico_campo`, cuentas de servicio autorizadas |

## 1.4 Errores de esta funcionalidad

| HTTP | Código | Cuándo |
|---|---|---|
| 400 | `DATOS_INVALIDOS` | Formato incorrecto, campo obligatorio ausente, longitud o decimales excedidos |
| 404 | `PARCELA_NO_ENCONTRADA` | El ID no existe |
| 409 | `NOMBRE_PARCELA_DUPLICADO` | El nombre ya está en uso |
| 409 | `CONFLICTO_CONCURRENCIA` | La parcela cambió desde que se leyó |
| 422 | `SUPERFICIE_INVALIDA` | Superficie menor o igual a 0 |

## 1.5 Criterios de éxito

- **CE-PAR-01**: El 100 % de las solicitudes con superficie menor o igual a 0 se rechazan, sin crear ni modificar datos.
- **CE-PAR-02**: Listado y detalle responden en menos de 3 s con al menos 1.000 parcelas cargadas (RNF-05).
- **CE-PAR-03**: Toda creación y modificación tiene su registro de auditoría (verificado en tests de integración).
- **CE-PAR-04**: Un administrador registra una parcela nueva en una sola solicitud, sin pasos previos.

## 1.6 Supuestos

- La superficie se expresa siempre en hectáreas (README, D-02).
- La ubicación es descriptiva (texto); no se guardan coordenadas ni geometría en esta versión.

## 1.7 Aclaraciones

- **AC-01** — Resuelta (2026-11-01, constitución v2.1.0): `tecnico_campo` puede listar y consultar parcelas para elegirlas al registrar labores.

## 1.8 Fuera de alcance

- Eliminación o desactivación de parcelas.
- Coordenadas, polígonos o mapas.
- Historial avanzado de uso de parcelas (fuera del alcance del sistema).

---

# 2. Plan

Criterio general: lo mínimo que cumple la spec y la constitución. Sin dependencias fuera del stack de la constitución, sin abstracciones que no tengan un uso real.

**Documentos que debe tener a mano quien implemente:** la constitución de gestión v2.4.0 (`servicios/servicio-gestion/Constitucion.md`), `specs/README.md` (decisiones transversales) y este archivo.

**Coordenadas del proyecto:** `groupId` `com.agrosystem`, `artifactId` `servicio-gestion`, paquete raíz `com.agrosystem.gestion`.

## 2.1 Fase 0 — Base del servicio

Se construye una sola vez, con esta funcionalidad, y la reutilizan todas las demás.

### Dependencias (`pom.xml`)

| Dependencia | Para qué |
|---|---|
| Spring Boot 3.4 (parent), Java 21 | Base; Boot 3.4 trae logs JSON nativos, sin librerías extra |
| `spring-boot-starter-web` | API REST |
| `spring-boot-starter-validation` | Validación de DTO |
| `spring-boot-starter-data-jpa` + `postgresql` | Persistencia |
| `flyway-core` + `flyway-database-postgresql` | Migraciones |
| `spring-boot-starter-oauth2-resource-server` | Validación de JWT de Keycloak |
| `spring-boot-starter-actuator` | `/salud` |
| `springdoc-openapi-starter-webmvc-ui` | OpenAPI y Swagger UI |
| `spring-boot-devtools` (opcional, fuera de la imagen final) | Recarga en caliente del entorno de Docker Compose |
| Test: `spring-boot-starter-test`, `spring-security-test`, `spring-boot-testcontainers`, `testcontainers` (`postgresql`, `junit-jupiter`) | Tests unitarios y de integración |
| Plugin `jacoco-maven-plugin` | Cobertura mínima del 80 % en `domain` y `application` |

Spring AMQP se agrega recién en `spec-costo-saga.md`, que es la primera funcionalidad que lo usa.

### Configuración (`application.yml`)

Todo valor sensible o de entorno sale de las variables que entrega `docker-compose.yml` (README D-14):

| Variable | Uso |
|---|---|
| `SERVER_PORT` | Puerto HTTP; Spring Boot lo lee directamente |
| `SPRING_DATASOURCE_URL`, `SPRING_DATASOURCE_USERNAME`, `SPRING_DATASOURCE_PASSWORD` | Conexión a PostgreSQL; Spring Boot las lee directamente |
| `KEYCLOAK_JWKS_URI` | Claves para validar la firma; se asigna a `spring.security.oauth2.resourceserver.jwt.jwk-set-uri` |
| `KEYCLOAK_ISSUER` | Emisor esperado (`iss`); se asigna a `spring.security.oauth2.resourceserver.jwt.issuer-uri` |
| `KEYCLOAK_AUDIENCE` | Audiencia esperada (`aud`), por defecto `servicio-gestion`; se asigna a `spring.security.oauth2.resourceserver.jwt.audiences` |

Valores fijos:

- `spring.jpa.hibernate.ddl-auto: validate` (el esquema lo crea Flyway).
- `logging.structured.format.console: ecs` (logs en JSON).
- `spring.jackson.default-leniency: false`, para que una fecha con hora no se acepte como `LocalDate`.
- Actuator con `management.endpoints.web.base-path: /`, `management.endpoints.web.path-mapping.health: salud`, solo `health` expuesto y los grupos `liveness` y `readiness` habilitados (`management.endpoint.health.probes.enabled: true`; readiness incluye la base de datos). Resultado: `/salud`, `/salud/liveness` y `/salud/readiness`.
- springdoc en sus rutas por defecto: `/v3/api-docs` y `/swagger-ui.html`.

### Perfil de tests (`src/test/resources/application-test.yml`)

- Emisor y audiencia ficticios (`KEYCLOAK_ISSUER: http://keycloak-ficticio/realms/agro`, `KEYCLOAK_JWKS_URI: http://keycloak-ficticio/realms/agro/protocol/openid-connect/certs`, `KEYCLOAK_AUDIENCE: servicio-gestion`). El decodificador JWT se crea de forma diferida y los tests usan `jwt()`, así que nunca se contacta al emisor.
- PostgreSQL con Testcontainers (`postgres:17-alpine`, la misma versión de Docker Compose) y `@ServiceConnection`, en una clase base `PruebaIntegracionBase` que reutilizan todos los tests `*IT`.

### Seguridad

- **`ConfiguracionSeguridad`**:
  - Sin sesión (stateless) y sin CSRF.
  - Rutas públicas: `/salud/**`, `/v3/api-docs/**`, `/swagger-ui/**` y `/swagger-ui.html`.
  - Cualquier otra ruta exige un JWT válido.
  - Permisos por endpoint con `@PreAuthorize`, activados con `@EnableMethodSecurity`.
- **Validación del token:** con `jwk-set-uri` e `issuer-uri` configurados, las claves se descargan de `jwk-set-uri` (red interna) y el emisor solo se compara con `iss`, sin conectarse a él. También se validan firma y vigencia. La audiencia se valida con la propiedad `audiences`. Spring Boot arma el decodificador con estas tres propiedades, sin un `JwtDecoder` propio.
- **`ConversorRolesKeycloak`**: lee los roles de realm en `realm_access.roles` y los convierte en autoridades `ROLE_<rol>`.
- **Roles:**

  | Rol de realm | Quién lo tiene |
  |---|---|
  | `administrador`, `gerencia`, `tecnico_campo` | Usuarios |
  | `lectura_gestion` | Cuentas de servicio de `servicio-ia` y GraphQL |
  | `estado_campania` | Cuentas de servicio de `servicio-operaciones` y GraphQL (lo usa `spec-consultas-integracion.md`) |

- Los errores 401 y 403 de seguridad responden con el formato común de error: `NO_AUTENTICADO` y `SIN_PERMISO`.

### Errores

- **`ExcepcionDominio`** (en `domain/shared`) lleva `codigo`, `mensaje` y un `tipo` (`NO_ENCONTRADO`, `CONFLICTO`, `REGLA_NEGOCIO` o `PROHIBIDO`). El dominio no conoce HTTP.
- **`ManejadorGlobalExcepciones`** traduce a `RespuestaError` (`codigo`, `mensaje`, `detalles`, `idCorrelacion`):

  | Origen | HTTP | Código |
  |---|---|---|
  | `MethodArgumentNotValidException`, `HttpMessageNotReadableException`, parámetros inválidos | 400 | `DATOS_INVALIDOS`, con un detalle por campo |
  | `ExcepcionDominio` tipo `NO_ENCONTRADO` | 404 | El de la excepción |
  | `ExcepcionDominio` tipo `CONFLICTO` | 409 | El de la excepción |
  | `ObjectOptimisticLockingFailureException` | 409 | `CONFLICTO_CONCURRENCIA` |
  | `ExcepcionDominio` tipo `REGLA_NEGOCIO` | 422 | El de la excepción |
  | `ExcepcionDominio` tipo `PROHIBIDO` (el permiso depende del dato, como en `spec-campanias.md`) | 403 | El de la excepción |
  | `AccessDeniedException` lanzada por `@PreAuthorize` | 403 | `SIN_PERMISO` |
  | `NoResourceFoundException` (ruta inexistente) | 404 | `RECURSO_NO_ENCONTRADO` |
  | `HttpRequestMethodNotSupportedException` | 405 | `METODO_NO_PERMITIDO` |
  | Cualquier otra | 500 | `ERROR_INTERNO`, sin exponer detalles (código incluido en el catálogo del README) |

### Correlación y logs

- **`FiltroIdCorrelacion`**: toma `X-Correlation-Id` de la solicitud o genera un UUID, lo pone en el MDC (`idCorrelacion`) y lo devuelve en la respuesta. Se ejecuta antes de la cadena de seguridad, para que las respuestas 401 y 403 también lo incluyan.
- Los logs no incluyen tokens ni datos personales; solo el `sub` del usuario.

### Auditoría

Solo los datos que exigen el documento de requisitos (§1.7.3) y la constitución (§4): usuario o servicio, acción, fecha y entidad.

- **Puerto** `RegistroAuditoria` en `application/port`, con dos métodos:
  - `registrar(accion, entidad, idEntidad)`: toma el actor (`sub` del JWT) del contexto de seguridad.
  - `registrarServicio(actor, accion, entidad, idEntidad)`: para los mensajes de la Saga, donde el actor es el `origen` del mensaje.
- **Implementación** `RegistroAuditoriaJpa` en `infrastructure/audit`: agrega la fecha y el `idCorrelacion` del MDC, y se ejecuta dentro de la misma transacción del caso de uso.
- **Acciones:** `CREAR`, `MODIFICAR`, `ELIMINAR`, `CAMBIAR_ESTADO`, `REGISTRAR_COSTO_SAGA` y `ANULAR_COSTO_SAGA`.

### Formato JSON

- Los decimales salen como texto, con escala fija: superficie `"25.5000"`. Se usa `@JsonFormat(shape = STRING)` en los DTO de respuesta.
- En la entrada solo se aceptan como texto. Un deserializador propio para `BigDecimal` rechaza los números JSON, que terminan en `400 DATOS_INVALIDOS`.
- Fechas y horas en ISO 8601 UTC.

### Paginación (común a todos los listados)

- Parámetros: `pagina` (desde 0, por defecto 0) y `tamanio` (por defecto 20, máximo 100). Fuera de rango, `400 DATOS_INVALIDOS`.
- Respuesta genérica `PaginaRespuesta<T>`: `items`, `pagina`, `tamanio`, `total`.

### Empaquetado y pipeline

- **`Dockerfile`** multi-etapa: compila con Maven sobre JDK 21 y ejecuta sobre JRE 21, con un usuario no root.
- **`.github/workflows/servicio-gestion.yml`** (en la raíz del repositorio, filtrado por `servicios/servicio-gestion/**`): `mvn verify` (incluye tests con Testcontainers y JaCoCo) y construcción de la imagen Docker.
- Los tests con sufijo `IT` se ejecutan con Surefire junto a los unitarios, para que JaCoCo mida todo en una sola pasada.
- El Docker Compose del sistema completo (RNF-19) vive fuera de este servicio; aquí solo se garantiza que la imagen arranca con las variables de entorno indicadas.

## 2.2 Endpoints

Prefijo: `/api/gestion/v1`.

| Método y ruta | Roles | Respuesta correcta | Errores |
|---|---|---|---|
| `POST /parcelas` | `administrador` | `201` + `Location` + parcela | 400, 401, 403, 409 `NOMBRE_PARCELA_DUPLICADO`, 422 `SUPERFICIE_INVALIDA` |
| `GET /parcelas?nombre=&pagina=&tamanio=` | `administrador`, `gerencia`, `tecnico_campo`, `lectura_gestion` | `200` + página | 400, 401, 403 |
| `GET /parcelas/{id}` | Igual que el listado | `200` + parcela | 401, 403, 404 `PARCELA_NO_ENCONTRADA` |
| `PUT /parcelas/{id}` | `administrador` | `200` + parcela | 400, 401, 403, 404, 409 `NOMBRE_PARCELA_DUPLICADO` o `CONFLICTO_CONCURRENCIA`, 422 |

**Solicitud de creación:**

```json
{
  "nombre": "Lote Norte",
  "superficieHectareas": "25.5",
  "ubicacion": "Km 12, camino a Warnes",
  "descripcion": "Suelo arcilloso"
}
```

**Solicitud de modificación:** los mismos campos más `version`, la que se recibió al consultar.

```json
{
  "nombre": "Lote Norte",
  "superficieHectareas": "27",
  "ubicacion": "Km 12, camino a Warnes",
  "descripcion": "Suelo arcilloso",
  "version": 0
}
```

**Respuesta de parcela:**

```json
{
  "id": "6f1c…",
  "nombre": "Lote Norte",
  "superficieHectareas": "25.5000",
  "ubicacion": "Km 12, camino a Warnes",
  "descripcion": "Suelo arcilloso",
  "version": 0,
  "fechaCreacion": "2026-11-02T14:00:00Z",
  "fechaActualizacion": "2026-11-02T14:00:00Z"
}
```

**Validaciones del DTO** (responden `400 DATOS_INVALIDOS`):

| Campo | Regla |
|---|---|
| `nombre` | `@NotBlank`, `@Size(max = 100)` |
| `superficieHectareas` | `@NotNull`, `@Digits(integer = 8, fraction = 4)` |
| `ubicacion` | `@Size(max = 200)` |
| `descripcion` | `@Size(max = 500)` |
| `version` (solo en `PUT`) | `@NotNull` |

El valor 0 o negativo de la superficie pasa el DTO y lo rechaza el dominio con `422 SUPERFICIE_INVALIDA`, como exige RQ-PAR-02.

## 2.3 Modelo de datos

**`V1__crear_registro_auditoria.sql`**

```sql
CREATE TABLE registro_auditoria (
    id              UUID PRIMARY KEY,
    actor           VARCHAR(100) NOT NULL,
    accion          VARCHAR(50)  NOT NULL,
    entidad         VARCHAR(50)  NOT NULL,
    id_entidad      UUID         NOT NULL,
    id_correlacion  VARCHAR(64),
    fecha           TIMESTAMPTZ  NOT NULL
);
CREATE INDEX ix_auditoria_entidad ON registro_auditoria (entidad, id_entidad);
```

**`V2__crear_parcela.sql`**

```sql
CREATE TABLE parcela (
    id                    UUID PRIMARY KEY,
    nombre                VARCHAR(100)  NOT NULL,
    superficie_hectareas  NUMERIC(12,4) NOT NULL CHECK (superficie_hectareas > 0),
    ubicacion             VARCHAR(200),
    descripcion           VARCHAR(500),
    version               BIGINT        NOT NULL,
    fecha_creacion        TIMESTAMPTZ   NOT NULL,
    fecha_actualizacion   TIMESTAMPTZ   NOT NULL
);
CREATE UNIQUE INDEX ux_parcela_nombre ON parcela (lower(nombre));
```

- El índice único sobre `lower(nombre)` garantiza la unicidad sin distinguir mayúsculas, también ante solicitudes simultáneas.
- El `CHECK` es una segunda barrera; la regla vive en el dominio.

## 2.4 Diseño por capas

| Capa | Clase | Responsabilidad |
|---|---|---|
| `domain/shared` | `Hectareas` | Objeto de valor; rechaza valores ≤ 0 con `SUPERFICIE_INVALIDA` |
| `domain/shared` | `ExcepcionDominio` | Error de dominio con código y tipo |
| `domain/plot` | `Parcela` | Agregado. `crear(...)` y `actualizar(...)` recortan el nombre y validan la superficie. Guarda `version` |
| `domain/plot` | `RepositorioParcela` | Puerto: `guardar`, `buscarPorId`, `listar(filtroNombre, pagina, tamanio)` |
| `application/plot` | `CrearParcelaCasoUso` | Crea, guarda y audita (acción `CREAR`) |
| `application/plot` | `ActualizarParcelaCasoUso` | Busca (o 404), compara `version` (si difiere, `CONFLICTO_CONCURRENCIA`), actualiza, guarda y audita (acción `MODIFICAR`) |
| `application/plot` | `ConsultarParcelaCasoUso` | Busca por ID o lanza `PARCELA_NO_ENCONTRADA` |
| `application/plot` | `ListarParcelasCasoUso` | Lista paginado y ordenado por nombre |
| `infrastructure/persistence` | `ParcelaEntidad`, `ParcelaSpringData`, `MapeadorParcela`, `RepositorioParcelaJpa` | Entidad JPA con `@Version`; consulta `findByNombreContainingIgnoreCase`; mapeo manual; traduce la violación de `ux_parcela_nombre` a `NOMBRE_PARCELA_DUPLICADO` (usa `saveAndFlush` para detectarla dentro de la transacción) |
| `interfaces/rest` | `ParcelaControlador` | Traduce HTTP ↔ caso de uso; `@PreAuthorize` por endpoint; documenta en OpenAPI los códigos de error de cada operación |
| `interfaces/rest/dto` | `CrearParcelaSolicitud`, `ActualizarParcelaSolicitud`, `ParcelaRespuesta`, `PaginaRespuesta<T>` | Records con validaciones y formato JSON |

**Concurrencia en dos niveles:** el caso de uso compara la `version` enviada por el cliente, y `@Version` de JPA cubre la carrera entre dos transacciones simultáneas. Ambos casos terminan en `409 CONFLICTO_CONCURRENCIA`.

**Superficie de campañas (RQ-PAR-05):** no requiere código aquí. La campaña guarda su propia copia de la superficie (ver `spec-campanias.md`), y este escenario se prueba en esa funcionalidad.

## 2.5 Tests

| Tipo | Clase | Qué verifica |
|---|---|---|
| Unitario | `HectareasTest` | 0 y negativos lanzan `SUPERFICIE_INVALIDA`; positivos se aceptan |
| Unitario | `ParcelaTest` | Recorte del nombre; `actualizar` valida la superficie |
| Unitario | `ActualizarParcelaCasoUsoTest` | 404 si no existe; `CONFLICTO_CONCURRENCIA` si la versión difiere; registro de auditoría `MODIFICAR` (repositorio y auditoría simulados a mano) |
| Integración | `ParcelaControladorIT` | Todos los escenarios de aceptación de las historias 1 a 3 y los casos borde de formato |
| Integración | `ParcelaConcurrenciaIT` | Dos creaciones simultáneas con el mismo nombre → una `201` y una `409`; dos `PUT` con la misma versión → la segunda `409 CONFLICTO_CONCURRENCIA` |
| Integración | `ParcelaRendimientoIT` | Con 1.000 parcelas, listado y detalle en menos de 3 s (CE-PAR-02) |
| Integración | `SeguridadIT` | Sin token → `401 NO_AUTENTICADO`; rol sin permiso → `403 SIN_PERMISO`; `/salud` y `/v3/api-docs` accesibles sin token; `X-Correlation-Id` e `idCorrelacion` presentes también en las respuestas 401 y 403 |

- Los tests de integración usan Testcontainers con PostgreSQL y el post-procesador `jwt()` de `spring-security-test` para simular los roles. No se levanta Keycloak.
- Cada test de integración que crea o modifica verifica también la fila en `registro_auditoria` (CE-PAR-03).

## 2.6 Decisiones del plan

| Decisión | Motivo |
|---|---|
| `PUT` con todos los campos editables | Más simple que `PATCH`; la parcela tiene pocos campos |
| `version` en el cuerpo JSON | Lo mínimo que cumple `CONFLICTO_CONCURRENCIA` sin headers adicionales |
| Decimales de entrada solo como texto | La constitución prohíbe transmitirlos como número JSON |
| Mapeadores manuales, sin Lombok ni MapStruct | Regla de simplicidad: ninguna dependencia sin necesidad real |
| Tests de seguridad con `jwt()` | Evita levantar Keycloak en los tests |
| Logs JSON nativos de Spring Boot 3.4 | Cumple RNF-22 sin librerías extra |
| Auditoría con usuario, acción, fecha y entidad | Exactamente lo que piden el documento de requisitos y la constitución |

---

# 3. Tareas

Cada tarea se da por terminada solo con sus tests en verde. Las marcadas con **[P]** pueden hacerse en paralelo con la anterior.

## Fase 0 — Base del servicio

- [x] **T01** — Crear el proyecto Maven (`pom.xml`, `AplicacionGestion.java`) con las dependencias de 2.1 y la estructura de carpetas de la constitución. *Hecho cuando:* `mvn verify` compila sin tests.
- [x] **T02** — Escribir `application.yml` (variables de entorno, logs JSON, Actuator en `/salud`, springdoc), `application-test.yml` y `PruebaIntegracionBase`. *Hecho cuando:* la aplicación arranca contra un PostgreSQL local y `/salud`, `/salud/liveness` y `/salud/readiness` responden `UP`.
- [x] **T03** — Implementar `ConfiguracionSeguridad`, `ConversorRolesKeycloak` y las propiedades de validación del token, con respuestas 401 y 403 en el formato común. *Hecho cuando:* pasa `SeguridadIT` y un test del decodificador rechaza tokens con `iss` o `aud` incorrectos (`jwt()` no pasa por esa validación).
- [x] **T04** [P] — Implementar `ExcepcionDominio`, `RespuestaError` y `ManejadorGlobalExcepciones` según la tabla de 2.1. *Hecho cuando:* un test de integración provoca un 400, un 403 de `@PreAuthorize`, un 404 de ruta inexistente, un 405 y un 500, y comprueba el formato.
- [x] **T05** [P] — Implementar `FiltroIdCorrelacion`. *Hecho cuando:* la respuesta devuelve el `X-Correlation-Id` recibido o uno generado, y aparece en los logs.
- [x] **T06** — Crear `V1__crear_registro_auditoria.sql` y el puerto `RegistroAuditoria` con `RegistroAuditoriaJpa`. *Hecho cuando:* un test de integración registra una auditoría y la lee con actor e `idCorrelacion`.
- [x] **T07** [P] — Crear `PaginaRespuesta<T>`, la validación común de `pagina` y `tamanio`, y el deserializador de decimales. *Hecho cuando:* un test de integración comprueba que un decimal enviado como número JSON responde `400 DATOS_INVALIDOS`.
- [x] **T08** [P] — Escribir el `Dockerfile` y `.github/workflows/servicio-gestion.yml` (en la raíz del repositorio), con la configuración de JaCoCo (mínimo 80 % en `domain` y `application`) y de Surefire (incluye `*IT`). *Hecho cuando:* el pipeline corre en verde y construye la imagen.

## Fase 1 — Parcelas

- [x] **T09** — Crear `Hectareas` y `Parcela` en el dominio, con `HectareasTest` y `ParcelaTest`.
- [x] **T10** — Crear `V2__crear_parcela.sql`, `ParcelaEntidad`, `ParcelaSpringData`, `MapeadorParcela` y `RepositorioParcelaJpa`, con la traducción del índice único a `NOMBRE_PARCELA_DUPLICADO`.
- [x] **T11** — Implementar `CrearParcelaCasoUso` y `POST /parcelas`. *Hecho cuando:* pasan los escenarios de la historia 1 en `ParcelaControladorIT`, con verificación de auditoría.
- [x] **T12** — Implementar `ConsultarParcelaCasoUso`, `ListarParcelasCasoUso` y los dos `GET`. *Hecho cuando:* pasan los escenarios de la historia 2, incluido el acceso de `tecnico_campo` y de `lectura_gestion`.
- [x] **T13** — Implementar `ActualizarParcelaCasoUso` y `PUT /parcelas/{id}`, con `ActualizarParcelaCasoUsoTest`. *Hecho cuando:* pasan los escenarios 1 y 3 de la historia 3, con su registro de auditoría.
- [x] **T14** — Escribir `ParcelaConcurrenciaIT` y los casos borde de formato restantes (decimales de más, superficie no numérica, nombre con espacios).
- [x] **T15** [P] — Escribir `ParcelaRendimientoIT` (CE-PAR-02).
- [x] **T16** — Documentar en OpenAPI los códigos de error de cada endpoint y revisar en Swagger UI. *Hecho cuando:* `/v3/api-docs` lista los cuatro endpoints con sus respuestas de error.
- [x] **T17** — Verificación final: `mvn verify` en verde, cobertura ≥ 80 % en `domain` y `application`, y todos los criterios CE-PAR-01 a CE-PAR-04 cubiertos por al menos un test.
